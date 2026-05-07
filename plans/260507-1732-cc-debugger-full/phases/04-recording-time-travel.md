# Phase 4: Recording & Time-Travel Debugging

## Metadata
```yaml
phase: 4
status: pending
effort: 1-week
priority: medium
dependencies: [phase-3]
```

## Objective

Implement execution recording and checkpoint-based time-travel debugging.

## Design Decisions

**Full trace vs Checkpoints**: Full execution trace is prohibitively expensive. Instead:
- Record checkpoints at breakpoints, manual triggers, and configurable intervals
- Store enough state to "restore view" (variables, stack, location)
- True re-execution from checkpoint requires process restart (optional advanced feature)

**Time-travel limitations**:
- `step-back` shows previous checkpoint state, doesn't actually reverse execution
- For true reversal, would need to re-run from start to checkpoint-1
- This is a UX improvement for agents to review execution history

## Tasks

### 4.1 Checkpoint Data Model
**Effort: 4 hours**

```python
# src/cc_debugger/core/recorder.py
from dataclasses import dataclass, field
from typing import Any
import time
import json
from pathlib import Path
from uuid import uuid4

@dataclass
class StackFrameSnapshot:
    id: int
    name: str
    file: str | None
    line: int
    locals: dict[str, Any]

@dataclass
class Checkpoint:
    id: str
    sequence: int  # Order in recording
    timestamp: float
    reason: str  # "breakpoint", "step", "manual", "auto"
    location: dict  # {file, line, function}
    stack: list[StackFrameSnapshot]
    variables: dict[str, Any]  # Flattened variable snapshot
    watches: dict[str, Any]  # Watch expression values
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "location": self.location,
            "stack": [
                {
                    "id": f.id,
                    "name": f.name,
                    "file": f.file,
                    "line": f.line,
                    "locals": f.locals
                }
                for f in self.stack
            ],
            "variables": self.variables,
            "watches": self.watches
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            id=data["id"],
            sequence=data["sequence"],
            timestamp=data["timestamp"],
            reason=data["reason"],
            location=data["location"],
            stack=[
                StackFrameSnapshot(**f) for f in data["stack"]
            ],
            variables=data["variables"],
            watches=data.get("watches", {})
        )
```

### 4.2 Recorder Core
**Effort: 8 hours**

