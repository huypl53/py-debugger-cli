"""Trace commands for execution logging."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


@click.group()
def trace() -> None:
    """Execution tracing commands."""
    pass


@trace.command("start")
@click.option("--max", "max_entries", default=1000, help="Max trace entries to record")
@click.option("--filter", "filter_pattern", default="", help="Only trace files containing this string")
def trace_start(max_entries: int, filter_pattern: str) -> None:
    """Start execution tracing (injects sys.settrace)."""
    try:
        result = _send_to_daemon({
            "action": "trace_start",
            "max_entries": max_entries,
            "filter": filter_pattern,
        })

        if not result.get("success"):
            error_code = result.get("error", "TRACE_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("trace start", error_code, message))
            raise SystemExit(1)

        output_json(format_success("trace start", {
            "trace_active": True,
            "max_entries": result.get("max_entries"),
            "filter": result.get("filter"),
        }))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("trace start", "TRACE_FAILED", str(e)))
        raise SystemExit(1) from None


@trace.command("stop")
def trace_stop() -> None:
    """Stop execution tracing."""
    try:
        result = _send_to_daemon({"action": "trace_stop"})

        if not result.get("success"):
            error_code = result.get("error", "TRACE_STOP_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("trace stop", error_code, message))
            raise SystemExit(1)

        output_json(format_success("trace stop", {"trace_active": False}))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("trace stop", "TRACE_STOP_FAILED", str(e)))
        raise SystemExit(1) from None


@trace.command("get")
@click.option("--limit", default=100, help="Max entries to retrieve")
def trace_get(limit: int) -> None:
    """Get recorded trace entries."""
    try:
        result = _send_to_daemon({"action": "trace_get", "limit": limit})

        if not result.get("success"):
            error_code = result.get("error", "TRACE_GET_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("trace get", error_code, message))
            raise SystemExit(1)

        output_json(format_success("trace get", {
            "trace": result.get("trace", []),
            "count": result.get("count", 0),
            "trace_active": result.get("trace_active", False),
        }))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("trace get", "TRACE_GET_FAILED", str(e)))
        raise SystemExit(1) from None
