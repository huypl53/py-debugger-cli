---
name: cc-debug
description: Debug Python programs with cc-debug CLI. Use when debugging runtime errors, stepping through code, setting breakpoints, inspecting variables, tracking value changes, or time-travel debugging. All output is JSON.
---

# CC-Debug: Python Debugger for Coding Agents

## Prerequisites

Install cc-debug CLI globally:

```bash
# Recommended: pipx (isolated, auto-adds to PATH)
pipx install git+https://github.com/huypl53/py-debugger-cli.git

# Alternative: uv tool
uv tool install git+https://github.com/huypl53/py-debugger-cli.git

# Verify installation
cc-debug --version
```

If `cc-debug` is not available, fall back to Python's built-in `pdb` or `breakpoint()`.

Debug Python programs interactively using the `cc-debug` CLI. All output is JSON for easy parsing.

## When to Use

Use this skill when:
- Debugging Python runtime errors, exceptions, or unexpected behavior
- Stepping through code to understand execution flow
- Inspecting variable values at specific points
- Setting breakpoints to pause at interesting locations
- Tracking how variables change over time
- Using time-travel debugging to revisit previous states

## Quick Start

```bash
# Start debugging
cc-debug start script.py

# Set breakpoint and continue
cc-debug bp set script.py:42
cc-debug continue

# Step through code
cc-debug next          # step over
cc-debug step          # step into
cc-debug stepout       # step out of function

# Inspect state
cc-debug vars          # show local variables
cc-debug eval "expr"   # evaluate expression
cc-debug stack         # show call stack

# End session
cc-debug quit
```

## Workflow

### 1. Start Session
```bash
cc-debug start <file.py> [--args "arg1 arg2"] [--no-stop]
```
- Launches debugpy daemon, pauses at first line by default
- Use `--no-stop` to run until first breakpoint

### 2. Set Breakpoints
```bash
cc-debug bp set <file>:<line> [-c "condition"]
cc-debug bp list
cc-debug bp del <id>
cc-debug bp func <function_name>
cc-debug bp exception [--raised/--no-raised] [--uncaught/--no-uncaught]
```

### 3. Control Execution
| Command | Action |
|---------|--------|
| `cc-debug continue` | Run until next breakpoint |
| `cc-debug next` | Step over (same level) |
| `cc-debug step` | Step into function |
| `cc-debug stepout` | Step out to caller |

### 4. Inspect State
```bash
cc-debug vars [--all] [--depth N]    # show variables
cc-debug eval "<expression>"          # evaluate in context
cc-debug stack [--depth N]            # show call stack
```

### 5. Watch Expressions
```bash
cc-debug watch add "x + y"    # track expression
cc-debug watch list           # show all with values
cc-debug watch del "x + y"    # remove watch
```
Watches auto-evaluate on each step, showing `changed: true` when values differ.

### 6. Time-Travel Debugging (Recording)
```bash
cc-debug record start [--auto-interval N]  # start recording
cc-debug record checkpoint --reason "msg"  # manual checkpoint
cc-debug record list                       # list checkpoints
cc-debug step-back                         # go to previous checkpoint
cc-debug step-forward                      # go to next checkpoint
cc-debug goto <checkpoint_id>              # jump to specific checkpoint
cc-debug record stop                       # stop recording
cc-debug record export output.json         # save recording
```

## JSON Output Format

All commands return JSON with `success` field:
```json
{"success": true, "command": "next", "data": {"event": "stopped", "location": {...}}}
{"success": false, "command": "eval", "error": {"code": "EVAL_FAILED", "message": "..."}}
```

Step commands include `changedVars` showing what changed since last stop.

## Debugging Strategy

1. **Reproduce first**: Run once without debugger to get error location
2. **Set strategic breakpoints**: Place just before error, not at every line
3. **Use watches for suspects**: Track variables you suspect are wrong
4. **Step sparingly**: Use `continue` to breakpoints, not step-by-step everywhere
5. **Check assumptions**: `eval` expressions to verify your mental model
6. **Record complex bugs**: Enable recording for time-travel on hard-to-reproduce issues

## Common Patterns

**Debug exception:**
```bash
cc-debug start script.py
cc-debug bp exception --raised
cc-debug continue
# stops when exception raised, inspect with vars/stack
```

**Debug specific function:**
```bash
cc-debug start script.py --no-stop
cc-debug bp func process_data
cc-debug continue
# stops on function entry
```

**Track variable corruption:**
```bash
cc-debug start script.py
cc-debug record start --auto-interval 5
cc-debug watch add "len(data)"
cc-debug continue
# after bug, step-back through checkpoints to find when data changed
```

## Reference

Full command details: `references/command-reference.md`
