# Phase 2: Core Commands

## Metadata
```yaml
phase: 2
status: pending
effort: 1-week
priority: critical
dependencies: [phase-1]
```

## Objective

Implement all core debugging commands: execution control, breakpoints, inspection.

## Tasks

### 2.1 Execution Control Commands
**Effort: 6 hours**

- [ ] `continue` - Run until breakpoint (blocks)
- [ ] `next` - Step over
- [ ] `step` - Step into
- [ ] `stepout` - Step out of function
- [ ] `pause` - Pause execution

```python
# src/cc_debugger/commands/control.py
import click
from ..core.session import get_active_session
from ..output import output_json

@click.command("continue")
def continue_cmd():
    """Continue execution until next breakpoint."""
    session = get_active_session()
    
    # Send continue request
    session.client.send_request("continue", {
        "threadId": session.state.thread_id
    })
    
    # Block until stopped event
    stopped = session.client.wait_for_event("stopped")
    
    # Get location info
    location = session.get_current_location()
    
    output_json({
        "success": True,
        "command": "continue",
        "result": {
            "event": "stopped",
            "reason": stopped["body"]["reason"],
            "location": location,
        }
    })

@click.command()
def next():
    """Step over to next line."""
    session = get_active_session()
    session.client.send_request("next", {
        "threadId": session.state.thread_id
    })
    stopped = session.client.wait_for_event("stopped")
    output_json({
        "success": True,
        "command": "next",
        "result": format_stopped(session, stopped)
    })

@click.command()
def step():
    """Step into function call."""
    session = get_active_session()
    session.client.send_request("stepIn", {
        "threadId": session.state.thread_id
    })
    stopped = session.client.wait_for_event("stopped")
    output_json({
        "success": True,
        "command": "step",
        "result": format_stopped(session, stopped)
    })

@click.command()
def stepout():
    """Step out of current function."""
    session = get_active_session()
    session.client.send_request("stepOut", {
        "threadId": session.state.thread_id
    })
    stopped = session.client.wait_for_event("stopped")
    output_json({
        "success": True,
        "command": "stepout", 
        "result": format_stopped(session, stopped)
    })
```

### 2.2 Breakpoint Commands
**Effort: 8 hours**

- [ ] `bp <file:line>` - Set line breakpoint
- [ ] `bp <file:line> -c "<condition>"` - Conditional breakpoint
- [ ] `bp list` - List all breakpoints
- [ ] `bp del <id>` - Delete breakpoint
- [ ] `bp clear` - Clear all breakpoints

```python
# src/cc_debugger/commands/breakpoints.py
import click
from pathlib import Path
from ..core.session import get_active_session

@click.group()
def bp():
    """Manage breakpoints."""
    pass

@bp.command("set")
@click.argument("location")  # file:line or just line
@click.option("-c", "--condition", help="Break condition")
def bp_set(location: str, condition: str | None):
    """Set a breakpoint at file:line."""
    session = get_active_session()
    
    # Parse location
    if ":" in location:
        file, line = location.rsplit(":", 1)
        file = str(Path(file).resolve())
    else:
        file = session.state.target_file
        line = location
    
    line = int(line)
    
    # Get existing breakpoints for this file
    existing = [b for b in session.state.breakpoints if b["file"] == file]
    
    # Add new breakpoint
    bp_entry = {"file": file, "line": line, "condition": condition}
    session.state.breakpoints.append(bp_entry)
    
    # Send to adapter
    breakpoints = [
        {"line": b["line"], "condition": b.get("condition")}
        for b in session.state.breakpoints
        if b["file"] == file
    ]
    
    resp = session.client.send_request("setBreakpoints", {
        "source": {"path": file},
        "breakpoints": breakpoints
    })
    
    # Get verified breakpoint info
    verified = resp["body"]["breakpoints"]
    bp_id = len(session.state.breakpoints) - 1
    
    session.state.save()
    
    output_json({
        "success": True,
        "command": "bp",
        "result": {
            "id": bp_id,
            "file": file,
            "line": line,
            "condition": condition,
            "verified": verified[-1].get("verified", True)
        }
    })

@bp.command("list")
def bp_list():
    """List all breakpoints."""
    session = get_active_session()
    output_json({
        "success": True,
        "command": "bp list",
        "result": {
            "breakpoints": [
                {"id": i, **bp}
                for i, bp in enumerate(session.state.breakpoints)
            ]
        }
    })

@bp.command("del")
@click.argument("bp_id", type=int)
def bp_del(bp_id: int):
    """Delete a breakpoint."""
    session = get_active_session()
    
    if bp_id >= len(session.state.breakpoints):
        raise ValueError(f"Breakpoint {bp_id} not found")
    
    removed = session.state.breakpoints.pop(bp_id)
    
    # Re-sync breakpoints for this file
    file = removed["file"]
    remaining = [
        {"line": b["line"], "condition": b.get("condition")}
        for b in session.state.breakpoints
        if b["file"] == file
    ]
    
    session.client.send_request("setBreakpoints", {
        "source": {"path": file},
        "breakpoints": remaining
    })
    
    session.state.save()
    
    output_json({
        "success": True,
        "command": "bp del",
        "result": {"removed": removed}
    })

@bp.command("clear")
def bp_clear():
    """Clear all breakpoints."""
    session = get_active_session()
    
    # Get unique files
    files = set(b["file"] for b in session.state.breakpoints)
    
    # Clear from each file
    for file in files:
        session.client.send_request("setBreakpoints", {
            "source": {"path": file},
            "breakpoints": []
        })
    
    count = len(session.state.breakpoints)
    session.state.breakpoints.clear()
    session.state.save()
    
    output_json({
        "success": True,
        "command": "bp clear",
        "result": {"removed": count}
    })
```

