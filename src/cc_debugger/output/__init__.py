"""Output formatting for CC-Debugger."""

from cc_debugger.output.json_formatter import (
    OutputFormatter,
    format_error,
    format_stopped,
    format_success,
    format_variables,
    output_json,
    print_program_output,
)

__all__ = [
    "output_json",
    "format_success",
    "format_error",
    "format_stopped",
    "format_variables",
    "OutputFormatter",
    "print_program_output",
]
