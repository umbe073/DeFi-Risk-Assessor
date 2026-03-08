#!/bin/bash
# Run the risk assessment and update the Excel file, then show a dialog

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

rm -f ../data/risk_report.done

echo "Starting risk assessment..."
python3 defi_complete_risk_assessment.py

# Wait until risk_report.json exists and is non-empty
REPORT_PATH="../data/risk_report.json"
TIMEOUT=600  # seconds (adjust if script runtime changes)
WAITED=0
SLEEP_INTERVAL=2

while [ ! -s "$REPORT_PATH" ] && [ $WAITED -lt $TIMEOUT ]; do
  echo "Waiting for risk_report.json to be created and non-empty..."
  sleep $SLEEP_INTERVAL
  WAITED=$((WAITED + SLEEP_INTERVAL))
done

if [ ! -s "$REPORT_PATH" ]; then
  echo "Error: risk_report.json was not created or is empty after $TIMEOUT seconds."
  osascript -e 'display dialog "ERROR: risk_report.json was not created or is empty. Please check the risk assessment script."'
  exit 1
fi

echo "Risk assessment complete. Waiting 2.5 seconds before starting Excel update..."
sleep 2.5
echo "Starting Excel update..."
python3 update_risk_assessment_xlsx.py
echo "Excel update complete. Checking flag file..."

# Wait for the flag file to be removed (should be removed by update_risk_assessment_xlsx.py)
while [ -f ../data/risk_report.done ]; do
  echo "Waiting for update to complete..."
  sleep 2
done

echo "All done! Showing dialog."
osascript -e 'display dialog "Update complete!\n\nDISCLAIMER\nThe results of this assessment may not be precise and may vary according to the availability of the API endpoint from which the data is taken."'