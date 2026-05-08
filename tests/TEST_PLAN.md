# Test Plan: Token-Efficient Debugging Features

## Overview

Test suites for 5 new features:
1. `vars --changed` - show only changed variables
2. `vars --limit N` - limit number of variables shown
3. `watch diff` - show only changed watches
4. `cc-debug why` - explain stop reason
5. Auto-truncate large values

---

## 1. Feature: `vars --changed`

### Description
Show only variables that changed since last stop. Reduces token usage by filtering unchanged vars.

### Test Fixtures Needed

**fixtures/var_changes.py**
```python
def main():
    x = 1      # line 2
    y = 2      # line 3
    x = 10     # line 4 - x changes
    z = 3      # line 5 - z is new
    y = y      # line 6 - y unchanged
    x = x + 1  # line 7 - x changes again
```

### Unit Tests (test_vars_changed.py)

| Test ID | Test Name | Description | Input | Expected Output |
|---------|-----------|-------------|-------|-----------------|
| VC-01 | `test_changed_first_stop` | First stop has no "previous" - show all | Start, stop at line 2 | All vars shown (x) |
| VC-02 | `test_changed_single_var` | One var changes | Step from line 3→4 | Only `x` in output |
| VC-03 | `test_changed_new_var` | New var appears | Step from line 4→5 | Only `z` (new counts as changed) |
| VC-04 | `test_changed_no_change` | No vars change | Step from line 5→6 | Empty list or `{"changed": []}` |
| VC-05 | `test_changed_multiple` | Multiple changes | After several steps | Only changed vars |
| VC-06 | `test_changed_combined_with_depth` | `--changed --depth 1` | Complex objects | Changed nested values |

### Integration Tests (CLI)

| Test ID | Command | Setup | Expected |
|---------|---------|-------|----------|
| VC-CLI-01 | `cc-debug vars --changed` | After step where x changed | JSON with only `x` |
| VC-CLI-02 | `cc-debug vars --changed` | After step, nothing changed | `{"names": [], "count": 0}` |
| VC-CLI-03 | `cc-debug vars --changed --names-only` | After step | Just changed names |

### Edge Cases

- First stop (no previous state) → show all vars
- Function call (new scope) → all local vars are "new"
- Variable deleted → should it appear in "changed"? (design decision)
- Same value reassigned (`x = x`) → not changed

---

## 2. Feature: `vars --limit N`

### Description
Show only the top N most "interesting" variables. Interest scoring:
1. Recently changed (highest)
2. Non-None values
3. Smaller/simpler types over large collections
4. Alphabetical as tiebreaker

### Test Fixtures Needed

**fixtures/many_vars.py**
```python
def main():
    a = 1
    b = 2
    c = None
    d = [1, 2, 3]
    e = "hello"
    f = None
    g = {"key": "value"}
    h = 100
    # 8 variables total
```

### Unit Tests (test_vars_limit.py)

| Test ID | Test Name | Description | Input | Expected Output |
|---------|-----------|-------------|-------|-----------------|
| VL-01 | `test_limit_basic` | Limit to 3 vars | 8 vars, limit=3 | Exactly 3 vars |
| VL-02 | `test_limit_exceeds_total` | Limit > available | 3 vars, limit=10 | All 3 vars |
| VL-03 | `test_limit_zero` | Limit=0 | Any vars | Empty or error? (design) |
| VL-04 | `test_limit_prioritizes_changed` | Changed vars first | 5 vars, 2 changed, limit=2 | The 2 changed |
| VL-05 | `test_limit_excludes_none` | None vars last | 3 None, 2 non-None, limit=2 | The 2 non-None |
| VL-06 | `test_limit_with_changed` | `--limit 3 --changed` | 5 changed, limit=3 | Top 3 changed |

### Integration Tests (CLI)

| Test ID | Command | Setup | Expected |
|---------|---------|-------|----------|
| VL-CLI-01 | `cc-debug vars --limit 3` | 8 vars in scope | JSON with 3 vars |
| VL-CLI-02 | `cc-debug vars --limit 5 --names-only` | 10 vars | 5 names |
| VL-CLI-03 | `cc-debug vars --limit 2 --changed` | 4 changed | 2 most recent changed |

### Edge Cases

- limit=1 → single most interesting var
- All vars are None → still return limit count
- Negative limit → error
- Non-integer limit → error

---

## 3. Feature: `watch diff`

### Description
Show only watches whose values changed since last evaluation. For long-running debug sessions with many watches.

### Test Fixtures Needed

**fixtures/watch_changes.py**
```python
def main():
    x = 0
    y = 0
    for i in range(5):
        x += 1        # x changes each iteration
        if i == 3:
            y = 100   # y changes only once
```

### Unit Tests (test_watch_diff.py)

