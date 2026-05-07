"""Execution recording and time-travel debugging."""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger("cc_debugger.recorder")


class SessionProtocol(Protocol):
    """Protocol for session objects (duck-typed for testability)."""
    def get_stack_frames(self, levels: int = 20) -> list: ...
    def get_scopes(self, frame_id: int) -> list: ...
    def get_variables(self, variables_ref: int) -> list: ...
    state_tracker: Any


@dataclass
class StackFrameSnapshot:
    """Snapshot of a stack frame."""

    id: int
    name: str
    file: str | None
    line: int
    locals: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file": self.file,
            "line": self.line,
            "locals": self.locals,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StackFrameSnapshot":
        return cls(
            id=data["id"],
            name=data["name"],
            file=data.get("file"),
            line=data["line"],
            locals=data.get("locals", {}),
        )


@dataclass
class Checkpoint:
    """Execution checkpoint for time-travel."""

    id: str
    sequence: int
    timestamp: float
    reason: str
    location: dict[str, Any]
    stack: list[StackFrameSnapshot]
    variables: dict[str, Any]
    watches: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "location": self.location,
            "stack": [f.to_dict() for f in self.stack],
            "variables": self.variables,
            "watches": self.watches,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            id=data["id"],
            sequence=data["sequence"],
            timestamp=data["timestamp"],
            reason=data["reason"],
            location=data["location"],
            stack=[StackFrameSnapshot.from_dict(f) for f in data.get("stack", [])],
            variables=data.get("variables", {}),
            watches=data.get("watches", {}),
        )


class Recorder:
    """Checkpoint-based execution recorder."""

    def __init__(self, max_checkpoints: int = 100, session_id: str | None = None):
        self.session_id = session_id or str(uuid4())[:8]
        self.checkpoints: list[Checkpoint] = []
        self.current_idx: int = -1
        self.max_checkpoints = max_checkpoints
        self.recording: bool = False
        self.auto_checkpoint_interval: int = 0
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

    def create_checkpoint(self, session: SessionProtocol, reason: str = "manual") -> Checkpoint:
        """Create checkpoint from current session state."""
        if not self.recording:
            raise RuntimeError("Recording not active")

        frames = session.get_stack_frames(levels=20)
        frame_snapshots: list[StackFrameSnapshot] = []
        variables: dict[str, Any] = {}

        for frame in frames:
            frame_locals: dict[str, Any] = {}

            try:
                scopes = session.get_scopes(frame.id)
                for scope in scopes:
                    if scope.name == "Locals":
                        vars_list = session.get_variables(scope.variablesReference)
                        frame_locals = {
                            v.name: {"type": v.type, "value": v.value}
                            for v in vars_list
                        }
                        break
            except (AttributeError, KeyError, TypeError) as e:
                logger.warning("Failed to capture locals for frame %s: %s", frame.id, e)

            frame_snapshots.append(StackFrameSnapshot(
                id=frame.id,
                name=frame.name,
                file=frame.source.path if frame.source else None,
                line=frame.line,
                locals=frame_locals,
            ))

            variables[f"frame_{frame.id}"] = frame_locals

        watch_values: dict[str, Any] = {}
        if session.state_tracker and session.state_tracker.watches:
            try:
                frame_id = frames[0].id if frames else 0
                watch_values = {
                    expr: {"value": r.value, "type": r.type, "changed": r.changed}
                    for expr, r in session.state_tracker.eval_watches(session, frame_id).items()
                    if not r.error
                }
            except (AttributeError, KeyError, IndexError) as e:
                logger.warning("Failed to evaluate watches: %s", e)

        top_frame = frames[0] if frames else None

        checkpoint = Checkpoint(
            id=str(uuid4())[:8],
            sequence=len(self.checkpoints),
            timestamp=time.time(),
            reason=reason,
            location={
                "file": top_frame.source.path if top_frame and top_frame.source else None,
                "line": top_frame.line if top_frame else 0,
                "function": top_frame.name if top_frame else None,
            },
            stack=frame_snapshots,
            variables=variables,
            watches=watch_values,
        )

        self.checkpoints.append(checkpoint)
        self.current_idx = len(self.checkpoints) - 1

        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints.pop(0)
            self.current_idx -= 1

        self.steps_since_checkpoint = 0
        self._save_checkpoint(checkpoint)

        return checkpoint

    def on_step(self, session: SessionProtocol, reason: str = "step") -> Checkpoint | None:
        """Called after each step to maybe create auto-checkpoint."""
        if not self.recording:
            return None

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

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all checkpoints (summary)."""
        return [
            {
                "id": cp.id,
                "sequence": cp.sequence,
                "reason": cp.reason,
                "location": cp.location,
                "current": i == self.current_idx,
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
            "created": time.time(),
        }
        (self.recording_dir / "meta.json").write_text(json.dumps(meta))

    def export(self, output_path: str) -> None:
        """Export recording to single file."""
        data = {
            "session_id": self.session_id,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
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
