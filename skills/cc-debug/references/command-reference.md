# CC-Debug Command Reference

## Session Commands

### `cc-debug start <file>`
Start debugging a Python file.

| Option | Default | Description |
|--------|---------|-------------|
| `--args` | "" | Arguments to pass to the program |
| `--no-stop` | false | Don't stop on entry (run until breakpoint) |

**Output:**
```json
{"success": true, "command": "start", "data": {"sessionId": "abc123", "file": "/path/to/file.py", "stopped": true}}
```

### `cc-debug quit`
End the current debug session. Terminates debuggee and daemon.

### `cc-debug status`
Show current session status.

**Output:**
```json
{"success": true, "command": "status", "data": {"state": "stopped", "location": {"file": "...", "line": 42, "function": "main"}}}
```

---

## Execution Control

### `cc-debug continue`
Continue execution until next breakpoint or program end.

**Output includes:**
- `reason`: "breakpoint", "step", "exception", "exit"
- `location`: current file/line/function
- `changedVars`: variables that changed since last stop
- `watches`: current watch expression values

### `cc-debug next`
Step over to next line (doesn't enter functions).

### `cc-debug step`
Step into function call on current line.

### `cc-debug stepout`
Step out of current function to caller.

---

## Breakpoints

### `cc-debug bp set <file>:<line>`
Set breakpoint at location.

| Option | Description |
|--------|-------------|
| `-c, --condition` | Condition expression (break only when true) |

**Example:**
```bash
cc-debug bp set myfile.py:42 -c "x > 100"
```

### `cc-debug bp list`
List all breakpoints with IDs.

### `cc-debug bp del <id>`
Delete breakpoint by ID.

### `cc-debug bp clear`
Remove all breakpoints.

### `cc-debug bp func <name>`
Break on function entry by name.

### `cc-debug bp exception`
Break on exceptions.

| Option | Default | Description |
|--------|---------|-------------|
| `--raised/--no-raised` | --raised | Break when exception is raised |
| `--uncaught/--no-uncaught` | --uncaught | Break on uncaught exceptions |

### `cc-debug bp watch <expression>`
Watch expression for changes (polls on each step). Alias for `watch add`.

---

## Inspection

### `cc-debug vars`
Show variables in current scope.

| Option | Default | Description |
|--------|---------|-------------|
| `--all` | false | Show all scopes (not just locals) |
| `--depth` | 3 | Max nested object depth |

### `cc-debug eval <expression>`
Evaluate expression in current context.

**Output:**
```json
{"success": true, "command": "eval", "data": {"expression": "x + 1", "value": "42", "type": "int"}}
```

### `cc-debug stack`
Show call stack with frame info.

| Option | Default | Description |
|--------|---------|-------------|
| `--depth` | 10 | Max frames to show |

---

## Watch Expressions

### `cc-debug watch add <expression>`
Add expression to watch list. Evaluated on each step.

### `cc-debug watch list`
List all watches with current values.

**Output:**
```json
{"success": true, "command": "watch list", "data": {"watches": ["x", "len(items)"], "values": {"x": {"value": "5", "type": "int", "changed": false}}}}
```

### `cc-debug watch del <expression>`
Remove expression from watch list.

### `cc-debug watch clear`
Clear all watches.

---

## Recording (Time-Travel)

### `cc-debug record start`
Start recording execution checkpoints.

| Option | Default | Description |
|--------|---------|-------------|
| `--auto-interval` | 0 | Auto-checkpoint every N steps (0=manual only) |

### `cc-debug record stop`
Stop recording. Returns checkpoint count.

### `cc-debug record checkpoint`
Create manual checkpoint at current location.

| Option | Default | Description |
|--------|---------|-------------|
| `--reason` | "manual" | Reason/label for checkpoint |

### `cc-debug record list`
List all checkpoints with IDs and locations.

### `cc-debug record export <file>`
Export recording to JSON file for later analysis.

---

## Time-Travel Navigation

### `cc-debug step-back`
Navigate to previous checkpoint. Shows checkpoint state (variables, watches at that point).

### `cc-debug step-forward`
Navigate to next checkpoint.

### `cc-debug goto <checkpoint_id>`
Jump to specific checkpoint by ID.

---

## Error Codes

| Code | Meaning |
|------|---------|
| `NO_SESSION` | No debug session running. Use `start` first. |
| `START_FAILED` | Failed to start debugging (check file path) |
| `STEP_FAILED` | Step command failed (program may have exited) |
| `EVAL_FAILED` | Expression evaluation error |
| `BREAKPOINT_ERROR` | Invalid breakpoint location |
| `NO_CHECKPOINT` | No checkpoint available in that direction |

---

## Environment Variables

| Variable | Effect |
|----------|--------|
| `CC_DEBUG_LOG` | Set to any value to enable debug logging to `~/.cc-debugger/daemon.log` |
