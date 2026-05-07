"""Watch expression commands."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


@click.group()
def watch() -> None:
    """Manage watch expressions."""
    pass


@watch.command("add")
@click.argument("expression")
def watch_add(expression: str) -> None:
    """Add a watch expression."""
    try:
        result = _send_to_daemon({"action": "watch_add", "expression": expression})
        if result.get("success"):
            output_json(format_success("watch add", {
                "expression": expression,
                "count": result.get("count"),
            }))
        else:
            output_json(format_error("watch add", "WATCH_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("watch add", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@watch.command("list")
def watch_list() -> None:
    """List all watch expressions with current values."""
    try:
        result = _send_to_daemon({"action": "watch_list"})
        if result.get("success"):
            output_json(format_success("watch list", {
                "watches": result.get("watches", []),
                "values": result.get("values", {}),
            }))
        else:
            output_json(format_error("watch list", "WATCH_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("watch list", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@watch.command("del")
@click.argument("expression")
def watch_del(expression: str) -> None:
    """Remove a watch expression."""
    try:
        result = _send_to_daemon({"action": "watch_del", "expression": expression})
        if result.get("success"):
            output_json(format_success("watch del", {
                "removed": result.get("removed"),
            }))
        else:
            output_json(format_error("watch del", "WATCH_NOT_FOUND", result.get("error", "Watch not found")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("watch del", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@watch.command("clear")
def watch_clear() -> None:
    """Clear all watch expressions."""
    try:
        result = _send_to_daemon({"action": "watch_clear"})
        if result.get("success"):
            output_json(format_success("watch clear", {
                "removed": result.get("removed"),
            }))
        else:
            output_json(format_error("watch clear", "WATCH_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("watch clear", "NO_SESSION", str(e)))
        raise SystemExit(1) from None
