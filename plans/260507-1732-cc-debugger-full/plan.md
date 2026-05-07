# CC-Debugger: Python Debugger CLI for Coding Agents

## Metadata
```yaml
status: ready
priority: high
effort: 5-weeks
risk: medium
blockedBy: []
blocks: []
created: 2026-05-07
```

## Overview

Build a CLI debugger that enables coding agents (Claude Code, Cursor, etc.) to programmatically debug Python code. Uses DAP protocol with debugpy backend, outputs structured JSON for agent parsing.

### Key Differentiators
- **Agent-first design**: JSON output, blocking commands, state diffs
- **Full feature set**: Core debugging + state tracking + recording + time-travel
- **Industry standard**: DAP protocol for ecosystem compatibility
- **Low overhead**: Python 3.12+ with sys.monitoring support

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
                              │ DAP (JSON-RPC over stdio/socket)
┌─────────────────────────────▼───────────────────────────────────┐
│                    debugpy Adapter Process                       │
│              (spawned per debug session)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ pydevd internals
┌─────────────────────────────▼───────────────────────────────────┐
│                   Target Python Process                          │
└─────────────────────────────────────────────────────────────────┘
```

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Python version | 3.12+ | sys.monitoring (PEP 669) |
| DAP client | Custom minimal | dap-python has deps issues; keep it simple |
| Debug adapter | debugpy | Microsoft-maintained, stable |
| CLI framework | Click | Clean, composable, testable |
| Output | JSON to stdout | Agent-parseable, no TTY needed |
| Session state | File-based (JSON) | Persist between CLI invocations |
| Recording | Checkpoint-based | Full trace too expensive |

## Project Structure

```
cc-debugger/
├── src/
│   └── cc_debugger/
│       ├── __init__.py
│       ├── cli.py              # Click CLI entry point
│       ├── commands/           # Command implementations
│       │   ├── __init__.py
│       │   ├── session.py      # start, attach, quit
│       │   ├── control.py      # run, continue, step, next, out
│       │   ├── breakpoints.py  # bp, watch, exception
│       │   └── inspect.py      # stack, vars, eval
│       ├── core/
│       │   ├── __init__.py
│       │   ├── dap_client.py   # DAP protocol client
│       │   ├── session.py      # Session manager
│       │   ├── state.py        # State tracker (var diffs)
│       │   └── recorder.py     # Execution recording
│       ├── output/
│       │   ├── __init__.py
│       │   └── json_formatter.py
│       └── models/
│           ├── __init__.py
│           ├── dap.py          # DAP message types
│           └── session.py      # Session state models
├── tests/
│   ├── conftest.py
│   ├── test_dap_client.py
│   ├── test_session.py
│   ├── test_state_tracker.py
│   ├── test_commands.py
│   └── fixtures/
│       └── sample_scripts/
├── pyproject.toml
└── README.md
```

## Phases

| Phase | Name | Effort | Dependencies |
|-------|------|--------|--------------|
| 1 | Project Setup & DAP Client | 1 week | None |
| 2 | Core Commands | 1 week | Phase 1 |
| 3 | State Tracking & Watch | 1 week | Phase 2 |
| 4 | Recording & Time-Travel | 1 week | Phase 3 |
| 5 | Smart Breakpoints & Polish | 1 week | Phase 4 |

## Phase Files

- `phases/01-setup-dap-client.md`
- `phases/02-core-commands.md`
- `phases/03-state-tracking.md`
- `phases/04-recording-time-travel.md`
- `phases/05-smart-breakpoints-polish.md`

## CLI Command Reference

### Session Commands
```bash
cc-debug start <file> [--args "..."]   # Start debugging
cc-debug attach <pid>                   # Attach to process
cc-debug quit                           # End session
cc-debug status                         # Show session state
```

### Execution Control
```bash
cc-debug run                # Run until breakpoint (blocks)
cc-debug continue           # Continue execution (blocks)
cc-debug next               # Step over
cc-debug step               # Step into
cc-debug stepout            # Step out
cc-debug pause              # Pause execution
```

### Breakpoints
```bash
cc-debug bp <file:line>              # Line breakpoint
cc-debug bp <file:line> -c "x > 5"   # Conditional
cc-debug bp --exception ValueError   # Exception breakpoint
cc-debug bp --watch "obj.attr"       # Watchpoint
cc-debug bp --func "*.process_*"     # Function pattern
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
cc-debug watch add "<expr>" # Add watch expression
cc-debug watch list         # List watches
cc-debug watch del <id>     # Remove watch
```

### Recording (Time-Travel)
```bash
cc-debug record start       # Begin recording
cc-debug record stop        # Stop recording
cc-debug record checkpoint  # Manual checkpoint
cc-debug step-back          # Step backward
cc-debug goto <checkpoint>  # Jump to checkpoint
cc-debug record export <file>  # Export trace
```

## Output Format

All commands output JSON to stdout:

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
    "stack": [
      {
        "id": 0,
        "name": "process_data",
        "file": "/path/to/app.py",
        "line": 42,
        "locals": {
          "x": {"type": "int", "value": "42"},
          "data": {"type": "list", "length": 100, "preview": "[1, 2, 3, ...]"}
        }
      }
    ],
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

## DAP Protocol Subset

Implementing minimal DAP subset for MVP:

| Category | Requests |
|----------|----------|
| Lifecycle | initialize, launch, attach, disconnect, terminate |
| Execution | continue, next, stepIn, stepOut, pause |
| Breakpoints | setBreakpoints, setExceptionBreakpoints |
| Inspection | stackTrace, scopes, variables, evaluate |

Events to handle: initialized, stopped, continued, terminated, output, thread

## State Tracking Implementation

```python
class StateTracker:
    def __init__(self):
        self.snapshots: dict[int, dict] = {}  # frame_id -> vars
        self.watches: dict[str, Any] = {}
    
    def capture(self, frame_id: int, variables: dict) -> set[str]:
        """Capture state, return changed variable names."""
        prev = self.snapshots.get(frame_id, {})
        changed = {k for k, v in variables.items() 
                   if k not in prev or prev[k] != v}
        self.snapshots[frame_id] = variables.copy()
        return changed
    
    def eval_watches(self, session) -> dict[str, WatchResult]:
        """Evaluate all watch expressions."""
        results = {}
        for expr, prev_val in self.watches.items():
            new_val = session.evaluate(expr)
            results[expr] = WatchResult(
                value=new_val,
                changed=(new_val != prev_val)
            )
            self.watches[expr] = new_val
        return results
