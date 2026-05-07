# Phase 5: Smart Breakpoints & Polish

## Metadata
```yaml
phase: 5
status: pending
effort: 1-week
priority: medium
dependencies: [phase-4]
```

## Objective

Implement advanced breakpoint types (exception, watchpoint, function pattern) and polish the overall experience.

## Tasks

### 5.1 Exception Breakpoints
**Effort: 6 hours**

Break when specific exception types are raised:

```python
# src/cc_debugger/commands/breakpoints.py (extend)

@bp.command("exception")
@click.argument("exception_type")
@click.option("--caught/--uncaught", default=False, help="Break on caught exceptions")
def bp_exception(exception_type: str, caught: bool):
    """Break when exception is raised."""
    session = get_active_session()
    
    # DAP setExceptionBreakpoints
    filters = []
    
    if exception_type == "all":
        filters = ["raised", "uncaught"] if caught else ["uncaught"]
    else:
        # Custom exception filter
        # Note: DAP has limited exception filtering
        # We'll use a condition-based approach
        filters = ["raised"] if caught else ["uncaught"]
    
    # Store exception breakpoint config
    session.state.exception_breakpoints.append({
        "type": exception_type,
        "caught": caught
    })
    
    resp = session.client.send_request("setExceptionBreakpoints", {
        "filters": filters,
        "filterOptions": [
            {
                "filterId": "raised" if caught else "uncaught",
                "condition": f"type(exc).__name__ == '{exception_type}'" if exception_type != "all" else None
            }
        ]
    })
    
    session.state.save()
    
    output_json({
        "success": True,
        "command": "bp exception",
        "result": {
            "type": exception_type,
            "caught": caught,
            "active": True
        }
    })

@bp.command("exception-clear")
def bp_exception_clear():
    """Clear all exception breakpoints."""
    session = get_active_session()
    
    session.client.send_request("setExceptionBreakpoints", {
        "filters": []
    })
    
    session.state.exception_breakpoints.clear()
    session.state.save()
    
    output_json({
        "success": True,
        "command": "bp exception-clear"
    })
```

### 5.2 Watchpoints (Data Breakpoints)
**Effort: 8 hours**

Break when variable changes:

```python
# src/cc_debugger/commands/breakpoints.py (extend)

@bp.command("watch")
@click.argument("expression")
@click.option("--access", type=click.Choice(["write", "read", "readWrite"]), default="write")
def bp_watch(expression: str, access: str):
    """Break when expression value changes."""
    session = get_active_session()
    
    # First evaluate to get variablesReference
    frame_id = session.get_current_frame_id()
    
    # Try to get data breakpoint info
    # Note: Not all debuggers support this
    try:
        eval_resp = session.client.send_request("evaluate", {
            "expression": expression,
            "frameId": frame_id,
            "context": "watch"
        })
        
        var_ref = eval_resp["body"].get("variablesReference", 0)
        
        if var_ref == 0:
            # Simple variable - try dataBreakpointInfo
            info_resp = session.client.send_request("dataBreakpointInfo", {
                "name": expression,
                "variablesReference": 0
            })
            
            if not info_resp["body"].get("dataId"):
                raise ValueError(f"Watchpoint not supported for: {expression}")
            
            data_id = info_resp["body"]["dataId"]
        else:
            # Complex expression - use polling approach
            # Store for manual checking
            data_id = None
    
    except Exception as e:
        # Fallback: Use polling-based watchpoint
        # Check value on each step
        session.state.poll_watchpoints.append({
            "expression": expression,
            "access": access,
            "last_value": eval_resp["body"]["result"] if 'eval_resp' in dir() else None
        })
        session.state.save()
        
        output_json({
            "success": True,
            "command": "bp watch",
            "result": {
                "expression": expression,
                "type": "polling",
                "note": "Hardware watchpoint not supported, using step-based checking"
            }
        })
        return
    
    # Set hardware watchpoint if supported
    if data_id:
        resp = session.client.send_request("setDataBreakpoints", {
            "breakpoints": [
                {
                    "dataId": data_id,
                    "accessType": access
                }
            ]
        })
        
        session.state.data_breakpoints.append({
            "dataId": data_id,
            "expression": expression,
            "access": access
        })
        session.state.save()
        
        output_json({
            "success": True,
            "command": "bp watch",
            "result": {
                "expression": expression,
                "dataId": data_id,
                "type": "hardware",
                "access": access
            }
        })
```

