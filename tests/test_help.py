from click.testing import CliRunner
from cc_debugger.commands.help import help_cmd
from cc_debugger.cli import main

def test_help_no_arguments():
    runner = CliRunner()
    result = runner.invoke(main, ["help"])
    assert result.exit_code == 0
    assert "CC-Debugger - Command Line Interface Help" in result.output
    assert "Quick Start:" in result.output
    assert "Session Commands" in result.output

def test_help_subcommand():
    runner = CliRunner()
    result = runner.invoke(main, ["help", "start"])
    assert result.exit_code == 0
    assert "start [OPTIONS] FILE" in result.output
    assert "--no-stop" in result.output
    assert "--uv" in result.output

def test_help_nested_subcommand():
    runner = CliRunner()
    result = runner.invoke(main, ["help", "bp", "set"])
    assert result.exit_code == 0
    assert "bp set [OPTIONS] LOCATION" in result.output
    assert "--condition" in result.output

def test_help_non_existent_command():
    runner = CliRunner()
    result = runner.invoke(main, ["help", "nonexistent"])
    assert result.exit_code != 0
    assert "Error: Command 'nonexistent' not found." in result.output

