"""CC-Debugger CLI entry point."""

import click

from cc_debugger.commands.breakpoints import bp
from cc_debugger.commands.control import continue_cmd, next_cmd, pause, step, stepout
from cc_debugger.commands.inspect import eval_cmd, stack, vars_cmd
from cc_debugger.commands.record import record
from cc_debugger.commands.session import quit_cmd, start, status
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

# Execution control
main.add_command(continue_cmd)
main.add_command(next_cmd)
main.add_command(step)
main.add_command(stepout)
main.add_command(pause)

# Breakpoints
main.add_command(bp)

# Inspection
main.add_command(stack)
main.add_command(vars_cmd, name="vars")
main.add_command(eval_cmd, name="eval")

# Watch expressions
main.add_command(watch)

# Recording
main.add_command(record)

# Time-travel
main.add_command(step_back)
main.add_command(step_forward)
main.add_command(goto)


if __name__ == "__main__":
    main()
