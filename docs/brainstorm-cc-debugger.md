# CC-Debugger: Python Debugger for Coding Agents

## Problem Statement

Coding agents (Claude Code, Cursor, etc.) lack proper debugging capabilities. They can read stack traces but cannot:
- Set breakpoints programmatically
- Step through execution
- Watch variable state changes
- Inspect call stacks interactively
- Track data flow between functions

## Research Findings

### Debug Adapter Protocol (DAP)
- **Standard**: JSON-RPC based protocol by Microsoft
- **Message types**: Request, Response, Event
- **Key commands**: initialize, launch/attach, setBreakpoints, stackTrace, scopes, variables, evaluate, step commands
- **Adoption**: VSCode, Neovim (nvim-dap), JetBrains, Emacs
- **Source**: [DAP Specification](https://microsoft.github.io/debug-adapter-protocol/specification.html)

### Python Debugging Stack

| Layer | Component | Purpose |
|-------|-----------|---------|
| Protocol | DAP | Standard communication |
| Adapter | debugpy | Python DAP server |
| Client | dap-python | Protocol client library |
| Backend | sys.monitoring (PEP 669) | Low-overhead tracing (Python 3.12+) |
| Legacy | sys.settrace / pdb / bdb | Traditional tracing |

### Existing Solutions Analysis

**1. Microsoft debug-gym** (March 2025)
- Text-based debugging environment for AI agents
- Tools: pdb, eval, view, edit, grep, listdir
- Gym-style interface: `env.reset()` → `env.step(action)`
- Docker-based sandboxing
- **Limitation**: Research-focused, not production-ready CLI tool

**2. LLMDebugger (LDB)**
- Step-by-step runtime verification
- Segments code into basic blocks
- Tracks intermediate variable states
- **Limitation**: Batch mode, not interactive

**3. dap-python**
- Transport-agnostic DAP client
- Pydantic models for type safety
- Supports subprocess, socket, asyncio
- **Best fit**: Foundation for DAP client component

**4. debugpy**
- Microsoft's official Python DAP adapter
- Modes: listen, attach, launch
- Programmatic API: `debugpy.listen()`, `breakpoint()`
- **Best fit**: Use as debug adapter backend

### Performance Comparison

| Approach | Overhead | Python Version |
|----------|----------|----------------|
| sys.settrace | 10-700x slowdown | All |
| sys.monitoring | Near-zero | 3.12+ |
| pdb (settrace backend) | 10x | All |
| pdb (monitoring backend) | ~1.1x | 3.14+ |

## Architecture Options

### Option A: DAP Client (Recommended)

```
┌─────────────────────────────────────────────────────────┐
│                    Coding Agent                         │
│              (Claude Code, Cursor, etc.)                │
└─────────────────────┬───────────────────────────────────┘
                      │ Text commands (JSON)
┌─────────────────────▼───────────────────────────────────┐
│                  CC-Debugger CLI                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Command     │  │ State       │  │ Output          │  │
│  │ Parser      │  │ Manager     │  │ Formatter       │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │                  │           │
│  ┌──────▼────────────────▼──────────────────▼────────┐  │
│  │              DAP Client (dap-python)              │  │
│  └─────────────────────┬────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────┘
                          │ DAP Protocol (JSON-RPC)
┌─────────────────────────▼───────────────────────────────┐
│                    debugpy Adapter                       │
│           (manages Python debugging session)             │
└─────────────────────────┬───────────────────────────────┘
                          │ pydevd / sys.monitoring
┌─────────────────────────▼───────────────────────────────┐
│                   Target Python Process                  │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Industry standard protocol
- Works with any DAP-compliant adapter
- Rich ecosystem (debugpy, future adapters)
- Supports remote debugging

**Cons:**
- Extra process overhead
- More complex setup

### Option B: Direct pdb Extension

```
┌─────────────────────────────────────────────────────────┐
│                    Coding Agent                         │
└─────────────────────┬───────────────────────────────────┘
                      │ Text commands
┌─────────────────────▼───────────────────────────────────┐
│                  CC-Debugger CLI                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │            Extended Pdb Class                    │    │
│  │  - JSON output mode                             │    │
│  │  - State tracking                               │    │
│  │  - Variable watching                            │    │
│  │  - Call graph tracing                           │    │
│  └─────────────────────┬───────────────────────────┘    │
└─────────────────────────┼───────────────────────────────┘
                          │ sys.monitoring (3.12+)
┌─────────────────────────▼───────────────────────────────┐
│                   Target Python Process                  │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Simpler, single-process
- Lower latency
- Easier to embed

**Cons:**
- Python-only
- Less ecosystem support

### Option C: Hybrid (Best of Both)

```
┌─────────────────────────────────────────────────────────┐
│                  CC-Debugger CLI                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Unified Interface                   │    │
│  │  - Agent-friendly commands                      │    │
│  │  - JSON structured output                       │    │
│  │  - State change tracking                        │    │
│  └─────────────────────┬───────────────────────────┘    │
│           ┌────────────┴────────────┐                   │
│           ▼                         ▼                   │
│  ┌─────────────────┐     ┌─────────────────────┐       │
│  │  DAP Backend    │     │  Direct Backend      │       │
│  │  (via debugpy)  │     │  (pdb + monitoring)  │       │
│  └─────────────────┘     └─────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

## Proposed Feature Set

### Core Commands (MVP)

| Command | Description | Output |
|---------|-------------|--------|
| `start <file>` | Start debugging session | Session ID |
| `attach <pid>` | Attach to running process | Session ID |
| `bp <file:line>` | Set breakpoint | Breakpoint ID |
| `bp -c <cond>` | Conditional breakpoint | Breakpoint ID |
| `run` | Run to breakpoint | Stop reason, location |
| `next` / `step` / `out` | Step execution | New location, changed vars |
| `continue` | Continue execution | Stop reason, location |
| `stack` | Show call stack | Frame list with locals |
| `vars` | Show current scope variables | Variable tree (JSON) |
| `watch <expr>` | Watch expression | Current value |
| `eval <expr>` | Evaluate expression | Result |
| `quit` | End session | - |

### Agent-Optimized Features

1. **Structured JSON Output**
   ```json
   {
     "event": "stopped",
     "reason": "breakpoint",
     "location": {"file": "app.py", "line": 42},
     "changedVars": ["x", "result"],
     "stack": [{"name": "process", "line": 42, "locals": {...}}]
   }
   ```

2. **State Diff Tracking**
   - Track variable changes between steps
   - Highlight mutations in data structures
   - Show data flow between function calls

3. **Smart Breakpoints**
   - Break on exception types
   - Break on variable mutation
   - Break on function entry/exit with pattern matching

4. **Execution Recording**
   - Record execution trace for replay
   - Time-travel debugging (step backward)
   - Export trace for analysis

5. **Context Compression**
   - Summarize large data structures
   - Limit output depth/breadth
   - Configurable verbosity levels

## Technical Decisions

### Recommended Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | sys.monitoring support |
| Protocol | DAP | Industry standard |
| Adapter | debugpy | Microsoft-maintained, robust |
| Client | dap-python or custom | Type-safe, async-ready |
| CLI | Click + Rich | Clean UX, structured output |
| Output | JSON | Agent-parseable |

### Key Design Principles

1. **Text-First**: All interactions via text commands and JSON responses
2. **Stateless Commands**: Each command is self-contained (no REPL state assumptions)
3. **Minimal Output**: Only relevant changes, not full state dumps
4. **Fail-Safe**: Clear error messages, graceful degradation
5. **Extensible**: Plugin architecture for new backends/features

## Implementation Phases

### Phase 1: MVP (2 weeks)
- Basic CLI with start/attach/breakpoint/step/vars
- JSON output mode
- debugpy backend integration
- Single-file debugging

### Phase 2: State Tracking (1 week)
- Variable change detection
- Watch expressions
- Call stack with locals

### Phase 3: Advanced Features (2 weeks)
- Conditional breakpoints
- Exception breakpoints
- Data flow tracking
- Execution recording

### Phase 4: Polish (1 week)
- Context compression
- Performance optimization
- Documentation
- Claude Code integration guide

## Risk Analysis

| Risk | Mitigation |
|------|------------|
| debugpy complexity | Start with minimal DAP subset |
| Performance overhead | Use sys.monitoring on 3.12+ |
| Process management | Use subprocess with proper cleanup |
| Async code debugging | Leverage debugpy's async support |

## Open Questions

1. **Scope**: Should we support languages beyond Python?
2. **Integration**: MCP server or standalone CLI?
3. **Sandboxing**: Docker integration like debug-gym?
4. **Recording**: Full trace or sampled checkpoints?

## References

- [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/)
- [debugpy](https://github.com/microsoft/debugpy)
- [dap-python](https://pypi.org/project/dap-python/)
- [nvim-dap](https://github.com/mfussenegger/nvim-dap)
- [debug-gym](https://github.com/microsoft/debug-gym)
- [LLMDebugger](https://github.com/FloridSleeves/LLMDebugger)
- [PEP 669 - sys.monitoring](https://peps.python.org/pep-0669/)
- [Python pdb](https://docs.python.org/3/library/pdb.html)
