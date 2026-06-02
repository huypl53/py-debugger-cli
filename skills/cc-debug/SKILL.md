---
name: cc-debug
description: Debug Python programs with cc-debug CLI. Use when debugging runtime errors, stepping through code, setting breakpoints, inspecting variables, tracking value changes, or time-travel debugging. All output is JSON.
---

# CC-Debug: Python Debugger for Coding Agents

## Quick Start

```bash
# Debug with project's venv (recommended)
cc-debug start script.py --uv

# Or debug with cc-debug's Python
cc-debug start script.py

# Set breakpoint and run
cc-debug bp set script.py:42
cc-debug continue

# Step and inspect
cc-debug next
cc-debug vars
cc-debug eval "len(items)"

# End session - ALWAYS call quit!
cc-debug quit
```

**IMPORTANT:** Always call `cc-debug quit` when done debugging. This cleanly shuts down the daemon and debugpy processes. Forgetting to quit leaves orphan processes running.

## Critical Debugging Workflows

To prevent the debugger or target application from hanging or remaining paused indefinitely, you **MUST** choose the correct workflow path based on your target program type:

### Pattern A: CLI Scripts (Stop-on-Entry)
*Use this when debugging a standard script from start to finish, or when you need to step through initial setup/imports.*
1. **Start the session**: `cc-debug start script.py --uv` (the program automatically pauses on line 1).
2. **Set your breakpoints**: `cc-debug bp set script.py:42`
3. **CRITICAL - Resume Execution**: `cc-debug continue` (or `next`/`step`). The target application **will remain paused on line 1 indefinitely** and will never run or hit breakpoints until you issue this command. Forgetting this step makes the script appear "hung".

