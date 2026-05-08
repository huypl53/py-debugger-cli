#!/usr/bin/env python3
"""Debug daemon main entry point."""

import json
import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from cc_debugger.models.session import get_session_dir

logger = logging.getLogger("cc_debugger.daemon")


class DebugSession:
    """Manages the debugpy connection."""

    def __init__(self) -> None:
        self.adapter_process: subprocess.Popen[bytes] | None = None
        self.sock: socket.socket | None = None
        self.sock_file: Any = None
        self.seq: int = 0
        self.pending: dict[int, Queue[dict[str, Any]]] = {}
        self.events: Queue[dict[str, Any]] = Queue()
        self._running: bool = False
        self._reader_thread: threading.Thread | None = None
        self.thread_id: int | None = None
        self.target_file: str | None = None
        self._events_lock = threading.Lock()  # Protects event queue operations
        # Store launch args for restart
        self.launch_args: list[str] = []
        self.stop_on_entry: bool = True

    def start(self, target_file: str, args: list[str], stop_on_entry: bool = True, python_path: str | None = None) -> dict[str, Any]:
        """Start debug session.

        Args:
            target_file: Path to Python file to debug
            args: Arguments to pass to the program
            stop_on_entry: Whether to stop at first line
            python_path: Python interpreter to use for target (None = use cc-debug's Python)
        """
        self.target_file = target_file
        self.launch_args = args
        self.stop_on_entry = stop_on_entry
        self.python_path = python_path or sys.executable

        # Find free port for adapter
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            adapter_port = s.getsockname()[1]

        # Start adapter using cc-debug's Python (has debugpy installed)
        self.adapter_process = subprocess.Popen(
            [sys.executable, "-m", "debugpy.adapter", "--host", "127.0.0.1", "--port", str(adapter_port)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Connect with retries
        time.sleep(0.5)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connected = False
        for _ in range(20):
            try:
                self.sock.connect(("127.0.0.1", adapter_port))
                connected = True
                break
            except ConnectionRefusedError:
                time.sleep(0.1)

        if not connected:
            self.sock.close()
            self.sock = None
            if self.adapter_process:
                self.adapter_process.terminate()
            raise ConnectionError("Could not connect to adapter")

        self.sock_file = self.sock.makefile("rwb")
        self._running = True

        # Start reader BEFORE sending any messages
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        time.sleep(0.1)  # Give reader time to start

        # Initialize
        self._send("initialize", {
            "clientID": "cc-debugger",
            "adapterID": "python",
            "pathFormat": "path",
            "linesStartAt1": True,
            "supportsVariableType": True,
        })
        time.sleep(0.2)  # Wait for response

        # Launch with specified Python interpreter
        launch_config = {
            "program": target_file,
            "args": args,
            "cwd": str(Path(target_file).parent),
            "stopOnEntry": stop_on_entry,
            "console": "internalConsole",
            "justMyCode": True,
        }
        if self.python_path != sys.executable:
            launch_config["pythonPath"] = self.python_path
        self._send("launch", launch_config)
        time.sleep(0.2)

        # ConfigurationDone
        self._send("configurationDone", {})

        if stop_on_entry:
            # Wait for stopped event with longer timeout
            ev = self._wait_event("stopped", timeout=60)
            self.thread_id = ev["body"].get("threadId", 1)
            return ev
        else:
            # With --no-stop, program is running - get thread ID and return
            time.sleep(0.3)  # Give program time to start
            try:
                resp = self.send_and_wait("threads", {}, timeout=5)
                threads = resp.get("body", {}).get("threads", [])
                if threads:
                    self.thread_id = threads[0].get("id", 1)
                else:
                    self.thread_id = 1
            except Exception:
                self.thread_id = 1
            return {"body": {"reason": "running", "threadId": self.thread_id}}

    def _read_loop(self) -> None:
        """Background message reader."""
        while self._running:
            try:
                if not self.sock_file:
                    return
                header = b""
                while b"\r\n\r\n" not in header:
                    b = self.sock_file.read(1)
                    if not b:
                        return
                    header += b

                length = 0
                for line in header.decode().split("\r\n"):
                    if line.startswith("Content-Length:"):
                        length = int(line.split(":")[1].strip())
                        break
                else:
                    continue

                body = self.sock_file.read(length).decode()
                msg = json.loads(body)

                mtype = msg.get("type")

                if mtype == "response":
                    seq = msg.get("request_seq")
                    if seq in self.pending:
                        self.pending[seq].put(msg)
                elif mtype == "event":
                    with self._events_lock:
                        self.events.put(msg)
            except (json.JSONDecodeError, OSError, ValueError):
                if self._running:
                    continue
                break

    def _send(self, command: str, args: dict[str, Any]) -> int:
        """Send DAP request."""
        self.seq += 1
        msg = {"seq": self.seq, "type": "request", "command": command, "arguments": args}
        body = json.dumps(msg)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        if self.sock_file:
            self.sock_file.write(header.encode() + body.encode())
            self.sock_file.flush()
        return self.seq

    def _recv_response(self, seq: int | None = None, timeout: float = 30) -> dict[str, Any]:
        """Wait for response."""
        if seq is None:
            seq = self.seq
        if seq not in self.pending:
            self.pending[seq] = Queue()
        try:
            return self.pending[seq].get(timeout=timeout)
        except Empty:
            raise TimeoutError("Response timeout") from None
        finally:
            if seq in self.pending:
                del self.pending[seq]

    def _wait_event(self, event_type: str, timeout: float | None = None) -> dict[str, Any]:
        """Wait for event."""
        pending: list[dict[str, Any]] = []
        while True:
            try:
                ev = self.events.get(timeout=timeout)
            except Empty:
                with self._events_lock:
                    for e in pending:
                        self.events.put(e)
                raise TimeoutError(f"Event {event_type} timeout") from None

            if ev.get("event") == event_type:
                with self._events_lock:
                    for e in pending:
                        self.events.put(e)
                return ev
            pending.append(ev)

    def send_and_wait(self, command: str, args: dict[str, Any], timeout: float = 30) -> dict[str, Any]:
        """Send request and wait for response."""
        seq = self._send(command, args)
        self.pending[seq] = Queue()
        return self._recv_response(seq, timeout)

    def step_and_wait(self, step_type: str, timeout: float = 30) -> dict[str, Any]:
        """Execute step and wait for stopped."""
        self._send(step_type, {"threadId": self.thread_id})
        return self._wait_event("stopped", timeout)

    def get_location(self) -> dict[str, Any]:
        """Get current location."""
        resp = self.send_and_wait("stackTrace", {"threadId": self.thread_id, "levels": 1})
        frames = resp.get("body", {}).get("stackFrames", [])
        if frames:
            f = frames[0]
            return {
                "file": f.get("source", {}).get("path"),
                "line": f.get("line"),
                "function": f.get("name"),
            }
        return {"file": self.target_file, "line": 1, "function": "<module>"}

    def terminate(self) -> None:
        """Terminate session."""
        self._running = False
        try:
            self._send("disconnect", {"terminateDebuggee": True})
        except (OSError, BrokenPipeError, TimeoutError) as e:
            logger.debug("Disconnect failed (expected during shutdown): %s", e)
        if self.adapter_process:
            try:
                self.adapter_process.terminate()
                self.adapter_process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.adapter_process.kill()
                except OSError as e:
                    logger.debug("Kill failed (process already dead): %s", e)



class DaemonServer:
    """Server that accepts commands from CLI."""

    def __init__(self, port: int):
        self.port = port
        self.session = None
        self._running = False
        self.prev_vars: dict[str, tuple[str, str]] = {}  # name -> (type, value)
        self.watches: dict[str, str | None] = {}  # expression -> last value
        # Frame navigation state
        self.current_frame_idx: int = 0
        # Breakpoint state (for temp breakpoint management)
        self.breakpoints: dict[str, list[dict]] = {}  # file -> list of breakpoints
        self.temp_breakpoints: dict[str, list[int]] = {}  # file -> list of temp lines
        # Program output capture
        self.output_buffer: list[dict] = []
        self.max_output_lines: int = 1000
        # Trace mode (records stepping events)
        self.trace_active: bool = False
        self.trace_log: list[dict] = []
        self.trace_max: int = 1000
        self.trace_filter: str = ""
        # Recording state
        self.recording = False
        self.checkpoints: list[dict] = []
        self.checkpoint_idx = -1
        self.auto_interval = 0
        self.steps_since_checkpoint = 0
        self.checkpoint_size_bytes = 0
        self.max_checkpoint_bytes = 50 * 1024 * 1024  # 50MB limit
        # Stop reason tracking for 'why' command
        self._last_stop_reason: str = "entry"
        self._prev_watch_values: dict[str, str | None] = {}
        # Track last changed vars from step commands
        self._last_changed_vars: list[str] = []

    def _get_source_context(self, file: str, line: int, context: int = 5) -> list[dict]:
        """Get source lines around current location."""
        try:
            path = Path(file)
            if not path.exists():
                return []
            lines = path.read_text().splitlines()
            start = max(0, line - context - 1)
            end = min(len(lines), line + context)
            result = []
            for i in range(start, end):
                result.append({
                    "number": i + 1,
                    "content": lines[i],
                    "current": i + 1 == line,
                })
            return result
        except Exception:
            return []

    def _get_stack_frames(self, levels: int = 20) -> list[dict]:
        """Get stack frames from debugpy."""
        if not self.session:
            return []
        resp = self.session.send_and_wait("stackTrace", {
            "threadId": self.session.thread_id,
            "levels": levels,
        })
        return resp.get("body", {}).get("stackFrames", [])

    def _get_frame_id(self) -> int:
        """Get frame ID for current frame index."""
        frames = self._get_stack_frames()
        if not frames:
            return 0
        idx = min(self.current_frame_idx, len(frames) - 1)
        return frames[idx].get("id", 0)

    def _reset_frame_idx(self) -> None:
        """Reset frame index to 0 (called after stepping)."""
        self.current_frame_idx = 0

    def _capture_output(self, event: dict) -> None:
        """Capture output event to buffer."""
        if event.get("event") == "output":
            body = event.get("body", {})
            category = body.get("category", "stdout")
            output = body.get("output", "")
            if category in ("stdout", "stderr") and output:
                self.output_buffer.append({
                    "category": category,
                    "output": output,
                })
                while len(self.output_buffer) > self.max_output_lines:
                    self.output_buffer.pop(0)

    def _drain_output_events(self) -> None:
        """Drain pending output events from session's event queue."""
        if not self.session:
            return
        with self.session._events_lock:
            pending = []
            while True:
                try:
                    ev = self.session.events.get_nowait()
                    if ev.get("event") == "output":
                        self._capture_output(ev)
                    else:
                        pending.append(ev)
                except Exception:
                    break
            for ev in pending:
                self.session.events.put(ev)

    def _record_trace(self, loc: dict) -> None:
        """Record a trace entry if tracing is active."""
        if not self.trace_active:
            return
        file = loc.get("file", "")
        if self.trace_filter and self.trace_filter not in file:
            return
        if len(self.trace_log) >= self.trace_max:
            return
        self.trace_log.append({
            "file": file,
            "line": loc.get("line", 0),
            "function": loc.get("function", ""),
        })

    def _expand_variables(self, vars_ref: int, depth: int, visited: set | None = None) -> dict:
        """Recursively expand variables up to depth."""
        if visited is None:
            visited = set()
        if vars_ref in visited:
            return {"__circular__": True}
        visited.add(vars_ref)

        result = {}
        if not self.session or depth < 0:
            return result

        try:
            vars_resp = self.session.send_and_wait("variables", {"variablesReference": vars_ref})
            for v in vars_resp.get("body", {}).get("variables", []):
                var_info: dict = {"type": v.get("type"), "value": v["value"]}
                child_ref = v.get("variablesReference", 0)
                if depth > 0 and child_ref > 0:
                    var_info["children"] = self._expand_variables(child_ref, depth - 1, visited)
                result[v["name"]] = var_info
        except Exception:
            pass

        return result

    def _add_temp_breakpoint(self, file: str, line: int) -> None:
        """Add a temporary breakpoint."""
        if file not in self.temp_breakpoints:
            self.temp_breakpoints[file] = []
        if line not in self.temp_breakpoints[file]:
            self.temp_breakpoints[file].append(line)
        self._sync_breakpoints(file)

    def _remove_temp_breakpoint(self, file: str, line: int) -> None:
        """Remove a temporary breakpoint."""
        if file in self.temp_breakpoints and line in self.temp_breakpoints[file]:
            self.temp_breakpoints[file].remove(line)
        self._sync_breakpoints(file)

    def _sync_breakpoints(self, file: str) -> None:
        """Sync permanent + temp breakpoints to debugpy."""
        if not self.session:
            return
        permanent = self.breakpoints.get(file, [])
        temp_lines = self.temp_breakpoints.get(file, [])
        all_bps = list(permanent)
        for line in temp_lines:
            if not any(bp.get("line") == line for bp in all_bps):
                all_bps.append({"line": line})
        self.session.send_and_wait("setBreakpoints", {
            "source": {"path": file},
            "breakpoints": all_bps,
        })

    def _get_current_vars(self) -> dict[str, tuple[str, str]]:
        """Get current local variables as dict."""
        if not self.session:
            return {}
        stack = self.session.send_and_wait("stackTrace", {"threadId": self.session.thread_id, "levels": 1})
        frames = stack.get("body", {}).get("stackFrames", [])
        if not frames:
            return {}
        frame_id = frames[0]["id"]
        scopes = self.session.send_and_wait("scopes", {"frameId": frame_id})
        result = {}
        for scope in scopes.get("body", {}).get("scopes", []):
            if scope["name"] in ("Locals", "Arguments"):
                vars_resp = self.session.send_and_wait("variables", {
                    "variablesReference": scope["variablesReference"]
                })
                for v in vars_resp.get("body", {}).get("variables", []):
                    if not v["name"].startswith("special ") and not v["name"].startswith("function "):
                        result[v["name"]] = (v.get("type", ""), v["value"])
        return result

    def _detect_changes(self) -> list[str]:
        """Detect changed variables since last check."""
        current = self._get_current_vars()
        changed = []
        for name, (vtype, value) in current.items():
            if name not in self.prev_vars:
                changed.append(name)
            elif self.prev_vars[name] != (vtype, value):
                changed.append(name)
        self.prev_vars = current
        return changed

    def _eval_watches(self) -> dict[str, dict]:
        """Evaluate all watch expressions."""
        if not self.session:
            return {}
        stack = self.session.send_and_wait("stackTrace", {"threadId": self.session.thread_id, "levels": 1})
        frame_id = stack.get("body", {}).get("stackFrames", [{}])[0].get("id", 0)
        results = {}
        for expr, prev_value in self.watches.items():
            try:
                resp = self.session.send_and_wait("evaluate", {
                    "expression": expr,
                    "frameId": frame_id,
                    "context": "watch",
                })
                new_value = resp.get("body", {}).get("result")
                new_type = resp.get("body", {}).get("type")
                results[expr] = {
                    "value": new_value,
                    "type": new_type,
                    "changed": prev_value is not None and new_value != prev_value,
                }
                self.watches[expr] = new_value
            except Exception as e:
                results[expr] = {"value": None, "type": None, "error": str(e), "changed": False}
        return results

    def _create_checkpoint(self, reason: str = "manual") -> dict:
        """Create a checkpoint from current state."""
        from uuid import uuid4
        loc = self.session.get_location() if self.session else {}
        variables = dict(self.prev_vars)  # Copy current vars
        watches = self._eval_watches() if self.watches else {}

        checkpoint = {
            "id": str(uuid4())[:8],
            "sequence": len(self.checkpoints),
            "timestamp": time.time(),
            "reason": reason,
            "location": loc,
            "variables": {k: {"type": v[0], "value": v[1]} for k, v in variables.items()},
            "watches": watches,
        }
        # Track checkpoint size for memory limiting
        cp_size = len(json.dumps(checkpoint))
        self.checkpoint_size_bytes += cp_size
        self.checkpoints.append(checkpoint)
        self.checkpoint_idx = len(self.checkpoints) - 1
        self.steps_since_checkpoint = 0

        # Enforce limits: max 100 checkpoints AND max 50MB total
        while len(self.checkpoints) > 100 or self.checkpoint_size_bytes > self.max_checkpoint_bytes:
            if not self.checkpoints:
                break
            removed = self.checkpoints.pop(0)
            self.checkpoint_size_bytes -= len(json.dumps(removed))
            self.checkpoint_idx -= 1

        return checkpoint

    def _on_step(self) -> dict | None:
        """Called after step, maybe create auto-checkpoint."""
        if not self.recording:
            return None
        self.steps_since_checkpoint += 1
        if self.auto_interval > 0 and self.steps_since_checkpoint >= self.auto_interval:
            return self._create_checkpoint("auto")
        return None

    def handle_command(self, cmd: dict) -> dict:
        """Handle incoming command."""
        action = cmd.get("action")

        try:
            if action == "start":
                if self.session:
                    return {"success": False, "error": "Session already active"}
                self.session = DebugSession()
                self._reset_frame_idx()
                self.breakpoints.clear()
                self.temp_breakpoints.clear()
                stop_on_entry = cmd.get("stop_on_entry", True)
                ev = self.session.start(
                    cmd["target_file"],
                    cmd.get("args", []),
                    stop_on_entry,
                    cmd.get("python"),
                )
                reason = ev["body"].get("reason")
                if reason == "running":
                    # Program is running (--no-stop), can't get location
                    return {
                        "success": True,
                        "state": "running",
                        "message": "Program running. Set breakpoints and use 'pause' or wait for breakpoint hit.",
                        "thread_id": self.session.thread_id,
                    }
                loc = self.session.get_location()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0))
                return {
                    "success": True,
                    "stopped": {
                        "reason": reason,
                        "location": loc,
                        "source_context": source_ctx,
                    },
                    "thread_id": self.session.thread_id,
                }

            elif action == "status":
                if not self.session:
                    return {"success": True, "state": "no_session"}
                loc = self.session.get_location()
                return {"success": True, "state": "stopped", "location": loc}

            elif action == "continue":
                if not self.session:
                    return {"success": False, "error": "No session"}
                self._reset_frame_idx()
                self.session._send("continue", {"threadId": self.session.thread_id})
                ev = self.session._wait_event("stopped", timeout=None)
                self._drain_output_events()
                self._last_stop_reason = ev["body"].get("reason", "breakpoint")
                loc = self.session.get_location()
                self._record_trace(loc)
                changed = self._detect_changes()
                self._last_changed_vars = list(changed)  # Save for vars --changed
                watches = self._eval_watches() if self.watches else {}
                auto_cp = self._on_step()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0), cmd.get("context", 5))
                # Include and clear output buffer
                output_lines = list(self.output_buffer)
                self.output_buffer.clear()
                result = {"success": True, "reason": ev["body"].get("reason"), "location": loc, "changedVars": changed, "watches": watches, "source_context": source_ctx, "output": output_lines}
                if auto_cp:
                    result["checkpoint"] = auto_cp
                return result

            elif action == "next":
                if not self.session:
                    return {"success": False, "error": "No session"}
                self._reset_frame_idx()
                ev = self.session.step_and_wait("next")
                self._drain_output_events()
                self._last_stop_reason = "step"
                loc = self.session.get_location()
                self._record_trace(loc)
                changed = self._detect_changes()
                self._last_changed_vars = list(changed)
                watches = self._eval_watches() if self.watches else {}
                auto_cp = self._on_step()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0), cmd.get("context", 5))
                output_lines = list(self.output_buffer)
                self.output_buffer.clear()
                result = {"success": True, "reason": ev["body"].get("reason"), "location": loc, "changedVars": changed, "watches": watches, "source_context": source_ctx, "output": output_lines}
                if auto_cp:
                    result["checkpoint"] = auto_cp
                return result

            elif action == "step":
                if not self.session:
                    return {"success": False, "error": "No session"}
                self._reset_frame_idx()
                ev = self.session.step_and_wait("stepIn")
                self._drain_output_events()
                self._last_stop_reason = "step"
                loc = self.session.get_location()
                self._record_trace(loc)
                changed = self._detect_changes()
                self._last_changed_vars = list(changed)  # Save for vars --changed
                watches = self._eval_watches() if self.watches else {}
                auto_cp = self._on_step()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0), cmd.get("context", 5))
                output_lines = list(self.output_buffer)
                self.output_buffer.clear()
                result = {"success": True, "reason": ev["body"].get("reason"), "location": loc, "changedVars": changed, "watches": watches, "source_context": source_ctx, "output": output_lines}
                if auto_cp:
                    result["checkpoint"] = auto_cp
                return result

            elif action == "stepout":
                if not self.session:
                    return {"success": False, "error": "No session"}
                self._reset_frame_idx()
                ev = self.session.step_and_wait("stepOut")
                self._drain_output_events()
                self._last_stop_reason = "step"
                loc = self.session.get_location()
                self._record_trace(loc)
                changed = self._detect_changes()
                self._last_changed_vars = list(changed)  # Save for vars --changed
                watches = self._eval_watches() if self.watches else {}
                auto_cp = self._on_step()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0), cmd.get("context", 5))
                output_lines = list(self.output_buffer)
                self.output_buffer.clear()
                result = {"success": True, "reason": ev["body"].get("reason"), "location": loc, "changedVars": changed, "watches": watches, "source_context": source_ctx, "output": output_lines}
                if auto_cp:
                    result["checkpoint"] = auto_cp
                return result

            elif action == "stack":
                if not self.session:
                    return {"success": False, "error": "No session"}
                resp = self.session.send_and_wait("stackTrace", {
                    "threadId": self.session.thread_id,
                    "levels": cmd.get("levels", 20),
                })
                return {"success": True, "frames": resp.get("body", {}).get("stackFrames", []), "current_frame_idx": self.current_frame_idx}

            elif action == "source":
                if not self.session:
                    return {"success": False, "error": "No session"}
                file = cmd.get("file")
                line = cmd.get("line")
                context = cmd.get("context", 5)
                if not file or not line:
                    loc = self.session.get_location()
                    file = file or loc.get("file", "")
                    line = line or loc.get("line", 1)
                source_ctx = self._get_source_context(file, line, context)
                if not source_ctx:
                    return {"success": False, "error": "FILE_NOT_FOUND", "message": f"Cannot read file: {file}"}
                return {"success": True, "file": file, "current_line": line, "lines": source_ctx}

            elif action == "frame_up":
                if not self.session:
                    return {"success": False, "error": "No session"}
                frames = self._get_stack_frames()
                if self.current_frame_idx >= len(frames) - 1:
                    return {"success": False, "error": "AT_TOP_FRAME", "message": "Already at outermost frame"}
                self.current_frame_idx += 1
                frame = frames[self.current_frame_idx]
                file = frame.get("source", {}).get("path", "")
                line = frame.get("line", 1)
                source_ctx = self._get_source_context(file, line)
                return {
                    "success": True,
                    "frame_index": self.current_frame_idx,
                    "frame": {"id": frame.get("id"), "name": frame.get("name"), "file": file, "line": line},
                    "source_context": source_ctx,
                }

            elif action == "frame_down":
                if not self.session:
                    return {"success": False, "error": "No session"}
                if self.current_frame_idx <= 0:
                    return {"success": False, "error": "AT_BOTTOM_FRAME", "message": "Already at innermost frame"}
                self.current_frame_idx -= 1
                frames = self._get_stack_frames()
                frame = frames[self.current_frame_idx]
                file = frame.get("source", {}).get("path", "")
                line = frame.get("line", 1)
                source_ctx = self._get_source_context(file, line)
                return {
                    "success": True,
                    "frame_index": self.current_frame_idx,
                    "frame": {"id": frame.get("id"), "name": frame.get("name"), "file": file, "line": line},
                    "source_context": source_ctx,
                }

            elif action == "run_to_cursor":
                if not self.session:
                    return {"success": False, "error": "No session"}
                file = cmd.get("file")
                line = cmd.get("line")
                if not file or not line:
                    return {"success": False, "error": "INVALID_ARGS", "message": "file and line required"}
                if not Path(file).exists():
                    return {"success": False, "error": "FILE_NOT_FOUND", "message": f"File not found: {file}"}
                self._reset_frame_idx()
                self._add_temp_breakpoint(file, line)
                try:
                    self.session._send("continue", {"threadId": self.session.thread_id})
                    ev = self.session._wait_event("stopped", timeout=None)
                    self._drain_output_events()
                    loc = self.session.get_location()
                    changed = self._detect_changes()
                    watches = self._eval_watches() if self.watches else {}
                    source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0))
                    output_lines = list(self.output_buffer)
                    self.output_buffer.clear()
                    return {
                        "success": True,
                        "reason": ev["body"].get("reason"),
                        "location": loc,
                        "changedVars": changed,
                        "watches": watches,
                        "source_context": source_ctx,
                        "temp_bp_removed": True,
                        "output": output_lines,
                    }
                finally:
                    self._remove_temp_breakpoint(file, line)

            elif action == "until":
                if not self.session:
                    return {"success": False, "error": "No session"}
                target_line = cmd.get("line")
                if not target_line:
                    return {"success": False, "error": "INVALID_ARGS", "message": "line required"}
                loc = self.session.get_location()
                current_file = loc.get("file", "")
                if not current_file or not Path(current_file).exists():
                    return {"success": False, "error": "FILE_NOT_FOUND", "message": "Cannot determine current file"}
                self._reset_frame_idx()
                self._add_temp_breakpoint(current_file, target_line)
                try:
                    self.session._send("continue", {"threadId": self.session.thread_id})
                    ev = self.session._wait_event("stopped", timeout=None)
                    self._drain_output_events()
                    new_loc = self.session.get_location()
                    changed = self._detect_changes()
                    watches = self._eval_watches() if self.watches else {}
                    source_ctx = self._get_source_context(new_loc.get("file", ""), new_loc.get("line", 0))
                    output_lines = list(self.output_buffer)
                    self.output_buffer.clear()
                    return {
                        "success": True,
                        "reason": ev["body"].get("reason"),
                        "location": new_loc,
                        "changedVars": changed,
                        "watches": watches,
                        "source_context": source_ctx,
                        "output": output_lines,
                    }
                finally:
                    self._remove_temp_breakpoint(current_file, target_line)

            elif action == "setvar":
                if not self.session:
                    return {"success": False, "error": "No session"}
                name = cmd.get("name", "")
                value_expr = cmd.get("value", "")
                if not name:
                    return {"success": False, "error": "INVALID_ARGS", "message": "variable name required"}
                frame_id = self._get_frame_id()
                assignment = f"{name} = {value_expr}"
                try:
                    self.session.send_and_wait("evaluate", {
                        "expression": assignment,
                        "frameId": frame_id,
                        "context": "repl",
                    })
                    resp = self.session.send_and_wait("evaluate", {
                        "expression": name,
                        "frameId": frame_id,
                        "context": "watch",
                    })
                    return {
                        "success": True,
                        "variable": name,
                        "expression": assignment,
                        "new_value": resp.get("body", {}).get("result"),
                        "new_type": resp.get("body", {}).get("type"),
                    }
                except Exception as e:
                    return {"success": False, "error": "EVAL_ERROR", "message": str(e)}

            elif action == "vars":
                if not self.session:
                    return {"success": False, "error": "No session"}
                frame_id = self._get_frame_id()
                depth = cmd.get("depth", 0)
                changed_only = cmd.get("changed_only", False)
                limit = cmd.get("limit")
                do_truncate = cmd.get("truncate", True)

                if not frame_id:
                    return {"success": True, "variables": {}, "frame_index": self.current_frame_idx}

                scopes = self.session.send_and_wait("scopes", {"frameId": frame_id})
                all_vars = {}
                for scope in scopes.get("body", {}).get("scopes", []):
                    if scope["name"] in ("Locals", "Arguments"):
                        vars_resp = self.session.send_and_wait("variables", {
                            "variablesReference": scope["variablesReference"]
                        })
                        for v in vars_resp.get("body", {}).get("variables", []):
                            var_info: dict = {"type": v.get("type"), "value": v["value"]}
                            if depth > 0 and v.get("variablesReference", 0) > 0:
                                var_info["children"] = self._expand_variables(v["variablesReference"], depth - 1)
                            all_vars[v["name"]] = var_info

                total_count = len(all_vars)
                # Use saved changed vars from last step (don't call _detect_changes again)
                changed = self._last_changed_vars

                # Apply --changed filter
                if changed_only:
                    all_vars = {k: v for k, v in all_vars.items() if k in changed}

                # Apply --limit
                if limit is not None and limit > 0:
                    from cc_debugger.core.state import limit_variables
                    all_vars = limit_variables(all_vars, limit, list(changed), only_changed=changed_only)

                # Apply truncation
                if do_truncate:
                    from cc_debugger.core.truncate import truncate_variables
                    all_vars = truncate_variables(all_vars)

                return {
                    "success": True,
                    "variables": all_vars,
                    "frame_index": self.current_frame_idx,
                    "changed": list(changed),
                    "total_count": total_count,
                }

            elif action == "eval":
                if not self.session:
                    return {"success": False, "error": "No session"}
                frame_id = self._get_frame_id()
                resp = self.session.send_and_wait("evaluate", {
                    "expression": cmd["expression"],
                    "frameId": frame_id,
                    "context": "repl",
                })
                return {"success": True, "value": resp.get("body", {}).get("result"), "type": resp.get("body", {}).get("type"), "frame_index": self.current_frame_idx}

            elif action == "bp":
                if not self.session:
                    return {"success": False, "error": "No session"}
                file = cmd["file"]
                breakpoints = cmd["breakpoints"]
                self.breakpoints[file] = breakpoints
                self._sync_breakpoints(file)
                return {"success": True, "breakpoints": breakpoints}

            elif action == "bp_exception":
                if not self.session:
                    return {"success": False, "error": "No session"}
                filters = []
                if cmd.get("raised", True):
                    filters.append("raised")
                if cmd.get("uncaught", True):
                    filters.append("uncaught")
                resp = self.session.send_and_wait("setExceptionBreakpoints", {
                    "filters": filters,
                })
                return {"success": True, "filters": filters}

            elif action == "bp_func":
                if not self.session:
                    return {"success": False, "error": "No session"}
                names = cmd.get("names", [])
                resp = self.session.send_and_wait("setFunctionBreakpoints", {
                    "breakpoints": [{"name": n} for n in names],
                })
                bps = resp.get("body", {}).get("breakpoints", [])
                return {"success": True, "breakpoints": bps}

            elif action == "watch_add":
                expr = cmd.get("expression", "")
                if not expr:
                    return {"success": False, "error": "Expression required"}
                self.watches[expr] = None
                return {"success": True, "expression": expr, "count": len(self.watches)}

            elif action == "watch_list":
                values = self._eval_watches() if self.session else {}
                return {"success": True, "watches": list(self.watches.keys()), "values": values}

            elif action == "watch_del":
                expr = cmd.get("expression", "")
                if expr in self.watches:
                    del self.watches[expr]
                    return {"success": True, "removed": expr}
                return {"success": False, "error": f"Watch not found: {expr}"}

            elif action == "watch_clear":
                count = len(self.watches)
                self.watches.clear()
                return {"success": True, "removed": count}

            elif action == "watch_diff":
                # Return only watches that changed since last evaluation
                if not self.watches:
                    return {"success": True, "changed": [], "unchanged_count": 0}
                values = self._eval_watches() if self.session else {}
                changed = []
                unchanged_count = 0
                for expr, info in values.items():
                    if info.get("changed") or info.get("error"):
                        changed.append({
                            "expression": expr,
                            "value": info.get("value"),
                            "type": info.get("type"),
                            "previous": self._prev_watch_values.get(expr) if hasattr(self, "_prev_watch_values") else None,
                            "error": info.get("error"),
                        })
                    else:
                        unchanged_count += 1
                # Store for next diff
                self._prev_watch_values = {expr: info.get("value") for expr, info in values.items()}
                return {"success": True, "changed": changed, "unchanged_count": unchanged_count}

            elif action == "record_start":
                self.recording = True
                self.auto_interval = cmd.get("auto_interval", 0)
                self.checkpoints = []
                self.checkpoint_idx = -1
                # Create initial checkpoint
                if self.session:
                    self._detect_changes()  # Capture current vars
                    self._create_checkpoint("start")
                return {"success": True, "recording": True, "auto_interval": self.auto_interval}

            elif action == "record_stop":
                self.recording = False
                return {"success": True, "recording": False, "checkpoint_count": len(self.checkpoints)}

            elif action == "record_checkpoint":
                if not self.recording:
                    return {"success": False, "error": "Recording not active"}
                reason = cmd.get("reason", "manual")
                cp = self._create_checkpoint(reason)
                return {"success": True, "checkpoint": cp}

            elif action == "record_list":
                return {
                    "success": True,
                    "recording": self.recording,
                    "checkpoints": [
                        {"id": cp["id"], "sequence": cp["sequence"], "reason": cp["reason"],
                         "location": cp["location"], "current": i == self.checkpoint_idx}
                        for i, cp in enumerate(self.checkpoints)
                    ],
                }

            elif action == "step_back":
                if self.checkpoint_idx <= 0:
                    return {"success": False, "error": "At oldest checkpoint"}
                self.checkpoint_idx -= 1
                cp = self.checkpoints[self.checkpoint_idx]
                return {"success": True, "checkpoint": cp}

            elif action == "step_forward":
                if self.checkpoint_idx >= len(self.checkpoints) - 1:
                    return {"success": False, "error": "At newest checkpoint"}
                self.checkpoint_idx += 1
                cp = self.checkpoints[self.checkpoint_idx]
                return {"success": True, "checkpoint": cp}

            elif action == "goto":
                cp_id = cmd.get("checkpoint_id", "")
                for i, cp in enumerate(self.checkpoints):
                    if cp["id"] == cp_id:
                        self.checkpoint_idx = i
                        return {"success": True, "checkpoint": cp}
                return {"success": False, "error": f"Checkpoint not found: {cp_id}"}

            elif action == "record_export":
                output_path = cmd.get("output_file", "")
                if not output_path:
                    return {"success": False, "error": "Output file required"}
                # Security: validate path is safe (no traversal, absolute only)
                try:
                    resolved = Path(output_path).resolve()
                    # Prevent path traversal - must be under home or cwd
                    cwd = Path.cwd().resolve()
                    home = Path.home().resolve()
                    if not (str(resolved).startswith(str(cwd)) or str(resolved).startswith(str(home))):
                        return {"success": False, "error": "Export path must be under home or current directory"}
                except (ValueError, OSError) as e:
                    return {"success": False, "error": f"Invalid path: {e}"}
                data = {"checkpoints": self.checkpoints}
                resolved.write_text(json.dumps(data, indent=2))
                return {"success": True, "file": str(resolved), "checkpoint_count": len(self.checkpoints)}

            elif action == "trace_start":
                if not self.session:
                    return {"success": False, "error": "No session"}
                if self.trace_active:
                    return {"success": False, "error": "TRACE_ALREADY_ACTIVE", "message": "Trace already running"}
                max_entries = cmd.get("max_entries", 1000)
                filter_pattern = cmd.get("filter", "")
                self.trace_active = True
                self.trace_max = max_entries
                self.trace_filter = filter_pattern
                self.trace_log = []
                return {"success": True, "trace_active": True, "max_entries": max_entries, "filter": filter_pattern}

            elif action == "trace_stop":
                if not self.session:
                    return {"success": False, "error": "No session"}
                if not self.trace_active:
                    return {"success": False, "error": "NO_TRACE", "message": "No trace active"}
                self.trace_active = False
                return {"success": True, "trace_active": False}

            elif action == "trace_get":
                limit = cmd.get("limit", 100)
                trace = self.trace_log[-limit:] if self.trace_log else []
                return {"success": True, "trace": trace, "count": len(trace), "trace_active": self.trace_active}

            elif action == "output":
                self._drain_output_events()
                clear = cmd.get("clear", False)
                lines = list(self.output_buffer)
                if clear:
                    self.output_buffer.clear()
                return {"success": True, "lines": lines, "count": len(lines)}

            elif action == "pm_start":
                if self.session:
                    return {"success": False, "error": "Session already active. Quit first."}
                crash_file = cmd.get("crash_file")
                crash_line = cmd.get("crash_line")
                if not crash_file or not crash_line:
                    return {"success": False, "error": "INVALID_ARGS", "message": "crash_file and crash_line required"}
                if not Path(crash_file).exists():
                    return {"success": False, "error": "FILE_NOT_FOUND", "message": f"File not found: {crash_file}"}
                self.session = DebugSession()
                self._reset_frame_idx()
                self.breakpoints.clear()
                self.temp_breakpoints.clear()
                ev = self.session.start(crash_file, [], stop_on_entry=True)
                self.breakpoints[crash_file] = [{"line": crash_line}]
                self._sync_breakpoints(crash_file)
                self.session._send("continue", {"threadId": self.session.thread_id})
                try:
                    stop_ev = self.session._wait_event("stopped", timeout=30)
                    loc = self.session.get_location()
                    source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0))
                    return {
                        "success": True,
                        "mode": "post_mortem",
                        "crash_location": {"file": crash_file, "line": crash_line},
                        "stopped": {
                            "reason": stop_ev["body"].get("reason"),
                            "location": loc,
                            "source_context": source_ctx,
                        },
                        "thread_id": self.session.thread_id,
                    }
                except TimeoutError:
                    loc = {"file": crash_file, "line": crash_line, "function": "unknown"}
                    return {
                        "success": True,
                        "mode": "post_mortem",
                        "crash_location": {"file": crash_file, "line": crash_line},
                        "note": "Program completed or crashed before reaching breakpoint line.",
                        "stopped": {"reason": "entry", "location": loc},
                        "thread_id": self.session.thread_id,
                    }

            elif action == "restart":
                if not self.session:
                    return {"success": False, "error": "No session"}
                target_file = self.session.target_file
                args = cmd.get("args", self.session.launch_args)
                stop_on_entry = self.session.stop_on_entry
                self.session.terminate()
                self.session = None
                self._reset_frame_idx()
                self.breakpoints.clear()
                self.temp_breakpoints.clear()
                self.prev_vars.clear()
                self.session = DebugSession()
                ev = self.session.start(target_file, args, stop_on_entry)
                loc = self.session.get_location()
                source_ctx = self._get_source_context(loc.get("file", ""), loc.get("line", 0))
                return {
                    "success": True,
                    "restarted": True,
                    "stopped": {
                        "reason": ev["body"].get("reason"),
                        "location": loc,
                        "source_context": source_ctx,
                    },
                    "thread_id": self.session.thread_id,
                }

            elif action == "inspect":
                # Batch command: location + vars + stack in one call
                if not self.session:
                    return {"success": False, "error": "No session"}
                compact = cmd.get("compact", False)
                loc = self.session.get_location()
                # Get variables
                frame_id = self._get_frame_id()
                variables = {}
                if frame_id:
                    scopes = self.session.send_and_wait("scopes", {"frameId": frame_id})
                    for scope in scopes.get("body", {}).get("scopes", []):
                        if scope["name"] in ("Locals", "Arguments"):
                            vars_resp = self.session.send_and_wait("variables", {
                                "variablesReference": scope["variablesReference"]
                            })
                            for v in vars_resp.get("body", {}).get("variables", []):
                                variables[v["name"]] = {"type": v.get("type"), "value": v["value"]}
                # Get stack (top 5 frames)
                stack_resp = self.session.send_and_wait("stackTrace", {
                    "threadId": self.session.thread_id,
                    "levels": 5,
                })
                frames = []
                for f in stack_resp.get("body", {}).get("stackFrames", []):
                    frames.append({
                        "name": f.get("name"),
                        "file": f.get("source", {}).get("path"),
                        "line": f.get("line"),
                    })
                if compact:
                    return {
                        "success": True,
                        "data": {
                            "location": f"{loc.get('file', '?')}:{loc.get('line', '?')} ({loc.get('function', '?')})",
                            "var_names": list(variables.keys()),
                            "stack_depth": len(frames),
                        },
                    }
                return {
                    "success": True,
                    "data": {
                        "location": loc,
                        "variables": variables,
                        "stack": frames,
                        "source_context": self._get_source_context(loc.get("file", ""), loc.get("line", 0)),
                    },
                }

            elif action == "snapshot":
                # Full state dump for context recovery
                if not self.session:
                    return {"success": False, "error": "No session"}
                loc = self.session.get_location()
                # Gather all state
                data = {
                    "target_file": self.session.target_file,
                    "location": loc,
                    "source_context": self._get_source_context(loc.get("file", ""), loc.get("line", 0)),
                    "breakpoints": {file: bps for file, bps in self.breakpoints.items()},
                    "watches": list(self.watches.keys()),
                    "watch_values": self._eval_watches() if self.watches else {},
                    "recording": self.recording,
                    "checkpoint_count": len(self.checkpoints),
                    "trace_active": self.trace_active,
                    "output_buffer_size": len(self.output_buffer),
                }
                return {"success": True, "data": data}

            elif action == "summary":
                # One-line state summary
                if not self.session:
                    return {"success": True, "data": {"summary": "no session"}}
                loc = self.session.get_location()
                file_name = loc.get("file", "?").split("/")[-1] if loc.get("file") else "?"
                func = loc.get("function", "?")
                line = loc.get("line", "?")
                watch_count = len(self.watches)
                bp_count = sum(len(bps) for bps in self.breakpoints.values())
                parts = [f"{file_name}:{line} ({func})"]
                if bp_count:
                    parts.append(f"{bp_count} bp")
                if watch_count:
                    parts.append(f"{watch_count} watch")
                if self.recording:
                    parts.append(f"{len(self.checkpoints)} checkpoints")
                if self.trace_active:
                    parts.append("tracing")
                return {"success": True, "data": {"summary": " | ".join(parts)}}

            elif action == "why":
                # Explain why execution stopped
                if not self.session:
                    return {"success": False, "error": "No session"}
                from cc_debugger.core.why import format_why
                loc = self.session.get_location()
                # Determine stop reason from last event or state
                stop_info = {
                    "reason": self._last_stop_reason if hasattr(self, "_last_stop_reason") else "step",
                    "location": loc,
                }
                # Add breakpoint info if stopped at breakpoint
                if hasattr(self, "_last_stop_reason") and self._last_stop_reason == "breakpoint":
                    file = loc.get("file", "")
                    line = loc.get("line", 0)
                    for i, bp in enumerate(self.breakpoints.get(file, [])):
                        if bp.get("line") == line:
                            stop_info["breakpoint_id"] = i + 1
                            if bp.get("condition"):
                                stop_info["condition"] = bp["condition"]
                            break
                result = format_why(stop_info)
                return {"success": True, "data": result}

            elif action == "quit":
                if self.session:
                    self.session.terminate()
                    self.session = None
                self._running = False
                return {"success": True, "message": "Session terminated"}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def run(self):
        """Run the daemon."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", self.port))
        server.listen(5)
        server.settimeout(1.0)

        self._running = True

        while self._running:
            try:
                client, _ = server.accept()
            except TimeoutError:
                continue

            try:
                client.settimeout(300.0)  # 5 minute timeout for long operations
                data = client.recv(65536)
                if data:
                    cmd = json.loads(data.decode())
                    result = self.handle_command(cmd)
                    client.sendall(json.dumps(result).encode())
            except TimeoutError:
                logger.debug("Client timed out, closing connection")
            except Exception as e:
                try:
                    client.sendall(json.dumps({"success": False, "error": str(e)}).encode())
                except OSError as e:
                    logger.debug("Failed to send error response: %s", e)
            finally:
                client.close()

        server.close()
        if self.session:
            self.session.terminate()


def main() -> None:
    """Main entry point for daemon."""
    import os
    import signal

    if os.environ.get("CC_DEBUG_LOG"):
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s %(levelname)s: %(message)s",
            filename=Path.home() / ".cc-debugger" / "daemon.log",
        )

    if len(sys.argv) < 2:
        print("Usage: daemon_main.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])
    daemon = DaemonServer(port)

    def handle_sigterm(signum, frame):
        """Handle SIGTERM for graceful shutdown."""
        logger.debug("Received SIGTERM, shutting down gracefully")
        daemon._running = False
        if daemon.session:
            daemon.session.terminate()
            daemon.session = None

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    daemon.run()


if __name__ == "__main__":
    main()
