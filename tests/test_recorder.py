"""Tests for recorder and time-travel."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
from cc_debugger.core.recorder import Recorder, Checkpoint, StackFrameSnapshot


class TestRecorder:
    """Tests for Recorder."""

    def test_start_stop_recording(self):
        recorder = Recorder()
        assert recorder.recording is False

        recorder.start_recording()
        assert recorder.recording is True

        session_id = recorder.stop_recording()
        assert recorder.recording is False
        assert session_id == recorder.session_id

    def test_create_checkpoint(self):
        recorder = Recorder()
        recorder.start_recording()

        mock_session = Mock()
        mock_frame = Mock()
        mock_frame.id = 1
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.source = Mock()
        mock_frame.source.path = "/path/to/file.py"

        mock_scope = Mock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1

        mock_var = Mock()
        mock_var.name = "x"
        mock_var.type = "int"
        mock_var.value = "42"

        mock_session.get_stack_frames.return_value = [mock_frame]
        mock_session.get_scopes.return_value = [mock_scope]
        mock_session.get_variables.return_value = [mock_var]
        mock_session.state_tracker = None

        cp = recorder.create_checkpoint(mock_session, reason="test")

        assert cp.reason == "test"
        assert len(recorder.checkpoints) == 1
        assert recorder.current_idx == 0

    def test_step_back_forward(self):
        recorder = Recorder()
        recorder.start_recording()

        mock_session = Mock()
        mock_frame = Mock()
        mock_frame.id = 1
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.source = Mock()
        mock_frame.source.path = "/path/to/file.py"

        mock_session.get_stack_frames.return_value = [mock_frame]
        mock_session.get_scopes.return_value = []
        mock_session.state_tracker = None

        cp1 = recorder.create_checkpoint(mock_session, reason="first")
        cp2 = recorder.create_checkpoint(mock_session, reason="second")
        cp3 = recorder.create_checkpoint(mock_session, reason="third")

        assert recorder.current_idx == 2

        back = recorder.step_back()
        assert back.id == cp2.id
        assert recorder.current_idx == 1

        back = recorder.step_back()
        assert back.id == cp1.id
        assert recorder.current_idx == 0

        back = recorder.step_back()
        assert back is None

        forward = recorder.step_forward()
        assert forward.id == cp2.id

    def test_goto(self):
        recorder = Recorder()
        recorder.start_recording()

        mock_session = Mock()
        mock_frame = Mock()
        mock_frame.id = 1
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.source = Mock()
        mock_frame.source.path = "/path/to/file.py"

        mock_session.get_stack_frames.return_value = [mock_frame]
        mock_session.get_scopes.return_value = []
        mock_session.state_tracker = None

        cp1 = recorder.create_checkpoint(mock_session, reason="first")
        cp2 = recorder.create_checkpoint(mock_session, reason="second")

        result = recorder.goto(cp1.id)
        assert result.id == cp1.id
        assert recorder.current_idx == 0

        result = recorder.goto("nonexistent")
        assert result is None

    def test_max_checkpoints(self):
        recorder = Recorder(max_checkpoints=3)
        recorder.start_recording()

        mock_session = Mock()
        mock_frame = Mock()
        mock_frame.id = 1
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.source = Mock()
        mock_frame.source.path = "/path/to/file.py"

        mock_session.get_stack_frames.return_value = [mock_frame]
        mock_session.get_scopes.return_value = []
        mock_session.state_tracker = None

        for i in range(5):
            recorder.create_checkpoint(mock_session, reason=f"cp_{i}")

        assert len(recorder.checkpoints) == 3
        assert recorder.checkpoints[0].reason == "cp_2"

    def test_export(self):
        recorder = Recorder()
        recorder.start_recording()

        mock_session = Mock()
        mock_frame = Mock()
        mock_frame.id = 1
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.source = Mock()
        mock_frame.source.path = "/path/to/file.py"

        mock_session.get_stack_frames.return_value = [mock_frame]
        mock_session.get_scopes.return_value = []
        mock_session.state_tracker = None

        recorder.create_checkpoint(mock_session, reason="test")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            recorder.export(f.name)
            content = Path(f.name).read_text()
            assert "checkpoints" in content
            assert "test" in content


class TestCheckpoint:
    """Tests for Checkpoint model."""

    def test_to_dict(self):
        frame = StackFrameSnapshot(
            id=1, name="main", file="/path/to/file.py", line=10, locals={"x": {"type": "int", "value": "42"}}
        )
        cp = Checkpoint(
            id="abc123",
            sequence=0,
            timestamp=1234567890.0,
            reason="manual",
            location={"file": "/path/to/file.py", "line": 10, "function": "main"},
            stack=[frame],
            variables={},
            watches={},
        )

        d = cp.to_dict()
        assert d["id"] == "abc123"
        assert d["reason"] == "manual"
        assert len(d["stack"]) == 1

    def test_from_dict(self):
        data = {
            "id": "abc123",
            "sequence": 0,
            "timestamp": 1234567890.0,
            "reason": "manual",
            "location": {"file": "/path/to/file.py", "line": 10},
            "stack": [
                {"id": 1, "name": "main", "file": "/path/to/file.py", "line": 10, "locals": {}}
            ],
            "variables": {},
            "watches": {},
        }

        cp = Checkpoint.from_dict(data)
        assert cp.id == "abc123"
        assert cp.reason == "manual"
        assert len(cp.stack) == 1
