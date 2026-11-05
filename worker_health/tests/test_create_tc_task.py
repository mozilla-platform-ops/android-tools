import json
import logging

import pytest

import create_tc_task
from create_tc_task import build_payload, default_bash_command


def test_default_bash_command_uses_timeout_minus_buffer():
    assert default_bash_command(70) == 'for ((i=1;i<=60;i++)); do echo "$i"; sleep 1; done'


def test_build_docker_worker_payload():
    payload = build_payload(
        "docker-worker",
        "echo hello",
        90,
        {"FOO": "bar"},
        "ubuntu:24.04",
    )

    assert payload == {
        "image": "ubuntu:24.04",
        "command": ["/bin/bash", "-lc", "echo hello"],
        "maxRunTime": 90,
        "env": {"FOO": "bar"},
    }


def test_build_python_script_command_passes_shell_style_arguments(tmp_path):
    script = tmp_path / "benchmark.py"
    script.write_text("#!/usr/bin/env python3\nprint('ok')\n")

    command = create_tc_task._build_command_from_script(
        script,
        "--configuration bitbar-docker-with-robustcheckout --output-dir 'clone results'",
    )

    assert command.startswith(
        "python3 - --configuration bitbar-docker-with-robustcheckout --output-dir 'clone results' << 'SCRIPT_EOF'",
    )
    assert "print('ok')" in command


def test_build_shell_script_command_rejects_arguments(tmp_path):
    script = tmp_path / "benchmark.sh"
    script.write_text("#!/bin/bash\necho ok\n")

    try:
        create_tc_task._build_command_from_script(script, "--configuration test")
    except ValueError as exc:
        assert str(exc) == "--script-args is supported only for non-shell --script-file inputs"
    else:
        raise AssertionError("expected shell script arguments to be rejected")


def test_wait_for_tasks_reports_result_and_worker(mocker):
    tcclient = object.__new__(create_tc_task.TCClient)
    tcclient.queue_object = mocker.Mock()
    tcclient.queue_object.status.return_value = {
        "status": {
            "state": "completed",
            "runs": [
                {
                    "state": "completed",
                    "reasonResolved": "completed",
                    "workerId": "worker-194",
                },
            ],
        },
    }

    details = tcclient.wait_for_tasks(["task-1"], poll_interval=0.01)

    assert details == {
        "task-1": {
            "state": "completed",
            "result": "completed",
            "worker_id": "worker-194",
        },
    }


def task_status(state, worker=None, reason=None):
    run = {"state": state}
    if worker:
        run["workerId"] = worker
    if reason:
        run["reasonResolved"] = reason
    return {"status": {"state": state, "runs": [run] if worker or reason else []}}


def test_wait_retries_errors_and_reports_worker_changes(mocker):
    client = object.__new__(create_tc_task.TCClient)
    client.queue_object = mocker.Mock()
    client.queue_object.status.side_effect = [
        RuntimeError("temporary API failure"),
        task_status("running", "worker-a"),
        task_status("running", "worker-a"),
        task_status("running", "worker-b"),
        task_status("completed", "worker-b", "completed"),
    ]
    sleep = mocker.patch.object(create_tc_task.time, "sleep")
    updates = []

    def progress(states, final, changed):
        updates.append((states["task-1"].copy(), final.copy(), changed.copy()))

    result = client.wait_for_tasks(["task-1"], 0.1, progress)

    assert [update[0]["worker_id"] for update in updates] == ["worker-a", "worker-b", "worker-b"]
    assert all(update[2] == ["task-1"] for update in updates)
    assert updates[-1][1] == result
    assert sleep.call_count == 4


@pytest.mark.parametrize("state", ["completed", "failed", "exception"])
def test_wait_terminal_state_without_runs(mocker, state):
    client = object.__new__(create_tc_task.TCClient)
    client.queue_object = mocker.Mock()
    client.queue_object.status.return_value = task_status(state)

    assert client.wait_for_tasks(["task-1"], 0.1) == {
        "task-1": {"state": state, "result": state, "worker_id": "-"},
    }