| Test ID | Test Name | Description | Input | Expected Output |
|---------|-----------|-------------|-------|-----------------|
| WD-01 | `test_diff_first_eval` | First eval, no previous | 3 watches | All 3 shown (all "new") |
| WD-02 | `test_diff_one_changed` | One watch value changed | watch x, y; x changed | Only x in diff |
| WD-03 | `test_diff_none_changed` | No changes | Step, no watch values changed | Empty diff |
| WD-04 | `test_diff_all_changed` | All watches changed | 3 watches, all changed | All 3 in diff |
| WD-05 | `test_diff_expression_watch` | Expression like `x + y` | Watch `x+y`, x changed | `x+y` in diff |
| WD-06 | `test_diff_with_errors` | Watch eval fails | Invalid expression | Error shown in diff |

### Integration Tests (CLI)

| Test ID | Command | Setup | Expected |
|---------|---------|-------|----------|
| WD-CLI-01 | `cc-debug watch diff` | 3 watches, 1 changed | JSON with 1 watch |
| WD-CLI-02 | `cc-debug watch diff` | No watches | Error or empty |
| WD-CLI-03 | `cc-debug watch diff` | First time | All watches (all "new") |

### Edge Cases

- No watches set → empty or helpful message
- Watch added mid-session → appears in diff as "new"
- Watch removed → not in diff
- Watch expression becomes invalid (var out of scope) → error in diff

---

## 4. Feature: `cc-debug why`

### Description
One-line explanation of why execution stopped. Helps agent quickly understand state without parsing complex JSON.

### Stop Reasons to Handle

| Reason | Example Output |
|--------|----------------|
| entry | `"Stopped at entry point: main.py:1"` |
| breakpoint | `"Hit breakpoint #3 at utils.py:42"` |
| conditional_breakpoint | `"Hit conditional breakpoint #2 (x > 10) at main.py:15"` |
| exception | `"Exception raised: ValueError('invalid') at parser.py:88"` |
| step | `"Step completed at main.py:25 in function process()"` |
| step_in | `"Stepped into helper() at utils.py:10"` |
| step_out | `"Stepped out to main() at main.py:30"` |
| until | `"Reached line 50 in main.py"` |
| pause | `"Paused by user request"` |
| exited | `"Program exited with code 0"` |

### Unit Tests (test_why.py)

| Test ID | Test Name | Description | Input State | Expected Output |
|---------|-----------|-------------|-------------|-----------------|
| WHY-01 | `test_why_entry` | Stop at entry | Start with stop_on_entry | `"Stopped at entry..."` |
| WHY-02 | `test_why_breakpoint` | Hit breakpoint | Continue to bp | `"Hit breakpoint #N..."` |
| WHY-03 | `test_why_exception` | Exception raised | bp exception, continue | `"Exception raised..."` |
| WHY-04 | `test_why_step` | After next | next command | `"Step completed..."` |
| WHY-05 | `test_why_exited` | Program done | Continue to end | `"Program exited..."` |
| WHY-06 | `test_why_conditional_bp` | Conditional bp hit | bp with condition | `"Hit conditional..."` |

### Integration Tests (CLI)

| Test ID | Command | Setup | Expected |
|---------|---------|-------|----------|
| WHY-CLI-01 | `cc-debug why` | After start | Entry point message |
| WHY-CLI-02 | `cc-debug why` | After hitting bp | Breakpoint message with ID |
| WHY-CLI-03 | `cc-debug why` | After exception | Exception type and message |
| WHY-CLI-04 | `cc-debug why` | No session | Error message |

### Edge Cases

- Multiple breakpoints on same line → which one?
- Exception with long message → truncate?
- Nested function calls → show full path or just current?

---

## 5. Feature: Auto-Truncate Large Values

### Description
Automatically truncate large collections/strings in variable output to prevent context explosion.

### Truncation Rules

| Type | Threshold | Truncated Format |
|------|-----------|------------------|
| list | > 20 items | `"[1, 2, 3, ...(47 more)..., 49, 50]"` |
| dict | > 20 keys | `"{'a': 1, 'b': 2, ...(47 more keys)...}"` |
| set | > 20 items | `"{1, 2, 3, ...(47 more)...}"` |
| str | > 200 chars | `"'hello world...(truncated, 1000 chars)'"` |
| bytes | > 100 bytes | `"b'\\x00\\x01...(truncated, 500 bytes)'"` |

### Test Fixtures Needed

**fixtures/large_values.py**
```python
def main():
    small_list = [1, 2, 3]
    large_list = list(range(100))
    small_dict = {"a": 1}
    large_dict = {f"key_{i}": i for i in range(50)}
    small_str = "hello"
    large_str = "x" * 500
    nested = {"data": list(range(100))}
```

