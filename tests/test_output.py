"""Tests for output formatting."""

import pytest
from unittest.mock import Mock
from cc_debugger.output.json_formatter import (
    format_success,
    format_error,
    format_stopped,
    format_variables,
    OutputFormatter,
)
from cc_debugger.models.session import Location


class TestOutputFormatting:
    """Tests for output formatting functions."""

    def test_format_success(self):
        result = format_success("test", {"key": "value"})
        assert result["success"] is True
        assert result["command"] == "test"
        assert result["result"]["key"] == "value"

    def test_format_error(self):
        result = format_error("test", "ERROR_CODE", "Error message")
        assert result["success"] is False
        assert result["command"] == "test"
        assert result["error"]["code"] == "ERROR_CODE"
        assert result["error"]["message"] == "Error message"

    def test_format_error_with_details(self):
        result = format_error("test", "ERROR_CODE", "Error message", {"extra": "info"})
        assert result["error"]["details"]["extra"] == "info"

    def test_format_stopped(self):
        location = Location(file="/path/to/file.py", line=42, function="main")
        result = format_stopped("breakpoint", location)
        assert result["event"] == "stopped"
        assert result["reason"] == "breakpoint"
        assert result["location"]["file"] == "/path/to/file.py"
        assert result["location"]["line"] == 42

    def test_format_stopped_with_changes(self):
        location = Location(file="/path/to/file.py", line=42, function="main")
        result = format_stopped("step", location, changed_vars=["x", "y"])
        assert result["changedVars"] == ["x", "y"]

    def test_format_variables(self):
        mock_var1 = Mock()
        mock_var1.name = "x"
        mock_var1.type = "int"
        mock_var1.value = "42"
        mock_var1.variablesReference = 0

        mock_var2 = Mock()
        mock_var2.name = "data"
        mock_var2.type = "list"
        mock_var2.value = "[1, 2, 3]"
        mock_var2.variablesReference = 5

        result = format_variables([mock_var1, mock_var2])
        assert result["x"]["type"] == "int"
        assert result["x"]["value"] == "42"
        assert result["data"]["expandable"] is True


class TestOutputFormatter:
    """Tests for OutputFormatter class."""

    def test_format_variable_truncation(self):
        formatter = OutputFormatter(max_value_len=10)
        var = {"type": "str", "value": "a" * 100, "variablesReference": 0}
        result = formatter.format_variable(var)
        assert result["value"].endswith("...")
        assert len(result["value"]) == 13

    def test_format_variable_expandable(self):
        formatter = OutputFormatter()
        var = {"type": "list", "value": "[1, 2, 3]", "variablesReference": 5}
        result = formatter.format_variable(var, depth=0)
        assert result["expandable"] is True

    def test_format_variable_truncated_depth(self):
        formatter = OutputFormatter(max_depth=2)
        var = {"type": "list", "value": "[1, 2, 3]", "variablesReference": 5}
        result = formatter.format_variable(var, depth=3)
        assert result["truncated"] is True
