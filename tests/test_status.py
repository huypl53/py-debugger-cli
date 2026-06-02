"""Tests for daemon session status tracking."""

import threading
from queue import Queue
from unittest.mock import Mock

from cc_debugger.daemon_main import DaemonServer


def test_status_reports_running_without_fetching_location():
    server = DaemonServer(port=0)
    server.session = Mock()
    server.session.events = Queue()
    server.session._events_lock = threading.Lock()
    server.execution_state = "running"
    server.session.get_location.side_effect = AssertionError(
        "running status should not fetch stack location"
    )

    result = server.handle_command({"action": "status"})

    assert result["success"] is True
    assert result["state"] == "running"
    assert "location" not in result


def test_status_updates_to_stopped_after_breakpoint_event():
    server = DaemonServer(port=0)
    session = Mock()
    session.events = Queue()
    session._events_lock = threading.Lock()
    session.thread_id = 7
    session.get_location.return_value = {
        "file": "/tmp/app.py",
        "line": 42,
        "function": "read_root",
    }
    session.events.put({
        "type": "event",
        "event": "stopped",
        "body": {"reason": "breakpoint", "threadId": 7},
    })

    server.session = session
    server.execution_state = "running"

    result = server.handle_command({"action": "status"})

    assert result["success"] is True
    assert result["state"] == "stopped"
    assert result["reason"] == "breakpoint"
    assert result["location"] == {
        "file": "/tmp/app.py",
        "line": 42,
        "function": "read_root",
    }