```

## Recording Implementation

Checkpoint-based recording (not full trace):

```python
@dataclass
class Checkpoint:
    id: str
    timestamp: float
    location: Location
    stack: list[FrameSnapshot]
    variables: dict[int, dict]  # frame_id -> vars
    
class Recorder:
    def __init__(self, max_checkpoints: int = 100):
        self.checkpoints: list[Checkpoint] = []
        self.current_idx: int = -1
        self.max_checkpoints = max_checkpoints
    
    def checkpoint(self, session: Session) -> str:
        """Create checkpoint from current state."""
        cp = Checkpoint(
            id=str(uuid4())[:8],
            timestamp=time.time(),
            location=session.current_location,
            stack=session.get_stack_snapshot(),
            variables=session.get_all_variables()
        )
        self.checkpoints.append(cp)
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.pop(0)
        self.current_idx = len(self.checkpoints) - 1
        return cp.id
    
    def restore(self, checkpoint_id: str) -> bool:
        """Restore to checkpoint (requires re-execution)."""
        # Note: True time-travel requires re-execution from start
        # This restores *view* of state, not actual execution
        ...
```

## Session Persistence

Session state saved to `~/.cc-debugger/sessions/<session_id>.json`:

```json
{
  "id": "abc123",
  "pid": 12345,
  "adapter_port": 5678,
  "target_file": "/path/to/app.py",
  "breakpoints": [
    {"file": "/path/to/app.py", "line": 42, "condition": null}
  ],
  "watches": ["len(data)", "x > 0"],
  "recording": true,
  "created_at": "2026-05-07T17:30:00Z"
}
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| debugpy spawn issues | Use subprocess with timeout, clear error messages |
| DAP message parsing | Use dataclasses with validation, test edge cases |
| State snapshot size | Limit depth, use previews for large objects |
| Recording memory | Cap checkpoint count, prune old entries |
| Process cleanup | atexit handlers, signal handling |

## Testing Strategy

1. **Unit tests**: DAP client, state tracker, recorder
2. **Integration tests**: Full debugging sessions with sample scripts
3. **Fixtures**: Collection of Python scripts with various patterns
4. **Mock adapter**: For testing without debugpy

## Success Criteria

- [ ] Start/attach debugging session
- [ ] Set breakpoints (line, conditional, exception)
- [ ] Step through code (next, step, stepout)
- [ ] Inspect variables with state diffs
- [ ] Watch expressions
- [ ] Record and step backward
- [ ] JSON output parseable by agents
- [ ] Clean error handling
- [ ] Test coverage > 80%

## References

- Research: `docs/brainstorm-cc-debugger.md`
- DAP Spec: https://microsoft.github.io/debug-adapter-protocol/specification.html
- debugpy: https://github.com/microsoft/debugpy
- PEP 669: https://peps.python.org/pep-0669/