### 2.3 Inspection Commands
**Effort: 8 hours**

- [ ] `stack` - Show call stack with frame locals
- [ ] `vars` - Show variables in current scope
- [ ] `vars --all` - Show all scopes
- [ ] `eval <expr>` - Evaluate expression

```python
# src/cc_debugger/commands/inspect.py
import click
from ..core.session import get_active_session

@click.command()
@click.option("--depth", default=10, help="Max frames to show")
def stack(depth: int):
    """Show call stack with locals."""
    session = get_active_session()
    
    # Get stack trace
    resp = session.client.send_request("stackTrace", {
        "threadId": session.state.thread_id,
        "levels": depth
    })
    
    frames = []
    for frame in resp["body"]["stackFrames"]:
        # Get scopes for each frame
        scopes_resp = session.client.send_request("scopes", {
            "frameId": frame["id"]
        })
        
        locals_scope = next(
            (s for s in scopes_resp["body"]["scopes"] if s["name"] == "Locals"),
            None
        )
        
        frame_data = {
            "id": frame["id"],
            "name": frame["name"],
            "file": frame["source"]["path"] if "source" in frame else None,
            "line": frame["line"],
            "locals": {}
        }
        
        if locals_scope:
            vars_resp = session.client.send_request("variables", {
                "variablesReference": locals_scope["variablesReference"]
            })
            frame_data["locals"] = format_variables(vars_resp["body"]["variables"])
        
        frames.append(frame_data)
    
    output_json({
        "success": True,
        "command": "stack",
        "result": {"frames": frames}
    })

@click.command()
@click.option("--all", "show_all", is_flag=True, help="Show all scopes")
@click.option("--depth", default=3, help="Max nested depth")
def vars(show_all: bool, depth: int):
    """Show variables in current scope."""
    session = get_active_session()
    
    # Get current frame
    stack_resp = session.client.send_request("stackTrace", {
        "threadId": session.state.thread_id,
        "levels": 1
    })
    frame_id = stack_resp["body"]["stackFrames"][0]["id"]
    
    # Get scopes
    scopes_resp = session.client.send_request("scopes", {
        "frameId": frame_id
    })
    
    result = {}
    for scope in scopes_resp["body"]["scopes"]:
        if not show_all and scope["name"] not in ("Locals", "Arguments"):
            continue
        
        vars_resp = session.client.send_request("variables", {
            "variablesReference": scope["variablesReference"]
        })
        
        result[scope["name"]] = format_variables(
            vars_resp["body"]["variables"],
            session=session,
            max_depth=depth
        )
    
    output_json({
        "success": True,
        "command": "vars",
        "result": result
    })

@click.command("eval")
@click.argument("expression")
def eval_cmd(expression: str):
    """Evaluate an expression in current context."""
    session = get_active_session()
    
    # Get current frame
    stack_resp = session.client.send_request("stackTrace", {
        "threadId": session.state.thread_id,
        "levels": 1
    })
    frame_id = stack_resp["body"]["stackFrames"][0]["id"]
    
    # Evaluate
    resp = session.client.send_request("evaluate", {
        "expression": expression,
        "frameId": frame_id,
        "context": "repl"
    })
    
    body = resp["body"]
    output_json({
        "success": True,
        "command": "eval",
        "result": {
            "expression": expression,
            "value": body["result"],
            "type": body.get("type"),
            "variablesReference": body.get("variablesReference", 0)
        }
    })

def format_variables(variables: list, session=None, max_depth: int = 3, current_depth: int = 0) -> dict:
    """Format variables for JSON output."""
    result = {}
    for var in variables:
        value = {
            "type": var.get("type", "unknown"),
            "value": var["value"]
        }
        
        # Handle nested structures
        if var.get("variablesReference", 0) > 0 and current_depth < max_depth:
            if session:
                nested_resp = session.client.send_request("variables", {
                    "variablesReference": var["variablesReference"]
                })
                value["children"] = format_variables(
                    nested_resp["body"]["variables"],
                    session=session,
                    max_depth=max_depth,
                    current_depth=current_depth + 1
                )
        elif var.get("variablesReference", 0) > 0:
            value["truncated"] = True
        
        result[var["name"]] = value
    
    return result
```

