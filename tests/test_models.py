"""Tests for data models."""

import pytest
from cc_debugger.models.dap import (
    Request,
    Response,
    Event,
    InitializeRequestArguments,
    LaunchRequestArguments,
    Source,
    SourceBreakpoint,
    StackFrame,
    Scope,
    Variable,
)
from cc_debugger.models.session import SessionState, Location, BreakpointState


class TestDAPModels:
    """Tests for DAP message models."""

    def test_request_to_dict(self):
        req = Request(seq=1, command="initialize", arguments={"clientID": "test"})
        d = req.to_dict()
        assert d["seq"] == 1
        assert d["type"] == "request"
        assert d["command"] == "initialize"
        assert d["arguments"]["clientID"] == "test"

    def test_response_from_dict(self):
        data = {
            "seq": 2,
            "type": "response",
            "request_seq": 1,
            "success": True,
            "command": "initialize",
            "body": {"supportsConfigurationDoneRequest": True},
        }
        resp = Response.from_dict(data)
        assert resp.seq == 2
        assert resp.request_seq == 1
        assert resp.success is True
        assert resp.body["supportsConfigurationDoneRequest"] is True

    def test_event_from_dict(self):
        data = {
            "seq": 3,
            "type": "event",
            "event": "stopped",
            "body": {"reason": "breakpoint", "threadId": 1},
        }
        event = Event.from_dict(data)
        assert event.seq == 3
        assert event.event == "stopped"
        assert event.body["reason"] == "breakpoint"

    def test_initialize_arguments(self):
        args = InitializeRequestArguments()
        d = args.to_dict()
        assert d["clientID"] == "cc-debugger"
        assert d["linesStartAt1"] is True

    def test_launch_arguments(self):
        args = LaunchRequestArguments(program="/path/to/file.py", args=["--verbose"])
        d = args.to_dict()
        assert d["program"] == "/path/to/file.py"
        assert d["args"] == ["--verbose"]
        assert d["stopOnEntry"] is False

    def test_source_breakpoint(self):
        bp = SourceBreakpoint(line=42, condition="x > 10")
        d = bp.to_dict()
        assert d["line"] == 42
        assert d["condition"] == "x > 10"

    def test_stack_frame_from_dict(self):
        data = {
            "id": 1,
            "name": "main",
            "line": 10,
            "column": 5,
            "source": {"path": "/path/to/file.py"},
        }
        frame = StackFrame.from_dict(data)
        assert frame.id == 1
        assert frame.name == "main"
        assert frame.source.path == "/path/to/file.py"

    def test_variable_from_dict(self):
        data = {
            "name": "x",
            "value": "42",
            "type": "int",
            "variablesReference": 0,
        }
        var = Variable.from_dict(data)
        assert var.name == "x"
        assert var.value == "42"
        assert var.type == "int"


class TestSessionModels:
    """Tests for session state models."""

    def test_location_to_dict(self):
        loc = Location(file="/path/to/file.py", line=42, function="main")
        d = loc.to_dict()
        assert d["file"] == "/path/to/file.py"
        assert d["line"] == 42
        assert d["function"] == "main"

    def test_breakpoint_state(self):
        bp = BreakpointState(file="/path/to/file.py", line=42, condition="x > 10")
        d = bp.to_dict()
        assert d["file"] == "/path/to/file.py"
        assert d["line"] == 42
        assert d["condition"] == "x > 10"

        bp2 = BreakpointState.from_dict(d)
        assert bp2.file == bp.file
        assert bp2.line == bp.line
        assert bp2.condition == bp.condition
