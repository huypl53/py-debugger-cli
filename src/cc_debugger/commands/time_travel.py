"""Time-travel debugging commands."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


@click.command("step-back")
def step_back() -> None:
    """Step backward to previous checkpoint."""
    try:
        result = _send_to_daemon({"action": "step_back"})
        if result.get("success"):
            cp = result.get("checkpoint", {})
            output_json(format_success("step-back", {
                "checkpoint": {
                    "id": cp.get("id"),
                    "sequence": cp.get("sequence"),
                    "reason": cp.get("reason"),
                    "location": cp.get("location"),
                    "variables": cp.get("variables", {}),
                    "watches": cp.get("watches", {}),
                },
            }))
        else:
            output_json(format_error("step-back", "NO_CHECKPOINT", result.get("error", "At oldest checkpoint")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("step-back", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@click.command("step-forward")
def step_forward() -> None:
    """Step forward to next checkpoint."""
    try:
        result = _send_to_daemon({"action": "step_forward"})
        if result.get("success"):
            cp = result.get("checkpoint", {})
            output_json(format_success("step-forward", {
                "checkpoint": {
                    "id": cp.get("id"),
                    "sequence": cp.get("sequence"),
                    "reason": cp.get("reason"),
                    "location": cp.get("location"),
                    "variables": cp.get("variables", {}),
                    "watches": cp.get("watches", {}),
                },
            }))
        else:
            output_json(format_error("step-forward", "NO_CHECKPOINT", result.get("error", "At newest checkpoint")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("step-forward", "NO_SESSION", str(e)))
        raise SystemExit(1) from None


@click.command()
@click.argument("checkpoint_id")
def goto(checkpoint_id: str) -> None:
    """Jump to specific checkpoint."""
    try:
        result = _send_to_daemon({"action": "goto", "checkpoint_id": checkpoint_id})
        if result.get("success"):
            cp = result.get("checkpoint", {})
            output_json(format_success("goto", {
                "checkpoint": {
                    "id": cp.get("id"),
                    "sequence": cp.get("sequence"),
                    "reason": cp.get("reason"),
                    "location": cp.get("location"),
                    "variables": cp.get("variables", {}),
                    "watches": cp.get("watches", {}),
                },
            }))
        else:
            output_json(format_error("goto", "NOT_FOUND", result.get("error", "Checkpoint not found")))
            raise SystemExit(1) from None
    except RuntimeError as e:
        output_json(format_error("goto", "NO_SESSION", str(e)))
        raise SystemExit(1) from None
