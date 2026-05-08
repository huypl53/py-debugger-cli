"""Session state models."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def get_session_dir() -> Path:
    """Get session directory scoped to current working directory.

    Each cwd gets its own session directory to allow multiple independent
    debug sessions across different projects.
    """
    cwd = os.getcwd()
    cwd_hash = hashlib.md5(cwd.encode()).hexdigest()[:12]
    return Path.home() / ".cc-debugger" / "sessions" / cwd_hash


def get_daemon_port_file() -> Path:
    return get_session_dir() / "daemon.port"


def get_daemon_pid_file() -> Path:
    return get_session_dir() / "daemon.pid"


@dataclass
class Location:
    """Code location."""

    file: str | None
    line: int
    function: str | None = None
    column: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"line": self.line}
        if self.file:
            result["file"] = self.file
        if self.function:
            result["function"] = self.function
        if self.column is not None:
            result["column"] = self.column
        return result


@dataclass
class BreakpointState:
    """Stored breakpoint state."""

    file: str
    line: int
    condition: str | None = None
    verified: bool = True
    id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "condition": self.condition,
            "verified": self.verified,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BreakpointState":
        return cls(
            file=data["file"],
            line=data["line"],
            condition=data.get("condition"),
            verified=data.get("verified", True),
            id=data.get("id"),
        )


@dataclass
class SessionState:
    """Persistent session state."""

    id: str
    target_file: str
    adapter_pid: int | None = None
    adapter_port: int | None = None
    thread_id: int | None = None
    breakpoints: list[BreakpointState] = field(default_factory=list)
    watches: list[str] = field(default_factory=list)
    exception_breakpoints: list[dict[str, Any]] = field(default_factory=list)
    function_breakpoints: list[dict[str, Any]] = field(default_factory=list)
    data_breakpoints: list[dict[str, Any]] = field(default_factory=list)
    poll_watchpoints: list[dict[str, Any]] = field(default_factory=list)
    function_patterns: list[dict[str, Any]] = field(default_factory=list)
    recording: bool = False
    recording_id: str | None = None

    def save(self) -> None:
        get_session_dir().mkdir(parents=True, exist_ok=True)
        path = get_session_dir() / f"{self.id}.json"
        data = {
            "id": self.id,
            "target_file": self.target_file,
            "adapter_pid": self.adapter_pid,
            "adapter_port": self.adapter_port,
            "thread_id": self.thread_id,
            "breakpoints": [bp.to_dict() for bp in self.breakpoints],
            "watches": self.watches,
            "exception_breakpoints": self.exception_breakpoints,
            "function_breakpoints": self.function_breakpoints,
            "data_breakpoints": self.data_breakpoints,
            "poll_watchpoints": self.poll_watchpoints,
            "function_patterns": self.function_patterns,
            "recording": self.recording,
            "recording_id": self.recording_id,
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        path = get_session_dir() / f"{session_id}.json"
        data = json.loads(path.read_text())
        breakpoints = [BreakpointState.from_dict(bp) for bp in data.get("breakpoints", [])]
        return cls(
            id=data["id"],
            target_file=data["target_file"],
            adapter_pid=data.get("adapter_pid"),
            adapter_port=data.get("adapter_port"),
            thread_id=data.get("thread_id"),
            breakpoints=breakpoints,
            watches=data.get("watches", []),
            exception_breakpoints=data.get("exception_breakpoints", []),
            function_breakpoints=data.get("function_breakpoints", []),
            data_breakpoints=data.get("data_breakpoints", []),
            poll_watchpoints=data.get("poll_watchpoints", []),
            function_patterns=data.get("function_patterns", []),
            recording=data.get("recording", False),
            recording_id=data.get("recording_id"),
        )

    @classmethod
    def get_active(cls) -> "SessionState | None":
        if not get_session_dir().exists():
            return None
        session_files = list(get_session_dir().glob("*.json"))
        if not session_files:
            return None
        latest = max(session_files, key=lambda p: p.stat().st_mtime)
        return cls.load(latest.stem)

    def delete(self) -> None:
        path = get_session_dir() / f"{self.id}.json"
        if path.exists():
            path.unlink()
