"""Tests for debug session launch configuration."""

from unittest.mock import Mock

from cc_debugger.daemon_main import DebugSession


class _FakeSocket:
    """Minimal socket stub for launch setup tests."""

    def __init__(self):
        self.connected_to = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def bind(self, addr):
        self.bound_to = addr

    def getsockname(self):
        return ("127.0.0.1", 56789)

    def connect(self, addr):
        self.connected_to = addr

    def close(self):
        return None

    def makefile(self, mode):
        return Mock()


def test_start_uses_requested_python_interpreter(monkeypatch, tmp_path):
    launch_requests = []
    sockets = [_FakeSocket(), _FakeSocket()]

    monkeypatch.setattr("cc_debugger.daemon_main.time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("cc_debugger.daemon_main.socket.socket", lambda *args, **kwargs: sockets.pop(0))
    monkeypatch.setattr("cc_debugger.daemon_main.subprocess.Popen", lambda *args, **kwargs: Mock())
    monkeypatch.setattr("cc_debugger.daemon_main.threading.Thread", lambda *args, **kwargs: Mock(start=lambda: None))

    def fake_send(self, command, args):
        launch_requests.append((command, args))
        return len(launch_requests)

    monkeypatch.setattr(DebugSession, "_send", fake_send)
    monkeypatch.setattr(
        DebugSession,
        "_wait_event",
        lambda self, event_type, timeout=60: {"body": {"threadId": 7}},
    )

    session = DebugSession()
    target_file = tmp_path / "app.py"
    target_file.write_text("print('ok')\n")
    python_path = str(tmp_path / ".venv" / "bin" / "python")
    cwd = str(tmp_path / "workspace")

    session.start(str(target_file), [], stop_on_entry=True, python_path=python_path, cwd=cwd)

    launch_command, launch_args = next(
        (command, args) for command, args in launch_requests if command == "launch"
    )
    assert launch_command == "launch"
    assert launch_args["python"] == [python_path]
    assert "pythonPath" not in launch_args
    assert launch_args["cwd"] == cwd
