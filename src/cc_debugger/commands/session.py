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

from cc_debugger.models.session import get_daemon_pid_file, get_daemon_port_file, get_session_dir
from cc_debugger.output import format_error, format_success, output_json

logger = logging.getLogger("cc_debugger.session")


def _find_free_port() -> int:
    """Find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _send_to_daemon(cmd: dict, timeout: float = 300) -> dict:
    """Send command to daemon and get response."""
    port_file = get_daemon_port_file()
    if not port_file.exists():
        raise RuntimeError("No debug session running. Use 'cc-debug start' first.")

    port = int(port_file.read_text().strip())

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
        get_daemon_port_file().unlink(missing_ok=True)
        get_daemon_pid_file().unlink(missing_ok=True)
        raise RuntimeError("Debug session is no longer running") from None
    finally:
        sock.close()


def _start_daemon() -> int:
    """Start daemon process and return its port."""
    port = _find_free_port()

    session_dir = get_session_dir()
    session_dir.mkdir(parents=True, exist_ok=True)
    log_file = session_dir / "daemon.log"
    # Open log file in append mode, unbuffered or line-buffered
    log_fp = open(log_file, "a", buffering=1)

    # Start daemon process
    daemon_module = Path(__file__).parent.parent / "daemon_main.py"
    proc = subprocess.Popen(
        [sys.executable, str(daemon_module), str(port)],
        stdin=subprocess.DEVNULL,
        stdout=log_fp,
        stderr=log_fp,
        start_new_session=True,
    )

    # Save daemon info
    get_daemon_port_file().write_text(str(port))
    get_daemon_pid_file().write_text(str(proc.pid))

    # Wait for daemon to be ready
    time.sleep(0.3)

    return port


def _stop_daemon():
    """Stop the daemon process gracefully."""
    port_file = get_daemon_port_file()
    pid_file = get_daemon_pid_file()

    # Try graceful shutdown via quit command first
    if port_file.exists():
        try:
            _send_to_daemon({"action": "quit"}, timeout=5)
        except Exception:
            pass  # Ignore errors, will kill process below

    # Then kill the process
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
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
        pid_file.unlink(missing_ok=True)

    port_file.unlink(missing_ok=True)


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
@click.option("--no-stop", is_flag=True, help="Don't stop on entry (recommended for web servers like FastAPI/Uvicorn)")
@click.option("--python", "python_path", default=None, help="Python interpreter for target (e.g., .venv/bin/python)")
@click.option("--uv", "use_uv", is_flag=True, help="Auto-detect project venv and install debugpy")
def start(file: str, args: str, no_stop: bool, python_path: str | None, use_uv: bool) -> None:
    """Start debugging a Python file.

    Use --no-stop when debugging web servers, API services, or long-running daemons
    (e.g., FastAPI, Uvicorn, Flask) so the program starts serving immediately
    without halting at the first line.

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
            # Preserve the venv launcher path instead of resolving symlinks to the base interpreter.
            resolved_python = str(Path(python_path).expanduser().absolute())

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
            "cwd": os.getcwd(),
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
            response = {
                "state": result.get("state"),
                "location": result.get("location"),
            }
            if result.get("reason"):
                response["reason"] = result.get("reason")
            output_json(format_success("status", response))

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
