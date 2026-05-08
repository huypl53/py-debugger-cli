"""Stop reason formatting for the 'why' command."""

from __future__ import annotations


def format_why(stop_info: dict | None) -> dict:
    """
    Format a human-readable explanation of why execution stopped.

    Args:
        stop_info: Stop event info from debugger, or None if no session

    Returns:
        Dict with 'reason', 'summary', and 'details'
    """
    if stop_info is None:
        return {
            "reason": "no_session",
            "summary": "No active debug session",
            "details": {},
        }

    reason = stop_info.get("reason", "unknown")
    location = stop_info.get("location", {})
    file_path = location.get("file", "?")
    file = file_path.split("/")[-1] if "/" in file_path else file_path  # basename
    line = location.get("line", "?")
    func = location.get("function", "?")

    details: dict = {"file": file, "line": line, "function": func}

    if reason == "entry":
        summary = f"Stopped at entry point: {file}:{line}"

    elif reason == "breakpoint":
        bp_id = stop_info.get("breakpoint_id", "?")
        condition = stop_info.get("condition")
        details["breakpoint_id"] = bp_id
        if condition:
            details["condition"] = condition
            summary = f"Hit conditional breakpoint #{bp_id} ({condition}) at {file}:{line}"
        else:
            summary = f"Hit breakpoint #{bp_id} at {file}:{line}"

    elif reason == "exception":
        exc = stop_info.get("exception", {})
        exc_type = exc.get("type", "Exception")
        exc_msg = exc.get("message", "")
        details["exception"] = exc
        # Truncate long messages
        if len(exc_msg) > 50:
            exc_msg = exc_msg[:47] + "..."
        summary = f"Exception raised: {exc_type}('{exc_msg}') at {file}:{line}"

    elif reason == "step":
        step_type = stop_info.get("step_type", "")
        if step_type == "in":
            summary = f"Stepped into {func}() at {file}:{line}"
        elif step_type == "out":
            summary = f"Stepped out to {func}() at {file}:{line}"
        else:
            summary = f"Step completed at {file}:{line} in {func}()"

    elif reason == "until":
        summary = f"Reached line {line} in {file}"

    elif reason == "exited":
        exit_code = stop_info.get("exit_code", 0)
        details["exit_code"] = exit_code
        summary = f"Program exited with code {exit_code}"

    elif reason == "pause":
        summary = "Paused by user request"

    elif reason == "run_to_cursor":
        summary = f"Reached cursor at {file}:{line}"

    else:
        summary = f"Stopped ({reason}) at {file}:{line}"

    return {
        "reason": reason,
        "summary": summary,
        "details": details,
    }
