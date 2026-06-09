"""Help and usage command for CC-Debugger."""

import sys
import click

# Detailed usage guide shown when running `cc-debug help` without arguments
DETAILED_HELP = """=========================================
 CC-Debugger - Command Line Interface Help
=========================================

CC-Debugger is a Python debugger CLI optimized for coding agents.
All commands output structured JSON for programmatic interaction.

Quick Start:
  1. Start debugging a script (automatically pauses on line 1):
     $ cc-debug start my_script.py --uv
  2. Set a breakpoint:
     $ cc-debug bp set my_script.py:10
  3. Resume execution:
     $ cc-debug continue
  4. Inspect local variables and stack:
     $ cc-debug vars
     $ cc-debug stack
  5. Quit the session when finished:
     $ cc-debug quit

For server/long-running scripts (e.g. FastAPI/Flask), use:
  $ cc-debug start server.py --uv --no-stop

Command Reference:
-----------------

--- Session Commands ---
  start FILE [OPTIONS]      Start a new debugging session.
      --args TEXT           Arguments to pass to the target script.
      --no-stop             Don't pause on entry (useful for web servers).
      --python PATH         Specify Python interpreter (e.g., .venv/bin/python).
      --uv                  Auto-detect venv and install debugpy.
  quit                      End the current debugging session and clean up.
  status                    Show the current debug session status.
  restart [OPTIONS]         Restart session with same or new arguments.
      --args TEXT           New arguments to pass.
  pm TRACEBACK_FILE         Post-mortem debugging from traceback.

--- Execution Control ---
  continue [OPTIONS]        Resume execution until next breakpoint.
      -c, --compact         Compact output (reduces tokens).
  next [OPTIONS]            Step over to the next line.
      -c, --compact         Compact output.
  step [OPTIONS]            Step into the function call.
      -c, --compact         Compact output.
  stepout [OPTIONS]         Step out of current function.
      -c, --compact         Compact output.
  pause                     Pause target execution if running.
  run-to-cursor LOCATION    Run to file:line (temporary breakpoint).
  until LINE                Run until line in current file.

--- Breakpoints (bp) ---
  bp set LOCATION [OPTIONS] Set breakpoint at file:line.
      -c, --condition TEXT  Condition expression (e.g., 'x > 5').
      --log TEXT            Log expression without stopping (e.g., 'x={x}').
      --hit INTEGER         Break after N hits.
  bp exception [OPTIONS]    Break on exceptions.
      --raised/--no-raised  Break on raised exceptions (default: True).
      --uncaught/--no-uncaught Break on uncaught exceptions (default: True).
  bp func NAME              Set breakpoint on function entry.
  bp watch EXPR             Set watchpoint on attribute (e.g., 'obj.attr').
  bp list                   List all breakpoints.
  bp del ID                 Delete breakpoint by ID.
  bp clear                  Clear all breakpoints.

--- Inspection ---
  vars [OPTIONS]            Show variables in current scope.
      --all                 Show all scopes.
      --depth INTEGER       Recursive expansion depth (default: 0).
      --names-only          List variable names only (reduces tokens).
      --changed             Show only changed variables.
      --limit INTEGER       Limit to N most interesting variables.
      --no-truncate         Disable auto-truncation of large values.
  eval EXPRESSION           Evaluate expression in current context.
  set ASSIGNMENT            Modify variable (e.g., 'x = 42').
  stack [OPTIONS]           Show call stack.
      --depth INTEGER       Max frames to show.
  up / down                 Move frame context up (caller) or down (callee).
  source [LOCATION] [OPTIONS] Show source code around current line/location.
      -n, --context INT     Lines of context (default: 5).
  output [OPTIONS]          Show stdout/stderr.
      --clear               Clear buffer after reading.
      -f, --follow          Stream continuously.
  why                       Explain why execution stopped (one-line summary).
  inspect                   Batch command: get location + vars + stack.
  snapshot                  Full state dump for context recovery.
  summary                   One-line state summary.

--- Watch Expressions ---
  watch add EXPR            Add watch expression.
  watch list                Show watch expressions with current values.
  watch diff                Show only changed watch expressions.
  watch del EXPR            Remove watch expression.
  watch clear               Clear all watches.

--- Recording & Time-Travel ---
  record start [OPTIONS]    Start recording execution checkpoints.
      --auto-interval INT   Auto-checkpoint every N steps.
  record checkpoint         Create manual checkpoint.
  record stop               Stop recording checkpoints.
  record list               List checkpoints.
  record export FILE        Export recording to file.
  step-back                 Go to previous checkpoint.
  step-forward              Go to next checkpoint.
  goto CHECKPOINT_ID        Jump to specific checkpoint.

--- Execution Tracing ---
  trace start [OPTIONS]     Start execution tracing.
      --max INT             Max trace entries.
      --filter TEXT         Filter files by string.
  trace get [OPTIONS]       Get recorded trace entries.
      --limit INT           Max entries to retrieve.
  trace stop                Stop execution tracing.

To view full details for a specific command, use:
  $ cc-debug help <command> (e.g., cc-debug help start)
"""


@click.command("help")
@click.argument("command_path", required=False, nargs=-1)
@click.pass_context
def help_cmd(ctx: click.Context, command_path: tuple[str, ...]) -> None:
    """Show detailed usage guide and commands reference."""
    # Find the main group
    main_group = ctx.parent.command if ctx.parent else None
    if not main_group:
        # Fallback if no parent context
        from cc_debugger.cli import main as main_group

    if not command_path:
        click.echo(DETAILED_HELP)
        return

    current = main_group
    current_ctx = ctx.parent if ctx.parent else click.Context(main_group)
    
    for name in command_path:
        if isinstance(current, click.Group) and name in current.commands:
            current = current.commands[name]
            current_ctx = click.Context(current, info_name=name, parent=current_ctx)
        else:
            click.echo(f"Error: Command '{' '.join(command_path)}' not found.", err=True)
            sys.exit(1)

    click.echo(current.get_help(current_ctx))