```python
# src/cc_debugger/core/recorder.py (continued)

class Recorder:
    def __init__(self, max_checkpoints: int = 100, session_id: str = None):
        self.session_id = session_id or str(uuid4())[:8]
        self.checkpoints: list[Checkpoint] = []
        self.current_idx: int = -1
        self.max_checkpoints = max_checkpoints
        self.recording: bool = False
        self.auto_checkpoint_interval: int = 0  # 0 = disabled
        self.steps_since_checkpoint: int = 0
    
    @property
    def recording_dir(self) -> Path:
        return Path.home() / ".cc-debugger" / "recordings" / self.session_id
    
    def start_recording(self) -> None:
        """Start recording checkpoints."""
        self.recording = True
        self.recording_dir.mkdir(parents=True, exist_ok=True)
    
    def stop_recording(self) -> str:
        """Stop recording and return recording ID."""
        self.recording = False
        self._save_recording()
        return self.session_id
    
    def create_checkpoint(
        self,
        session,
        reason: str = "manual"
    ) -> Checkpoint:
        """Create checkpoint from current session state."""
        if not self.recording:
            raise RuntimeError("Recording not active")
        
        # Get current location
        stack_resp = session.client.send_request("stackTrace", {
            "threadId": session.state.thread_id,
            "levels": 20
        })
        
        frames = []
        variables = {}
        
        for frame_data in stack_resp["body"]["stackFrames"]:
            # Get locals for each frame
            scopes_resp = session.client.send_request("scopes", {
                "frameId": frame_data["id"]
            })
            
            frame_locals = {}
            for scope in scopes_resp["body"]["scopes"]:
                if scope["name"] == "Locals":
                    vars_resp = session.client.send_request("variables", {
                        "variablesReference": scope["variablesReference"]
                    })
                    frame_locals = {
                        v["name"]: {"type": v.get("type"), "value": v["value"]}
                        for v in vars_resp["body"]["variables"]
                    }
                    break
            
            frames.append(StackFrameSnapshot(
                id=frame_data["id"],
                name=frame_data["name"],
                file=frame_data["source"]["path"] if "source" in frame_data else None,
                line=frame_data["line"],
                locals=frame_locals
            ))
            
            # Flatten variables by frame
            variables[f"frame_{frame_data['id']}"] = frame_locals
        
        # Evaluate watches
        watch_values = {}
        if session.state_tracker.watches:
            frame_id = frames[0].id if frames else 0
            watch_values = session.state_tracker.eval_watches(session, frame_id)
        
        top_frame = frames[0] if frames else None
        
        checkpoint = Checkpoint(
            id=str(uuid4())[:8],
            sequence=len(self.checkpoints),
            timestamp=time.time(),
            reason=reason,
            location={
                "file": top_frame.file if top_frame else None,
                "line": top_frame.line if top_frame else 0,
                "function": top_frame.name if top_frame else None
            },
            stack=frames,
            variables=variables,
            watches=watch_values
        )
        
        self.checkpoints.append(checkpoint)
        self.current_idx = len(self.checkpoints) - 1
        
        # Prune old checkpoints
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.pop(0)
            self.current_idx -= 1
        
        self.steps_since_checkpoint = 0
        self._save_checkpoint(checkpoint)
        
        return checkpoint
    
    def on_step(self, session, reason: str = "step") -> Checkpoint | None:
        """Called after each step to maybe create auto-checkpoint."""
        self.steps_since_checkpoint += 1
        
        if self.auto_checkpoint_interval > 0:
            if self.steps_since_checkpoint >= self.auto_checkpoint_interval:
                return self.create_checkpoint(session, reason="auto")
        
        return None
    
    def step_back(self) -> Checkpoint | None:
        """Move to previous checkpoint."""
        if self.current_idx <= 0:
            return None
        
        self.current_idx -= 1
        return self.checkpoints[self.current_idx]
    
    def step_forward(self) -> Checkpoint | None:
        """Move to next checkpoint."""
        if self.current_idx >= len(self.checkpoints) - 1:
            return None
        
        self.current_idx += 1
        return self.checkpoints[self.current_idx]
    
    def goto(self, checkpoint_id: str) -> Checkpoint | None:
        """Jump to specific checkpoint."""
        for i, cp in enumerate(self.checkpoints):
            if cp.id == checkpoint_id:
                self.current_idx = i
                return cp
        return None
    
    def get_current(self) -> Checkpoint | None:
        """Get current checkpoint."""
        if 0 <= self.current_idx < len(self.checkpoints):
            return self.checkpoints[self.current_idx]
        return None
    
    def list_checkpoints(self) -> list[dict]:
        """List all checkpoints (summary)."""
        return [
            {
                "id": cp.id,
                "sequence": cp.sequence,
                "reason": cp.reason,
                "location": cp.location,
                "current": i == self.current_idx
            }
            for i, cp in enumerate(self.checkpoints)
        ]
    
    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint to disk."""
        path = self.recording_dir / f"{checkpoint.sequence:05d}_{checkpoint.id}.json"
        path.write_text(json.dumps(checkpoint.to_dict(), indent=2))
    
    def _save_recording(self) -> None:
        """Save recording metadata."""
        meta = {
            "session_id": self.session_id,
            "checkpoint_count": len(self.checkpoints),
            "created": time.time()
        }
        (self.recording_dir / "meta.json").write_text(json.dumps(meta))
    
    def export(self, output_path: str) -> None:
        """Export recording to single file."""
        data = {
            "session_id": self.session_id,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints]
        }
        Path(output_path).write_text(json.dumps(data, indent=2))
    
    @classmethod
    def load(cls, session_id: str) -> "Recorder":
        """Load recording from disk."""
        recorder = cls(session_id=session_id)
        
        for path in sorted(recorder.recording_dir.glob("*.json")):
            if path.name == "meta.json":
                continue
            data = json.loads(path.read_text())
            recorder.checkpoints.append(Checkpoint.from_dict(data))
        
        recorder.current_idx = len(recorder.checkpoints) - 1
        return recorder
```

### 4.3 Recording Commands
**Effort: 6 hours**

```python
# src/cc_debugger/commands/record.py
import click
from ..core.session import get_active_session
from ..output import output_json

@click.group()
def record():
    """Recording and time-travel commands."""
    pass

@record.command("start")
@click.option("--auto-interval", default=0, help="Auto-checkpoint every N steps")
def record_start(auto_interval: int):
    """Start recording execution."""
    session = get_active_session()
    
    session.recorder.auto_checkpoint_interval = auto_interval
    session.recorder.start_recording()
    session.state.recording = True
    session.state.save()
    
    # Create initial checkpoint
    cp = session.recorder.create_checkpoint(session, reason="start")
    
    output_json({
        "success": True,
        "command": "record start",
        "result": {
            "recordingId": session.recorder.session_id,
            "checkpoint": {
                "id": cp.id,
                "location": cp.location
            }
        }
    })

@record.command("stop")
def record_stop():
    """Stop recording."""
    session = get_active_session()
    
    recording_id = session.recorder.stop_recording()
    session.state.recording = False
    session.state.save()
    
    output_json({
        "success": True,
        "command": "record stop",
        "result": {
            "recordingId": recording_id,
            "checkpoints": len(session.recorder.checkpoints)
        }
    })

@record.command("checkpoint")
@click.option("--reason", default="manual", help="Checkpoint reason")
def record_checkpoint(reason: str):
    """Create manual checkpoint."""
    session = get_active_session()
    
    if not session.recorder.recording:
        raise RuntimeError("Recording not active")
    
    cp = session.recorder.create_checkpoint(session, reason=reason)
    
    output_json({
        "success": True,
        "command": "record checkpoint",
        "result": {
            "id": cp.id,
            "sequence": cp.sequence,
            "location": cp.location
        }
    })

@record.command("list")
def record_list():
    """List all checkpoints."""
    session = get_active_session()
    
    output_json({
        "success": True,
        "command": "record list",
        "result": {
            "recording": session.recorder.recording,
            "checkpoints": session.recorder.list_checkpoints()
        }
    })

@record.command("export")
@click.argument("output_file", type=click.Path())
def record_export(output_file: str):
    """Export recording to file."""
    session = get_active_session()
    
    session.recorder.export(output_file)
    
    output_json({
        "success": True,
        "command": "record export",
        "result": {
            "file": output_file,
            "checkpoints": len(session.recorder.checkpoints)
        }
    })
```

