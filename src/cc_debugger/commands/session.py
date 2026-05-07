"""Session management commands."""

import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import click

from cc_debugger.models.session import SESSION_DIR
from cc_debugger.output import format_error, format_success, output_json

logger = logging.getLogger("cc_debugger.session")

DAEMON_PORT_FILE = SESSION_DIR / "daemon.port"
DAEMON_PID_FILE = SESSION_DIR / "daemon.pid"


def _find_free_port() -> int:
    """Find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _send_to_daemon(cmd: dict, timeout: float = 300) -> dict:
    """Send command to daemon and get response."""
    if not DAEMON_PORT_FILE.exists():
        raise RuntimeError("No debug session running. Use 'cc-debug start' first.")

    port = int(DAEMON_PORT_FILE.read_text().strip())

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect(("127.0.0.1", port))
        sock.sendall(json.dumps(cmd).encode())

        # Read response
        data = b""
        while True:
            try:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data += chunk
            except TimeoutError:
                break

        if not data:
            raise RuntimeError("No response from daemon")

        return json.loads(data.decode())
    except ConnectionRefusedError:
        # Clean up stale files
        DAEMON_PORT_FILE.unlink(missing_ok=True)
        DAEMON_PID_FILE.unlink(missing_ok=True)
        raise RuntimeError("Debug session is no longer running") from None
    finally:
        sock.close()


def _start_daemon() -> int:
    """Start daemon process and return its port."""
    port = _find_free_port()

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    # Start daemon process
    daemon_module = Path(__file__).parent.parent / "daemon_main.py"
    proc = subprocess.Popen(
        [sys.executable, str(daemon_module), str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Save daemon info
    DAEMON_PORT_FILE.write_text(str(port))
    DAEMON_PID_FILE.write_text(str(proc.pid))

    # Wait for daemon to be ready
    time.sleep(0.3)

    return port


def _stop_daemon():
    """Stop the daemon process."""
    if DAEMON_PID_FILE.exists():
        try:
            pid = int(DAEMON_PID_FILE.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
        except (ProcessLookupError, ValueError) as e:
            logger.debug("Stop daemon failed (process already dead): %s", e)
        DAEMON_PID_FILE.unlink(missing_ok=True)

    DAEMON_PORT_FILE.unlink(missing_ok=True)


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--args", default="", help="Arguments to pass to the program")
@click.option("--no-stop", is_flag=True, help="Don't stop on entry")
def start(file: str, args: str, no_stop: bool) -> None:
    """Start debugging a Python file."""
    try:
        target_file = str(Path(file).resolve())
        session_id = str(uuid4())[:8]

        # Stop any existing daemon
        _stop_daemon()

        # Start new daemon
        _start_daemon()

        # Send start command
        result = _send_to_daemon({
            "action": "start",
            "target_file": target_file,
            "args": args.split() if args else [],
            "stop_on_entry": not no_stop,
        })

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Failed to start"))

        output_json(format_success("start", {
            "sessionId": session_id,
            "file": target_file,
            "stopped": result.get("stopped"),
        }))

    except Exception as e:
        _stop_daemon()
        output_json(format_error("start", "START_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command("quit")
def quit_cmd() -> None:
    """End the current debug session."""
    try:
        try:
            _send_to_daemon({"action": "quit"}, timeout=5)
        except RuntimeError as e:
            logger.debug("Quit command failed (daemon already stopped): %s", e)

        _stop_daemon()

        output_json(format_success("quit", {"message": "Debug session ended"}))

    except Exception as e:
        _stop_daemon()
        output_json(format_error("quit", "QUIT_FAILED", str(e)))
        raise SystemExit(1) from None


@click.command()
def status() -> None:
    """Show current debug session status."""
    try:
        result = _send_to_daemon({"action": "status"})

        if result.get("state") == "no_session":
            output_json(format_success("status", {
                "state": "no_session",
                "message": "No active debug session",
            }))
        else:
            output_json(format_success("status", {
                "state": result.get("state"),
                "location": result.get("location"),
            }))

    except RuntimeError:
        output_json(format_success("status", {
            "state": "no_session",
            "message": "No active debug session",
        }))
