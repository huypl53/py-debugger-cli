# CC-Debugger Feature Roadmap

## Executive Summary

10 features across 4 phases (reduced from 14 after red-team review). Architecture pattern: CLI command → daemon handler → DAP call → JSON output.

**Key design change**: Source context embedded in ALL stopped events, not as separate command.

---

## Phase 1 — High-Value Core (Tier 1) ✅ COMPLETE

Ship as one PR. No interdependencies.

### 1.1 Embedded Source Context

**Value**: Agents need code context with every stop — no extra round-trip.

**Complexity**: Low

**Design**: Embed `source_context` in ALL stopped event responses (`continue`, `next`, `step`, `stepout`, `run-to-cursor`, `until`).

**Files**:
- `daemon_main.py` — Add `_get_source_context(file, line, context=5)` helper
- Call helper in every stepping handler before returning

**Output** (in every stopped response):
```json
{
  "success": true,
  "command": "next",
  "result": {
    "event": "stopped",
    "reason": "step",
    "location": {"file": "/app.py", "line": 42, "function": "main"},
    "source_context": [
      {"number": 40, "content": "    x = 1", "current": false},
      {"number": 41, "content": "    y = 2", "current": false},
      {"number": 42, "content": "    z = x + y", "current": true},
      {"number": 43, "content": "    return z", "current": false}
    ]
  }
}
```

**Also add**: Standalone `source` command for when agent needs different context size or specific file:
```bash
cc-debug source              # Current location, default context
cc-debug source -n 10        # 10 lines before/after
cc-debug source app.py:100   # Specific location
```

---

### 1.2 `up` / `down` — Stack Frame Navigation

**Value**: Inspect caller variables without parsing `stack` output.

**Complexity**: Low

**Files**:
- `daemon_main.py` — Add `current_frame_idx` state, `"frame_up"/"frame_down"` handlers
- `commands/inspect.py` — Add `up`, `down` commands

**State Management**:
- Reset `current_frame_idx = 0` on every step/continue
- `vars` and `eval` use `frames[current_frame_idx]` instead of `frames[0]`

**Output**:
```json
{
  "success": true,
  "command": "up",
  "result": {
    "frame_index": 1,
    "frame": {"id": 5, "name": "caller_function", "file": "/app.py", "line": 15},
    "source_context": [...]
  }
}
```

---

### 1.3 `run-to-cursor <file:line>` — Temporary Breakpoint

**Value**: Continue to specific line without polluting permanent breakpoints.

**Complexity**: Low-Medium

**Files**:
- `daemon_main.py` — Add `"run_to_cursor"` handler (set temp bp → continue → remove)
- `commands/control.py` — Add `run_to_cursor` command

**Refactoring Required**:
```python
# Extract helper methods for Features 1.3 and 2.3
def _add_temp_breakpoint(self, file: str, line: int) -> None
def _remove_temp_breakpoint(self, file: str, line: int) -> None
```

---

### 1.4 `set <var> = <value>` — Variable Mutation

**Value**: "What-if" testing by changing state mid-execution.

**Complexity**: Medium

**Design**: Use `evaluate` with `context="repl"` (not `setVariable`)

**Files**:
- `daemon_main.py` — Add `"setvar"` handler
- `commands/inspect.py` — Add `set_cmd`

**Output**:
```json
{
  "success": true,
  "command": "set",
  "result": {"variable": "x", "new_value": "42", "new_type": "int"}
}
```

---

## Phase 2 — Breakpoint & Control Enhancements (Tier 2) ✅ COMPLETE

Ship as one PR. Extends existing commands.

### 2.1 Log Breakpoints

**Value**: Print-debugging without stopping.

**Files**: `commands/breakpoints.py` — Add `--log` option

**DAP**: `logMessage` field (already in `SourceBreakpoint` model)

```bash
cc-debug bp set app.py:10 --log "x={x}, y={y}"
```

---

### 2.2 Hit Count Breakpoints

**Value**: Break on Nth hit (skip loop iterations).

**Files**: `commands/breakpoints.py` — Add `--hit` option

**DAP**: `hitCondition` field

```bash
cc-debug bp set loop.py:7 --hit 5
```

---

### 2.3 `until <line>` — Run to Line

**Value**: Faster than `next` for skipping code blocks.

**Complexity**: Low-Medium

**Design**: Like `run-to-cursor` but line-only (uses current file). **No forward restriction** — matches GDB/pdb behavior.

