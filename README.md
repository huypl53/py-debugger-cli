# CC-Debugger

Python debugger CLI designed for coding agents (Claude Code, Cursor, etc.).

## Claude Code Plugin

Install as a Claude Code plugin to get the `/cc-debug` skill:

```bash
# Install from GitHub
/plugin install huypl53/py-debugger-cli

# Or install locally
cc --plugin-dir /path/to/py-debugger-cli
```

Then use `/cc-debug` to debug Python programs with guided workflows.

## Features

- **Agent-first design**: JSON output, blocking commands, state diffs
- **Full debugging**: Breakpoints, stepping, variable inspection, expression evaluation
- **State tracking**: Track variable changes between steps, watch expressions
- **Time-travel**: Record execution and navigate through checkpoints
- **Smart breakpoints**: Line, conditional, exception, watchpoint, function patterns

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
# Start debugging
cc-debug start myapp.py

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

# End session
cc-debug quit
```

## Command Reference

### Session Commands

```bash
cc-debug start <file> [--args "..."]   # Start debugging
cc-debug quit                           # End session
cc-debug status                         # Show session state
```

### Execution Control

```bash
cc-debug continue    # Run until breakpoint (blocks)
cc-debug next        # Step over
cc-debug step        # Step into
cc-debug stepout     # Step out
cc-debug pause       # Pause execution
```

### Breakpoints

```bash
cc-debug bp set <file:line>          # Line breakpoint
cc-debug bp set <file:line> -c "x>5" # Conditional
cc-debug bp exception                # Break on all exceptions
cc-debug bp exception --no-raised    # Break only on uncaught
cc-debug bp watch "obj.attr"         # Watchpoint (polls on step)
cc-debug bp func <name>              # Function breakpoint
cc-debug bp list                     # List all
cc-debug bp del <id>                 # Delete
cc-debug bp clear                    # Clear all
```

### Inspection

```bash
cc-debug stack              # Call stack with locals
cc-debug vars               # Variables in current scope
cc-debug vars --all         # All scopes
cc-debug eval "<expr>"      # Evaluate expression
```

### Watch Expressions

```bash
cc-debug watch add "<expr>" # Add watch expression
cc-debug watch list         # List watches
cc-debug watch del "<expr>" # Remove watch
cc-debug watch clear        # Clear all
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

All commands return JSON for easy parsing:

### Success Response

```json
{
  "success": true,
  "command": "continue",
  "result": {
    "event": "stopped",
    "reason": "breakpoint",
    "location": {
      "file": "/path/to/app.py",
      "line": 42,
      "function": "process_data"
    },
    "changedVars": ["x", "result"],
    "watches": {
      "len(data)": {"value": "100", "changed": true}
    }
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

### Using the Skill

Copy the skill to your Claude Code skills directory:

```bash
cp -r .claude/skills/cc-debug ~/.claude/skills/
```

Then invoke with `/cc-debug` or let Claude auto-activate when debugging Python.

### Manual Usage

Use with the Bash tool:

```
Run: cc-debug start tests/test_app.py
Run: cc-debug bp test_app.py:25
Run: cc-debug continue
```

The JSON output provides structured data for analysis and decision-making.

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
