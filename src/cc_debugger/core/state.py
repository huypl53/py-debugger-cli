"""State tracking for variable changes."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class SessionProtocol(Protocol):
    """Protocol for session objects."""
    def get_scopes(self, frame_id: int) -> list: ...
    def get_variables(self, variables_ref: int) -> list: ...
    def evaluate(self, expression: str, frame_id: int, context: str = "repl") -> dict: ...


@dataclass
class VariableSnapshot:
    """Snapshot of a variable's state."""

    name: str
    type: str
    value: str
    hash_value: int
    variables_ref: int = 0


@dataclass
class FrameSnapshot:
    """Snapshot of a frame's state."""

    frame_id: int
    function: str
    variables: dict[str, VariableSnapshot] = field(default_factory=dict)


@dataclass
class WatchResult:
    """Result of evaluating a watch expression."""

    value: str | None
    type: str | None
    changed: bool
    error: str | None = None
    previous: str | None = None


class StateTracker:
    """Track variable state changes between steps."""

    def __init__(self) -> None:
        self.snapshots: dict[int, FrameSnapshot] = {}
        self.watches: dict[str, str | None] = {}
        self.watch_results: dict[str, WatchResult] = {}

    def capture_frame(self, session: SessionProtocol, frame_id: int) -> set[str]:
        """Capture frame state, return changed variable names."""
        scopes = session.get_scopes(frame_id)

        locals_scope = next((s for s in scopes if s.name == "Locals"), None)
        if not locals_scope:
            return set()

        variables = session.get_variables(locals_scope.variablesReference)

        current_vars: dict[str, VariableSnapshot] = {}
        for var in variables:
            snapshot = VariableSnapshot(
                name=var.name,
                type=var.type or "unknown",
                value=var.value,
                hash_value=hash((var.type, var.value)),
                variables_ref=var.variablesReference,
            )
            current_vars[var.name] = snapshot

        prev_snapshot = self.snapshots.get(frame_id)
        changed: set[str] = set()

        if prev_snapshot:
            prev_vars = prev_snapshot.variables

            for name, snap in current_vars.items():
                if name not in prev_vars:
                    changed.add(name)
                elif prev_vars[name].hash_value != snap.hash_value:
                    changed.add(name)

            for name in prev_vars:
                if name not in current_vars:
                    changed.add(f"-{name}")
        else:
            changed = set(current_vars.keys())

        self.snapshots[frame_id] = FrameSnapshot(
            frame_id=frame_id,
            function="",
            variables=current_vars,
        )

        return changed

    def add_watch(self, expression: str) -> None:
        """Add a watch expression."""
        self.watches[expression] = None

    def remove_watch(self, expression: str) -> bool:
        """Remove a watch expression."""
        if expression in self.watches:
            del self.watches[expression]
            if expression in self.watch_results:
                del self.watch_results[expression]
            return True
        return False

    def clear_watches(self) -> int:
        """Clear all watch expressions, return count removed."""
        count = len(self.watches)
        self.watches.clear()
        self.watch_results.clear()
        return count

    def eval_watches(self, session: SessionProtocol, frame_id: int) -> dict[str, WatchResult]:
        """Evaluate all watch expressions, track changes."""
        results: dict[str, WatchResult] = {}

        for expr, prev_value in self.watches.items():
            try:
                result = session.evaluate(expr, frame_id, context="watch")
                new_value = result["value"]
                new_type = result.get("type")

                results[expr] = WatchResult(
                    value=new_value,
                    type=new_type,
                    changed=prev_value is not None and new_value != prev_value,
                    previous=prev_value,
                )

                self.watches[expr] = new_value

            except Exception as e:
                # Error is a change if we had a value before
                results[expr] = WatchResult(
                    value=f"Error: {e}",
                    type=None,
                    changed=prev_value is not None,
                    error=str(e),
                    previous=prev_value,
                )

        self.watch_results = results
        return results

    def get_watch_diff(self) -> list[dict]:
        """Get only watches that changed since last evaluation."""
        diff = []
        for expr, result in self.watch_results.items():
            if result.changed or result.error:
                entry = {
                    "expression": expr,
                    "value": result.value,
                    "type": result.type,
                    "previous": result.previous,
                }
                if result.error:
                    entry["error"] = result.error
                diff.append(entry)
        return diff

    def get_frame_variables(self, frame_id: int) -> dict[str, dict[str, Any]]:
        """Get variables for a frame."""
        snapshot = self.snapshots.get(frame_id)
        if not snapshot:
            return {}

        return {
            name: {"type": v.type, "value": v.value}
            for name, v in snapshot.variables.items()
        }

    def get_changed_variables(
        self,
        frame_id: int,
        changed_names: set[str],
    ) -> dict[str, dict[str, Any]]:
        """Get only changed variables with their previous values."""
        snapshot = self.snapshots.get(frame_id)
        if not snapshot:
            return {}

        result = {}
        for name in changed_names:
            if name.startswith("-"):
                # Deleted variable
                continue
            if name in snapshot.variables:
                var = snapshot.variables[name]
                result[name] = {"type": var.type, "value": var.value}

        return result


def limit_variables(
    variables: dict[str, dict],
    limit: int,
    changed: list[str] | None = None,
    only_changed: bool = False,
) -> dict[str, dict]:
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

    changed_set = set(changed or [])

    def interest_score(name: str) -> tuple:
        """Higher score = more interesting. Returns tuple for sorting."""
        info = variables[name]
        is_changed = name in changed_set
        value = info.get("value", "")
        var_type = info.get("type", "")
        is_none = value == "None" or var_type == "NoneType"
        # Estimate size from value length
        is_large = len(value) > 200

        return (
            is_changed,      # Changed first (True > False)
            not is_none,     # Non-None second
            not is_large,    # Smaller values preferred
            name,            # Alphabetical tiebreaker
        )

    if only_changed:
        candidates = {k: v for k, v in variables.items() if k in changed_set}
    else:
        candidates = variables

    sorted_names = sorted(
        candidates.keys(),
        key=interest_score,
        reverse=True,
    )[:limit]

    return {name: variables[name] for name in sorted_names}