**Files**:
- `daemon_main.py` — Add `"until"` handler
- `commands/control.py` — Add `until` command

---

### 2.4 `restart` — Re-run Program (NEW)

**Value**: Essential for iteration. Currently must `quit` + `start`.

**Complexity**: Low

**Design**: Call DAP `disconnect` then `launch` with same arguments.

**Files**:
- `daemon_main.py` — Add `"restart"` handler, store launch args in session
- `commands/session.py` — Add `restart` command

```bash
cc-debug restart              # Re-run with same args
cc-debug restart --args "new" # Re-run with new args
```

---

## Phase 3 — I/O & Diagnostics (Tier 2-B) ✅ COMPLETE

Individual PRs, each standalone.

### 3.1 Program Output Capture (NEW)

**Value**: See stdout/stderr from debugged program without separate terminal.

**Complexity**: Medium

**Design**: debugpy sends `output` events. Daemon buffers them, CLI retrieves.

**Files**:
- `daemon_main.py` — Add `output_buffer: list[dict]`, capture `output` events
- `commands/inspect.py` — Add `output` command

```bash
cc-debug output          # Show buffered output
cc-debug output --clear  # Clear buffer
cc-debug output --follow # Stream (blocks)
```

**Output**:
```json
{
  "success": true,
  "command": "output",
  "result": {
    "lines": [
      {"category": "stdout", "output": "Processing item 1\n"},
      {"category": "stderr", "output": "Warning: deprecated\n"}
    ]
  }
}
```

---

### 3.2 `locals --recursive` — Deep Object Inspection

**Value**: Inspect nested structures without multiple `eval` calls.

**Complexity**: Medium

**Files**:
- `daemon_main.py` — Add `_expand_variables(vars_ref, depth)` helper
- `commands/inspect.py` — Wire `--depth` option

```bash
cc-debug vars --depth 3
```

---

## Phase 4 — Advanced Features (Tier 3) ✅ COMPLETE

Individual PRs, gated behind `--experimental`.

### 4.1 `trace` Mode — Execution Logging (IMPLEMENTED)

**Value**: Log steps during debugging.

**Complexity**: Medium (revised from High)

**Design (FINAL)**: Record step events in daemon memory, NOT sys.settrace injection (conflicts with debugpy).

**Why redesign**: Stepping loop = O(n) DAP round-trips. 1000 lines = 10+ seconds. Unusable.

**New approach**:
1. Inject trace function via `evaluate`:
   ```python
   evaluate("""
   import sys
   _cc_trace_log = []
   def _cc_tracer(frame, event, arg):
       if event == 'line':
           _cc_trace_log.append((frame.f_code.co_filename, frame.f_lineno))
       return _cc_tracer
   sys.settrace(_cc_tracer)
   """)
   ```
2. Continue execution (non-blocking or until breakpoint)
3. Retrieve log via `evaluate("_cc_trace_log[-100:]")`
4. Stop tracing via `evaluate("sys.settrace(None)")`

**Files**:
- `daemon_main.py` — Add `"trace_start/stop/get"` handlers
- `commands/trace.py` — New file

**Output**:
```json
{
  "result": {
    "steps": 247,
    "trace": [
      {"file": "/app.py", "line": 10, "function": "main"},
      {"file": "/app.py", "line": 11, "function": "main"}
    ]
  }
}
```

---

### 4.2 `pm <traceback-file>` — Post-Mortem Debugging

**Value**: Debug crashes from saved tracebacks.

**Complexity**: High

**Files**:
- `core/traceback_parser.py` — New file to parse Python tracebacks
- `commands/session.py` — Add `pm` command
- `daemon_main.py` — Add `"pm_start"` handler

**Design**: Parse traceback → extract crash location → start session with breakpoint at crash line.

```bash
cc-debug pm traceback.txt
cc-debug pm -              # Read from stdin
```

---

## Dropped Features (YAGNI)

| Feature | Reason |
|---------|--------|
| `attach <pid>` | Requires target cooperation (`debugpy.listen()`). Real attach needs `ptrace`/memory injection — out of scope. |
| `bp module` | Niche use case. Import tracing via `importlib` is simpler if needed. |
| Call graph capture | Build when proven demand exists. |
| Memory profiling | `python -m tracemalloc` exists. Don't reimplement. |

---

## Implementation Order

