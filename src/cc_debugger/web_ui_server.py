"""Web UI server for CC-Debugger monitoring dashboard."""

import json
import socket
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from cc_debugger.models.session import get_daemon_port_file, get_session_dir

app = FastAPI(title="CC-Debugger Web UI")

# Path to static HTML
STATIC_HTML = Path(__file__).parent / "web_ui" / "static" / "index.html"


def read_port_file() -> int | None:
    """Read daemon port from file."""
    port_file = get_daemon_port_file()
    if port_file.exists():
        return int(port_file.read_text().strip())
    return None


def send_to_daemon(cmd: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    """Send command to debugger daemon and get response."""
    port = read_port_file()
    if not port:
        return {"success": False, "error": "Daemon not running (no port file). Start debugging with 'cc-debug start <file>' first."}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("127.0.0.1", port))
        sock.sendall(json.dumps(cmd).encode())
        data = sock.recv(65536)
        sock.close()
        if data:
            return json.loads(data.decode())
        return {"success": False, "error": "No response from daemon"}
    except TimeoutError:
        return {"success": False, "error": "Command timed out. The debugger may be waiting for input or the program has finished."}
    except ConnectionRefusedError:
        return {"success": False, "error": "Connection refused - daemon not running. Start debugging with 'cc-debug start <file>' first."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Active WebSocket connections
connected_clients: list[WebSocket] = []
clients_lock = threading.Lock()


async def broadcast_state() -> None:
    """Broadcast current debugger state to all connected clients."""
    snapshot = send_to_daemon({"action": "snapshot"})
    inspect = send_to_daemon({"action": "inspect"})

    if snapshot.get("success"):
        data = snapshot.get("data", {})
        if inspect.get("success"):
            inspect_data = inspect.get("data", {})
            data["variables"] = inspect_data.get("variables", {})
            data["stack"] = inspect_data.get("stack", [])
        state = {"success": True, "data": data}
    else:
        state = snapshot

    async with clients_lock:
        for client in connected_clients:
            try:
                await client.send_json(state)
            except Exception:
                pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time debugger state updates."""
    await websocket.accept()
    async with clients_lock:
        connected_clients.append(websocket)
    try:
        snapshot = send_to_daemon({"action": "snapshot"})
        inspect = send_to_daemon({"action": "inspect"})

        if snapshot.get("success"):
            data = snapshot.get("data", {})
            if inspect.get("success"):
                inspect_data = inspect.get("data", {})
                data["variables"] = inspect_data.get("variables", {})
                data["stack"] = inspect_data.get("stack", [])
            state = {"success": True, "data": data}
        else:
            state = snapshot

        await websocket.send_json(state)

        while True:
            data = await websocket.receive_text()
            cmd = json.loads(data)
            result = send_to_daemon(cmd)
            await websocket.send_json(result)
            await broadcast_state()
    except WebSocketDisconnect:
        pass
    finally:
        async with clients_lock:
            connected_clients.remove(websocket)


@app.get("/")
async def get_dashboard():
    """Serve the debugger dashboard."""
    if STATIC_HTML.exists():
        return FileResponse(STATIC_HTML)
    return {"error": "Dashboard not found. Make sure web_ui/static/index.html exists."}


@app.get("/api/state")
async def get_state():
    """Get current debugger state - combines snapshot + inspect for full data."""
    snapshot = send_to_daemon({"action": "snapshot"})
    inspect = send_to_daemon({"action": "inspect"})

    if snapshot.get("success"):
        data = snapshot.get("data", {})
        if inspect.get("success"):
            inspect_data = inspect.get("data", {})
            data["variables"] = inspect_data.get("variables", {})
            data["stack"] = inspect_data.get("stack", [])
        return {"success": True, "data": data}
    return snapshot


@app.get("/api/status")
async def get_status():
    """Check if daemon is running."""
    port = read_port_file()
    if port:
        return {"success": True, "running": True, "port": port}
    return {"success": True, "running": False}


@app.post("/api/command")
async def send_command(cmd: dict[str, Any]):
    """Send a command to the debugger."""
    return send_to_daemon(cmd)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)