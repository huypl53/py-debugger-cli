"""Tests for watch diff feature."""

import pytest
from unittest.mock import Mock
from cc_debugger.core.state import StateTracker


class TestWatchDiff:
    """Tests for watch diff functionality."""

    def test_diff_first_eval_shows_all(self):
        """WD-01: First evaluation shows all watches as 'new'."""
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.add_watch("y")
        tracker.add_watch("z")

        mock_session = Mock()
        mock_session.evaluate.side_effect = [
            {"value": "1", "type": "int"},
            {"value": "2", "type": "int"},
            {"value": "3", "type": "int"},
        ]

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=True)

        assert len(diff) == 3
        assert all(w["is_new"] for w in diff)

    def test_diff_one_changed(self):
        """WD-02: Only changed watch appears in diff."""
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.add_watch("y")

        # Set initial values
        tracker.watches["x"] = "5"
        tracker.watches["y"] = "10"
        previous_values = {"x": "5", "y": "10"}

        mock_session = Mock()
        mock_session.evaluate.side_effect = [
            {"value": "5", "type": "int"},   # x unchanged
            {"value": "20", "type": "int"},  # y changed
        ]

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False, previous_values=previous_values)

        assert len(diff) == 1
        assert diff[0]["expression"] == "y"
        assert diff[0]["previous"] == "10"
        assert diff[0]["value"] == "20"

    def test_diff_none_changed(self):
        """WD-03: No changes returns empty diff."""
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.add_watch("y")

        # Set values that won't change
        tracker.watches["x"] = "5"
        tracker.watches["y"] = "10"

        mock_session = Mock()
        mock_session.evaluate.side_effect = [
            {"value": "5", "type": "int"},
            {"value": "10", "type": "int"},
        ]

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False)

        assert len(diff) == 0

    def test_diff_all_changed(self):
        """WD-04: All watches changed."""
        tracker = StateTracker()
        tracker.add_watch("x")
        tracker.add_watch("y")
        tracker.add_watch("z")

        tracker.watches["x"] = "1"
        tracker.watches["y"] = "2"
        tracker.watches["z"] = "3"

        mock_session = Mock()
        mock_session.evaluate.side_effect = [
            {"value": "10", "type": "int"},
            {"value": "20", "type": "int"},
            {"value": "30", "type": "int"},
        ]

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False)

        assert len(diff) == 3

    def test_diff_expression_watch(self):
        """WD-05: Expression watch like 'x + y' tracks correctly."""
        tracker = StateTracker()
        tracker.add_watch("x + y")

        tracker.watches["x + y"] = "10"
        previous_values = {"x + y": "10"}

        mock_session = Mock()
        mock_session.evaluate.return_value = {"value": "15", "type": "int"}

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False, previous_values=previous_values)

        assert len(diff) == 1
        assert diff[0]["expression"] == "x + y"
        assert diff[0]["previous"] == "10"
        assert diff[0]["value"] == "15"

    def test_diff_with_eval_error(self):
        """WD-06: Watch eval error appears in diff."""
        tracker = StateTracker()
        tracker.add_watch("invalid_var")
        tracker.watches["invalid_var"] = "5"  # Had a value before
        previous_values = {"invalid_var": "5"}

        mock_session = Mock()
        mock_session.evaluate.side_effect = Exception("NameError: invalid_var")

        results = tracker.eval_watches(mock_session, frame_id=1)

        # The result should have error info - check the WatchResult
        assert "invalid_var" in results
        result = results["invalid_var"]
        # Error causes a "change" since value is now an error
        assert result.error is not None or result.value.startswith("Error")

        diff = get_watch_diff(results, is_first=False, previous_values=previous_values)

        # Error should appear as a change (value became error)
        assert len(diff) == 1
        assert "error" in diff[0] or diff[0].get("value", "").startswith("Error")

    def test_diff_no_watches(self):
        """WD-07: No watches set returns empty."""
        tracker = StateTracker()

        mock_session = Mock()

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False)

        assert len(diff) == 0

    def test_diff_includes_type_info(self):
        """WD-08: Diff includes type information."""
        tracker = StateTracker()
        tracker.add_watch("data")
        tracker.watches["data"] = "[1, 2]"

        mock_session = Mock()
        mock_session.evaluate.return_value = {"value": "[1, 2, 3]", "type": "list"}

        results = tracker.eval_watches(mock_session, frame_id=1)
        diff = get_watch_diff(results, is_first=False)

        assert len(diff) == 1
        assert diff[0]["type"] == "list"


def get_watch_diff(results: dict, is_first: bool = False, previous_values: dict | None = None) -> list:
    """
    Extract only changed watches from eval results.

    Args:
        results: Dict of expression -> WatchResult
        is_first: If True, treat all as "new" (first evaluation)
        previous_values: Dict of expression -> previous value string

    Returns:
        List of changed watch info dicts
    """
    diff = []
    previous_values = previous_values or {}

    for expr, result in results.items():
        if is_first:
            diff.append({
                "expression": expr,
                "value": result.value,
                "type": result.type,
                "is_new": True,
            })
        elif result.changed or (hasattr(result, "error") and result.error):
            entry = {
                "expression": expr,
                "value": result.value,
                "type": result.type,
                "previous": previous_values.get(expr),
            }
            if hasattr(result, "error") and result.error:
                entry["error"] = result.error
            diff.append(entry)

    return diff
