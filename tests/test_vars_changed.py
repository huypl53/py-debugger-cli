"""Tests for vars --changed feature."""

import pytest
from unittest.mock import Mock
from cc_debugger.core.state import StateTracker


class TestVarsChanged:
    """Tests for --changed flag functionality."""

    def _create_mock_var(self, name: str, value: str, var_type: str = "int"):
        """Create a mock variable object."""
        mock_var = Mock()
        mock_var.name = name
        mock_var.value = value
        mock_var.type = var_type
        mock_var.variablesReference = 0
        return mock_var

    def _create_mock_session(self, variables: list):
        """Create a mock debug session with variables."""
        mock_session = Mock()
        mock_scope = Mock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1
        mock_session.get_scopes.return_value = [mock_scope]
        mock_session.get_variables.return_value = variables
        return mock_session

    def test_changed_first_stop_shows_all(self):
        """VC-01: First stop has no previous state - all vars count as changed."""
        tracker = StateTracker()
        mock_session = self._create_mock_session([
            self._create_mock_var("x", "1"),
            self._create_mock_var("y", "2"),
        ])

        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed
        assert "y" in changed
        assert len(changed) == 2

    def test_changed_single_var(self):
        """VC-02: Only the changed variable appears."""
        tracker = StateTracker()
        mock_var_x = self._create_mock_var("x", "1")
        mock_var_y = self._create_mock_var("y", "2")
        mock_session = self._create_mock_session([mock_var_x, mock_var_y])

        # First capture
        tracker.capture_frame(mock_session, frame_id=1)

        # Change x only
        mock_var_x.value = "10"
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed
        assert "y" not in changed

    def test_changed_new_var_appears(self):
        """VC-03: New variable counts as changed."""
        tracker = StateTracker()
        mock_var_x = self._create_mock_var("x", "1")
        mock_session = self._create_mock_session([mock_var_x])

        # First capture with only x
        tracker.capture_frame(mock_session, frame_id=1)

        # Add new variable z
        mock_var_z = self._create_mock_var("z", "3")
        mock_session.get_variables.return_value = [mock_var_x, mock_var_z]
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "z" in changed
        assert "x" not in changed  # x unchanged

    def test_changed_no_changes(self):
        """VC-04: No variables changed returns empty."""
        tracker = StateTracker()
        mock_var_x = self._create_mock_var("x", "1")
        mock_var_y = self._create_mock_var("y", "2")
        mock_session = self._create_mock_session([mock_var_x, mock_var_y])

        # First capture
        tracker.capture_frame(mock_session, frame_id=1)

        # Capture again with no changes
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert len(changed) == 0

    def test_changed_same_value_reassigned(self):
        """VC-05: Same value reassigned (y = y) should not count as changed."""
        tracker = StateTracker()
        mock_var_y = self._create_mock_var("y", "2")
        mock_session = self._create_mock_session([mock_var_y])

        # First capture
        tracker.capture_frame(mock_session, frame_id=1)

        # "Reassign" with same value (value string unchanged)
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "y" not in changed

    def test_changed_multiple_vars(self):
        """VC-06: Multiple variables change at once."""
        tracker = StateTracker()
        mock_var_x = self._create_mock_var("x", "1")
        mock_var_y = self._create_mock_var("y", "2")
        mock_var_z = self._create_mock_var("z", "3")
        mock_session = self._create_mock_session([mock_var_x, mock_var_y, mock_var_z])

        # First capture
        tracker.capture_frame(mock_session, frame_id=1)

        # Change x and z, not y
        mock_var_x.value = "10"
        mock_var_z.value = "30"
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed
        assert "z" in changed
        assert "y" not in changed

    def test_changed_type_change(self):
        """VC-07: Type change counts as change even if repr similar."""
        tracker = StateTracker()
        mock_var = self._create_mock_var("x", "1", "int")
        mock_session = self._create_mock_session([mock_var])

        tracker.capture_frame(mock_session, frame_id=1)

        # Change type from int to str
        mock_var.type = "str"
        mock_var.value = "'1'"
        changed = tracker.capture_frame(mock_session, frame_id=1)

        assert "x" in changed
