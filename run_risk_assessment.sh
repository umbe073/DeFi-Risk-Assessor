#!/bin/bash

# DeFi Risk Assessment Launcher
# This script launches the Python risk assessment tool with native progress bar

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Set up script paths
SCRIPT_FILE="defi_complete_risk_assessment.py"
UPDATE_SCRIPT_FILE="update_risk_assessment_xlsx.py"

resolve_python() {
    # 1) Explicit override via environment variable
    if [ -n "${PYTHON_PATH:-}" ]; then
        if [ -x "$PYTHON_PATH" ]; then
            echo "$PYTHON_PATH"
            return 0
        fi
        echo "Error: PYTHON_PATH is set but not executable: $PYTHON_PATH" >&2
        return 1
    fi

    # 2) Active virtualenv
    if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
        echo "$VIRTUAL_ENV/bin/python3"
        return 0
    fi

    # 3) Repository-local virtualenvs (common for non-activated shells)
    if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
        echo "$SCRIPT_DIR/.venv/bin/python3"
        return 0
    fi

    if [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
        echo "$SCRIPT_DIR/venv/bin/python3"
        return 0
    fi

    # 4) Fallback to system python3
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi

    echo "Error: Could not locate a usable python3 interpreter." >&2
    return 1
}

# Check if Python script exists
if [ ! -f "$SCRIPT_FILE" ]; then
    echo "Error: $SCRIPT_FILE not found in $SCRIPT_DIR"
    exit 1
fi

if [ ! -f "$UPDATE_SCRIPT_FILE" ]; then
    echo "Error: $UPDATE_SCRIPT_FILE not found in $SCRIPT_DIR"
    exit 1
fi

PYTHON_BIN="$(resolve_python)" || {
    echo "Please set PYTHON_PATH or activate a virtual environment before running."
    exit 1
}

echo "🚀 Launching DeFi Risk Assessment Tool..."
echo "📁 Working directory: $SCRIPT_DIR"
echo "🐍 Python: $PYTHON_BIN"
echo "📄 Script: $SCRIPT_FILE"
echo ""

# Launch the main Python script with progress bar
"$PYTHON_BIN" "$SCRIPT_FILE"
MAIN_EXIT_CODE=$?

if [ $MAIN_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Risk assessment failed while running $SCRIPT_FILE (exit code: $MAIN_EXIT_CODE)"
    exit $MAIN_EXIT_CODE
fi

# Update the Excel report after the main script completes
"$PYTHON_BIN" "$UPDATE_SCRIPT_FILE"
UPDATE_EXIT_CODE=$?

if [ $UPDATE_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Risk assessment completed successfully!"
    echo "📊 Check the output files in $SCRIPT_DIR"
else
    echo ""
    echo "❌ Risk assessment failed while running $UPDATE_SCRIPT_FILE (exit code: $UPDATE_EXIT_CODE)"
    echo "📝 Check the logs for error details"
    exit $UPDATE_EXIT_CODE
fi
