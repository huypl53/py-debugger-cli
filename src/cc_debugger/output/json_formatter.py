"""JSON output formatting."""

import json
import sys
from dataclasses import dataclass
from typing import Any

from cc_debugger.models.session import Location


def output_json(data: dict[str, Any]) -> None:
    """Output JSON to stdout."""
    print(json.dumps(data, indent=2))


def print_program_output(output_lines: list[dict]) -> None:
    """Print program stdout/stderr to stderr so users can see it.

    Output format: [stdout] or [stderr] prefix followed by content.
    """
    if not output_lines:
        return
    for item in output_lines:
        category = item.get("category", "stdout")
        content = item.get("output", "")
        if content:
            prefix = f"[{category}] " if category == "stderr" else ""
            sys.stderr.write(f"{prefix}{content}")
            if not content.endswith("\n"):
                sys.stderr.write("\n")
    sys.stderr.flush()


def format_success(command: str, result: dict[str, Any]) -> dict[str, Any]:
    """Format successful command result."""
    return {
        "success": True,
        "command": command,
        "result": result,
    }


def format_error(command: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Format error result."""
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        error["details"] = details

    return {
        "success": False,
        "command": command,
        "error": error,
    }


def format_stopped(
    reason: str,
    location: Location,
    changed_vars: list[str] | None = None,
    watches: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Format a stopped event."""
    result: dict[str, Any] = {
        "event": "stopped",
        "reason": reason,
        "location": location.to_dict(),
    }

    if changed_vars:
        result["changedVars"] = changed_vars

    if watches:
        result["watches"] = {
            expr: {
                "value": w.value,
                "type": w.type,
                "changed": w.changed,
            }
            for expr, w in watches.items()
            if not w.error
        }

        errors = {expr: w.error for expr, w in watches.items() if w.error}
        if errors:
            result["watchErrors"] = errors

    return result


def format_variables(
    variables: list[Any],
    max_depth: int = 3,
    current_depth: int = 0,
) -> dict[str, dict[str, Any]]:
    """Format variables for JSON output."""
    result: dict[str, dict[str, Any]] = {}

    for var in variables:
        value: dict[str, Any] = {
            "type": var.type or "unknown",
            "value": _truncate_value(var.value),
        }

        if var.variablesReference > 0:
            if current_depth < max_depth:
                value["expandable"] = True
            else:
                value["truncated"] = True

        result[var.name] = value

    return result


def _truncate_value(value: str, max_len: int = 200) -> str:
    """Truncate long values."""
    if len(value) > max_len:
        return value[:max_len] + "..."
    return value


@dataclass
class OutputFormatter:
    """Configurable output formatter."""

    max_depth: int = 5
    max_items: int = 100
    max_value_len: int = 200

    def format_stopped_event(
        self,
        reason: str,
        location: Location,
        changed_vars: list[str] | None = None,
        watches: dict[str, Any] | None = None,
        stack: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Format a stopped event with state changes."""
        result: dict[str, Any] = {
            "event": "stopped",
            "reason": reason,
            "location": location.to_dict(),
        }

        if changed_vars:
            result["changedVars"] = changed_vars

        if watches:
            result["watches"] = self._format_watches(watches)

        if stack:
            result["stack"] = self._format_stack(stack)

        return result

    def format_variable(self, var: dict[str, Any], depth: int = 0) -> dict[str, Any]:
        """Format a variable with truncation."""
        formatted: dict[str, Any] = {
            "type": var.get("type", "unknown"),
            "value": self._truncate(var.get("value", "")),
        }

        if var.get("variablesReference", 0) > 0:
            if depth < self.max_depth:
                formatted["expandable"] = True
            else:
                formatted["truncated"] = True

        return formatted

    def _truncate(self, value: str) -> str:
        """Truncate long values."""
        if len(value) > self.max_value_len:
            return value[: self.max_value_len] + "..."
        return value

    def _format_watches(self, watches: dict[str, Any]) -> dict[str, Any]:
        """Format watch results."""
        result: dict[str, Any] = {}
        for expr, watch in watches.items():
            if hasattr(watch, "error") and watch.error:
                continue
            result[expr] = {
                "value": watch.value if hasattr(watch, "value") else watch.get("value"),
                "type": watch.type if hasattr(watch, "type") else watch.get("type"),
                "changed": watch.changed if hasattr(watch, "changed") else watch.get("changed"),
            }
        return result

    def _format_stack(self, frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format stack frames."""
        return [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "file": f.get("file"),
                "line": f.get("line"),
                "locals": self._summarize_locals(f.get("locals", {})),
            }
            for f in frames[: self.max_items]
        ]

    def _summarize_locals(self, locals_dict: dict[str, Any]) -> dict[str, Any]:
        """Summarize locals for stack view."""
        if len(locals_dict) > 10:
            items = list(locals_dict.items())[:10]
            summary = dict(items)
            summary["..."] = f"{len(locals_dict) - 10} more"
            return summary
        return locals_dict
