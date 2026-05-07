"""Inspection commands."""


import click

from cc_debugger.commands.session import _send_to_daemon
from cc_debugger.output import format_error, format_success, output_json


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
@click.option("--depth", default=3, help="Max nested depth")
def vars_cmd(show_all: bool, depth: int) -> None:
    """Show variables in current scope."""
    try:
        result = _send_to_daemon({"action": "vars"})

        if not result.get("success"):
            raise RuntimeError(result.get("error"))

        output_json(format_success("vars", {"Locals": result.get("variables", {})}))

    except Exception as e:
        output_json(format_error("vars", "VARS_FAILED", str(e)))
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
