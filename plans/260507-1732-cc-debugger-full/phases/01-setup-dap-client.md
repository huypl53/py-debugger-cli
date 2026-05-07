# Phase 1: Project Setup & DAP Client

## Metadata
```yaml
phase: 1
status: pending
effort: 1-week
priority: critical
```

## Objective

Bootstrap project structure and implement minimal DAP client that can communicate with debugpy.

## Tasks

### 1.1 Project Scaffolding
**Effort: 2 hours**

- [ ] Create `pyproject.toml` with dependencies
- [ ] Set up src layout with `cc_debugger` package
- [ ] Configure pytest, ruff, mypy
- [ ] Create CLI entry point with Click

```toml
# pyproject.toml
[project]
name = "cc-debugger"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
]

[project.scripts]
cc-debug = "cc_debugger.cli:main"
```

### 1.2 DAP Message Types
**Effort: 4 hours**

Implement DAP protocol message models using dataclasses/Pydantic:

- [ ] Base message types: Request, Response, Event
- [ ] Lifecycle: InitializeRequest, LaunchRequest, AttachRequest
- [ ] Execution: ContinueRequest, NextRequest, StepInRequest, StepOutRequest
- [ ] Breakpoints: SetBreakpointsRequest, SetExceptionBreakpointsRequest
- [ ] Inspection: StackTraceRequest, ScopesRequest, VariablesRequest, EvaluateRequest
- [ ] Events: StoppedEvent, ContinuedEvent, TerminatedEvent, OutputEvent

```python
# src/cc_debugger/models/dap.py
from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass
class ProtocolMessage:
    seq: int
    type: Literal["request", "response", "event"]

@dataclass
class Request(ProtocolMessage):
    type: Literal["request"] = "request"
    command: str = ""
    arguments: dict = field(default_factory=dict)

@dataclass
class Response(ProtocolMessage):
    type: Literal["response"] = "response"
    request_seq: int = 0
    success: bool = True
    command: str = ""
    message: str | None = None
    body: dict = field(default_factory=dict)

@dataclass
class Event(ProtocolMessage):
    type: Literal["event"] = "event"
    event: str = ""
    body: dict = field(default_factory=dict)

# Specific request types
@dataclass
class InitializeRequestArguments:
    clientID: str = "cc-debugger"
    clientName: str = "CC-Debugger"
    adapterID: str = "python"
    pathFormat: str = "path"
    linesStartAt1: bool = True
    columnsStartAt1: bool = True
    supportsVariableType: bool = True
    supportsVariablePaging: bool = False

@dataclass  
class LaunchRequestArguments:
    program: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] | None = None
    stopOnEntry: bool = False
    console: str = "internalConsole"

@dataclass
class SetBreakpointsArguments:
    source: dict  # {"path": str}
    breakpoints: list[dict]  # [{"line": int, "condition": str?}]

@dataclass
class StackTraceArguments:
    threadId: int
    startFrame: int = 0
    levels: int = 20

@dataclass
class VariablesArguments:
    variablesReference: int
    filter: str | None = None
    start: int | None = None
    count: int | None = None
```

### 1.3 DAP Client Core
**Effort: 8 hours**

Implement transport-agnostic DAP client:

- [ ] Message encoding/decoding (Content-Length header)
- [ ] Sequence number management
- [ ] Request/response correlation
- [ ] Event handling
- [ ] Blocking wait for response

```python
# src/cc_debugger/core/dap_client.py
import json
import subprocess
from dataclasses import dataclass
from typing import Iterator
from queue import Queue
from threading import Thread

@dataclass
class DAPClient:
    process: subprocess.Popen | None = None
    seq: int = 0
    pending: dict[int, Queue] = field(default_factory=dict)
    events: Queue = field(default_factory=Queue)
    
    def connect_stdio(self, cmd: list[str]) -> None:
        """Launch adapter and connect via stdio."""
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Start reader thread
        Thread(target=self._read_messages, daemon=True).start()
    
    def _read_messages(self) -> None:
        """Read DAP messages from stdout."""
        while self.process and self.process.stdout:
            # Read Content-Length header
            header = self.process.stdout.readline().decode()
            if not header.startswith("Content-Length:"):
                continue
            length = int(header.split(":")[1].strip())
            self.process.stdout.readline()  # Empty line
            
            # Read body
            body = self.process.stdout.read(length).decode()
            msg = json.loads(body)
            
            if msg["type"] == "response":
                seq = msg["request_seq"]
                if seq in self.pending:
                    self.pending[seq].put(msg)
            elif msg["type"] == "event":
                self.events.put(msg)
    
    def send_request(self, command: str, arguments: dict = None) -> dict:
        """Send request and wait for response."""
        self.seq += 1
        msg = {
            "seq": self.seq,
            "type": "request",
            "command": command,
            "arguments": arguments or {}
        }
        
        # Set up response queue
        response_queue = Queue()
        self.pending[self.seq] = response_queue
        
        # Send message
        body = json.dumps(msg)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        self.process.stdin.write(header.encode() + body.encode())
        self.process.stdin.flush()
        
        # Wait for response
        response = response_queue.get(timeout=30)
        del self.pending[self.seq]
        return response
    
    def wait_for_event(self, event_type: str, timeout: float = None) -> dict:
        """Wait for specific event type."""
        while True:
            event = self.events.get(timeout=timeout)
            if event["event"] == event_type:
                return event
            # Re-queue non-matching events
            self.events.put(event)
```