### Pattern B: Web Servers & Daemons (No-Stop)
*Use this for FastAPI, Uvicorn, Flask, Django, celery workers, or any long-running service.*
1. **Start the server with `--no-stop`**: `cc-debug start server.py --uv --no-stop` (the server initializes and starts listening on ports immediately without stopping).
2. **Stream server logs**: `cc-debug output -f &` (run in background or a separate terminal so you can see the server's print/log output).
3. **Set your breakpoints**: `cc-debug bp set handler.py:25`
4. **Trigger execution**: Send HTTP requests (via `curl` or python `urllib`) or trigger the background tasks. The debugger will automatically halt execution when the breakpoint line is executed.
5. **Resume intentionally**: after inspecting a breakpoint hit, use `cc-debug continue` only when you deliberately want to wait for the *next* stop. For long-running servers, `continue` is a blocking command and usually will not return until another breakpoint/exception is hit or the process exits.

> [!TIP]
> **Debugging Web Servers (FastAPI, Uvicorn, Flask, etc.)**:
> Always use the `--no-stop` flag when starting web servers or API services:
> `cc-debug start server.py --uv --no-stop`
> This allows the server to initialize and start serving immediately. Otherwise, the app stops on entry (line 1), and sending `continue` may block or time out if the initialization takes a long time.
>
> After a breakpoint hit in a server, `cc-debug continue` resumes execution **and then waits** for the next stop. Do not expect it to "resume and return immediately". If you only need to let the request finish, run `continue` in a separate terminal/session or be prepared for the command to stay blocked.


## Debugging Different Venvs

**Recommended: Use `--uv` flag** for automatic venv detection:

```bash
cc-debug start script.py --uv
```

The `--uv` flag:
1. Finds `.venv` by walking up from target file
2. Auto-installs `debugpy` if missing
3. Uses that venv's Python for debugging

**Manual approach:**

```bash
cd /path/to/project && uv pip install debugpy
cc-debug start script.py --python .venv/bin/python
```

## Session Commands

```bash
cc-debug start <file>                    # Start debugging (stops on entry)
cc-debug start <file> --uv               # Auto-detect venv
cc-debug start <file> --python PATH      # Use specific interpreter
cc-debug start <file> --args "a b"       # Pass arguments
cc-debug start <file> --no-stop          # Don't stop on entry (for servers)
cc-debug quit                            # End session
cc-debug status                          # Show state
cc-debug restart [--args "..."]          # Restart session
cc-debug pm <traceback-file>             # Post-mortem from crash
```

**For servers/long-running programs:** Use `--no-stop` - returns immediately with `state: "running"`. Set breakpoints to stop at specific lines.

**Blocking behavior:** `cc-debug continue` is a blocking command. For scripts, that is usually what you want. For long-running servers, it means the caller will wait until the next breakpoint/exception/termination, so do not use it as a fire-and-forget resume command.

## Execution Control

| Command | Action |
|---------|--------|
| `cc-debug continue` | Run until breakpoint |
| `cc-debug next` | Step over |
| `cc-debug step` | Step into |
| `cc-debug stepout` | Step out |
| `cc-debug run-to-cursor <file:line>` | Run to line (temp bp) |
| `cc-debug until <line>` | Run to line in current file |
| `cc-debug pause` | Pause execution |

## Breakpoints

```bash
cc-debug bp set <file>:<line>              # Line breakpoint
cc-debug bp set <file>:<line> -c "x>5"     # Conditional
cc-debug bp set <file>:<line> --log "x={x}" # Log (print without stopping)
cc-debug bp set <file>:<line> --hit 5      # Hit count (break on 5th)
cc-debug bp exception                       # Break on exceptions
cc-debug bp func <name>                     # Function breakpoint
cc-debug bp watch "obj.attr"                # Watchpoint
cc-debug bp list                            # List all
cc-debug bp del <id>                        # Delete
cc-debug bp clear                           # Clear all
```

## Inspection

```bash
cc-debug vars                   # Local variables
cc-debug vars --depth 3         # Recursive expansion
cc-debug eval "<expr>"          # Evaluate expression
cc-debug set "x = 42"           # Modify variable
cc-debug stack                  # Call stack
cc-debug up                     # Move to caller frame
cc-debug down                   # Move to callee frame
cc-debug source                 # Show source context
cc-debug source -n 10           # 10 lines of context
cc-debug output                 # Show stdout/stderr
cc-debug output --clear         # Clear after reading
cc-debug output -f              # Stream continuously (like tail -f)
```

## Execution Tracing

```bash
cc-debug trace start            # Start recording steps
cc-debug trace start --max 500  # Limit entries
cc-debug trace get              # Get trace log
cc-debug trace stop             # Stop recording
```

## Watch Expressions

```bash
cc-debug watch add "x + y"      # Track expression
cc-debug watch list             # Show all with values
cc-debug watch del "x + y"      # Remove watch
```

## Time-Travel (Recording)

```bash
cc-debug record start           # Start recording
cc-debug record checkpoint      # Manual checkpoint
cc-debug step-back              # Go to previous
cc-debug step-forward           # Go to next
cc-debug goto <id>              # Jump to checkpoint
cc-debug record stop            # Stop recording
cc-debug record export out.json # Export trace
```

## JSON Output

All commands return JSON. Program output (print/logging) streams in real-time:
- **stderr**: Users see output in terminal
- **JSON output field**: Agents parse output array

```json
{
  "success": true,
  "command": "next",
  "result": {
    "event": "stopped",
    "reason": "step",
    "location": {"file": "/app.py", "line": 42, "function": "main"},
    "source_context": [
      {"number": 41, "content": "    x = 1", "current": false},
      {"number": 42, "content": "    y = 2", "current": true}
    ],
    "changedVars": ["x"],
    "output": [{"category": "stdout", "output": "Debug: x=1\n"}]
  }
}
```

## Common Patterns

**Debug with project packages:**
```bash
cc-debug start myproject/main.py --uv
cc-debug continue
```

**Debug exception:**
```bash
cc-debug start script.py --uv
cc-debug bp exception --raised
cc-debug continue
# stops at exception, inspect with vars/stack
```

**Post-mortem from crash:**
```bash
python script.py 2> traceback.txt
cc-debug pm traceback.txt
# starts at crash location
```

**Track variable changes:**
```bash
cc-debug start script.py --uv
cc-debug watch add "len(data)"
cc-debug record start
cc-debug continue
# use step-back to find when data changed
```

**Debug server/long-running program:**
```bash
# 1. Start server (returns immediately)
cc-debug start server.py --uv --no-stop

# 2. IMPORTANT: Stream logs to see server output
cc-debug output -f &            # Run in background OR separate terminal

# 3. Set breakpoints
cc-debug bp set server.py:100

# 4. Trigger the server (e.g., send request)
# Debugger stops when breakpoint hit

# 5. Inspect state
cc-debug vars
cc-debug stack

# 6. Resume request processing when ready
# WARNING: this blocks until the next stop, so use a separate terminal/session if needed
cc-debug continue

# 7. Always quit when done
cc-debug quit
```

**Note:** Without `output -f`, server stdout/stderr is invisible. Always stream logs when debugging servers.
