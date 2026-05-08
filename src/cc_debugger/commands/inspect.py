"""Inspection commands."""


import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json, print_program_output


@click.command()
@click.option("--context", "-n", default=5, help="Lines before/after current line")
@click.argument("location", required=False)
def source(context: int, location: str | None) -> None:
    """Show source code around current location."""
    try:
        cmd: dict = {"action": "source", "context": context}
        if location:
            if ":" in location:
                file, line = location.rsplit(":", 1)
                cmd["file"] = file
                cmd["line"] = int(line)
            else:
                cmd["file"] = location

        result = _send_to_daemon(cmd)

        if not result.get("success"):
            raise RuntimeError(result.get("error", result.get("message", "Unknown error")))

        output_json(format_success("source", {
            "file": result.get("file"),
            "current_line": result.get("current_line"),
            "lines": result.get("lines", []),
        }))

    except Exception as e:
        output_json(format_error("source", "SOURCE_FAILED", str(e)))
        raise SystemExit(1) from None


# Alias for source
@click.command("list")
@click.option("--context", "-n", default=5, help="Lines before/after current line")
@click.argument("location", required=False)
def list_cmd(context: int, location: str | None) -> None:
    """Alias for source command."""
    source.main([f"--context={context}"] + ([location] if location else []), standalone_mode=False)


@click.command()
def up() -> None:
    """Move up one stack frame (to caller)."""
    try:
        result = _send_to_daemon({"action": "frame_up"})

        if not result.get("success"):
            error_code = result.get("error", "FRAME_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("up", error_code, message))
            raise SystemExit(1)

        output_json(format_success("up", {
            "frame_index": result.get("frame_index"),
            "frame": result.get("frame"),
            "source_context": result.get("source_context", []),
        }))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("up", "FRAME_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def down() -> None:
    """Move down one stack frame (to callee)."""
    try:
        result = _send_to_daemon({"action": "frame_down"})

        if not result.get("success"):
            error_code = result.get("error", "FRAME_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("down", error_code, message))
            raise SystemExit(1)

        output_json(format_success("down", {
            "frame_index": result.get("frame_index"),
            "frame": result.get("frame"),
            "source_context": result.get("source_context", []),
        }))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("down", "FRAME_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("set")
@click.argument("assignment")
def set_cmd(assignment: str) -> None:
    """Set a variable value (e.g., 'x = 42' or 'x=42')."""
    try:
        if "=" not in assignment:
            raise ValueError("Assignment must contain '=' (e.g., 'x = 42')")

        parts = assignment.split("=", 1)
        name = parts[0].strip()
        value = parts[1].strip()

        result = _send_to_daemon({"action": "setvar", "name": name, "value": value})

        if not result.get("success"):
            error_code = result.get("error", "SET_FAILED")
            message = result.get("message", str(result.get("error", "Unknown error")))
            output_json(format_error("set", error_code, message))
            raise SystemExit(1)

        output_json(format_success("set", {
            "variable": result.get("variable"),
            "expression": result.get("expression"),
            "new_value": result.get("new_value"),
            "new_type": result.get("new_type"),
        }))

    except SystemExit:
        raise
    except Exception as e:
        output_json(format_error("set", "SET_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
@click.option("--depth", default=10, help="Max frames to show")
def stack(depth: int) -> None:
    """Show call stack with locals."""
    try:
        result = _send_to_daemon({"action": "stack", "levels": depth})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        frames = []
        for f in result.get("frames", []):
            frames.append({
                "id": f.get("id"),
                "name": f.get("name"),
                "file": f.get("source", {}).get("path"),
                "line": f.get("line"),
            })

        output_json(format_success("stack", {"frames": frames}))

    except Exception as e:
        output_json(format_error("stack", "STACK_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("vars")
@click.option("--all", "show_all", is_flag=True, help="Show all scopes")
@click.option("--depth", default=0, help="Recursive expansion depth (0=no expansion)")
def vars_cmd(show_all: bool, depth: int) -> None:
    """Show variables in current scope."""
    try:
        result = _send_to_daemon({"action": "vars", "depth": depth})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        data = {"Locals": result.get("variables", {})}
        if result.get("frame_index", 0) > 0:
            data["frame_index"] = result["frame_index"]

        output_json(format_success("vars", data))

    except Exception as e:
        output_json(format_error("vars", "VARS_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
@click.option("--clear", is_flag=True, help="Clear output buffer after reading")
def output(clear: bool) -> None:
    """Show program stdout/stderr output."""
    try:
        result = _send_to_daemon({"action": "output", "clear": clear})

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Unknown error"))

        lines = result.get("lines", [])
        # Print to stderr for user visibility
        if lines:
            print_program_output(lines)

        output_json(format_success("output", {
            "lines": lines,
            "count": result.get("count", 0),
        }))

    except Exception as e:
        output_json(format_error("output", "OUTPUT_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("eval")
@click.argument("expression")
def eval_cmd(expression: str) -> None:
    """Evaluate an expression in current context."""
    try:
        result = _send_to_daemon({"action": "eval", "expression": expression})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        output_json(format_success("eval", {
            "expression": expression,
            "value": result.get("value"),
            "type": result.get("type"),
        }))

    except Exception as e:
        output_json(format_error("eval", "EVAL_FAILED", str(e)))
        raise SystemExit(1) from None
