"""Error types for CC-Debugger."""

from dataclasses import dataclass
from typing import Any


@dataclass
class DebuggerError(Exception):
    """Base debugger error with structured output."""

    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class SessionNotFoundError(DebuggerError):
    """No active debug session."""

    def __init__(self, session_id: str | None = None):
        msg = "No active debug session" if not session_id else f"Session not found: {session_id}"
        super().__init__(code="SESSION_NOT_FOUND", message=msg)


class AdapterError(DebuggerError):
    """Error from debug adapter."""

    def __init__(self, message: str, dap_error: dict[str, Any] | None = None):
        super().__init__(code="ADAPTER_ERROR", message=message, details=dap_error)


class BreakpointError(DebuggerError):
    """Breakpoint operation error."""

    def __init__(self, message: str, location: dict[str, Any] | None = None):
        details = {"location": location} if location else None
        super().__init__(code="BREAKPOINT_ERROR", message=message, details=details)


class TimeoutError(DebuggerError):
    """Operation timed out."""

    def __init__(self, operation: str, timeout: float):
        super().__init__(
            code="TIMEOUT",
            message=f"Operation timed out: {operation}",
            details={"timeout_seconds": timeout},
        )


class RecordingError(DebuggerError):
    """Recording/time-travel error."""

    def __init__(self, message: str):
        super().__init__(code="RECORDING_ERROR", message=message)


class EvaluationError(DebuggerError):
    """Expression evaluation error."""

    def __init__(self, expression: str, message: str):
        super().__init__(
            code="EVALUATION_ERROR",
            message=message,
            details={"expression": expression},
        )
