#!/bin/bash
# ===============================
# ARCHIVAL: launch_risk_assessment.sh
# This file is for historical reference only.
# Initial shell script to launch the risk assessment tool, later consolidated into run_risk_assessment.sh.
# ===============================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/../../venv"
PYTHON="$VENV_PATH/bin/python3"

if [ ! -f "$PYTHON" ]; then
  osascript -e 'display dialog "Python environment not found!" buttons {"OK"} default button 1'
  exit 1
fi

source "$VENV_PATH/bin/activate"

python3 "$SCRIPT_DIR/defi_complete_risk_assessment.py"

if [ $? -eq 0 ]; then
  osascript -e 'display dialog "Risk assessment completed!" buttons {"OK"} default button 1'
else
  osascript -e 'display dialog "Risk assessment failed!" buttons {"OK"} default button 1'
fi 