### 5.3 Function Pattern Breakpoints
**Effort: 6 hours**

Break on function entry matching pattern:

```python
# src/cc_debugger/commands/breakpoints.py (extend)

import fnmatch

@bp.command("func")
@click.argument("pattern")  # e.g., "*.process_*" or "MyClass.method"
@click.option("--entry/--exit", default=True, help="Break on entry or exit")
def bp_func(pattern: str, entry: bool):
    """Break on function matching pattern."""
    session = get_active_session()
    
    # DAP setFunctionBreakpoints
    session.state.function_breakpoints.append({
        "pattern": pattern,
        "entry": entry
    })
    
    # Convert pattern to function breakpoint
    # Note: DAP function breakpoints are exact matches
    # For patterns, we need workaround
    
    if "*" in pattern or "?" in pattern:
        # Pattern-based: Use instruction breakpoints on CALL opcodes
        # This is complex, fall back to logging
        session.state.function_patterns.append({
            "pattern": pattern,
            "entry": entry,
            "hits": []
        })
        session.state.save()
        
        output_json({
            "success": True,
            "command": "bp func",
            "result": {
                "pattern": pattern,
                "type": "pattern",
                "note": "Will check function names during stepping"
            }
        })
    else:
        # Exact function name
        resp = session.client.send_request("setFunctionBreakpoints", {
            "breakpoints": [
                {"name": pattern}
            ]
        })
        
        bp_info = resp["body"]["breakpoints"][0]
        session.state.save()
        
        output_json({
            "success": True,
            "command": "bp func",
            "result": {
                "pattern": pattern,
                "type": "exact",
                "verified": bp_info.get("verified", False),
                "id": bp_info.get("id")
            }
        })

def check_function_patterns(session, frame_name: str) -> list[dict]:
    """Check if frame matches any function patterns."""
    matches = []
    for fp in session.state.function_patterns:
        if fnmatch.fnmatch(frame_name, fp["pattern"]):
            matches.append({
                "pattern": fp["pattern"],
                "function": frame_name
            })
    return matches
```

### 5.4 Enhanced Error Handling
**Effort: 4 hours**

```python
# src/cc_debugger/errors.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class DebuggerError(Exception):
    code: str
    message: str
    details: Optional[dict] = None
    
    def to_json(self) -> dict:
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.details:
            result["details"] = self.details
        return result

class SessionNotFoundError(DebuggerError):
    def __init__(self, session_id: str = None):
        super().__init__(
            code="SESSION_NOT_FOUND",
            message="No active debug session" if not session_id else f"Session not found: {session_id}"
        )

class AdapterError(DebuggerError):
    def __init__(self, message: str, dap_error: dict = None):
        super().__init__(
            code="ADAPTER_ERROR",
            message=message,
            details=dap_error
        )

class BreakpointError(DebuggerError):
    def __init__(self, message: str, location: dict = None):
        super().__init__(
            code="BREAKPOINT_ERROR",
            message=message,
            details={"location": location} if location else None
        )

class TimeoutError(DebuggerError):
    def __init__(self, operation: str, timeout: float):
        super().__init__(
            code="TIMEOUT",
            message=f"Operation timed out: {operation}",
            details={"timeout_seconds": timeout}
        )

# Error handler decorator
def handle_errors(func):
    """Decorator to catch and format errors as JSON."""
    import functools
    import sys
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DebuggerError as e:
            output_json({
                "success": False,
                "command": func.__name__.replace("_", " "),
                "error": e.to_json()
            })
            sys.exit(1)
        except Exception as e:
            output_json({
                "success": False,
                "command": func.__name__.replace("_", " "),
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "type": type(e).__name__
                }
            })
            sys.exit(1)
    
    return wrapper
```

### 5.5 Session Status Command
**Effort: 2 hours**

```python
# src/cc_debugger/commands/session.py

@click.command()
def status():
    """Show current debug session status."""
    try:
        session = get_active_session()
        
        # Get current location
        location = session.get_current_location()
        
        output_json({
            "success": True,
            "command": "status",
            "result": {
                "sessionId": session.state.id,
                "targetFile": session.state.target_file,
                "state": "stopped",
                "location": location,
                "breakpoints": len(session.state.breakpoints),
                "watches": len(session.state.watches),
                "recording": session.state.recording,
                "checkpoints": len(session.recorder.checkpoints) if session.recorder else 0
            }
        })
        
    except SessionNotFoundError:
        output_json({
            "success": True,
            "command": "status",
            "result": {
                "state": "no_session",
                "message": "No active debug session"
            }
        })
```