@pytest.fixture
def cli_client(mocker):
    client = object.__new__(create_tc_task.TCClient)
    client.queue_object = mocker.Mock()
    client.queue_object.status.return_value = task_status("completed", "worker-1", "completed")
    mocker.patch.object(client, "create_task", side_effect=["task-1", "task-2"])
    mocker.patch.object(create_tc_task, "TCClient", return_value=client)
    mocker.patch.object(create_tc_task, "is_interactive_terminal", return_value=False)
    mocker.patch.object(create_tc_task.time, "sleep")
    return client


def run_cli(mocker, *options):
    mocker.patch("sys.argv", ["create_tc_task.py", "-q", "test/pool", "-c", "2", "--wait", *options])
    create_tc_task.main()


def test_cli_json_stdout_is_parseable_and_ordered(mocker, cli_client, capsys):
    run_cli(mocker, "--output", "json")
    captured = capsys.readouterr()
    tasks = json.loads(captured.out)["tasks"]
    assert tasks == [
        {
            "task_id": task_id,
            "state": "completed",
            "result": "completed",
            "worker_id": "worker-1",
            "url": f"https://firefox-ci-tc.services.mozilla.com/tasks/{task_id}",
        }
        for task_id in ("task-1", "task-2")
    ]


@pytest.mark.parametrize("interactive", [False, True])
def test_cli_table_shows_results_and_summary(mocker, cli_client, capsys, interactive):
    mocker.patch.object(create_tc_task, "is_interactive_terminal", return_value=interactive)
    run_cli(mocker)
    output = capsys.readouterr().out
    assert "Task results" in output
    assert "task-1" in output
    assert "task-2" in output
    assert "worker-1" in output
    assert "Summary: 2 completed, 0 failed, 0 exception" in output


def test_cli_log_reports_transitions_and_summary(mocker, cli_client, caplog, capsys):
    cli_client.queue_object.status.side_effect = [
        task_status("pending"),
        task_status("running", "worker-2"),
        task_status("completed", "worker-1", "completed"),
        task_status("completed", "worker-2", "completed"),
    ]
    with caplog.at_level(logging.INFO):
        run_cli(mocker, "--output", "log")
    assert "pending" in caplog.text
    assert "running" in caplog.text
    assert "worker=worker-2" in caplog.text
    assert "Summary: 2 completed, 0 failed, 0 exception" in caplog.text
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("state, reason", [("failed", "failed"), ("exception", "worker-shutdown")])
def test_cli_unsuccessful_tasks_return_failure_with_results(mocker, cli_client, capsys, state, reason):
    cli_client.queue_object.status.return_value = task_status(state, "worker-1", reason)
    with pytest.raises(SystemExit) as exc:
        run_cli(mocker, "--output", "json")
    assert exc.value.code == 1
    tasks = json.loads(capsys.readouterr().out)["tasks"]
    assert len(tasks) == 2
    assert all(task["result"] == reason and task["state"] == state for task in tasks)


@pytest.mark.parametrize("created", [[None, None], ["task-1", None]])
def test_cli_submission_failures_return_failure(mocker, cli_client, capsys, created):
    cli_client.create_task.side_effect = created
    with pytest.raises(SystemExit) as exc:
        run_cli(mocker, "--output", "json")
    assert exc.value.code == 1
    tasks = json.loads(capsys.readouterr().out)["tasks"]
    assert len(tasks) == sum(task_id is not None for task_id in created)


def test_cli_dry_run_does_not_poll(mocker, cli_client, capsys):
    cli_client.create_task.side_effect = [None, None]
    run_cli(mocker, "--output", "json", "--dry-run")
    assert json.loads(capsys.readouterr().out) == {"tasks": []}
    cli_client.queue_object.status.assert_not_called()


def test_task_links_and_status_colors():
    task_id = create_tc_task._task_id_text("task-1")
    assert task_id.spans[0].style == "link https://firefox-ci-tc.services.mozilla.com/tasks/task-1"
    assert create_tc_task._task_state_text("failed").style == "red"
