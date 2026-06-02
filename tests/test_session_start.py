"""Tests for session start command."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cc_debugger.commands.session import start


def test_start_preserves_python_venv_wrapper_path(tmp_path):
    target_file = tmp_path / "app.py"
    target_file.write_text("print('ok')\n")

    real_python = tmp_path / "python-real"
    real_python.write_text("")

    venv_dir = tmp_path / ".venv" / "bin"
    venv_dir.mkdir(parents=True)
    venv_python = venv_dir / "python"
    venv_python.symlink_to(real_python)

    runner = CliRunner()

    with (
        patch("cc_debugger.commands.session._stop_daemon"),
        patch("cc_debugger.commands.session._start_daemon"),
        patch("cc_debugger.commands.session._send_to_daemon") as mock_send,
    ):
        mock_send.return_value = {"success": True, "stopped": {"reason": "entry"}}
        result = runner.invoke(
            start,
            [str(target_file), "--python", str(venv_python)],
        )

    assert result.exit_code == 0
    sent_command = mock_send.call_args.args[0]
    assert sent_command["python"] == str(venv_python.absolute())
    assert sent_command["python"] != str(real_python.resolve())


def test_start_uses_invocation_cwd_for_launch(tmp_path, monkeypatch):
    target_dir = tmp_path / ".venv" / "bin"
    target_dir.mkdir(parents=True)
    target_file = target_dir / "uvicorn"
    target_file.write_text("#!/bin/sh\n")

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    monkeypatch.chdir(workspace_dir)

    runner = CliRunner()

    with (
        patch("cc_debugger.commands.session._stop_daemon"),
        patch("cc_debugger.commands.session._start_daemon"),
        patch("cc_debugger.commands.session._send_to_daemon") as mock_send,
    ):
        mock_send.return_value = {"success": True, "state": "running", "message": "ok"}
        result = runner.invoke(start, [str(target_file), "--no-stop"])

    assert result.exit_code == 0
    sent_command = mock_send.call_args.args[0]
    assert sent_command["cwd"] == str(workspace_dir)
