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
