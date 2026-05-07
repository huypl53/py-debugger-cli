# Phase 3: State Tracking & Watch Expressions

## Metadata
```yaml
phase: 3
status: pending
effort: 1-week
priority: high
dependencies: [phase-2]
```

## Objective

Track variable state changes between steps and implement watch expressions.

## Tasks

### 3.1 State Tracker Core
**Effort: 8 hours**

Implement state tracking with diff detection:

```python
# src/cc_debugger/core/state.py
from dataclasses import dataclass, field
from typing import Any
import copy

@dataclass
class VariableSnapshot:
    name: str
    type: str
    value: str
    hash: int  # For change detection
    children: dict = field(default_factory=dict)

@dataclass
class FrameSnapshot:
    frame_id: int
    function: str
    variables: dict[str, VariableSnapshot] = field(default_factory=dict)

class StateTracker:
    def __init__(self):
        self.snapshots: dict[int, FrameSnapshot] = {}
        self.watches: dict[str, Any] = {}  # expr -> last_value
        self.watch_results: dict[str, dict] = {}
    
    def capture_frame(self, session, frame_id: int) -> set[str]:
        """Capture frame state, return changed variable names."""
        # Get variables from DAP
        scopes = session.client.send_request("scopes", {"frameId": frame_id})
        
        locals_scope = next(
            (s for s in scopes["body"]["scopes"] if s["name"] == "Locals"),
            None
        )
        
        if not locals_scope:
            return set()
        
        vars_resp = session.client.send_request("variables", {
            "variablesReference": locals_scope["variablesReference"]
        })
        
        # Build current snapshot
        current_vars = {}
        for var in vars_resp["body"]["variables"]:
            snapshot = VariableSnapshot(
                name=var["name"],
                type=var.get("type", "unknown"),
                value=var["value"],
                hash=hash((var.get("type"), var["value"]))
            )
            current_vars[var["name"]] = snapshot
        
        # Compare with previous snapshot
        prev_snapshot = self.snapshots.get(frame_id)
        changed = set()
        
        if prev_snapshot:
            prev_vars = prev_snapshot.variables
            
            # New or changed variables
            for name, snap in current_vars.items():
                if name not in prev_vars:
                    changed.add(name)
                elif prev_vars[name].hash != snap.hash:
                    changed.add(name)
            
            # Removed variables (function returned, etc)
            for name in prev_vars:
                if name not in current_vars:
                    changed.add(f"-{name}")  # Prefix with - for removed
        else:
            # First capture, all are "new"
            changed = set(current_vars.keys())
        
        # Update snapshot
        self.snapshots[frame_id] = FrameSnapshot(
            frame_id=frame_id,
            function="",  # Filled by caller
            variables=current_vars
        )
        
        return changed
    
    def add_watch(self, expression: str) -> None:
        """Add a watch expression."""
        self.watches[expression] = None  # Initial value unknown
    
    def remove_watch(self, expression: str) -> bool:
        """Remove a watch expression."""
        if expression in self.watches:
            del self.watches[expression]
            if expression in self.watch_results:
                del self.watch_results[expression]
            return True
        return False
    
    def eval_watches(self, session, frame_id: int) -> dict[str, dict]:
        """Evaluate all watch expressions, track changes."""
        results = {}
        
        for expr, prev_value in self.watches.items():
            try:
                resp = session.client.send_request("evaluate", {
                    "expression": expr,
                    "frameId": frame_id,
                    "context": "watch"
                })
                
                new_value = resp["body"]["result"]
                new_type = resp["body"].get("type", "unknown")
                
                results[expr] = {
                    "value": new_value,
                    "type": new_type,
                    "changed": prev_value is not None and new_value != prev_value,
                    "error": None
                }
                
                self.watches[expr] = new_value
                
            except Exception as e:
                results[expr] = {
                    "value": None,
                    "type": None,
                    "changed": False,
                    "error": str(e)
                }
        
        self.watch_results = results
        return results
    
    def get_diff_summary(self, frame_id: int) -> dict:
        """Get summary of changes for a frame."""
        snapshot = self.snapshots.get(frame_id)
        if not snapshot:
            return {"added": [], "modified": [], "removed": []}
        
        # This would need previous state comparison
        # For now, return current state
        return {
            "variables": {
                name: {"type": v.type, "value": v.value}
                for name, v in snapshot.variables.items()
            }
        }
```

