"""Tests for cc-debug why feature."""

import pytest


class TestWhy:
    """Tests for why command functionality."""

    def test_why_entry(self):
        """WHY-01: Stop at entry point."""
        stop_info = {
            "reason": "entry",
            "location": {
                "file": "/path/to/main.py",
                "line": 1,
                "function": "<module>",
            }
        }

        result = format_why(stop_info)

        assert "entry" in result["summary"].lower()
        assert "main.py:1" in result["summary"]
        assert result["reason"] == "entry"

    def test_why_breakpoint(self):
        """WHY-02: Hit a breakpoint."""
        stop_info = {
            "reason": "breakpoint",
            "location": {
                "file": "/path/to/utils.py",
                "line": 42,
                "function": "process",
            },
            "breakpoint_id": 3,
        }

        result = format_why(stop_info)

        assert "breakpoint" in result["summary"].lower()
        assert "#3" in result["summary"] or "3" in result["summary"]
        assert "utils.py:42" in result["summary"]
        assert result["details"]["breakpoint_id"] == 3

    def test_why_conditional_breakpoint(self):
        """WHY-03: Hit conditional breakpoint."""
        stop_info = {
            "reason": "breakpoint",
            "location": {
                "file": "/path/to/main.py",
                "line": 15,
                "function": "check",
            },
            "breakpoint_id": 2,
            "condition": "x > 10",
        }

        result = format_why(stop_info)

        assert "conditional" in result["summary"].lower() or "x > 10" in result["summary"]
        assert result["details"]["condition"] == "x > 10"

    def test_why_exception(self):
        """WHY-04: Exception raised."""
        stop_info = {
            "reason": "exception",
            "location": {
                "file": "/path/to/parser.py",
                "line": 88,
                "function": "parse",
            },
            "exception": {
                "type": "ValueError",
                "message": "invalid literal for int()",
            }
        }

        result = format_why(stop_info)

        assert "exception" in result["summary"].lower() or "ValueError" in result["summary"]
        assert "invalid literal" in result["summary"] or "ValueError" in result["summary"]
        assert result["details"]["exception"]["type"] == "ValueError"

    def test_why_step(self):
        """WHY-05: Step completed."""
        stop_info = {
            "reason": "step",
            "location": {
                "file": "/path/to/main.py",
                "line": 25,
                "function": "process",
            }
        }

        result = format_why(stop_info)

        assert "step" in result["summary"].lower()
        assert "main.py:25" in result["summary"]
        assert "process" in result["summary"]

    def test_why_step_in(self):
        """WHY-06: Stepped into function."""
        stop_info = {
            "reason": "step",
            "step_type": "in",
            "location": {
                "file": "/path/to/utils.py",
                "line": 10,
                "function": "helper",
            }
        }

        result = format_why(stop_info)

        assert "into" in result["summary"].lower() or "step" in result["summary"].lower()
        assert "helper" in result["summary"]

    def test_why_step_out(self):
        """WHY-07: Stepped out of function."""
        stop_info = {
            "reason": "step",
            "step_type": "out",
            "location": {
                "file": "/path/to/main.py",
                "line": 30,
                "function": "main",
            }
        }

        result = format_why(stop_info)

        assert "out" in result["summary"].lower() or "step" in result["summary"].lower()

    def test_why_exited(self):
        """WHY-08: Program exited."""
        stop_info = {
            "reason": "exited",
            "exit_code": 0,
        }

        result = format_why(stop_info)

        assert "exit" in result["summary"].lower()
        assert "0" in result["summary"]

    def test_why_exited_with_error(self):
        """WHY-09: Program exited with error code."""
        stop_info = {
            "reason": "exited",
            "exit_code": 1,
        }

        result = format_why(stop_info)

        assert "exit" in result["summary"].lower()
        assert "1" in result["summary"]

    def test_why_until(self):
        """WHY-10: Reached target line via until."""
        stop_info = {
            "reason": "until",
            "location": {
                "file": "/path/to/main.py",
                "line": 50,
                "function": "loop",
            }
        }

        result = format_why(stop_info)

        assert "50" in result["summary"]
        assert "main.py" in result["summary"]

    def test_why_no_session(self):
        """WHY-11: No active session."""
        stop_info = None

        result = format_why(stop_info)

        assert result["reason"] == "no_session"
        assert "no" in result["summary"].lower() and "session" in result["summary"].lower()


def format_why(stop_info: dict | None) -> dict:
    """
    Format a human-readable explanation of why execution stopped.

    Args:
        stop_info: Stop event info from debugger, or None if no session

    Returns:
        Dict with 'reason', 'summary', and 'details'
    """
    if stop_info is None:
        return {
            "reason": "no_session",
            "summary": "No active debug session",
            "details": {},
        }

    reason = stop_info.get("reason", "unknown")
    location = stop_info.get("location", {})
    file = location.get("file", "?").split("/")[-1]  # basename
    line = location.get("line", "?")
    func = location.get("function", "?")

    details = {"file": file, "line": line, "function": func}

    if reason == "entry":
        summary = f"Stopped at entry point: {file}:{line}"

    elif reason == "breakpoint":
        bp_id = stop_info.get("breakpoint_id", "?")
        condition = stop_info.get("condition")
        details["breakpoint_id"] = bp_id
        if condition:
            details["condition"] = condition
            summary = f"Hit conditional breakpoint #{bp_id} ({condition}) at {file}:{line}"
        else:
            summary = f"Hit breakpoint #{bp_id} at {file}:{line}"

    elif reason == "exception":
        exc = stop_info.get("exception", {})
        exc_type = exc.get("type", "Exception")
        exc_msg = exc.get("message", "")
        details["exception"] = exc
        # Truncate long messages
        if len(exc_msg) > 50:
            exc_msg = exc_msg[:47] + "..."
        summary = f"Exception raised: {exc_type}('{exc_msg}') at {file}:{line}"

    elif reason == "step":
        step_type = stop_info.get("step_type", "")
        if step_type == "in":
            summary = f"Stepped into {func}() at {file}:{line}"
        elif step_type == "out":
            summary = f"Stepped out to {func}() at {file}:{line}"
        else:
            summary = f"Step completed at {file}:{line} in {func}()"

    elif reason == "until":
        summary = f"Reached line {line} in {file}"

    elif reason == "exited":
        exit_code = stop_info.get("exit_code", 0)
        details["exit_code"] = exit_code
        summary = f"Program exited with code {exit_code}"

    elif reason == "pause":
        summary = "Paused by user request"

    else:
        summary = f"Stopped ({reason}) at {file}:{line}"

    return {
        "reason": reason,
        "summary": summary,
        "details": details,
    }
