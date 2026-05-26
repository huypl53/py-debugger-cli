import pytest
from pathlib import Path
from click.testing import CliRunner
from cc_debugger.commands.breakpoints import bp_set
from cc_debugger.commands.control import run_to_cursor
from unittest.mock import patch

def test_bp_set_warning(tmp_path):
    file_path = tmp_path / "app.py"
    file_path.write_text("def my_func():\n    pass\n")

    runner = CliRunner()
    with patch("cc_debugger.commands.breakpoints._send_to_daemon") as mock_send:
        mock_send.return_value = {"success": True}
        result = runner.invoke(bp_set, [f"{file_path}:1"])
        assert result.exit_code == 0
        assert "warning" in result.output
        assert "contains a function, method, or class definition" in result.output

def test_run_to_cursor_warning(tmp_path):
    file_path = tmp_path / "app.py"
    file_path.write_text("class MyClass:\n    pass\n")

    runner = CliRunner()
    with patch("cc_debugger.commands.control._send_to_daemon") as mock_send:
        mock_send.return_value = {"success": True}
        result = runner.invoke(run_to_cursor, [f"{file_path}:1"])
        assert result.exit_code == 0
        # Warning is printed to stderr, click's CliRunner captures mix of stdout/stderr in result.output
        assert "Warning: Line 1 contains a function/class definition" in result.output
