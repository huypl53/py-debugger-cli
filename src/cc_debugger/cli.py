"""CC-Debugger CLI entry point."""

import click

from cc_debugger.commands.breakpoints import bp
from cc_debugger.commands.control import continue_cmd, next_cmd, pause, run_to_cursor, step, stepout, until
from cc_debugger.commands.inspect import down, eval_cmd, list_cmd, output, set_cmd, source, stack, up, vars_cmd
from cc_debugger.commands.record import record
from cc_debugger.commands.session import pm, quit_cmd, restart, start, status
from cc_debugger.commands.trace import trace
from cc_debugger.commands.time_travel import goto, step_back, step_forward
from cc_debugger.commands.watch import watch


@click.group()
@click.version_option(package_name="cc-debugger")
def main() -> None:
    """CC-Debugger: Python debugger CLI for coding agents.

    Start debugging with 'cc-debug start <file>' and use the various
    commands to control execution, set breakpoints, and inspect state.

    All commands output JSON for easy parsing by coding agents.
    """
    pass


# Session commands
main.add_command(start)
main.add_command(quit_cmd)
main.add_command(status)
main.add_command(restart)

# Execution control
main.add_command(continue_cmd)
main.add_command(next_cmd)
main.add_command(step)
main.add_command(stepout)
main.add_command(pause)
main.add_command(run_to_cursor)
main.add_command(until)

# Breakpoints
main.add_command(bp)

# Inspection
main.add_command(stack)
main.add_command(vars_cmd, name="vars")
main.add_command(eval_cmd, name="eval")
main.add_command(source)
main.add_command(list_cmd, name="list")
main.add_command(up)
main.add_command(down)
main.add_command(set_cmd, name="set")
main.add_command(output)

# Watch expressions
main.add_command(watch)

# Recording
main.add_command(record)

# Time-travel
main.add_command(step_back)
main.add_command(step_forward)
main.add_command(goto)

# Tracing
main.add_command(trace)

# Post-mortem
main.add_command(pm)


if __name__ == "__main__":
    main()