### 2.4 Helper Functions
**Effort: 4 hours**

- [ ] `get_active_session()` - Load/create session
- [ ] `get_current_location()` - Get file:line:function
- [ ] `format_stopped()` - Format stopped event for output
- [ ] Variable formatting with previews

```python
# src/cc_debugger/core/helpers.py
from pathlib import Path
from .session import Session, SessionState, SESSION_DIR

_active_session: Session | None = None

def get_active_session() -> Session:
    """Get or restore active debug session."""
    global _active_session
    
    if _active_session:
        return _active_session
    
    # Find most recent session file
    session_files = list(SESSION_DIR.glob("*.json"))
    if not session_files:
        raise RuntimeError("No active debug session. Use 'cc-debug start' first.")
    
    latest = max(session_files, key=lambda p: p.stat().st_mtime)
    state = SessionState.load(latest.stem)
    
    # Reconnect to adapter
    _active_session = Session(state)
    _active_session.reconnect()
    
    return _active_session

def format_stopped(session: Session, stopped_event: dict) -> dict:
    """Format stopped event with location and context."""
    body = stopped_event["body"]
    
    # Get current location
    stack = session.client.send_request("stackTrace", {
        "threadId": body["threadId"],
        "levels": 1
    })
    
    frame = stack["body"]["stackFrames"][0]
    
    return {
        "event": "stopped",
        "reason": body["reason"],
        "location": {
            "file": frame["source"]["path"] if "source" in frame else None,
            "line": frame["line"],
            "function": frame["name"]
        },
        "threadId": body["threadId"]
    }
```

### 2.5 CLI Integration
**Effort: 4 hours**

- [ ] Register all commands with Click group
- [ ] Add `--session` option for multi-session support
- [ ] Add `--timeout` option for blocking commands
- [ ] Improve error messages

### 2.6 Tests
**Effort: 6 hours**

- [ ] Test breakpoint set/delete/clear
- [ ] Test step commands
- [ ] Test variable inspection
- [ ] Test expression evaluation
- [ ] Integration tests with sample scripts

## Deliverables

- [ ] All execution control commands working
- [ ] Breakpoint management complete
- [ ] Variable inspection with nested structures
- [ ] Expression evaluation
- [ ] Tests for all commands

## Verification

```bash
# Full debugging flow
cc-debug start tests/fixtures/loop.py

# Set breakpoint
cc-debug bp loop.py:10
# {"success": true, "result": {"id": 0, "line": 10, ...}}

# Continue to breakpoint
cc-debug continue
# {"success": true, "result": {"event": "stopped", "reason": "breakpoint", ...}}

# Inspect
cc-debug stack
cc-debug vars
cc-debug eval "len(items)"

# Step
cc-debug next
cc-debug step
cc-debug stepout

# Cleanup
cc-debug bp clear
cc-debug quit
```