```
Phase 1 (1 PR):
├── 1.1 embedded source     [Low]      ← Design change: in all stopped events
├── 1.2 up/down             [Low]
├── 1.3 run-to-cursor       [Low-Med]
└── 1.4 set                 [Medium]

Phase 2 (1 PR):
├── 2.1 log breakpoints     [Low]
├── 2.2 hit count bps       [Low]
├── 2.3 until               [Low-Med]  ← No forward restriction
└── 2.4 restart             [Low]      ← NEW

Phase 3 (2 PRs):
├── 3.1 output capture      [Medium]   ← NEW (replaces attach)
└── 3.2 locals --recursive  [Medium]

Phase 4 (2 PRs, --experimental):
├── 4.1 trace               [High]     ← REDESIGNED: settrace injection
└── 4.2 pm                  [High]
```

**Total: 10 features, 6 PRs** (down from 14 features, 9 PRs)

---

## Prerequisites / Refactoring

### Before Phase 1

1. **Move breakpoint state to daemon** — Currently `_breakpoints` is CLI-side. Daemon needs to track permanent breakpoints for temp breakpoint math.
   
   **Migration strategy**:
   - Add `DaemonServer.breakpoints: dict[str, list[dict]]`
   - CLI sends full breakpoint state on `bp set/del`
   - Deprecate CLI-side `_breakpoints` dict
   - Add migration test: old CLI + new daemon compatibility

2. **Extract temp breakpoint helpers** — Shared by 1.3 and 2.3:
   ```python
   def _add_temp_breakpoint(self, file: str, line: int) -> None
   def _remove_temp_breakpoint(self, file: str, line: int) -> None
   ```

3. **Add `_get_source_context()` helper** — Used by all stepping handlers:
   ```python
   def _get_source_context(self, file: str, line: int, context: int = 5) -> list[dict]
   ```

4. **Frame index reset policy** — Every execution action must reset `current_frame_idx = 0`.

---

## New Error Codes

| Code | Feature | Meaning |
|------|---------|---------|
| `FILE_NOT_FOUND` | source, pm | File doesn't exist |
| `AT_TOP_FRAME` | up | Already at outermost frame |
| `AT_BOTTOM_FRAME` | down | Already at innermost frame |
| `INVALID_LINE` | run-to-cursor, until | Line doesn't exist in file |
| `TRACE_ALREADY_ACTIVE` | trace | Trace already running |
| `NO_OUTPUT` | output | No buffered output |

---

## Test Strategy

### Unit Tests (mock daemon)
- `tests/test_source_context.py` — Verify source lines in stopped events
- `tests/test_frame_navigation.py` — up/down/reset behavior
- `tests/test_temp_breakpoints.py` — run-to-cursor, until
- `tests/test_restart.py` — Session restart preserves/updates args

### Integration Tests (real debugpy)
- Mark with `@pytest.mark.integration`
- Skip in CI unless `CC_DEBUG_INTEGRATION=1`

### Test Fixtures

| Fixture | Purpose |
|---------|---------|
| `fixtures/annotated.py` | 30-line script for line-number tests |
| `fixtures/nested.py` | Nested data structures for `--recursive` |
| `fixtures/crash.py` | Guaranteed `ZeroDivisionError` for pm tests |
| `fixtures/output.py` | Script with stdout/stderr for output capture |

---

## Critical Implementation Files

- `src/cc_debugger/daemon_main.py` — All handlers + source context helper
- `src/cc_debugger/commands/inspect.py` — source, up/down, set, vars --depth, output
- `src/cc_debugger/commands/control.py` — run-to-cursor, until
- `src/cc_debugger/commands/breakpoints.py` — log, hit options
- `src/cc_debugger/commands/session.py` — restart, pm
- `src/cc_debugger/commands/trace.py` — trace (new)
- `src/cc_debugger/core/traceback_parser.py` — pm parser (new)

---

## Red-Team Review Changes Applied

| Original | Change | Reason |
|----------|--------|--------|
| Separate `source` command | Embed in all stopped events | Reduce round-trips |
| `until` forward-only | Allow any line | Match GDB/pdb behavior |
| `attach <pid>` | Dropped | Requires target cooperation, nearly useless |
| `bp module` | Dropped | Niche, YAGNI |
| Trace via stepping loop | Redesign with `sys.settrace()` | O(n) round-trips → O(1) injection |
| Call graph | Dropped | YAGNI |
| Memory profiling | Dropped | stdlib `tracemalloc` exists |
| (missing) | Add `restart` | Essential for iteration |
| (missing) | Add output capture | Replaces attach, more useful |
| No migration plan | Add migration strategy | Breaking change risk |
