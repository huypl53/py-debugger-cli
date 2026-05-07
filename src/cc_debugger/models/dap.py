"""DAP (Debug Adapter Protocol) message types."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ProtocolMessage:
    """Base DAP protocol message."""

    seq: int
    type: Literal["request", "response", "event"]


@dataclass
class Request(ProtocolMessage):
    """DAP request message."""

    type: Literal["request"] = field(default="request", init=False)
    command: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "type": self.type,
            "command": self.command,
            "arguments": self.arguments,
        }


@dataclass
class Response(ProtocolMessage):
    """DAP response message."""

    type: Literal["response"] = field(default="response", init=False)
    request_seq: int = 0
    success: bool = True
    command: str = ""
    message: str | None = None
    body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Response":
        return cls(
            seq=data.get("seq", 0),
            request_seq=data.get("request_seq", 0),
            success=data.get("success", True),
            command=data.get("command", ""),
            message=data.get("message"),
            body=data.get("body", {}),
        )


@dataclass
class Event(ProtocolMessage):
    """DAP event message."""

    type: Literal["event"] = field(default="event", init=False)
    event: str = ""
    body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            seq=data.get("seq", 0),
            event=data.get("event", ""),
            body=data.get("body", {}),
        )


@dataclass
class InitializeRequestArguments:
    """Arguments for initialize request."""

    clientID: str = "cc-debugger"
    clientName: str = "CC-Debugger"
    adapterID: str = "python"
    pathFormat: str = "path"
    linesStartAt1: bool = True
    columnsStartAt1: bool = True
    supportsVariableType: bool = True
    supportsVariablePaging: bool = False
    supportsRunInTerminalRequest: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "clientID": self.clientID,
            "clientName": self.clientName,
            "adapterID": self.adapterID,
            "pathFormat": self.pathFormat,
            "linesStartAt1": self.linesStartAt1,
            "columnsStartAt1": self.columnsStartAt1,
            "supportsVariableType": self.supportsVariableType,
            "supportsVariablePaging": self.supportsVariablePaging,
            "supportsRunInTerminalRequest": self.supportsRunInTerminalRequest,
        }


@dataclass
class LaunchRequestArguments:
    """Arguments for launch request."""

    program: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] | None = None
    stopOnEntry: bool = False
    console: str = "internalConsole"
    justMyCode: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "program": self.program,
            "args": self.args,
            "stopOnEntry": self.stopOnEntry,
            "console": self.console,
            "justMyCode": self.justMyCode,
        }
        if self.cwd:
            result["cwd"] = self.cwd
        if self.env:
            result["env"] = self.env
        return result


@dataclass
class Source:
    """DAP source reference."""

    path: str | None = None
    name: str | None = None
    sourceReference: int = 0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.path:
            result["path"] = self.path
        if self.name:
            result["name"] = self.name
        if self.sourceReference:
            result["sourceReference"] = self.sourceReference
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Source":
        return cls(
            path=data.get("path"),
            name=data.get("name"),
            sourceReference=data.get("sourceReference", 0),
        )


@dataclass
class SourceBreakpoint:
    """DAP source breakpoint."""

    line: int
    column: int | None = None
    condition: str | None = None
    hitCondition: str | None = None
    logMessage: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"line": self.line}
        if self.column is not None:
            result["column"] = self.column
        if self.condition:
            result["condition"] = self.condition
        if self.hitCondition:
            result["hitCondition"] = self.hitCondition
        if self.logMessage:
            result["logMessage"] = self.logMessage
        return result


@dataclass
class SetBreakpointsArguments:
    """Arguments for setBreakpoints request."""

    source: Source
    breakpoints: list[SourceBreakpoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "breakpoints": [bp.to_dict() for bp in self.breakpoints],
        }


@dataclass
class StackTraceArguments:
    """Arguments for stackTrace request."""

    threadId: int
    startFrame: int = 0
    levels: int = 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "threadId": self.threadId,
            "startFrame": self.startFrame,
            "levels": self.levels,
        }


@dataclass
class VariablesArguments:
    """Arguments for variables request."""

    variablesReference: int
    filter: str | None = None
    start: int | None = None
    count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"variablesReference": self.variablesReference}
        if self.filter:
            result["filter"] = self.filter
        if self.start is not None:
            result["start"] = self.start
        if self.count is not None:
            result["count"] = self.count
        return result


@dataclass
class StackFrame:
    """DAP stack frame."""

    id: int
    name: str
    line: int
    column: int = 0
    source: Source | None = None
    moduleId: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StackFrame":
        source = None
        if "source" in data:
            source = Source.from_dict(data["source"])
        return cls(
            id=data["id"],
            name=data["name"],
            line=data["line"],
            column=data.get("column", 0),
            source=source,
            moduleId=data.get("moduleId"),
        )


@dataclass
class Scope:
    """DAP scope."""

    name: str
    variablesReference: int
    expensive: bool = False
    namedVariables: int | None = None
    indexedVariables: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scope":
        return cls(
            name=data["name"],
            variablesReference=data["variablesReference"],
            expensive=data.get("expensive", False),
            namedVariables=data.get("namedVariables"),
            indexedVariables=data.get("indexedVariables"),
        )


@dataclass
class Variable:
    """DAP variable."""

    name: str
    value: str
    type: str | None = None
    variablesReference: int = 0
    namedVariables: int | None = None
    indexedVariables: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Variable":
        return cls(
            name=data["name"],
            value=data["value"],
            type=data.get("type"),
            variablesReference=data.get("variablesReference", 0),
            namedVariables=data.get("namedVariables"),
            indexedVariables=data.get("indexedVariables"),
        )


@dataclass
class StoppedEventBody:
    """Body of stopped event."""

    reason: str
    threadId: int | None = None
    allThreadsStopped: bool = True
    hitBreakpointIds: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoppedEventBody":
        return cls(
            reason=data["reason"],
            threadId=data.get("threadId"),
            allThreadsStopped=data.get("allThreadsStopped", True),
            hitBreakpointIds=data.get("hitBreakpointIds", []),
        )
