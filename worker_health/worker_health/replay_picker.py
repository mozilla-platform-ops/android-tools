"""Discover recent replay workloads and select one in a terminal."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import curses
from dataclasses import dataclass
from datetime import datetime
import logging
import re

import taskcluster


LEVEL_PATTERN = re.compile(r"level-(\d+)(?=[/\-]|$)")
PRIORITIES = ("highest", "very-high", "high", "medium", "low", "very-low", "lowest")


def level_one_problem(task):
    """Require positive level-1 evidence and reject conflicting resource levels."""
    env_level = str(task.get("payload", {}).get("env", {}).get("MOZ_SCM_LEVEL", ""))
    if env_level and env_level != "1":
        return f"source has MOZ_SCM_LEVEL={env_level}"
    scopes = task.get("scopes", [])
    if any(
        scope_covered(scope, scopes)
        for scope in (
            "secrets:get:project/perftest/gecko/level-3/perftest-login",
            "generic-worker:cache:gecko-level-3-pip",
        )
    ):
        return "source requests level-3 access or a wildcard covering it"
    resources = [task.get("schedulerId", ""), *task.get("scopes", [])]
    payload = task.get("payload", {})
    resources.extend(mount.get("cacheName", "") for mount in payload.get("mounts", []))
    resources.extend(payload.get("cache", {}))
    levels = {match.group(1) for value in resources for match in LEVEL_PATTERN.finditer(value)}
    if levels - {"1"}:
        return "source references resources outside level 1"
    if env_level != "1" and "1" not in levels:
        return "source has no explicit level-1 marker"
    return None


def scope_covered(scope, granted):
    return any(scope == item or (item.endswith("*") and scope.startswith(item[:-1])) for item in granted)


def missing_scopes(source, destination, granted):
    required = [*source.get("scopes", []), "queue:create-task:project:none", "queue:scheduler-id:-"]
    missing = [scope for scope in required if not scope_covered(scope, granted)]
    if not any(scope_covered(f"queue:create-task:{priority}:{destination}", granted) for priority in PRIORITIES):
        missing.append(f"queue:create-task:lowest:{destination}")
    return sorted(set(missing))


@dataclass
class ReplayJob:
    task_id: str
    task: dict
    completed: str
    seconds: float | None
    worker: str
    observed: int = 1

    @property
    def name(self):
        return self.task["metadata"]["name"]

    @property
    def secrets(self):
        return [scope for scope in self.task.get("scopes", []) if scope.startswith("secrets:")]


@dataclass
class Discovery:
    jobs: list
    workers: int
    task_ids: int
    eligible_tasks: int
    unavailable_workers: int
    cached_at: float | None = None


@dataclass(frozen=True)
class RefreshPicker:
    query: str


def batch_results(method, ids, key):
    for start in range(0, len(ids), 100):
        options = {}
        while True:
            page = method({"taskIds": ids[start : start + 100]}, **options)
            yield from page[key]
            if not page.get("continuationToken"):
                break
            options["continuationToken"] = page["continuationToken"]


def discover_jobs(queue, manager, pool, progress=lambda message: None):
    """Collect every worker's bounded history, deduplicate IDs, and group workloads."""
    # TODO: Add Pool Classifier history as another source of task IDs.
    provisioner, worker_type = pool.split("/", 1)
    workers = {}
    options = {}
    while True:
        page = manager.listWorkers(provisioner, worker_type, **options)
        for worker in page["workers"]:
            workers[(worker["workerGroup"], worker["workerId"])] = worker
        if not page.get("continuationToken"):
            break
        options["continuationToken"] = page["continuationToken"]

    ids = {worker["latestTask"]["taskId"] for worker in workers.values() if worker.get("latestTask")}
    unavailable = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(manager.getWorker, provisioner, worker_type, group, worker_id): (group, worker_id)
            for group, worker_id in workers
        }
        for index, future in enumerate(as_completed(futures), 1):
            try:
                ids.update(task["taskId"] for task in future.result().get("recentTasks", []))
            except taskcluster.exceptions.TaskclusterFailure as exc:
                unavailable += 1
                logging.warning("Could not read history for %s/%s: %s", *futures[future], exc)
            progress(f"Reading worker history: {index}/{len(workers)} workers; {len(ids)} unique task IDs")

    progress(f"Checking status of {len(ids)} observed tasks")
    statuses = {
        entry["taskId"]: entry["status"]
        for entry in batch_results(queue.statuses, sorted(ids), "statuses")
        if entry["status"]["state"] == "completed"
    }
    progress(f"Reading {len(statuses)} completed task definitions")
    grouped = {}
    eligible = 0
    for entry in batch_results(queue.tasks, sorted(statuses), "tasks"):
        task = entry["task"]
        task_pool = task.get("taskQueueId") or f"{task.get('provisionerId')}/{task.get('workerType')}"
        if task_pool != pool or level_one_problem(task):
            continue
        status = statuses[entry["taskId"]]
        run = next((run for run in reversed(status.get("runs", [])) if run.get("state") == "completed"), {})
        seconds = None
        if run.get("resolved") and run.get("started"):
            seconds = max(
                0,
                (
                    datetime.fromisoformat(run["resolved"].replace("Z", "+00:00"))
                    - datetime.fromisoformat(run["started"].replace("Z", "+00:00"))
                ).total_seconds(),
            )
        job = ReplayJob(entry["taskId"], task, run.get("resolved", task["created"]), seconds, run.get("workerId", "-"))
        eligible += 1
        # Keep scope variants separate so a new secret requirement does not hide a usable workload.
        key = (job.name, tuple(sorted(task.get("scopes", []))))
        previous = grouped.get(key)
        if previous:
            if job.completed > previous.completed:
                job.observed = previous.observed + 1
                grouped[key] = job
            else:
                previous.observed += 1
        else:
            grouped[key] = job
    return Discovery(
        sorted(grouped.values(), key=lambda job: job.completed, reverse=True),
        len(workers),
        len(ids),
        eligible,
        unavailable,
    )


