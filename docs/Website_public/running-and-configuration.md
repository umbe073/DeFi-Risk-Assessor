> **Public security notice:** This documentation is intentionally redacted. Sensitive server paths, private keys, secret tokens, and origin network details are removed.

# Running the Assessment & Configuration

This page focuses on how to execute the Hodler Suite, configure
its behavior and interpret the resulting files.

---

## Prerequisites

- Python 3 environment with all dependencies from `requirements.txt`.  
- A populated `DATA_DIR` (typically `<PROJECT_ROOT>/data`) containing at least:
  - `tokens.csv` – list of tokens to assess (address, symbol, chain, labels).  
  - `fallbacks/fallbacks.json` – optional fallback data.  
  - `token_data_viewer.csv` – optional market snapshot (see
    **[Token Data Viewer](token-data-viewer.md)**).  
  - `settings.json` – optional configuration (EU-mode, cache settings, etc.).

Recommended:

- Configure API keys via the **Secure Credentials System**
  (see **[Secure Credentials](secure-credentials.md)**).  
- Run `update_token_data_viewer.py` to refresh the viewer before heavy runs.

---

## Basic execution

The main script lives at:

- `scripts/v2.0/defi_complete_risk_assessment_clean.py`

A simple run from the project root:

```bash
cd /path/to/venv
python3 scripts/v2.0/defi_complete_risk_assessment_clean.py
```

Typical behavior:

- Logs progress to `logs/risk_assessment_verbose.log` and a concise summary to
  `logs/risk_assessment_summary.txt`.  
- Writes timestamped reports under `data/risk_reports/`.  
- Updates `*_latest` files for dashboards to consume.

---

## Key configuration files

### `data/settings.json`

Controls:

- **EU-mode** and MiCA-related flags (see
  **[EU Mode vs Global Mode](eu-mode-and-global-mode.md)**).  
- **Cache behavior** (retention windows, metric-drift thresholds, etc.).  
- **Per-service toggles** and rate-limit policies.

Example outline:

```json
{
  "eu_mode": { ... },
  "cache": {
    "metric_drift_threshold_pct": 2.0,
    "cache_retention": "48 hours"
  },
  "services": {
    "trmlabs": { "enabled": true },
    "social_sentiment": { "enabled": false }
  }
}
```

### `data/tokens.csv`

Defines the token universe. Columns typically include:

- `address`, `symbol`, `chain`, optional labels or tags.

The engine iterates this CSV to schedule per-token assessments.

### `data/fallbacks/fallbacks.json`

Contains pre-computed or static data for tokens, used when APIs are unavailable
or rate-limited. Structure is engine-specific but usually keyed by token
address or symbol.

---

## Outputs

Under `data/risk_reports/` the engine writes:

- `DeFi Tokens Risk Assessment Results_<timestamp>.xlsx` – main Excel report.  
- `risk_report_<timestamp>.json` – full JSON payload (one entry per token).  
- `risk_report_<timestamp>.csv` – CSV summary.

It also maintains convenience aliases:

- `DeFi Tokens Risk Assessment Results_latest.xlsx`  
- `risk_report_latest.json`  
- `risk_report_latest.csv`

These “latest” files are what dashboards and helper scripts (such as the social
score report generator) typically consume.

---

## Environment variables

Several behaviors can be tuned via environment variables, including:

- Thread pool size for the shared API scheduler.  
- Certain penalty / discount magnitudes (e.g. market-structure penalties).  
- Native chain token risk discount.

Example:

```bash
export SHARED_API_SCHEDULER_WORKERS=16
export NATIVE_CHAIN_TOKEN_RISK_DISCOUNT=<REDACTED>
python3 scripts/v2.0/defi_complete_risk_assessment_clean.py
```

See inline comments in the script for additional environment-based knobs.

---

## Operational tips

- **Warm up caches** by running a smaller subset of tokens before a full
  universe. This reduces rate-limit pressure for large runs.  
- **Monitor logs** (`logs/risk_assessment_verbose.log`) for repeated errors from
  specific services; consider disabling or reconfiguring them in `settings.json`
  if necessary.  
- **Reuse outputs** – dashboards should primarily read from the `*_latest`
  files, not from timestamped filenames that change on every run.

Together, these practices help keep the engine predictable and safe to operate
in production-like environments.

