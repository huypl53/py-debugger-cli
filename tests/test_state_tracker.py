"""Tests for state tracker."""

import pytest
from unittest.mock import Mock, MagicMock
from cc_debugger.core.state import StateTracker, VariableSnapshot


class TestStateTracker:
    """Tests for StateTracker."""

    def test_add_watch(self):
        tracker = StateTracker()
        tracker.add_watch("x + y")
        assert "x + y" in tracker.watches
        assert tracker.watches["x + y"] is None

    def test_remove_watch(self):
        tracker = StateTracker()
        tracker.add_watch("x")
        assert tracker.remove_watch("x") is True
        assert "x" not in tracker.watches

    def test_remove_nonexistent_watch(self):
        tracker = StateTracker()
        assert tracker.remove_watch("nonexistent") is False

    def test_clear_watches(self):
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.add_watch("y")
        tracker.add_watch("z")
        count = tracker.clear_watches()
        assert count == 3
        assert len(tracker.watches) == 0

    def test_capture_frame_initial(self):
        tracker = StateTracker()

        mock_session = Mock()
        mock_scope = Mock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1

        mock_var = Mock()
        mock_var.name = "x"
        mock_var.type = "int"
        mock_var.value = "42"
        mock_var.variablesReference = 0

        mock_session.get_scopes.return_value = [mock_scope]
        mock_session.get_variables.return_value = [mock_var]

        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed
        assert 1 in tracker.snapshots
        assert "x" in tracker.snapshots[1].variables

    def test_capture_frame_detects_changes(self):
        tracker = StateTracker()

        mock_session = Mock()
        mock_scope = Mock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1

        mock_var = Mock()
        mock_var.name = "x"
        mock_var.type = "int"
        mock_var.value = "42"
        mock_var.variablesReference = 0

        mock_session.get_scopes.return_value = [mock_scope]
        mock_session.get_variables.return_value = [mock_var]

        tracker.capture_frame(mock_session, frame_id=1)

        mock_var.value = "100"
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed

    def test_eval_watches(self):
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.watches["x"] = None

        mock_session = Mock()
        mock_session.evaluate.return_value = {"value": "42", "type": "int"}

        results = tracker.eval_watches(mock_session, frame_id=1)

        assert "x" in results
        assert results["x"].value == "42"
        assert results["x"].changed is False

    def test_eval_watches_detects_changes(self):
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.watches["x"] = "42"

        mock_session = Mock()
        mock_session.evaluate.return_value = {"value": "100", "type": "int"}

        results = tracker.eval_watches(mock_session, frame_id=1)

        assert results["x"].changed is True