def filtered_jobs(jobs, query):
    words = query.casefold().split()
    return [job for job in jobs if all(word in f"{job.name} {job.task_id} {job.worker}".casefold() for word in words)]


def runtime_label(seconds):
    return "-" if seconds is None else f"{int(seconds) // 60}m {int(seconds) % 60:02d}s"


def pick_job(discovery, source_pool, destination, query="", granted=None, preview=False):
    """Run the curses picker; cancellation returns None without submitting anything."""
    # TODO: Support selecting multiple workloads in one picker session.
    try:
        return curses.wrapper(_picker_screen, discovery, source_pool, destination, query, granted, preview)
    except curses.error as exc:
        raise ValueError("Cannot open terminal picker; use a task ID or a supported terminal") from exc


def _picker_screen(screen, discovery, source_pool, destination, query, granted=None, preview=False):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    screen.keypad(True)
    selected = 0
    blocked = False
    permissions = (
        {job.task_id: missing_scopes(job.task, destination, granted) for job in discovery.jobs}
        if granted is not None
        else {}
    )

    def line(row, text, style=0):
        height, width = screen.getmaxyx()
        if row < height:
            try:
                screen.addnstr(row, 0, text, max(0, width - 1), style)
            except curses.error:
                pass

    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 16 or width < 60:
            line(0, "Resize terminal to at least 60 columns x 16 rows; Esc to cancel")
            screen.refresh()
            if screen.getch() in (27, 3):
                return None
            continue
        jobs = filtered_jobs(discovery.jobs, query)
        selected = min(selected, max(0, len(jobs) - 1))
        missing = permissions.get(jobs[selected].task_id, []) if jobs else []
        details_height = min(8, 3 + len(missing))
        page_size = max(1, height - 9 - details_height)
        top = (selected // page_size) * page_size
        line(0, "Replay a completed level-1 job", curses.A_BOLD)
        line(1, f"From: {source_pool}")
        line(2, f"To:   {destination}")
        line(
            3,
            f"{'Cached' if discovery.cached_at is not None else 'Recent'} worker history (~20/worker): {discovery.workers} workers, {discovery.task_ids} IDs, {discovery.eligible_tasks} eligible runs",
            curses.A_DIM,
        )
        line(4, f"Filter: {query}   ({len(jobs)}/{len(discovery.jobs)} workloads)", curses.A_BOLD)
        line(5, "  Runtime  Access    Runs  Completed UTC         Workload", curses.A_UNDERLINE)
        for row, job in enumerate(jobs[top : top + page_size], 6):
            index = top + row - 6
            denied = permissions.get(job.task_id, [])
            access = f"need {len(denied)}" if denied else "ready" if granted is not None else "unknown"
            label = f"{'>' if index == selected else ' '} {runtime_label(job.seconds):>7}  {access:>8} {job.observed:>4}  {job.completed[:19].replace('T', ' ')}  {job.name}"
            style = curses.A_REVERSE if index == selected else 0
            if denied and not preview:
                style |= curses.A_DIM
            line(row, label, style)
        if not jobs:
            line(6, "No matching jobs. Backspace to change the filter.")
        if jobs:
            job = jobs[selected]
            detail_start = height - details_height - 2
            line(detail_start, job.name, curses.A_BOLD)
            line(detail_start + 1, f"Task: {job.task_id}  Worker: {job.worker}")
            line(detail_start + 2, "Secrets: " + (", ".join(job.secrets) or "none"), curses.A_DIM)
            for index, scope in enumerate(missing[: details_height - 3], detail_start + 3):
                line(index, "Missing: " + scope, curses.A_BOLD)
        line(height - 2, "Arrows / PgUp / PgDn: move | Type: filter | Backspace: erase")
        footer = (
            "Selection disabled: client lacks scopes. Choose another job or Ctrl+R to refresh."
            if blocked
            else "Enter: preview"
            if preview
            else "Enter: select and check inputs"
        )
        line(height - 1, footer + " | Ctrl+R: refresh | Esc: cancel", curses.A_DIM)
        screen.refresh()
        key = screen.get_wch()
        if key in ("\x1b", "\x03"):
            return None
        if key == "\x12":
            return RefreshPicker(query)
        if key in ("\n", "\r", curses.KEY_ENTER) and jobs:
            if missing and not preview:
                blocked = True
                continue
            return jobs[selected]
        blocked = False
        if key == curses.KEY_UP:
            selected = max(0, selected - 1)
        elif key == curses.KEY_DOWN:
            selected = min(max(0, len(jobs) - 1), selected + 1)
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - page_size)
        elif key == curses.KEY_NPAGE:
            selected = min(max(0, len(jobs) - 1), selected + page_size)
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            query = query[:-1]
            selected = 0
        elif isinstance(key, str) and key.isprintable():
            query += key
            selected = 0