### 3.2 Integrate State Tracking with Commands
**Effort: 6 hours**

Modify step commands to include state changes:

```python
# Update src/cc_debugger/commands/control.py

def execute_step(session, step_type: str) -> dict:
    """Execute a step command with state tracking."""
    tracker = session.state_tracker
    
    # Capture pre-step state
    frame_id = session.get_current_frame_id()
    
    # Execute step
    command = {
        "next": "next",
        "step": "stepIn", 
        "stepout": "stepOut"
    }[step_type]
    
    session.client.send_request(command, {
        "threadId": session.state.thread_id
    })
    
    # Wait for stopped
    stopped = session.client.wait_for_event("stopped")
    
    # Capture post-step state
    new_frame_id = session.get_current_frame_id()
    changed_vars = tracker.capture_frame(session, new_frame_id)
    watch_results = tracker.eval_watches(session, new_frame_id)
    
    # Get location
    location = session.get_current_location()
    
    return {
        "event": "stopped",
        "reason": stopped["body"]["reason"],
        "location": location,
        "changedVars": list(changed_vars),
        "watches": watch_results
    }
```

### 3.3 Watch Commands
**Effort: 4 hours**

```python
# src/cc_debugger/commands/watch.py
import click
from ..core.session import get_active_session

@click.group()
def watch():
    """Manage watch expressions."""
    pass

@watch.command("add")
@click.argument("expression")
def watch_add(expression: str):
    """Add a watch expression."""
    session = get_active_session()
    session.state_tracker.add_watch(expression)
    session.state.watches.append(expression)
    session.state.save()
    
    # Evaluate immediately
    frame_id = session.get_current_frame_id()
    results = session.state_tracker.eval_watches(session, frame_id)
    
    output_json({
        "success": True,
        "command": "watch add",
        "result": {
            "expression": expression,
            "current": results.get(expression)
        }
    })

@watch.command("list")
def watch_list():
    """List all watch expressions."""
    session = get_active_session()
    
    output_json({
        "success": True,
        "command": "watch list",
        "result": {
            "watches": list(session.state_tracker.watches.keys()),
            "values": session.state_tracker.watch_results
        }
    })

@watch.command("del")
@click.argument("expression")
def watch_del(expression: str):
    """Remove a watch expression."""
    session = get_active_session()
    
    if not session.state_tracker.remove_watch(expression):
        raise ValueError(f"Watch not found: {expression}")
    
    session.state.watches.remove(expression)
    session.state.save()
    
    output_json({
        "success": True,
        "command": "watch del",
        "result": {"removed": expression}
    })

@watch.command("clear")
def watch_clear():
    """Clear all watch expressions."""
    session = get_active_session()
    
    count = len(session.state_tracker.watches)
    session.state_tracker.watches.clear()
    session.state_tracker.watch_results.clear()
    session.state.watches.clear()
    session.state.save()
    
    output_json({
        "success": True,
        "command": "watch clear",
        "result": {"removed": count}
    })
```

### 3.4 Enhanced Output Format
**Effort: 4 hours**

Update output to highlight changes:

