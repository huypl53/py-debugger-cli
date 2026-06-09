# CC-Debugger

Python debugger CLI designed for coding agents (Claude Code, Cursor, etc.).

## Claude Code Plugin

Install as a Claude Code plugin to get the `/cc-debug` skill:

```bash
# Step 1: Add the marketplace
/plugin marketplace add huypl53/py-debugger-cli

# Step 2: Install the plugin
/plugin install py-debugger@py-debugger-cli
```

Or install from a local clone:

```bash
# Add local directory as marketplace
/plugin marketplace add ./path/to/py-debugger-cli

# Then install
/plugin install py-debugger@py-debugger-cli
```

After installing, reload without restarting:

```bash
/reload-plugins
```

Then use `/cc-debug` to debug Python programs with guided workflows.

## Features

- **Agent-first design**: JSON output, blocking commands, source context in every stop
- **Token-efficient**: `--compact`, `--changed`, `--limit`, auto-truncate large values
- **Full debugging**: Breakpoints, stepping, variable inspection, expression evaluation
- **State tracking**: Track variable changes between steps, watch expressions
- **Stack navigation**: Move up/down call stack, modify variables in any frame
- **Smart breakpoints**: Line, conditional, log, hit count, exception, watchpoint, function
- **Execution tracing**: Record step-by-step execution path
- **Time-travel**: Record execution and navigate through checkpoints
- **Post-mortem**: Debug from crash tracebacks without re-running
- **Program I/O**: Real-time stdout/stderr streaming (visible to users and agents)
- **Venv integration**: Auto-detect project venv with `--uv`, or specify with `--python`

## Installation

### Global Install (Recommended)

```bash
# Using pipx (isolated, auto-adds to PATH)
pipx install git+https://github.com/huypl53/py-debugger-cli.git

# Or using uv tool
uv tool install git+https://github.com/huypl53/py-debugger-cli.git

# Verify
cc-debug --version
```

### Development Install

```bash
# Create virtual environment
uv venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
uv pip install -e ".[dev]" debugpy
```

Requires Python 3.12+ and `debugpy` for the debug adapter.

## Quick Start

```bash
# Start debugging (uses cc-debug's Python)
cc-debug start myapp.py

# Start debugging with project's venv (recommended for projects)
cc-debug start myapp.py --uv

# Set breakpoint
cc-debug bp set myapp.py:42

# Run to breakpoint
cc-debug continue

# Step through code
cc-debug next
cc-debug step
cc-debug stepout

# Inspect state
cc-debug vars
cc-debug stack
cc-debug eval "len(items)"

# Watch expressions
cc-debug watch add "total > 100"

# Recording and time-travel
cc-debug record start
cc-debug next
cc-debug step-back

# End session - ALWAYS call quit!
cc-debug quit
```

**IMPORTANT:** Always call `cc-debug quit` when done. This shuts down the daemon and debugpy processes. Forgetting leaves orphan processes.

## Command Reference

### Session Commands

```bash
cc-debug start <file>                              # Start debugging (stops on entry)
cc-debug start <file> --uv                         # Auto-detect venv, install debugpy
cc-debug start <file> --no-stop                    # Start without stopping (for servers)
cc-debug start <file> --python .venv/bin/python   # Debug with specific interpreter
cc-debug quit                                      # End session
cc-debug status                                    # Show session state
cc-debug restart [--args "..."]                    # Restart with same/new args
cc-debug pm <traceback-file>                       # Post-mortem debug from crash
cc-debug help                                      # Show detailed usage guide
cc-debug help <command>                            # Show help for a specific command
```

**Recommended:** Use `--uv` flag for projects with their own venv - it auto-detects the venv and installs debugpy if needed.

**For servers:** Use `--no-stop` to start without stopping on entry. Set breakpoints and the debugger will stop when hit.

### Execution Control

```bash
cc-debug continue          # Run until breakpoint (blocks)
cc-debug next              # Step over
cc-debug next -c           # Step over (compact output, reduced tokens)
cc-debug step              # Step into
cc-debug stepout           # Step out
cc-debug pause             # Pause execution
cc-debug run-to-cursor <file:line>  # Run to specific line (temp bp)
cc-debug until <line>      # Run to line in current file
```

### Breakpoints

```bash
cc-debug bp set <file:line>            # Line breakpoint
cc-debug bp set <file:line> -c "x>5"   # Conditional
cc-debug bp set <file:line> --log "x={x}"  # Log breakpoint (prints without stopping)
cc-debug bp set <file:line> --hit 5    # Hit count (break on 5th hit)
cc-debug bp exception                  # Break on all exceptions
cc-debug bp exception --no-raised      # Break only on uncaught
cc-debug bp watch "obj.attr"           # Watchpoint (polls on step)
cc-debug bp func <name>                # Function breakpoint
cc-debug bp list                       # List all
cc-debug bp del <id>                   # Delete
cc-debug bp clear                      # Clear all
```

### Inspection