### Unit Tests (test_truncate.py)

| Test ID | Test Name | Description | Input | Expected Output |
|---------|-----------|-------------|-------|-----------------|
| TR-01 | `test_truncate_small_list` | Under threshold | [1,2,3] | Full list |
| TR-02 | `test_truncate_large_list` | Over threshold | range(100) | Truncated with count |
| TR-03 | `test_truncate_large_dict` | Dict over threshold | 50 keys | Truncated with key count |
| TR-04 | `test_truncate_large_string` | Long string | 500 chars | Truncated with char count |
| TR-05 | `test_truncate_nested` | Nested large value | {"data": [100 items]} | Inner truncated |
| TR-06 | `test_truncate_preserves_type` | Type info kept | large list | `"type": "list"` still present |
| TR-07 | `test_truncate_depth_interaction` | `--depth` with truncate | depth=2, large nested | Both applied |

### Integration Tests (CLI)

| Test ID | Command | Setup | Expected |
|---------|---------|-------|----------|
| TR-CLI-01 | `cc-debug vars` | large_list in scope | Truncated output |
| TR-CLI-02 | `cc-debug eval "list(range(1000))"` | - | Truncated result |
| TR-CLI-03 | `cc-debug vars --no-truncate` | large_list | Full output (opt-out) |

### Edge Cases

- Empty collections → no truncation
- Exactly at threshold → no truncation
- Threshold + 1 → truncated
- Recursive/circular references → handle gracefully
- Custom __repr__ that's huge → truncate repr output

---

## Test Fixtures Summary

### New Fixtures Needed

| Fixture | Purpose | Lines |
|---------|---------|-------|
| `var_changes.py` | Test --changed flag | ~10 |
| `many_vars.py` | Test --limit flag | ~15 |
| `watch_changes.py` | Test watch diff | ~10 |
| `large_values.py` | Test auto-truncate | ~15 |

### Existing Fixtures to Reuse

| Fixture | Reuse For |
|---------|-----------|
| `simple.py` | Basic why tests |
| `errors.py` | Exception why tests |
| `state_changes.py` | Changed vars in loops |

---

## Test Execution Matrix

### Unit Tests (pytest, no daemon needed)

```bash
pytest tests/test_vars_changed.py -v
pytest tests/test_vars_limit.py -v
pytest tests/test_watch_diff.py -v
pytest tests/test_why.py -v
pytest tests/test_truncate.py -v
```

### Integration Tests (requires daemon)

```bash
pytest tests/integration/test_cli_vars.py -v
pytest tests/integration/test_cli_watch.py -v
pytest tests/integration/test_cli_why.py -v
pytest tests/integration/test_cli_truncate.py -v
```

---

## JSON Output Schemas

### vars --changed

```json
{
  "success": true,
  "command": "vars",
  "result": {
    "changed": ["x", "z"],
    "variables": {
      "x": {"type": "int", "value": "10", "previous": "1"},
      "z": {"type": "int", "value": "3", "previous": null}
    },
    "unchanged_count": 5
  }
}
```

### vars --limit N

```json
{
  "success": true,
  "command": "vars",
  "result": {
    "variables": {"x": {...}, "y": {...}, "z": {...}},
    "shown": 3,
    "total": 10,
    "truncated": true
  }
}
```

### watch diff

```json
{
  "success": true,
  "command": "watch",
  "subcommand": "diff",
  "result": {
    "changed": [
      {"expression": "x", "value": "10", "previous": "5", "type": "int"}
    ],
    "unchanged_count": 2
  }
}
```

### why

```json
{
  "success": true,
  "command": "why",
  "result": {
    "reason": "breakpoint",
    "summary": "Hit breakpoint #3 at utils.py:42",
    "details": {
      "breakpoint_id": 3,
      "file": "utils.py",
      "line": 42,
      "condition": null
    }
  }
}
```

### Auto-truncate (in vars output)

```json
{
  "large_list": {
    "type": "list",
    "value": "[0, 1, 2, ...(97 more items)]",
    "length": 100,
    "truncated": true
  }
}
```

---

## Implementation Order

1. **Auto-truncate** - Foundation, affects all other outputs
2. **vars --changed** - Builds on state tracking (already exists)
3. **vars --limit** - Independent, simple
4. **watch diff** - Builds on watch system
5. **why** - Independent, simple

---

## Acceptance Criteria

| Feature | Criteria |
|---------|----------|
| vars --changed | Only changed vars shown; first stop shows all; works with --names-only |
| vars --limit | Exactly N vars; prioritizes changed/non-None; works with --changed |
| watch diff | Only changed watches; shows previous value; handles errors |
| why | One-line summary; covers all stop reasons; includes location |
| auto-truncate | Configurable threshold; shows count; opt-out flag available |
