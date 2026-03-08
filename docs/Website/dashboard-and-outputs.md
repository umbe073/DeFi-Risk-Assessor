# Outputs & Dashboards

This page describes the files produced by the engine and how dashboards or
external tools can consume them.

---

## Output directory structure

All primary outputs live under:

- `DATA_DIR/risk_reports/`

Key paths (set early in the script):

```321:337:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
RISK_REPORT_DIR = os.path.join(DATA_DIR, 'risk_reports')
...
EXCEL_REPORT_PATH = os.path.join(RISK_REPORT_DIR, f'DeFi Tokens Risk Assessment Results_{timestamp}.xlsx')
RISK_REPORT_JSON = os.path.join(RISK_REPORT_DIR, f\"risk_report_{timestamp}.json\")
RISK_REPORT_CSV = os.path.join(RISK_REPORT_DIR, f\"risk_report_{timestamp}.csv\")
...
EXCEL_REPORT_LATEST = os.path.join(RISK_REPORT_DIR, 'DeFi Tokens Risk Assessment Results_latest.xlsx')
RISK_REPORT_JSON_LATEST = os.path.join(RISK_REPORT_DIR, \"risk_report_latest.json\")
RISK_REPORT_CSV_LATEST = os.path.join(RISK_REPORT_DIR, \"risk_report_latest.csv\")
```

For each run, the engine writes:

- a timestamped Excel file,  
- a timestamped JSON file,  
- a timestamped CSV file,

and refreshes the three `_latest` aliases.

---

## JSON report structure

The JSON report is the richest representation of token risk. It is an array of
objects where each entry typically contains:

- basic identity fields (symbol, address, chain),  
- raw and normalized metrics (market cap, liquidity, holder stats, etc.),  
- component scores and final risk score,  
- red flags and context flags,  
- provenance / credibility metadata,  
- social_data payloads and per-source details (when available).

Downstream tools should prefer the JSON report when:

- building interactive dashboards,  
- computing aggregates over the full universe,  
- exporting to data warehouses.

---

## CSV summary

The CSV report is a flattened subset of the JSON, designed for:

- quick inspection in spreadsheets,  
- simple imports into BI tools that do not handle nested JSON well,  
- ad-hoc analysis by analysts.

It typically includes:

- core identifiers,  
- final risk score and behavioral sub-scores,  
- key liquidity and holder metrics,  
- selected red-flag indicators.

---

## Excel report

`DeFi Tokens Risk Assessment Results_<timestamp>.xlsx` is a user-friendly view
for non-technical stakeholders. It usually contains:

- one row per token,  
- formatted columns with:
  - token identifiers,  
  - risk scores and traffic-light coloring,  
  - selected metrics (market cap, volume, liquidity, holders),  
  - important red flags or notes.

The “latest” Excel file is a convenient artifact to send in reports or attach
to ticketing / case-management systems.

---

## Social score reports

The social score analysis is generated separately via:

- `generate_social_score_report()` in the main script.

Output:

- `SOCIAL_REPORT_DIR/social_score_report_<timestamp>.txt`

Contents:

- summary of token coverage,  
- per-source effectiveness metrics,  
- keyword frequencies and candidates for replacement.

This file is best consumed by:

- research or data teams maintaining the keyword dictionary,  
- engineers evaluating which social / news APIs are worth keeping enabled.

---

## Dashboard integration patterns

Common approaches:

- **File-based dashboards**  
  - Point BI tools or custom dashboards at:
    - `risk_report_latest.json` for detailed analysis, or  
    - `risk_report_latest.csv` / latest Excel for simpler views.  
  - Refresh the data source after each engine run.

- **Webhook-driven updates**  
  - Listen on the local webhook endpoint used by the engine when it updates
    cache entries (`/webhook/update_token`).  
  - Trigger partial dashboard refreshes when a token is updated.

- **Scheduled batch processing**  
  - Run the engine on a fixed schedule (e.g. nightly).  
  - Archive timestamped JSON / CSV / XLSX to object storage.  
  - Maintain only `*_latest` locally for dashboards.

By separating timestamped artifacts from stable “latest” pointers, the engine
makes it easy for dashboards and downstream systems to stay in sync without
having to track changing filenames.