```bash
cc-debug stack              # Call stack with locals
cc-debug vars               # Variables in current scope
cc-debug vars --all         # All scopes
cc-debug vars --depth 3     # Recursive expansion (nested objects)
cc-debug vars --changed     # Only changed variables (token-efficient)
cc-debug vars --limit 5     # Top 5 most interesting variables
cc-debug vars --names-only  # Just names, no values
cc-debug vars --no-truncate # Disable auto-truncation of large values
cc-debug eval "<expr>"      # Evaluate expression
cc-debug set "x = 42"       # Modify variable value
cc-debug up                 # Move up one stack frame (to caller)
cc-debug down               # Move down one stack frame (to callee)
cc-debug source             # Show source around current location
cc-debug source -n 10       # Show 10 lines of context
cc-debug source app.py:100  # Show source at specific location
cc-debug output             # Show program stdout/stderr
cc-debug output --clear     # Clear output buffer after reading
cc-debug output -f          # Stream output continuously (like tail -f)
cc-debug why                # Explain why execution stopped (one-line)
cc-debug inspect            # Batch: location + vars + stack in one call
cc-debug snapshot           # Full state dump for context recovery
cc-debug summary            # One-line state summary (minimal tokens)
```

### Watch Expressions

```bash
cc-debug watch add "<expr>" # Add watch expression
cc-debug watch list         # List watches with values
cc-debug watch diff         # Show only changed watches (token-efficient)
cc-debug watch del "<expr>" # Remove watch
cc-debug watch clear        # Clear all
```

### Execution Tracing

```bash
cc-debug trace start                # Begin recording step locations
cc-debug trace start --max 1000     # Max entries to record
cc-debug trace start --filter app   # Only trace files containing "app"
cc-debug trace get                  # Get recorded trace entries
cc-debug trace get --limit 50       # Limit returned entries
cc-debug trace stop                 # Stop recording (log retained)
```

### Recording (Time-Travel)

```bash
cc-debug record start       # Begin recording
cc-debug record stop        # Stop recording
cc-debug record checkpoint  # Manual checkpoint
cc-debug step-back          # Step backward
cc-debug step-forward       # Step forward
cc-debug goto <checkpoint>  # Jump to checkpoint
cc-debug record export <file>  # Export trace
```

## Output Format

All commands return JSON for easy parsing. **Program output (print/logging) is shown in real-time:**
- **To stderr**: Visible to users watching the terminal
- **In JSON**: Included in `output` array for agent parsing

### Success Response

```json
{
  "success": true,
  "command": "next",
  "result": {
    "event": "stopped",
    "reason": "step",
    "location": {
      "file": "/path/to/app.py",
      "line": 42,
      "function": "process_data"
    },
    "source_context": [
      {"number": 40, "content": "    x = 1", "current": false},
      {"number": 41, "content": "    y = 2", "current": false},
      {"number": 42, "content": "    z = x + y", "current": true},
      {"number": 43, "content": "    return z", "current": false}
    ],
    "changedVars": ["x", "result"],
    "watches": {
      "len(data)": {"value": "100", "changed": true}
    },
    "output": [
      {"category": "stdout", "output": "Processing item 42\n"}
    ]
  }
}
```

### Error Response

```json
{
  "success": false,
  "command": "bp",
  "error": {
    "code": "INVALID_LOCATION",
    "message": "File not found: /path/to/missing.py"
  }
}
```

## Claude Code Integration

### As a Plugin (Recommended)

Install via the marketplace (see [Claude Code Plugin](#claude-code-plugin) above).
The plugin registers the `/cc-debug` skill which auto-activates when debugging Python.

### Manual Skill Setup

If not using the plugin, copy the skill directly:

```bash
cp -r .claude/skills/cc-debug ~/.claude/skills/
```

Then invoke with `/cc-debug`.

### Direct CLI Usage

Use `cc-debug` directly with the Bash tool:

```
Run: cc-debug start tests/test_app.py
Run: cc-debug bp test_app.py:25
Run: cc-debug continue
```

All commands return JSON for agent parsing and decision-making.

## Debugging Projects with Different Venvs

When debugging a script that uses packages from its own virtual environment:

### Recommended: Use `--uv` flag

```bash
# Automatically detects .venv, installs debugpy if needed
cc-debug start myproject/main.py --uv
```

The `--uv` flag:
1. Walks up from target file to find `.venv` directory
2. Auto-installs `debugpy` in that venv using `uv pip`
3. Uses that venv's Python interpreter for debugging

### Manual: Use `--python` flag

```bash
# First install debugpy in the target venv
cd myproject && uv pip install debugpy

# Then debug with explicit Python path
cc-debug start main.py --python .venv/bin/python
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CC-Debugger CLI                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Click CLI    │  │ Session Mgr  │  │ JSON Output        │    │
│  │ (commands)   │  │ (lifecycle)  │  │ (formatter)        │    │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘    │
│         │                 │                    │               │
│  ┌──────▼─────────────────▼────────────────────▼──────────┐    │
│  │                   DAP Client Layer                      │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │    │
│  │  │ Protocol    │  │ State        │  │ Recorder      │  │    │
│  │  │ Handler     │  │ Tracker      │  │ (snapshots)   │  │    │
│  │  └─────────────┘  └──────────────┘  └───────────────┘  │    │
│  └─────────────────────────┬──────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────┘
                              │ DAP (JSON-RPC over stdio)
┌─────────────────────────────▼───────────────────────────────────┐
│                    debugpy Adapter Process                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │ pydevd internals
┌─────────────────────────────▼───────────────────────────────────┐
│                   Target Python Process                          │
└─────────────────────────────────────────────────────────────────┘
```

## Time-Travel Limitations

1. **View-only**: `step-back` shows historical state but doesn't reverse execution
2. **Memory bounded**: Max 100 checkpoints by default
3. **No I/O reversal**: File/network operations cannot be undone

## Development

```bash
# Setup
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]" debugpy

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT
