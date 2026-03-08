# Token Data Viewer

The **Token Data Viewer** is a CSV-backed snapshot of market data used as both:

- a fast baseline for many metrics during assessments, and  
- a signal for **when** it is worth running a full risk assessment.

---

## Files and locations

The viewer uses the following files under `DATA_DIR`:

- `token_data_viewer.csv` – primary snapshot used by the main script.  
- `token_data_viewer_export.csv` – alternate / export view for other tools.  
- Additional helper scripts read/write the same CSVs.

Helpers:

- `scripts/v2.0/update_token_data_viewer.py` – creates or refreshes the viewer.  
- `scripts/v2.0/refresh_token_data_viewer.py` – refresh with enhanced APIs.  
- `scripts/v2.0/comprehensive_data_fix.py`, `fix_liquidity_and_apis.py`, etc. –
  utilities to correct or enrich viewer data.

---

## Loading the snapshot

Early in the main script, `_load_token_viewer_snapshot()` reads the CSV:

```268:313:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _load_token_viewer_snapshot():
    \"\"\"Load token_data_viewer.csv into chain-aware symbol metrics.\"\"\"
    viewer_path = os.path.join(DATA_DIR, \"token_data_viewer.csv\")
    snapshot: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(viewer_path):
        return snapshot
    try:
        df = pd.read_csv(viewer_path)
        for row_pair in df.iterrows():
            row = row_pair[1]
            sym = str(row.get(\"Symbol\", \"\")).upper()
            ...
            entry = {
                \"market_cap\": _num(row.get(\"Market Cap\", 0)),
                \"volume_24h\": _num(row.get(\"Volume 24h\", 0)),
                \"liquidity\": _num(row.get(\"Liquidity\", 0)),
                \"price\": _num(row.get(\"Price\", 0)),
                \"holders\": _num(row.get(\"Holders\", 0)),
                \"source\": \"token_data_viewer\"
            }
            snapshot[sym] = entry
            if chain:
                snapshot[f\"{chain}:{sym}\"] = entry
```

The helper `_num` cleans string / numeric fields, coercing invalid or NaN values
to `0.0`, ensuring downstream code does not crash on malformed input.

---

## Using the snapshot during scoring

Throughout the engine, the viewer snapshot is treated as:

- an additional **non-estimated seed** when cache/fallback data is absent, and  
- a **last-resort liquidity / market data source** when live APIs are
  temporarily unavailable.

For example, when computing liquidity and market-structure metrics, if live
sources and cache are missing, the engine may fall back to viewer-derived
liquidity values while clearly marking them as such in the provenance data.

Because entries are keyed by both `SYMBOL` and `chain:SYMBOL`, the snapshot can
distinguish between the same ticker across different chains (e.g. `USDC` on
Ethereum vs Polygon).

---

## Updating the viewer

The script `update_token_data_viewer.py` builds or refreshes the CSV by pulling
data from the latest XLSX report and/or live APIs:

```4065:4070:<PROJECT_ROOT>/scripts/v2.0/update_token_data_viewer.py
def create_token_data_viewer_csv():
    \"\"\"Create the token_data_viewer.csv file with current data\"\"\"
    print(\"🔄 Updating Token Data Viewer CSV...\")
    ...
```

The process typically:

1. Reads the latest risk report XLSX.  
2. Normalizes market cap, volume, liquidity and holder counts.  
3. Writes consistent rows to:
   - `token_data_viewer.csv`  
   - `token_data_viewer_export.csv`

Separate utilities such as `refresh_token_data_viewer.py` or
`comprehensive_data_fix.py` can be used to:

- pull enhanced market data from improved APIs,  
- correct known bad entries,  
- regenerate viewer files when the schema changes.

---

## Operational best practices

- **Run viewer refresh before heavy assessments**  
  Ensure `token_data_viewer.csv` is up-to-date and contains non-zero values for
  as many tokens as possible before starting a full assessment run.

- **Treat sparse viewer data as a signal**  
  If many rows show `0` or `N/A`, consider delaying large runs or restricting
  them to well-covered assets.

- **Use viewer data as a baseline, not as truth**  
  Viewer values are convenient and fast, but where possible they should be
  superseded by live API calls and caches at assessment time.

By using the Token Data Viewer as a first-stage market snapshot and quality
gate, the engine avoids wasting rate limits on illiquid or inactive tokens and
provides more stable, timely risk reports.

