"""Capacity-limited, persistent scheduling of diagnostic replays."""

import fcntl
import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import taskcluster
from replay_tc_task import (
    check_inputs,
    clone_task,
    gen_task_id,
    parse_timestamp,
    source_queue,
)
from rich.console import Group
from rich.table import Table
from rich.text import Text

from worker_health.replay_cache import load_discovery, save_discovery
from worker_health.replay_coverage import remember_results, remember_submission
from worker_health.replay_picker import discover_jobs, missing_scopes

ACTIVE = ("reserved", "pending", "running", "unscheduled")
TERMINAL = ("completed", "failed", "exception")
logger = logging.getLogger(__name__)


def workload_key(source_pool, job):
    return json.dumps([source_pool, job.name, sorted(set(job.task.get("scopes", [])))])


def state_path(destination):
    root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return (
        root
        / "worker-health"
        / "replay-controller"
        / f"{hashlib.sha256(destination.encode()).hexdigest()[:24]}.sqlite3"
    )


def active_worker_count(manager, pool, now, minutes):
    """Standalone worker capacity is one worker, independent of its capacity field."""
    provisioner, worker_type = pool.split("/", 1)
    active = set()
    options = {}
    while True:
        page = manager.listWorkers(provisioner, worker_type, **options)
        for worker in page["workers"]:
            try:
                last_active = parse_timestamp(worker["lastDateActive"])
                quarantine = parse_timestamp(worker["quarantineUntil"]) if worker.get("quarantineUntil") else None
                if now - timedelta(minutes=minutes) <= last_active <= now and (quarantine is None or quarantine <= now):
                    active.add((worker["workerGroup"], worker["workerId"]))
            except (KeyError, TypeError, ValueError):
                # Missing or malformed activity is not evidence of usable capacity.
                continue
        if not page.get("continuationToken"):
            return len(active)
        options["continuationToken"] = page["continuationToken"]


