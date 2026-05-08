"""Execution control commands."""

import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json, print_program_output


def _format_step_result(result: dict, compact: bool = False) -> dict:
    """Format step/continue result, optionally in compact mode."""
    # Print program output to stderr for user visibility
    if result.get("output"):
        print_program_output(result["output"])

    if compact:
        # Compact mode: minimal output for reduced tokens
        loc = result.get("location", {})
        return {
            "location": f"{loc.get('file', '?')}:{loc.get('line', '?')}",
            "function": loc.get("function", "?"),
            "reason": result.get("reason"),
        }

    # Full mode: include all details
    data = {
        "event": "stopped",
        "reason": result.get("reason"),
        "location": result.get("location"),
        "source_context": result.get("source_context", []),
    }
    if result.get("changedVars"):
        data["changedVars"] = result["changedVars"]
    if result.get("watches"):
        data["watches"] = result["watches"]
    if result.get("output"):
        data["output"] = result["output"]
    return data


@click.command("continue")
@click.option("--compact", "-c", is_flag=True, help="Minimal output (reduces tokens)")
def continue_cmd(compact: bool) -> None:
    """Continue execution until next breakpoint."""
    try:
        result = _send_to_daemon({"action": "continue"}, timeout=None)

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = _format_step_result(result, compact)
        output_json(format_success("continue", data))

    except Exception as e:
        output_json(format_error("continue", "CONTINUE_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("next")
@click.option("--compact", "-c", is_flag=True, help="Minimal output (reduces tokens)")
def next_cmd(compact: bool) -> None:
    """Step over to next line."""
    try:
        result = _send_to_daemon({"action": "next"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = _format_step_result(result, compact)
        output_json(format_success("next", data))

    except Exception as e:
        output_json(format_error("next", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
@click.option("--compact", "-c", is_flag=True, help="Minimal output (reduces tokens)")
def step(compact: bool) -> None:
    """Step into function call."""
    try:
        result = _send_to_daemon({"action": "step"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = _format_step_result(result, compact)
        output_json(format_success("step", data))

    except Exception as e:
        output_json(format_error("step", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
@click.option("--compact", "-c", is_flag=True, help="Minimal output (reduces tokens)")
def stepout(compact: bool) -> None:
    """Step out of current function."""
    try:
        result = _send_to_daemon({"action": "stepout"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = _format_step_result(result, compact)
        output_json(format_success("stepout", data))

    except Exception as e:
        output_json(format_error("stepout", "STEP_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def pause() -> None:
    """Pause execution."""
    output_json(format_error("pause", "NOT_IMPLEMENTED", "Pause not yet implemented"))
    raise SystemExit(1) from None


@click.command()
@click.argument("line", type=int)
def until(line: int) -> None:
    """Run until a specific line in the current file."""
    try:
        result = _send_to_daemon({
            "action": "until",
            "line": line,
        }, timeout=None)

        if not result.get("success"):
            error_code = result.get("error", "UNTIL_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("until", error_code, message))
            raise SystemExit(1)

        # Print program output to stderr for user visibility
        if result.get("output"):
            print_program_output(result["output"])

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
            "source_context": result.get("source_context", []),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]
        if result.get("output"):
            data["output"] = result["output"]

        output_json(format_success("until", data))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("until", "UNTIL_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("run-to-cursor")
@click.argument("location")
def run_to_cursor(location: str) -> None:
    """Run to a specific line without setting permanent breakpoint."""
    try:
        if ":" not in location:
            raise ValueError("Location must be file:line (e.g., 'app.py:42')")

        file, line = location.rsplit(":", 1)
        result = _send_to_daemon({
            "action": "run_to_cursor",
            "file": file,
            "line": int(line),
        }, timeout=None)

        if not result.get("success"):
            error_code = result.get("error", "RUN_TO_CURSOR_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("run-to-cursor", error_code, message))
            raise SystemExit(1)

        # Print program output to stderr for user visibility
        if result.get("output"):
            print_program_output(result["output"])

        data = {
            "event": "stopped",
            "reason": result.get("reason"),
            "location": result.get("location"),
            "source_context": result.get("source_context", []),
            "temp_bp_removed": result.get("temp_bp_removed", True),
        }
        if result.get("changedVars"):
            data["changedVars"] = result["changedVars"]
        if result.get("watches"):
            data["watches"] = result["watches"]
        if result.get("output"):
            data["output"] = result["output"]

        output_json(format_success("run-to-cursor", data))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("run-to-cursor", "RUN_TO_CURSOR_FAILED", str(e)))
        raise SystemExit(1) from None
