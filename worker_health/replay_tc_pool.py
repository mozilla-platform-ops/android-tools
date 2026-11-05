#!/usr/bin/env python3
"""Continuously replay a fair mix of level-1 jobs into available pool capacity."""

import argparse
import logging
import sqlite3
import time
from contextlib import nullcontext

import taskcluster
from replay_tc_task import positive_int, queue_argument, queue_client
from rich.console import Console
from rich.live import Live
from rich.logging import RichHandler
from worker_health.replay_controller import (
    ControllerState,
    ReplayController,
    state_path,
)

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-pool", required=True, type=queue_argument, help="Source pool ID or worker pool URL")
    parser.add_argument(
        "-q",
        "--queue",
        required=True,
        type=queue_argument,
        help="Destination pool ID or worker pool URL",
    )
    parser.add_argument("--worker-active-minutes", type=positive_int, default=90)
    parser.add_argument(
        "--tasks-per-worker",
        type=positive_int,
        default=1,
        help="Maximum outstanding tasks per active worker",
    )
    parser.add_argument(
        "--poll-interval",
        type=positive_int,
        default=60,
        help="Seconds between scheduling cycles (default: 60)",
    )
    parser.add_argument(
        "--submit-interval",
        type=positive_int,
        default=60,
        help="Minimum seconds between submissions (default: 60)",
    )
    parser.add_argument("--source-refresh-minutes", type=positive_int, default=10)
    parser.add_argument(
        "--failure-backoff",
        type=positive_int,
        default=300,
        help="Initial retry delay in seconds, doubling up to one hour",
    )
    parser.add_argument("--dry-run", action="store_true", help="Check permissions and inputs without submitting tasks")
    parser.add_argument("--once", action="store_true", help="Run one scheduling cycle and exit")
    parser.add_argument("--output", choices=("table", "log"), default="table")
    args = parser.parse_args()
    if args.from_pool == args.queue:
        parser.error("Source and destination pools must differ")
    if args.failure_backoff > 3600:
        parser.error("--failure-backoff must be at most 3600 seconds")
    return args


def main():
    args = parse_args()
    console = Console(stderr=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )
    try:
        queue = queue_client(authenticated=True)
        with ControllerState(state_path(args.queue)) as state:
            controller = ReplayController(
                queue,
                taskcluster.WorkerManager(queue.options),
                taskcluster.Auth(queue.options),
                state,
                args,
            )
            display = (
                Live(
                    get_renderable=lambda: controller.render(max_rows=max(1, console.height - 10)),
                    console=console,
                    refresh_per_second=2,
                )
                if args.output == "table" and console.is_terminal
                else nullcontext()
            )
            with display as live:
                while True:
                    failed = False
                    try:
                        controller.tick()
                    except (taskcluster.exceptions.TaskclusterFailure, ValueError, KeyError) as exc:
                        # Never schedule from stale capacity or permissions after a failed API call.
                        controller.message = f"Cycle paused: {exc}"
                        logger.warning("%s", controller.message)
                        failed = True
                    finally:
                        controller.refresh_view()
                    if live:
                        live.refresh()
                    elif args.output == "table":
                        console.print(controller.render())
                    logger.info(
                        "Workers=%s outstanding=%s/%s | %s",
                        controller.workers,
                        controller.outstanding,
                        controller.limit,
                        controller.message,
                    )
                    if args.once:
                        return int(failed)
                    time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        logger.info("Stopped scheduling; submitted tasks keep running. Restart to resume tracking.")
        return 0
    except (OSError, sqlite3.Error, ValueError, taskcluster.exceptions.TaskclusterFailure) as exc:
        logger.error("Controller stopped: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