### 4.4 Time-Travel Commands
**Effort: 6 hours**

```python
# src/cc_debugger/commands/time_travel.py
import click
from ..core.session import get_active_session
from ..output import output_json

@click.command("step-back")
def step_back():
    """Step backward to previous checkpoint."""
    session = get_active_session()
    
    cp = session.recorder.step_back()
    
    if not cp:
        output_json({
            "success": False,
            "command": "step-back",
            "error": {
                "code": "NO_PREVIOUS",
                "message": "No previous checkpoint available"
            }
        })
        return
    
    output_json({
        "success": True,
        "command": "step-back",
        "result": {
            "checkpoint": {
                "id": cp.id,
                "sequence": cp.sequence,
                "reason": cp.reason,
                "location": cp.location,
                "stack": [
                    {"name": f.name, "file": f.file, "line": f.line}
                    for f in cp.stack
                ],
                "variables": cp.variables.get(f"frame_{cp.stack[0].id}", {}) if cp.stack else {}
            },
            "note": "This shows historical state. Use 'goto' to re-execute from checkpoint."
        }
    })

@click.command("step-forward")
def step_forward():
    """Step forward to next checkpoint."""
    session = get_active_session()
    
    cp = session.recorder.step_forward()
    
    if not cp:
        output_json({
            "success": False,
            "command": "step-forward",
            "error": {
                "code": "NO_NEXT",
                "message": "No next checkpoint (use 'continue' for live execution)"
            }
        })
        return
    
    output_json({
        "success": True,
        "command": "step-forward",
        "result": format_checkpoint(cp)
    })

@click.command()
@click.argument("checkpoint_id")
def goto(checkpoint_id: str):
    """Jump to specific checkpoint."""
    session = get_active_session()
    
    cp = session.recorder.goto(checkpoint_id)
    
    if not cp:
        output_json({
            "success": False,
            "command": "goto",
            "error": {
                "code": "NOT_FOUND",
                "message": f"Checkpoint not found: {checkpoint_id}"
            }
        })
        return
    
    output_json({
        "success": True,
        "command": "goto",
        "result": format_checkpoint(cp)
    })

def format_checkpoint(cp) -> dict:
    """Format checkpoint for output."""
    return {
        "checkpoint": {
            "id": cp.id,
            "sequence": cp.sequence,
            "reason": cp.reason,
            "location": cp.location,
            "stack": [
                {"name": f.name, "file": f.file, "line": f.line, "locals": f.locals}
                for f in cp.stack
            ],
            "watches": cp.watches
        }
    }
```

### 4.5 Integrate with Step Commands
**Effort: 4 hours**

Update step commands to auto-checkpoint when recording:

```python
# Update control.py

def execute_step_with_recording(session, step_type: str) -> dict:
    """Execute step with optional recording."""
    result = execute_step(session, step_type)
    
    if session.recorder.recording:
        # Check for auto-checkpoint
        auto_cp = session.recorder.on_step(session, reason=step_type)
        if auto_cp:
            result["checkpoint"] = {
                "id": auto_cp.id,
                "auto": True
            }
    
    return result
```

### 4.6 Tests
**Effort: 6 hours**

- [ ] Test checkpoint creation
- [ ] Test step-back/step-forward navigation
- [ ] Test goto by ID
- [ ] Test export/import
- [ ] Test auto-checkpoint intervals
- [ ] Test max checkpoint pruning

## Deliverables

- [ ] Checkpoint-based recording
- [ ] step-back/step-forward commands
- [ ] goto checkpoint command
- [ ] Export recording to file
- [ ] Auto-checkpoint support
- [ ] Tests passing

## Verification

```bash
# Start with recording
cc-debug start tests/fixtures/loop.py
cc-debug record start --auto-interval 5

# Execute some steps
cc-debug continue  # to breakpoint
cc-debug next
cc-debug next
cc-debug record checkpoint --reason "before error"
cc-debug next

# Navigate history
cc-debug step-back
# Shows previous checkpoint state

cc-debug record list
# Shows all checkpoints

cc-debug goto abc123
# Jump to specific checkpoint

# Export
cc-debug record export ./trace.json
cc-debug record stop
```

## Limitations (Document for Users)

1. **View-only time travel**: `step-back` shows historical state but doesn't reverse execution
2. **Re-execution required**: To truly restore execution, process must restart
3. **Memory bounded**: Max 100 checkpoints by default
4. **No I/O reversal**: File/network operations cannot be undone
