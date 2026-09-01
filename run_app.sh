#!/usr/bin/env bash
# =======================================================
# Cross-Platform Dictionary Launcher for Linux / macOS
# =======================================================
set -e

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 run_gui.py
