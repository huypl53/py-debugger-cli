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
    """Stop the daemon process gracefully."""
    # Try graceful shutdown via quit command first
    if DAEMON_PORT_FILE.exists():
        try:
            _send_to_daemon({"action": "quit"}, timeout=5)
        except Exception:
            pass  # Ignore errors, will kill process below

    # Then kill the process
    if DAEMON_PID_FILE.exists():
        try:
            pid = int(DAEMON_PID_FILE.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            # Wait briefly for graceful shutdown
            import time
            for _ in range(10):
                try:
                    os.kill(pid, 0)  # Check if still alive
                    time.sleep(0.1)
                except ProcessLookupError:
                    break  # Process terminated
            else:
                # Force kill if still alive
                try:
                    os.kill(pid, 9)  # SIGKILL
                except ProcessLookupError:
                    pass
        except (ProcessLookupError, ValueError) as e:
            logger.debug("Stop daemon failed (process already dead): %s", e)
        DAEMON_PID_FILE.unlink(missing_ok=True)

    DAEMON_PORT_FILE.unlink(missing_ok=True)


def _find_project_venv(target_file: str) -> Path | None:
    """Find project venv by walking up from target file."""
    target_path = Path(target_file).resolve()
    search_dir = target_path.parent

    for _ in range(10):  # Max 10 levels up
        venv_path = search_dir / ".venv"
        if venv_path.is_dir():
            python_path = venv_path / "bin" / "python"
            if python_path.exists():
                return python_path
        pyproject = search_dir / "pyproject.toml"
        if pyproject.exists() and (search_dir / ".venv").is_dir():
            return search_dir / ".venv" / "bin" / "python"
        if search_dir.parent == search_dir:
            break
        search_dir = search_dir.parent
    return None


def _ensure_debugpy_in_venv(venv_python: Path) -> bool:
    """Ensure debugpy is installed in the target venv using uv."""
    import shutil

    venv_dir = venv_python.parent.parent
    try:
        # Check if debugpy already installed
        result = subprocess.run(
            [str(venv_python), "-c", "import debugpy"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True

        # Try to install with uv
        if shutil.which("uv"):
            result = subprocess.run(
                ["uv", "pip", "install", "debugpy", "--quiet"],
                cwd=str(venv_dir.parent),
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0

        # Fallback to pip
        pip_path = venv_dir / "bin" / "pip"
        if pip_path.exists():
            result = subprocess.run(
                [str(pip_path), "install", "debugpy", "--quiet"],
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0

        return False
    except Exception:
        return False


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--args", default="", help="Arguments to pass to the program")
@click.option("--no-stop", is_flag=True, help="Don't stop on entry")
@click.option("--python", "python_path", default=None, help="Python interpreter for target (e.g., .venv/bin/python)")
@click.option("--uv", "use_uv", is_flag=True, help="Auto-detect project venv and install debugpy")
def start(file: str, args: str, no_stop: bool, python_path: str | None, use_uv: bool) -> None:
    """Start debugging a Python file.

    Use --python to specify the interpreter for the target script,
    e.g., when the script needs packages from a specific venv.

    Use --uv to auto-detect the project's venv and ensure debugpy is installed.
    """
    try:
        target_file = str(Path(file).resolve())
        session_id = str(uuid4())[:8]

        resolved_python = None

        # Handle --uv flag: auto-detect venv and install debugpy
        if use_uv and not python_path:
            venv_python = _find_project_venv(target_file)
            if venv_python:
                if not _ensure_debugpy_in_venv(venv_python):
                    logger.warning("Failed to install debugpy in project venv, using default Python")
                else:
                    resolved_python = str(venv_python)
        elif python_path:
            resolved_python = str(Path(python_path).resolve())

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
            "python": resolved_python,
        })

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Failed to start"))

        response_data: dict = {
            "sessionId": session_id,
            "file": target_file,
        }
        if result.get("state") == "running":
            response_data["state"] = "running"
            response_data["message"] = result.get("message")
        else:
            response_data["stopped"] = result.get("stopped")

        output_json(format_success("start", response_data))

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
@click.option("--args", default=None, help="New arguments (uses original if not specified)")
def restart(args: str | None) -> None:
    """Restart the debug session with the same or new arguments."""
    try:
        cmd: dict = {"action": "restart"}
        if args is not None:
            cmd["args"] = args.split() if args else []

        result = _send_to_daemon(cmd)

        if not result.get("success"):
            raise RuntimeError(result.get("error", "Restart failed"))

        output_json(format_success("restart", {
            "restarted": True,
            "stopped": result.get("stopped"),
        }))

    except Exception as e:
        output_json(format_error("restart", "RESTART_FAILED", str(e)))
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


@click.command()
@click.argument("traceback_file", type=click.Path())
def pm(traceback_file: str) -> None:
    """Start post-mortem debugging from a traceback file.

    Pass '-' to read from stdin.
    """
    from cc_debugger.core.traceback_parser import get_crash_location, parse_traceback_file

    try:
        frames = parse_traceback_file(traceback_file)

        if not frames:
            output_json(format_error("pm", "NO_TRACEBACK", "No valid traceback found"))
            raise SystemExit(1)

        crash = frames[-1]
        crash_file = crash["file"]
        crash_line = crash["line"]

        if not Path(crash_file).exists():
            output_json(format_error("pm", "FILE_NOT_FOUND", f"Crash file not found: {crash_file}"))
            raise SystemExit(1)

        _stop_daemon()
        _start_daemon()

        result = _send_to_daemon({
            "action": "pm_start",
            "crash_file": crash_file,
            "crash_line": crash_line,
            "frames": frames,
        })

        if not result.get("success"):
            raise RuntimeError(result.get("error", "PM start failed"))

        output_json(format_success("pm", {
            "crash_location": f"{crash_file}:{crash_line}",
            "crash_function": crash.get("function"),
            "crash_code": crash.get("code"),
            "frame_count": len(frames),
            "stopped": result.get("stopped"),
            "source_context": result.get("source_context", []),
        }))

    except FileNotFoundError as e:
        output_json(format_error("pm", "FILE_NOT_FOUND", str(e)))
        raise SystemExit(1) from None
    except SystemExit:
        raise
    except Exception as e:
        _stop_daemon()
        output_json(format_error("pm", "PM_FAILED", str(e)))
        raise SystemExit(1) from None
