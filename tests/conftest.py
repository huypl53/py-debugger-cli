"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_script(fixtures_dir: Path) -> Path:
    """Return path to simple.py fixture."""
    return fixtures_dir / "simple.py"


@pytest.fixture
def loop_script(fixtures_dir: Path) -> Path:
    """Return path to loop.py fixture."""
    return fixtures_dir / "loop.py"


@pytest.fixture
def state_script(fixtures_dir: Path) -> Path:
    """Return path to state_changes.py fixture."""
    return fixtures_dir / "state_changes.py"


@pytest.fixture
def errors_script(fixtures_dir: Path) -> Path:
    """Return path to errors.py fixture."""
    return fixtures_dir / "errors.py"


@pytest.fixture
def var_changes_script(fixtures_dir: Path) -> Path:
    """Return path to var_changes.py fixture for --changed tests."""
    return fixtures_dir / "var_changes.py"


@pytest.fixture
def many_vars_script(fixtures_dir: Path) -> Path:
    """Return path to many_vars.py fixture for --limit tests."""
    return fixtures_dir / "many_vars.py"


@pytest.fixture
def watch_changes_script(fixtures_dir: Path) -> Path:
    """Return path to watch_changes.py fixture for watch diff tests."""
    return fixtures_dir / "watch_changes.py"


@pytest.fixture
def large_values_script(fixtures_dir: Path) -> Path:
    """Return path to large_values.py fixture for truncation tests."""
    return fixtures_dir / "large_values.py"
