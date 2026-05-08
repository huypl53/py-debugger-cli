#!/bin/bash
# Install script for cc-debug plugin
# Runs in the plugin's installation directory

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing cc-debug in $PLUGIN_DIR..."

# Check for uv first (preferred)
if command -v uv &> /dev/null; then
    echo "Using uv to create venv and install..."
    cd "$PLUGIN_DIR"
    uv venv .venv --quiet 2>/dev/null || true
    uv pip install -e . --quiet
    echo "Installed with uv"
elif command -v python3 &> /dev/null; then
    echo "Using python3 venv..."
    cd "$PLUGIN_DIR"
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -e . --quiet
    echo "Installed with python3 venv"
else
    echo "ERROR: Neither uv nor python3 found. Please install Python 3.12+."
    exit 1
fi

# Also need debugpy
if [ -d ".venv" ]; then
    if command -v uv &> /dev/null; then
        uv pip install debugpy --quiet
    else
        .venv/bin/pip install debugpy --quiet
    fi
fi

echo "cc-debug installed successfully!"
echo "The skill will use: $PLUGIN_DIR/.venv/bin/cc-debug"
