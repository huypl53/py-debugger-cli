"""Execution control commands."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


@click.command("continue")
def continue_cmd() -> None:
    """Continue execution until next breakpoint."""
    try:
        result = _send_to_daemon({"action": "continue"}, timeout=None)

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]

        output_json(format_success("continue", data))

    except Exception as e:
        output_json(format_error("continue", "CONTINUE_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("next")
def next_cmd() -> None:
    """Step over to next line."""
    try:
        result = _send_to_daemon({"action": "next"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]

        output_json(format_success("next", data))

    except Exception as e:
        output_json(format_error("next", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def step() -> None:
    """Step into function call."""
    try:
        result = _send_to_daemon({"action": "step"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]

        output_json(format_success("step", data))

    except Exception as e:
        output_json(format_error("step", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def stepout() -> None:
    """Step out of current function."""
    try:
        result = _send_to_daemon({"action": "stepout"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]

        output_json(format_success("stepout", data))

    except Exception as e:
        output_json(format_error("stepout", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def pause() -> None:
    """Pause execution."""
    output_json(format_error("pause", "NOT_IMPLEMENTED", "Pause not yet implemented"))
    raise SystemExit(1) from None
