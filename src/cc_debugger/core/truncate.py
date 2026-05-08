"""Auto-truncation of large values to reduce token usage."""

from __future__ import annotations

# Default thresholds for truncation
DEFAULT_THRESHOLDS = {
    "list": 20,
    "tuple": 20,
    "dict": 20,
    "set": 20,
    "frozenset": 20,
    "str": 200,
    "bytes": 100,
    "bytearray": 100,
}


def truncate_value(
    value: str,
    value_type: str,
    length: int | None = None,
    threshold: int | None = None,
    enabled: bool = True,
) -> dict:
    """
    Truncate large values for display.

    Args:
        value: String representation of value
        value_type: Python type name
        length: Length/size of the value (estimated from value if None)
        threshold: Custom threshold (uses default if None)
        enabled: If False, skip truncation

    Returns:
        Dict with 'value', 'type', 'truncated', optionally 'original_length'
    """
    result = {
        "value": value,
        "type": value_type,
        "truncated": False,
    }

    if not enabled:
        return result

    # Estimate length from value if not provided
    if length is None:
        length = _estimate_length(value, value_type)

    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(value_type, 50)

    if length <= threshold:
        return result

    result["truncated"] = True
    result["original_length"] = length
    hidden = length - threshold

    if value_type in ("list", "tuple"):
        bracket = "[" if value_type == "list" else "("
        close = "]" if value_type == "list" else ")"
        result["value"] = f"{bracket}...({length} items, showing first {threshold}){close}"

    elif value_type == "dict":
        result["value"] = f"{{...({length} keys, showing first {threshold})}}"

    elif value_type in ("set", "frozenset"):
        result["value"] = f"{{...({length} items)}}"

    elif value_type == "str":
        # Show beginning with char count
        if len(value) > 53:  # Account for quotes
            preview = value[:50]
        else:
            preview = value[:20]
        result["value"] = f"{preview}...(truncated, {length} chars)"

    elif value_type in ("bytes", "bytearray"):
        result["value"] = f"b'...(truncated, {length} bytes)'"

    else:
        # Generic truncation for unknown types
        if len(value) > 100:
            result["value"] = f"{value[:50]}...(truncated)"

    return result


def _estimate_length(value: str, value_type: str) -> int:
    """Estimate collection length from string representation."""
    if value_type in ("list", "tuple", "set", "frozenset"):
        # Count commas (rough estimate)
        if value in ("[]", "()", "{}", "set()", "frozenset()"):
            return 0
        return value.count(",") + 1

    elif value_type == "dict":
        if value == "{}":
            return 0
        return value.count(":")

    elif value_type == "str":
        # Remove quotes
        return len(value) - 2 if len(value) >= 2 else len(value)

    elif value_type in ("bytes", "bytearray"):
        # Rough estimate from repr
        return len(value) // 4  # \x00 = 4 chars per byte

    return len(value)


def truncate_variables(
    variables: dict[str, dict],
    enabled: bool = True,
    thresholds: dict[str, int] | None = None,
) -> dict[str, dict]:
    """
    Apply truncation to a dict of variables.

    Args:
        variables: Dict of var_name -> {"type": ..., "value": ...}
        enabled: If False, return unchanged
        thresholds: Custom thresholds per type

    Returns:
        Variables dict with truncated values
    """
    if not enabled:
        return variables

    result = {}
    custom_thresholds = thresholds or {}

    for name, info in variables.items():
        value_type = info.get("type", "")
        value = info.get("value", "")

        threshold = custom_thresholds.get(value_type)
        truncated = truncate_value(
            value=value,
            value_type=value_type,
            threshold=threshold,
            enabled=enabled,
        )

        result[name] = {
            "type": value_type,
            "value": truncated["value"],
        }
        if truncated["truncated"]:
            result[name]["truncated"] = True
            result[name]["original_length"] = truncated.get("original_length")

    return result
