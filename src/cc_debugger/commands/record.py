"""Recording commands."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


@click.group()
def record() -> None:
    """Recording and time-travel commands."""
    pass


@record.command("start")
@click.option("--auto-interval", default=0, help="Auto-checkpoint every N steps")
def record_start(auto_interval: int) -> None:
    """Start recording execution."""
    try:
        result = _send_to_daemon({"action": "record_start", "auto_interval": auto_interval})
        if result.get("success"):
            output_json(format_success("record start", {
                "recording": True,
                "autoInterval": result.get("auto_interval", 0),
            }))
        else:
            output_json(format_error("record start", "RECORD_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("record start", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@record.command("stop")
def record_stop() -> None:
    """Stop recording."""
    try:
        result = _send_to_daemon({"action": "record_stop"})
        if result.get("success"):
            output_json(format_success("record stop", {
                "recording": False,
                "checkpointCount": result.get("checkpoint_count", 0),
            }))
        else:
            output_json(format_error("record stop", "RECORD_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("record stop", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@record.command("checkpoint")
@click.option("--reason", default="manual")
def record_checkpoint(reason: str) -> None:
    """Create manual checkpoint."""
    try:
        result = _send_to_daemon({"action": "record_checkpoint", "reason": reason})
        if result.get("success"):
            cp = result.get("checkpoint", {})
            output_json(format_success("record checkpoint", {
                "id": cp.get("id"),
                "sequence": cp.get("sequence"),
                "reason": cp.get("reason"),
                "location": cp.get("location"),
            }))
        else:
            output_json(format_error("record checkpoint", "CHECKPOINT_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("record checkpoint", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@record.command("list")
def record_list() -> None:
    """List all checkpoints."""
    try:
        result = _send_to_daemon({"action": "record_list"})
        if result.get("success"):
            output_json(format_success("record list", {
                "recording": result.get("recording", False),
                "checkpoints": result.get("checkpoints", []),
            }))
        else:
            output_json(format_error("record list", "LIST_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("record list", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@record.command("export")
@click.argument("output_file", type=click.Path())
def record_export(output_file: str) -> None:
    """Export recording to file."""
    try:
        from pathlib import Path
        output_path = str(Path(output_file).resolve())
        result = _send_to_daemon({"action": "record_export", "output_file": output_path})
        if result.get("success"):
            output_json(format_success("record export", {
                "file": result.get("file"),
                "checkpointCount": result.get("checkpoint_count", 0),
            }))
        else:
            output_json(format_error("record export", "EXPORT_FAILED", result.get("error", "Unknown error")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("record export", "NO_SESSION", str(e)))
        raise SystemExit(1) from None