```python
# src/cc_debugger/output/json_formatter.py
from typing import Any
import json

class OutputFormatter:
    def __init__(self, max_depth: int = 5, max_items: int = 100):
        self.max_depth = max_depth
        self.max_items = max_items
    
    def format_stopped_event(
        self,
        reason: str,
        location: dict,
        changed_vars: list[str],
        watches: dict,
        stack: list[dict] | None = None
    ) -> dict:
        """Format a stopped event with state changes highlighted."""
        result = {
            "event": "stopped",
            "reason": reason,
            "location": location,
        }
        
        if changed_vars:
            result["changedVars"] = changed_vars
        
        if watches:
            result["watches"] = {
                expr: {
                    "value": w["value"],
                    "type": w["type"],
                    "changed": w["changed"]
                }
                for expr, w in watches.items()
                if not w.get("error")
            }
            
            # Report watch errors separately
            errors = {
                expr: w["error"]
                for expr, w in watches.items()
                if w.get("error")
            }
            if errors:
                result["watchErrors"] = errors
        
        if stack:
            result["stack"] = self._format_stack(stack)
        
        return result
    
    def format_variable(self, var: dict, depth: int = 0) -> dict:
        """Format a variable with truncation for large structures."""
        formatted = {
            "type": var.get("type", "unknown"),
            "value": self._truncate_value(var["value"])
        }
        
        if var.get("variablesReference", 0) > 0:
            if depth < self.max_depth:
                formatted["expandable"] = True
            else:
                formatted["truncated"] = True
        
        return formatted
    
    def _truncate_value(self, value: str, max_len: int = 200) -> str:
        """Truncate long values."""
        if len(value) > max_len:
            return value[:max_len] + "..."
        return value
    
    def _format_stack(self, frames: list[dict]) -> list[dict]:
        """Format stack frames with locals summary."""
        return [
            {
                "id": f["id"],
                "name": f["name"],
                "file": f.get("file"),
                "line": f.get("line"),
                "locals": self._summarize_locals(f.get("locals", {}))
            }
            for f in frames
        ]
    
    def _summarize_locals(self, locals_dict: dict) -> dict:
        """Summarize locals for stack view."""
        if len(locals_dict) > 10:
            # Only show first 10 vars
            items = list(locals_dict.items())[:10]
            summary = dict(items)
            summary["..."] = f"{len(locals_dict) - 10} more"
            return summary
        return locals_dict
```

### 3.5 Data Structure Change Detection
**Effort: 6 hours**

Detect changes within mutable data structures:

```python
# src/cc_debugger/core/deep_diff.py
from typing import Any

def compute_variable_hash(var_data: dict, session, max_depth: int = 3) -> int:
    """Compute hash for variable including nested structure."""
    if max_depth <= 0:
        return hash(var_data["value"])
    
    ref = var_data.get("variablesReference", 0)
    if ref == 0:
        # Primitive value
        return hash((var_data.get("type"), var_data["value"]))
    
    # Fetch children and hash them
    try:
        resp = session.client.send_request("variables", {
            "variablesReference": ref
        })
        
        child_hashes = []
        for child in resp["body"]["variables"]:
            child_hash = compute_variable_hash(child, session, max_depth - 1)
            child_hashes.append((child["name"], child_hash))
        
        return hash(tuple(sorted(child_hashes)))
    except:
        return hash(var_data["value"])

def diff_variables(old: dict, new: dict) -> dict:
    """Compute diff between two variable snapshots."""
    diff = {
        "added": [],
        "removed": [],
        "modified": []
    }
    
    old_names = set(old.keys())
    new_names = set(new.keys())
    
    diff["added"] = list(new_names - old_names)
    diff["removed"] = list(old_names - new_names)
    
    for name in old_names & new_names:
        if old[name].hash != new[name].hash:
            diff["modified"].append({
                "name": name,
                "old": {"type": old[name].type, "value": old[name].value},
                "new": {"type": new[name].type, "value": new[name].value}
            })
    
    return diff
```

### 3.6 Tests
**Effort: 6 hours**

- [ ] Test state capture
- [ ] Test change detection
- [ ] Test watch expressions
- [ ] Test nested structure tracking
- [ ] Integration tests

## Deliverables

- [ ] StateTracker with diff detection
- [ ] Watch expression management
- [ ] Changed variables in step output
- [ ] Nested structure change detection
- [ ] Tests passing

## Verification

```bash
# Start debugging
cc-debug start tests/fixtures/state_changes.py

# Add watches
cc-debug watch add "len(items)"
cc-debug watch add "total > 100"

# Step and observe changes
cc-debug next
# {"success": true, "result": {
#   "event": "stopped",
#   "changedVars": ["i", "item"],
#   "watches": {
#     "len(items)": {"value": "5", "changed": false},
#     "total > 100": {"value": "False", "changed": true}
#   }
# }}

# List watches
cc-debug watch list
```
