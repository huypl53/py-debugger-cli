# Core Insights

Accumulated knowledge for future sessions. Each `/baton` reads this file and tests critical paths before completing.

---

## CC-Debug Skill (2026-05-07)

**Critical Path:** Skill invocation → CLI availability check → debugging workflow
**Why Critical:** Skill is useless if cc-debug CLI not installed

**Test Command:**
```bash
# In a Claude Code session (tmux pane)
/cc-debug
# Then: "debug /tmp/test_debug.py"
```

**Gotchas:**
- `cc-debug` CLI must be installed globally or in PATH for skill to work
- Skill gracefully degrades to pdb if cc-debug unavailable
- Exit code 127 = command not found, prompt user to install

**Verification:**
- Skill SKILL.md now includes Prerequisites section with install instructions
- Skill is in both `.claude/skills/cc-debug/` (local) and `~/.claude/skills/cc-debug/` (global)

---

## Daemon Architecture (2026-05-07)

**Critical Path:** `cc-debug start` → daemon launches on port → commands routed via socket
**Why Critical:** All debugging commands depend on daemon running

**Test Command:**
```bash
cc-debug start script.py
cc-debug status  # Should show state: stopped
cc-debug quit
```

**Gotchas:**
- Daemon port/pid stored in `~/.cc-debugger/session/`
- Only one session at a time
- Socket timeout is 300s, launch timeout is 120s
- Enable debug logging: `CC_DEBUG_LOG=1 cc-debug start ...`

---

## Security Hardening (2026-05-07)

**Critical Fixes Applied:**
- Path traversal protection in `record_export`
- Memory limits: 50MB max checkpoint storage
- Socket timeouts prevent hung connections
- Proper exception logging (no silent `pass`)
- Thread-safe event queue with `_events_lock`

**Test Command:**
```bash
# Verify recording export can't escape recordings dir
.venv/bin/pytest tests/ -v
```

**Why Critical:** Security vulnerabilities could allow malicious code execution or data exfiltration

---

## GitHub Distribution (2026-05-07)

**Critical Path:** `uv tool install git+https://github.com/huypl53/py-debugger-cli.git` → cc-debug in PATH
**Why Critical:** Users need working install path

**Test Command:**
```bash
uv tool install git+https://github.com/huypl53/py-debugger-cli.git
which cc-debug && cc-debug --version
```

**Gotchas:**
- debugpy MUST be in runtime dependencies (not dev) for uv tool install to work
- `~/.local/bin` must be in PATH for Claude Code to find cc-debug
- New tmux/Claude sessions may not inherit PATH changes immediately
- Skill gracefully degrades to pdb if cc-debug not found (exit 127)

---

## Plugin Marketplace (2026-05-07)

**Critical Path:** `/plugin marketplace add huypl53/py-debugger-cli` → `/plugin install py-debugger` → `/reload-plugins`
**Why Critical:** Primary distribution method for Claude Code users

**Test Command:**
```bash
# In Claude Code session
/plugin marketplace add huypl53/py-debugger-cli
/plugin install py-debugger
/reload-plugins
/cc-debug
```

**Gotchas:**
- marketplace.json MUST use `"source": "url"` with git URL, NOT `"local"`, `"github"`, or `"git-subdir"`
- Working format: `{"source": "url", "url": "https://github.com/owner/repo.git"}`
- `"source": "local"` only works for plugin-dir local installs, not marketplace
- `"source": "github"` with `repo: "owner/repo"` not supported by Claude Code v2.1.132
- Plugin skill directory structure: `.claude-plugin/skills/cc-debug/SKILL.md`

---

## Bug Fix: Daemon Event Loop Deadlock on Process Termination/Starvation (2026-05-26)

**Category:** bug-fix
**Root cause:** 
- The debugger daemon's main thread blocked synchronously on `_wait_event("stopped", timeout=None)` during execution control commands (like `continue`).
- When the target application has heavy initialization (e.g., uvicorn / fastapi with DB connections, LangGraph setup), the GIL/CPU starvation could cause the debugpy adapter connection to disconnect.
- On disconnect or normal program exit, the adapter socket closed, causing the background reader thread to exit. However, the main thread remained deadlocked waiting on the `events` queue for a `"stopped"` event that would never arrive.
- Subsequent client commands to the daemon failed with connection errors or timed out because the single-threaded daemon was hung.

**Fix:**
- Added `_handle_disconnect()` to `DebugSession` which runs when the adapter connection receives EOF or throws an error. It inserts a `"terminated"` event into the queue.
- Updated `_wait_event()` to immediately return on `"terminated"` or `"exited"` events instead of blocking.
- Handled `"terminated"` / `"exited"` results in the command handlers (`continue`, `next`, `step`, `stepout`, `until`, `run-to-cursor`) by cleanly terminating the debug session, clearing state, and returning a JSON success response indicating program termination.

**Why it matters:** Prevents the debugger daemon from hanging forever and blocking all future CLI commands when the target process crashes, exits, or disconnects.

---

## Debugging Long Async Tasks & Web Servers (2026-05-26)

**Category:** gotcha
**Issue:** 
- In Uvicorn/FastAPI applications, heavy sync startup initialization (e.g. DB connects, model loads) locks the GIL, causing `debugpy` adapter timeouts.
- Background coroutines (scheduled via `asyncio.create_task`) run concurrently inside the async event loop and are fully traceable, but setting breakpoints on definition lines (e.g., `async def ...`) does not trigger debug pauses.
- Interactive `breakpoint()` calls fail or deadlock in Uvicorn processes due to stdin redirection.

**Solutions/Rules:**
- Use `--no-stop` to bypass pause-on-entry and prevent initial startup timeouts/hangs.
- Set line breakpoints *inside* the coroutine body (not on the `async def` definition line) to reliably capture the execution of async tasks.
- Avoid using `breakpoint()` interactively. Rely on client CLI commands (`bp set`, `stack`, `vars`) or logging.

**Why it matters:** Ensures developers can debug long-running async tasks and heavy web applications without triggering connection timeouts or missed breakpoints.

