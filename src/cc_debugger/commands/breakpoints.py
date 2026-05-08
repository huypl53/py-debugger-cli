"""Breakpoint management commands."""

from pathlib import Path

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json

# Track breakpoints locally (daemon doesn't persist them across restarts)
_breakpoints: dict[str, list[dict]] = {}


@click.group()
def bp() -> None:
    """Manage breakpoints."""
    pass


@bp.command("set")
@click.argument("location")
@click.option("-c", "--condition", help="Breakpoint condition")
@click.option("--log", "log_message", help="Log expression without stopping (e.g., 'x={x}')")
@click.option("--hit", "hit_count", type=int, help="Break after N hits")
def bp_set(location: str, condition: str | None, log_message: str | None, hit_count: int | None) -> None:
    """Set a breakpoint at file:line."""
    try:
        if ":" not in location:
            output_json(format_error("bp set", "INVALID_LOCATION",
                "Location must be file:line format (e.g., myfile.py:42)"))
            raise SystemExit(1) from None

        file, line_str = location.rsplit(":", 1)
        file = str(Path(file).resolve())
        line = int(line_str)

        if file not in _breakpoints:
            _breakpoints[file] = []

        bp_entry: dict = {"line": line}
        if condition:
            bp_entry["condition"] = condition
        if log_message:
            bp_entry["logMessage"] = log_message
        if hit_count:
            bp_entry["hitCondition"] = str(hit_count)

        _breakpoints[file].append(bp_entry)

        result = _send_to_daemon({
            "action": "bp",
            "file": file,
            "breakpoints": _breakpoints[file],
        })

        if not result.get("success"):
            _breakpoints[file].pop()
            raise RuntimeError(result.get("error"))

        bp_type = "log" if log_message else "breakpoint"

        output_json(format_success("bp set", {
            "id": len(_breakpoints[file]) - 1,
            "file": file,
            "line": line,
            "condition": condition,
            "logMessage": log_message,
            "hitCondition": str(hit_count) if hit_count else None,
            "type": bp_type,
            "verified": True,
        }))

    except Exception as e:
        output_json(format_error("bp set", "BREAKPOINT_ERROR", str(e)))
        raise SystemExit(1) from None


@bp.command("list")
def bp_list() -> None:
    """List all breakpoints."""
    try:
        all_bps = []
        idx = 0
        for file, bps in _breakpoints.items():
            for bp_entry in bps:
                bp_info: dict = {
                    "id": idx,
                    "file": file,
                    "line": bp_entry["line"],
                    "condition": bp_entry.get("condition"),
                }
                if bp_entry.get("logMessage"):
                    bp_info["logMessage"] = bp_entry["logMessage"]
                    bp_info["type"] = "log"
                if bp_entry.get("hitCondition"):
                    bp_info["hitCondition"] = bp_entry["hitCondition"]
                all_bps.append(bp_info)
                idx += 1

        output_json(format_success("bp list", {"breakpoints": all_bps}))

    except Exception as e:
        output_json(format_error("bp list", "LIST_FAILED", str(e)))
        raise SystemExit(1) from None


@bp.command("del")
@click.argument("bp_id", type=int)
def bp_del(bp_id: int) -> None:
    """Delete a breakpoint by ID."""
    try:
        idx = 0
        for file, bps in list(_breakpoints.items()):
            for i, _bp_entry in enumerate(bps):
                if idx == bp_id:
                    removed = bps.pop(i)
                    _send_to_daemon({
                        "action": "bp",
                        "file": file,
                        "breakpoints": bps,
                    })
                    output_json(format_success("bp del", {
                        "removed": {"id": bp_id, "file": file, "line": removed["line"]}
                    }))
                    return
                idx += 1

        raise ValueError(f"Breakpoint {bp_id} not found")

    except Exception as e:
        output_json(format_error("bp del", "DELETE_FAILED", str(e)))
        raise SystemExit(1) from None


@bp.command("clear")
def bp_clear() -> None:
    """Clear all breakpoints."""
    try:
        count = sum(len(bps) for bps in _breakpoints.values())

        for file in list(_breakpoints.keys()):
            _send_to_daemon({
                "action": "bp",
                "file": file,
                "breakpoints": [],
            })

        _breakpoints.clear()

        output_json(format_success("bp clear", {"removed": count}))

    except Exception as e:
        output_json(format_error("bp clear", "CLEAR_FAILED", str(e)))
        raise SystemExit(1) from None


@bp.command("exception")
@click.option("--raised/--no-raised", default=True, help="Break on raised exceptions")
@click.option("--uncaught/--no-uncaught", default=True, help="Break on uncaught exceptions")
def bp_exception(raised: bool, uncaught: bool) -> None:
    """Break when exception is raised."""
    try:
        result = _send_to_daemon({
            "action": "bp_exception",
            "raised": raised,
            "uncaught": uncaught,
        })
        if result.get("success"):
            output_json(format_success("bp exception", {
                "filters": result.get("filters", []),
            }))
        else:
            output_json(format_error("bp exception", "EXCEPTION_BP_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("bp exception", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@bp.command("watch")
@click.argument("expression")
def bp_watch(expression: str) -> None:
    """Watch expression for changes (polls on each step)."""
    try:
        result = _send_to_daemon({"action": "watch_add", "expression": expression})
        if result.get("success"):
            output_json(format_success("bp watch", {
                "expression": expression,
                "note": "Uses watch system (evaluated on each step)",
            }))
        else:
            output_json(format_error("bp watch", "WATCH_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("bp watch", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@bp.command("func")
@click.argument("name")
def bp_func(name: str) -> None:
    """Break on function entry by name."""
    try:
        result = _send_to_daemon({
            "action": "bp_func",
            "names": [name],
        })
        if result.get("success"):
            bps = result.get("breakpoints", [])
            if bps:
                bp_info = bps[0]
                output_json(format_success("bp func", {
                    "name": name,
                    "verified": bp_info.get("verified", False),
                    "message": bp_info.get("message", ""),
                }))
            else:
                output_json(format_success("bp func", {"name": name, "verified": False}))
        else:
            output_json(format_error("bp func", "FUNC_BP_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("bp func", "NO_SESSION", str(e)))
        raise SystemExit(1) from None
