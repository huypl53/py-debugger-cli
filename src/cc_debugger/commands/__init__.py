"""CLI commands for CC-Debugger."""

from cc_debugger.commands.breakpoints import bp
from cc_debugger.commands.control import continue_cmd, next_cmd, pause, step, stepout
from cc_debugger.commands.inspect import eval_cmd, stack, vars_cmd
from cc_debugger.commands.record import record
from cc_debugger.commands.session import quit_cmd, start, status
from cc_debugger.commands.time_travel import goto, step_back, step_forward
from cc_debugger.commands.watch import watch

__all__ = [
    "start",
    "quit_cmd",
    "status",
    "continue_cmd",
    "next_cmd",
    "step",
    "stepout",
    "pause",
    "bp",
    "stack",
    "vars_cmd",
    "eval_cmd",
    "watch",
    "record",
    "step_back",
    "step_forward",
    "goto",
]