### 5.6 Process Cleanup
**Effort: 4 hours**

```python
# src/cc_debugger/core/cleanup.py
import atexit
import signal
import sys
from pathlib import Path

_cleanup_registered = False
_session = None

def register_cleanup(session):
    """Register cleanup handlers for graceful shutdown."""
    global _cleanup_registered, _session
    
    if _cleanup_registered:
        return
    
    _session = session
    
    atexit.register(_cleanup_on_exit)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    
    _cleanup_registered = True

def _cleanup_on_exit():
    """Cleanup on normal exit."""
    if _session and _session.client.process:
        try:
            _session.client.send_request("disconnect", {
                "terminateDebuggee": True
            })
        except:
            pass
        
        try:
            _session.client.process.terminate()
            _session.client.process.wait(timeout=5)
        except:
            _session.client.process.kill()

def _signal_handler(signum, frame):
    """Handle termination signals."""
    _cleanup_on_exit()
    sys.exit(128 + signum)

def cleanup_stale_sessions():
    """Clean up old session files."""
    session_dir = Path.home() / ".cc-debugger" / "sessions"
    
    if not session_dir.exists():
        return
    
    import time
    max_age = 24 * 60 * 60  # 24 hours
    now = time.time()
    
    for session_file in session_dir.glob("*.json"):
        if now - session_file.stat().st_mtime > max_age:
            session_file.unlink()
```

### 5.7 Documentation & README
**Effort: 4 hours**

- [ ] Complete README with examples
- [ ] Claude Code integration guide
- [ ] API reference
- [ ] Troubleshooting guide

```markdown
# README.md

# CC-Debugger

Python debugger CLI designed for coding agents (Claude Code, Cursor, etc.).

## Installation

```bash
pip install cc-debugger
# or
pip install git+https://github.com/user/cc-debugger.git
```

## Quick Start

```bash
# Start debugging
cc-debug start myapp.py

# Set breakpoint
cc-debug bp myapp.py:42

# Run to breakpoint
cc-debug continue
# Returns JSON with location, variables, etc.

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

# Recording
cc-debug record start
cc-debug next
cc-debug step-back  # View previous state

# End session
cc-debug quit
```

## Claude Code Integration

Use with Bash tool:

```
Run: cc-debug start tests/test_app.py
Run: cc-debug bp test_app.py:25
Run: cc-debug continue
```

The JSON output provides structured data for analysis.

## Output Format

All commands return JSON:

```json
{
  "success": true,
  "command": "continue",
  "result": {
    "event": "stopped",
    "reason": "breakpoint",
    "location": {"file": "app.py", "line": 42, "function": "process"},
    "changedVars": ["x", "result"],
    "watches": {"len(items)": {"value": "5", "changed": true}}
  }
}
```
```

### 5.8 Tests & Coverage
**Effort: 6 hours**

- [ ] Integration tests for all commands
- [ ] Edge case tests
- [ ] Error handling tests
- [ ] Coverage > 80%

## Deliverables

- [ ] Exception breakpoints
- [ ] Watchpoints (polling fallback)
- [ ] Function pattern breakpoints
- [ ] Enhanced error handling
- [ ] Status command
- [ ] Process cleanup
- [ ] README & documentation
- [ ] Test coverage > 80%

## Verification

```bash
# Exception breakpoint
cc-debug start tests/fixtures/errors.py
cc-debug bp exception ValueError
cc-debug continue
# Should stop on ValueError

# Watchpoint
cc-debug bp watch "obj.value"
cc-debug continue
# Should stop when obj.value changes

# Function pattern
cc-debug bp func "*.process_*"
cc-debug continue
# Should stop on matching function

# Full test suite
pytest --cov=cc_debugger --cov-report=term-missing
```

## Final Checklist

- [ ] All commands implemented and tested
- [ ] JSON output consistent across all commands
- [ ] Error handling comprehensive
- [ ] Process cleanup reliable
- [ ] Documentation complete
- [ ] PyPI ready (optional)
