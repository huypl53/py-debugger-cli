"""Tests for vars --limit feature."""

import pytest
from cc_debugger.core.state import StateTracker


class TestVarsLimit:
    """Tests for --limit N flag functionality."""

    def test_limit_basic(self):
        """VL-01: Limit to N variables."""
        variables = {
            "a": {"type": "int", "value": "1"},
            "b": {"type": "int", "value": "2"},
            "c": {"type": "int", "value": "3"},
            "d": {"type": "int", "value": "4"},
            "e": {"type": "int", "value": "5"},
        }

        limited = limit_variables(variables, limit=3)

        assert len(limited) == 3

    def test_limit_exceeds_total(self):
        """VL-02: Limit greater than available returns all."""
        variables = {
            "a": {"type": "int", "value": "1"},
            "b": {"type": "int", "value": "2"},
        }

        limited = limit_variables(variables, limit=10)

        assert len(limited) == 2

    def test_limit_zero(self):
        """VL-03: Limit=0 returns empty."""
        variables = {
            "a": {"type": "int", "value": "1"},
        }

        limited = limit_variables(variables, limit=0)

        assert len(limited) == 0

    def test_limit_prioritizes_changed(self):
        """VL-04: Changed variables come first."""
        variables = {
            "unchanged1": {"type": "int", "value": "1"},
            "changed1": {"type": "int", "value": "10"},
            "unchanged2": {"type": "int", "value": "2"},
            "changed2": {"type": "int", "value": "20"},
        }
        changed = ["changed1", "changed2"]

        limited = limit_variables(variables, limit=2, changed=changed)

        assert "changed1" in limited
        assert "changed2" in limited
        assert "unchanged1" not in limited

    def test_limit_excludes_none_last(self):
        """VL-05: None variables have lower priority."""
        variables = {
            "none1": {"type": "NoneType", "value": "None"},
            "value1": {"type": "int", "value": "42"},
            "none2": {"type": "NoneType", "value": "None"},
            "value2": {"type": "str", "value": "'hello'"},
        }

        limited = limit_variables(variables, limit=2)

        assert "value1" in limited
        assert "value2" in limited
        assert "none1" not in limited
        assert "none2" not in limited

    def test_limit_with_changed_filter(self):
        """VL-06: --limit combined with --changed."""
        variables = {
            "a": {"type": "int", "value": "1"},
            "b": {"type": "int", "value": "2"},
            "c": {"type": "int", "value": "3"},
            "d": {"type": "int", "value": "4"},
            "e": {"type": "int", "value": "5"},
        }
        changed = ["a", "c", "e"]  # 3 changed

        # Only show 2 of the 3 changed
        limited = limit_variables(variables, limit=2, changed=changed, only_changed=True)

        assert len(limited) == 2
        for name in limited:
            assert name in changed

    def test_limit_negative_raises_error(self):
        """VL-07: Negative limit raises ValueError."""
        variables = {"a": {"type": "int", "value": "1"}}

        with pytest.raises(ValueError):
            limit_variables(variables, limit=-1)

    def test_limit_preserves_order_by_interest(self):
        """VL-08: Variables ordered by interest score."""
        variables = {
            "none_var": {"type": "NoneType", "value": "None"},
            "large_list": {"type": "list", "value": "[...]", "length": 1000},
            "simple_int": {"type": "int", "value": "42"},
            "small_list": {"type": "list", "value": "[1, 2]", "length": 2},
        }
        changed = ["simple_int"]  # This one is most interesting

        limited = limit_variables(variables, limit=2, changed=changed)
        keys = list(limited.keys())

        # Changed var should be first
        assert keys[0] == "simple_int"


def limit_variables(
    variables: dict,
    limit: int,
    changed: list | None = None,
    only_changed: bool = False
) -> dict:
    """
    Limit variables to top N most interesting.

    Interest scoring (highest first):
    1. Recently changed
    2. Non-None values
    3. Smaller/simpler types
    4. Alphabetical tiebreaker

    Args:
        variables: Dict of variable name -> info
        limit: Max variables to return
        changed: List of changed variable names
        only_changed: If True, only include changed variables

    Returns:
        Limited dict of variables
    """
    if limit < 0:
        raise ValueError("Limit must be non-negative")

    if limit == 0:
        return {}

    changed = changed or []

    def interest_score(name: str) -> tuple:
        """Higher score = more interesting. Returns tuple for sorting."""
        info = variables[name]
        is_changed = name in changed
        is_none = info.get("value") == "None" or info.get("type") == "NoneType"
        is_large = info.get("length", 0) > 100

        return (
            is_changed,      # Changed first (True > False)
            not is_none,     # Non-None second
            not is_large,    # Smaller values preferred
            name,            # Alphabetical tiebreaker (reversed for desc)
        )

    if only_changed:
        candidates = {k: v for k, v in variables.items() if k in changed}
    else:
        candidates = variables

    sorted_names = sorted(
        candidates.keys(),
        key=interest_score,
        reverse=True
    )[:limit]

    return {name: variables[name] for name in sorted_names}