### 1.4 Session Manager
**Effort: 6 hours**

Manage debug session lifecycle:

- [ ] Session state persistence
- [ ] Adapter process management
- [ ] Initialization handshake
- [ ] Graceful shutdown

```python
# src/cc_debugger/core/session.py
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from .dap_client import DAPClient

SESSION_DIR = Path.home() / ".cc-debugger" / "sessions"

@dataclass
class SessionState:
    id: str
    target_file: str
    adapter_pid: int | None = None
    thread_id: int | None = None
    breakpoints: list[dict] = field(default_factory=list)
    watches: list[str] = field(default_factory=list)
    recording: bool = False
    
    def save(self) -> None:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        path = SESSION_DIR / f"{self.id}.json"
        path.write_text(json.dumps(asdict(self)))
    
    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        path = SESSION_DIR / f"{session_id}.json"
        data = json.loads(path.read_text())
        return cls(**data)

class Session:
    def __init__(self, state: SessionState):
        self.state = state
        self.client = DAPClient()
    
    def start(self, file: str, args: list[str] = None) -> dict:
        """Start debugging a file."""
        # Launch debugpy adapter
        self.client.connect_stdio([
            "python", "-m", "debugpy.adapter"
        ])
        
        # Initialize
        init_resp = self.client.send_request("initialize", {
            "clientID": "cc-debugger",
            "adapterID": "python",
            "pathFormat": "path",
            "linesStartAt1": True,
            "supportsVariableType": True,
        })
        
        # Wait for initialized event
        self.client.wait_for_event("initialized")
        
        # Launch
        launch_resp = self.client.send_request("launch", {
            "program": file,
            "args": args or [],
            "console": "internalConsole",
            "stopOnEntry": True,
        })
        
        # Wait for stopped event
        stopped = self.client.wait_for_event("stopped")
        self.state.thread_id = stopped["body"]["threadId"]
        self.state.target_file = file
        self.state.save()
        
        return stopped
    
    def terminate(self) -> None:
        """End debug session."""
        self.client.send_request("disconnect", {"terminateDebuggee": True})
        if self.client.process:
            self.client.process.terminate()
```

### 1.5 Basic CLI Structure
**Effort: 4 hours**

- [ ] Click group with subcommands
- [ ] Session management commands (start, quit, status)
- [ ] JSON output helper
- [ ] Error handling wrapper

```python
# src/cc_debugger/cli.py
import click
import json
import sys
from uuid import uuid4
from .core.session import Session, SessionState

def output_json(data: dict) -> None:
    """Output JSON to stdout."""
    click.echo(json.dumps(data, indent=2))

def handle_errors(func):
    """Decorator to catch and format errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            output_json({
                "success": False,
                "error": {
                    "code": type(e).__name__,
                    "message": str(e)
                }
            })
            sys.exit(1)
    return wrapper

@click.group()
def main():
    """CC-Debugger: Python debugger for coding agents."""
    pass

@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--args", default="", help="Arguments to pass")
@handle_errors
def start(file: str, args: str):
    """Start debugging a Python file."""
    session_id = str(uuid4())[:8]
    state = SessionState(id=session_id, target_file=file)
    session = Session(state)
    
    result = session.start(file, args.split() if args else [])
    output_json({
        "success": True,
        "command": "start",
        "result": {
            "sessionId": session_id,
            "stopped": result["body"]
        }
    })

@main.command()
@handle_errors
def quit():
    """End current debug session."""
    # Load active session
    # ...
    output_json({
        "success": True,
        "command": "quit"
    })
```

### 1.6 Tests
**Effort: 4 hours**

- [ ] Unit tests for DAP message encoding/decoding
- [ ] Unit tests for session state persistence
- [ ] Integration test with debugpy (basic start/stop)
- [ ] Mock adapter for testing without debugpy

## Deliverables

- [ ] Working project with `pip install -e .`
- [ ] `cc-debug start <file>` launches debugpy and stops on entry
- [ ] `cc-debug quit` terminates session
- [ ] JSON output for all commands
- [ ] Tests passing

## Verification

```bash
# Install
pip install -e ".[dev]"

# Test basic flow
cc-debug start tests/fixtures/simple.py
# Should output JSON with stopped event

cc-debug quit
# Should output success

# Run tests
pytest tests/
```
