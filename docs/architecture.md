# CC-Debugger Architecture

## Overview

CLI debugger for Python using Debug Adapter Protocol (DAP) via debugpy.

## Components

```
cc-debug CLI → daemon_main.py (socket server) → debugpy (DAP)
```

### Daemon Architecture

`daemon_main.py` runs as background process:
- Socket server on localhost (dynamic port)
- Port/PID stored in `~/.cc-debugger/session/`
- Single active session at a time
- Commands: start, quit, continue, step, next, stepout, bp, eval, record, etc.

### State Tracking (`core/state.py`)

- Variable change detection between steps
- Watch expression evaluation
- Protocol-based duck typing for testability

### Recording (`core/recorder.py`)

- Checkpoint-based execution snapshots
- Time-travel navigation (step_back, step_forward, goto)
- Export/load to JSON files
- Memory-bounded: 50MB max, 100 checkpoints

## Security Hardening

- **Path traversal protection**: Export paths validated to stay within recordings dir
- **Socket timeouts**: 300s client timeout, 120s launch timeout
- **Memory limits**: Checkpoint size capped at 50MB total
- **Thread safety**: Event queue protected by `_events_lock`
- **Exception handling**: Specific exceptions (no bare except), proper chaining

## CLI Commands

```
cc-debug start <file>     # Start debugging
cc-debug quit             # End session
cc-debug next/step/stepout/continue  # Execution control
cc-debug bp set/list/del  # Breakpoints
cc-debug eval <expr>      # Evaluate expression
cc-debug record start/stop/checkpoint  # Recording
```