class ControllerState:
    """One local controller per destination; commit submission intent before the API call."""

    def __init__(self, path):
        self.path = Path(path)
        self.db = None
        self.lock = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.lock = os.fdopen(os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600), "w")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            raise ValueError("Another replay controller is using this destination's state") from exc
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            self.db = sqlite3.connect(self.path)
            self.db.row_factory = sqlite3.Row
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS workloads (
                    key TEXT PRIMARY KEY, name TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
                    last_attempt REAL NOT NULL DEFAULT 0, retry_after REAL NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, workload TEXT NOT NULL, definition TEXT NOT NULL,
                    state TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL NOT NULL);
            """)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_args):
        if self.db:
            self.db.close()
        if self.lock:
            self.lock.close()

    def ensure_job(self, key, name):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO workloads (key, name) VALUES (?, ?)", (key, name))

    def history(self, key):
        return self.db.execute("SELECT * FROM workloads WHERE key=?", (key,)).fetchone()

    def active(self):
        return self.db.execute(
            "SELECT * FROM tasks WHERE state IN ('reserved','pending','running','unscheduled') ORDER BY created",
        ).fetchall()

    def rate_ready(self, now, interval):
        row = self.db.execute("SELECT value FROM settings WHERE key='last_submission'").fetchone()
        return row is None or now - row[0] >= interval

    def mark_submission(self, now):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('last_submission', ?)", (now,))

    def reject(self, key, error, now, backoff, attempted=True):
        failures = self.history(key)["failures"] + 1
        delay = min(3600, backoff * 2 ** min(failures - 1, 10))
        self.db.execute(
            "UPDATE workloads SET attempts=attempts+?, failures=?, last_attempt=?, retry_after=?, error=? WHERE key=?",
            (int(attempted), failures, now, now + delay, str(error), key),
        )

    def reserve(self, key, task_id, definition, now):
        with self.db:
            self.db.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, 'reserved', ?)",
                (task_id, key, json.dumps(definition), now),
            )
            self.db.execute("UPDATE workloads SET attempts=attempts+1, last_attempt=? WHERE key=?", (now, key))

    def set_status(self, row, state, now, backoff):
        with self.db:
            self.db.execute("UPDATE tasks SET state=? WHERE task_id=?", (state, row["task_id"]))
            if state == "completed":
                self.db.execute(
                    "UPDATE workloads SET successes=successes+1, failures=0, retry_after=0, error='' WHERE key=?",
                    (row["workload"],),
                )
            elif state in ("failed", "exception", "rejected"):
                self.reject(row["workload"], f"Replay {row['task_id']}: {state}", now, backoff, attempted=False)


class ReplayController:
    def __init__(self, queue, manager, auth, state, args, clock=None):
        self.queue, self.manager, self.auth, self.state, self.args = queue, manager, auth, state, args
        self.jobs = []
        self.granted = []
        self.last_discovery = None
        self.workers = self.outstanding = self.limit = 0
        self.message = "Starting"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.histories = {}
        self.active_types = set()

    def refresh_view(self):
        # Rich refreshes in another thread; render only snapshots, never SQLite queries.
        self.histories = {row["key"]: dict(row) for row in self.state.db.execute("SELECT * FROM workloads")}
        self.active_types = {row["workload"] for row in self.state.active()}

    def progress(self, message):
        self.message = message

    def capacity(self, now):
        self.workers = active_worker_count(self.manager, self.args.queue, now, self.args.worker_active_minutes)
        self.limit = self.workers * self.args.tasks_per_worker
        counts = self.queue.taskQueueCounts(self.args.queue)
        remote = counts["pendingTasks"] + counts["claimedTasks"]
        local = self.state.active()
        # A reservation may already exist remotely after a lost createTask response.
        # Double-count it conservatively until status confirms where it stands.
        self.outstanding = max(remote + sum(row["state"] == "reserved" for row in local), len(local))

    def reconcile(self, now):
        for row in self.state.active():
            try:
                status = self.queue.status(row["task_id"])["status"]
            except taskcluster.exceptions.TaskclusterRestFailure as exc:
                if exc.status_code == 404:
                    definition = json.loads(row["definition"])
                    if parse_timestamp(definition["deadline"]) <= now:
                        self.state.set_status(row, "exception", now.timestamp(), self.args.failure_backoff)
                        continue
                    if row["state"] == "reserved":
                        continue
                raise
            state = status["state"]
            if state not in (*ACTIVE, *TERMINAL):
                raise ValueError(f"Unknown task state: {state}")
            self.state.set_status(row, state, now.timestamp(), self.args.failure_backoff)
            if state in TERMINAL:
                remember_results(self.args.queue, {row["task_id"]: {"state": state}})

    def submit(self, row, now):
        definition = json.loads(row["definition"])
        self.state.mark_submission(now.timestamp())
        try:
            self.queue.createTask(row["task_id"], definition)
        except taskcluster.exceptions.TaskclusterRestFailure as exc:
            if exc.status_code in (400, 401, 403):
                self.state.set_status(row, "rejected", now.timestamp(), self.args.failure_backoff)
            # Other failures can leave a created task behind. Retain the exact ID/definition.
            raise
        self.state.set_status(row, "pending", now.timestamp(), self.args.failure_backoff)
        remember_submission(self.args.queue, row["task_id"], definition)
        self.message = f"Submitted {row['task_id']}: {definition['metadata']['name']}"
        logger.info("%s", self.message)

    def tick(self, now=None):
        now = now or self.clock()
        self.progress("Checking submitted tasks")
        self.reconcile(now)
        self.progress("Reading current client scopes")
        self.granted = self.auth.currentScopes()["scopes"]
        if (
            self.last_discovery is None
            or (now - self.last_discovery).total_seconds() >= self.args.source_refresh_minutes * 60
        ):
            discovery = load_discovery(self.args.from_pool, self.args.source_refresh_minutes)
            if discovery is None:
                discovery = discover_jobs(self.queue, self.manager, self.args.from_pool, progress=self.progress)
                save_discovery(self.args.from_pool, discovery)
            for job in discovery.jobs:
                self.state.ensure_job(workload_key(self.args.from_pool, job), job.name)
            self.jobs = discovery.jobs
            self.last_discovery = now
        self.refresh_view()
        self.progress("Reading destination activity and queue counts")
        self.capacity(now)
        if not self.state.rate_ready(now.timestamp(), self.args.submit_interval):
            self.message = "Waiting for submission rate limit"
            return

        # Resolve uncertain submissions first, reusing the persisted ID and definition.
        reserved = [row for row in self.state.active() if row["state"] == "reserved"]
        if reserved:
            row = reserved[0]
            if self.outstanding - len(reserved) >= self.limit:
                self.message = "Waiting for capacity to retry an uncertain submission"
                return
            definition = json.loads(row["definition"])
            if missing_scopes(definition, self.args.queue, self.granted):
                self.message = "Uncertain submission lacks scopes; waiting for permissions"
                return
            source_id = definition["extra"]["replay"]["sourceTaskId"]
            try:
                check_inputs(self.queue, definition, source_id, now, progress=self.progress)
            except ValueError as exc:
                if not self.args.dry_run:
                    self.state.set_status(row, "rejected", now.timestamp(), self.args.failure_backoff)
                self.message = f"Uncertain submission inputs no longer valid: {exc}"
                return
            self.granted = self.auth.currentScopes()["scopes"]
            if missing_scopes(definition, self.args.queue, self.granted):
                self.message = "Permissions changed during input validation; no task submitted"
                return
            now = self.clock()
            self.capacity(now)
            if self.outstanding - len(reserved) >= self.limit:
                self.message = "Capacity changed during input validation; no task submitted"
                return
            if self.args.dry_run:
                self.message = f"DRY RUN: would retry {row['task_id']}"
            else:
                self.submit(row, now)
            return
        if self.outstanding >= self.limit:
            self.message = "Waiting for destination capacity"
            return

        active_types = {row["workload"] for row in self.state.active()}
        candidates = []
        for job in self.jobs:
            key = workload_key(self.args.from_pool, job)
            history = self.state.history(key)
            if (
                key not in active_types
                and history["retry_after"] <= now.timestamp()
                and not missing_scopes(job.task, self.args.queue, self.granted)
            ):
                candidates.append((history["successes"] > 0, history["attempts"], history["last_attempt"], key, job))
        for _, _, _, key, job in sorted(candidates, key=lambda item: item[:4]):
            self.progress(f"Checking inputs: {job.name}")
            try:
                source = self.queue.task(job.task_id)
                if (
                    source_queue(source) != self.args.from_pool
                    or workload_key(self.args.from_pool, replace(job, task=source)) != key
                ):
                    raise ValueError("Source pool or workload identity changed")
                denied = missing_scopes(source, self.args.queue, self.granted)
                if denied:
                    raise ValueError("Client lacks replay scopes: " + ", ".join(denied))
                check_inputs(self.queue, source, job.task_id, now, progress=self.progress)
                task_id = gen_task_id()
                definition = clone_task(source, job.task_id, task_id, self.args.queue, now)
            except (ValueError, KeyError, taskcluster.exceptions.TaskclusterFailure) as exc:
                if not self.args.dry_run:
                    with self.state.db:
                        self.state.reject(key, exc, now.timestamp(), self.args.failure_backoff)
                logger.warning("Skipping %s: %s", job.name, exc)
                continue
            # Preflight can take time: refresh scopes and capacity just before submission.
            self.granted = self.auth.currentScopes()["scopes"]
            if missing_scopes(source, self.args.queue, self.granted):
                self.message = "Permissions changed during input validation; no task submitted"
                return
            now = self.clock()
            self.capacity(now)
            if self.outstanding >= self.limit:
                self.message = "Capacity changed during input validation; no task submitted"
                return
            if self.args.dry_run:
                self.message = f"DRY RUN: would submit {job.name}"
                logger.info("%s", self.message)
                return
            self.state.reserve(key, task_id, definition, now.timestamp())
            row = next(row for row in self.state.active() if row["task_id"] == task_id)
            self.submit(row, now)
            self.outstanding += 1
            return  # At most one submission each cycle, even after long preflight checks.
        self.message = "No eligible workload ready (permissions, in-flight work, or backoff)"

    def render(self):
        table = Table(title=f"Continuous replay: {self.args.from_pool} → {self.args.queue}")
        for column in ("Workload", "Succeeded", "Attempts", "Status"):
            table.add_column(column)
        passed = eligible = 0
        now = self.clock().timestamp()
        for job in self.jobs:
            key = workload_key(self.args.from_pool, job)
            history = self.histories.get(key, {"successes": 0, "attempts": 0, "retry_after": 0})
            denied = missing_scopes(job.task, self.args.queue, self.granted)
            eligible += not denied
            passed += bool(history["successes"]) and not denied
            status = (
                "missing scopes"
                if denied
                else "in flight"
                if key in self.active_types
                else f"retry in {max(0, int(history['retry_after'] - now))}s"
                if history["retry_after"] > now
                else "ready"
            )
            table.add_row(Text(job.name), str(history["successes"]), str(history["attempts"]), status)
        return Group(
            Text(
                f"Active workers: {self.workers} | Outstanding: {self.outstanding}/{self.limit} | Coverage: {passed}/{eligible} eligible types",
            ),
            table,
            Text(self.message),
            Text("Ctrl+C: stop scheduling; submitted tasks keep running"),
        )
