# Risk Worker Runtime (Seasons 3-4)

This deploy pack runs queued risk jobs from `risk_jobs.db` using the internal endpoint,
plus Season 4 data-plane maintenance timers for compliance dataset refresh and token
cache warming.

## Risk Worker (Season 3)

**HTTP execution model:** User-facing `POST /api/v1/risk/jobs` (and batch/compat queue routes) only **persist a queued job** in `risk_jobs.db` and return `201` with `execution_model: async_queue`. No route in the web portal runs the full legacy assessment script synchronously inside a Gunicorn worker; the timer/service calls `POST /api/v1/risk/internal/run-once`, which claims work and **spawns** `risk_worker_process.py` (or runs the small in-process placeholder when the engine is missing).

The core job processor: `POST /api/v1/risk/internal/run-once`

When jobs are claimed, the web portal spawns `risk_worker_process.py` as a subprocess
that imports the legacy scoring engine (`DeFiRiskAssessor`) and reports progress/results
via the events API. **Live Assessment list batches** (shared `list_batch_id` in job
metadata): all queued jobs in that batch are claimed together and processed in **one**
subprocess so pandas/web3/engine init run **once per batch**, not once per token. Single
jobs behave as before (one assessment per process). If the engine is not found on disk,
the portal falls back to deterministic placeholder results.

On Linux and macOS, the worker uses a **fork supervisor**: the parent process posts
periodic “Supervisor: …” heartbeat lines while the **child** process imports heavy
libraries (so the Live Assessment log stays active even when the child holds the GIL
during native extension import). The supervisor **must** start **after** `fork()` (never
start Python background threads in the same process before forking—the child can hang
indefinitely during `import`). Set `HODLER_RISK_WORKER_NO_FORK=1` to force the older
single-process mode (e.g. debugging).

### Optional: warm import (page cache, not a shared in-memory engine)

`deploy/risk/warm_risk_engine_import.py` runs `import` + `DeFiRiskAssessor()` once and exits.
Use after deploy or from a systemd timer to reduce **disk** warm-up for the next subprocess.
It does **not** keep the engine loaded for users; a true always-hot engine would be a separate
long-lived daemon (or moving assessments into `hodler-script-api`)—not yet standardized here.

### Risk Worker Files

- `deploy/risk/risk_worker_run_once.sh` — shell script called by systemd timer
- `deploy/risk/risk_worker_process.py` — out-of-process Python worker (real engine)
- `deploy/risk/risk_parity_harness.py` — pinned parity check against representative desktop-style samples
- `deploy/risk/risk-worker.service` — systemd oneshot unit
- `deploy/risk/risk-worker.timer` — systemd timer (every 30s)

### Risk Worker Install

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/risk/risk_worker_run_once.sh /usr/local/sbin/hodler_risk_worker_run_once.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/risk-worker.service /etc/systemd/system/risk-worker.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/risk-worker.timer /etc/systemd/system/risk-worker.timer
sudo systemctl daemon-reload
sudo systemctl enable --now risk-worker.timer
sudo systemctl start risk-worker.service
sudo systemctl status --no-pager risk-worker.service
sudo systemctl list-timers --all | grep risk-worker
```

### Required Env Keys

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `RISK_WORKER_SHARED_SECRET=<same value used by internal risk worker endpoints>`

Optional:

- `RISK_WORKER_BASE_URL=http://127.0.0.1:5050`
- `RISK_WORKER_TIMEOUT_SECONDS=600` (subprocess timeout for real engine; default 600s)
- `RISK_WORKER_WAIT_FOR_APP_SECONDS=20`
- `RISK_WORKER_ID=<stable node id>`
- `RISK_ENGINE_ROOT=/opt/hodler-suite/scripts/v2.0` (path to the legacy engine directory)
- `RISK_ENGINE_ENV_FILE=/opt/hodler-suite/.env` (path to .env with API keys)
- `RISK_WORKER_PROCESS_SCRIPT=<path to risk_worker_process.py>` (auto-detected if not set)
- `RISK_WORKER_PYTHON=<python binary for the subprocess>` (defaults to web portal's Python)
- `RISK_WORKER_SUBPROCESS_STDERR_LOG=/var/log/hodler-suite/risk_worker_subprocess.log` (optional; append engine tracebacks from `risk_worker_process.py` — otherwise stderr is discarded). Lines prefixed **`[hodler-risk-worker …]`** are structured diagnostics: `fork`, `supervisor_wait`, `import`, `init`, `token`, `heartbeat_api`, etc. Use **`tail -f`** on this file while reproducing a stuck job to see exactly where the worker is (even if the Live Assessment UI stops updating).
- `HODLER_RISK_WORKER_SILENCE_DIAG=1` (optional; disable `[hodler-risk-worker]` stderr lines)
- `HODLER_RISK_WORKER_NO_FORK=1` (optional; disable fork supervisor — Windows ignores fork anyway)

Fallback behavior:

- if `RISK_WORKER_SHARED_SECRET` is empty, script falls back to `WEBHOOK_SHARED_SECRET`.

### Troubleshooting: UI at ~5% “Loading scoring engine…”

This is **normal for 1–3 minutes** on first run after deploy or reboot: the subprocess must **import**
`defi_complete_risk_assessment_clean` (pandas, web3, etc.). The worker now posts **periodic user-safe
heartbeat lines** (elapsed time, generic status only—no paths or secrets) to the Live Assessment log
while import and engine init run, so the page does not look frozen. It is **not** caused by the Free tier
(plan env vars apply after the engine loads).

If it never advances:

1. On the server, time the import:  
   `time /opt/defi-risk/venv/bin/python3 -c "import sys; sys.path.insert(0,'/opt/defi-risk/app/scripts/v2.0'); from defi_complete_risk_assessment_clean import DeFiRiskAssessor; print('ok')"`  
   (adjust paths to match `RISK_ENGINE_ROOT` / venv.)
2. Check for **OOM**: `sudo dmesg -T | grep -i oom` (large imports can exhaust RAM on small VPS plans).
3. Set `RISK_WORKER_SUBPROCESS_STDERR_LOG` in `web_portal.env`, restart `hodler-web-portal`, reproduce once, then inspect the log for tracebacks.
4. Confirm a worker process is running: `pgrep -af risk_worker_process` (should exist until the job finishes or crashes).

### Risk Worker Manual One-shot

```bash
sudo /usr/local/sbin/hodler_risk_worker_run_once.sh
```

Expected output examples:

- idle queue: `[risk-worker] status=idle processed=False claimed=False`
- processed job: `[risk-worker] status=processed processed=True claimed=True job_id=RJ-... job_status=succeeded risk_score=...`

### Risk Worker Parity Harness

Run this after adapter/worker changes to confirm the deployed checkout still matches
the pinned desktop-style baseline samples:

```bash
sudo /opt/hodler-suite/web_portal/.venv/bin/python3 \
    /opt/hodler-suite/web_portal/deploy/risk/risk_parity_harness.py
```

Expected output:

- success: `OK: 3 parity case(s) matched the pinned baseline.`
- failure: non-zero exit with nested field drift lines for the mismatched case(s)

## Dataset Refresh Timer (Season 4)

Keeps OFAC/SLS, ScamSniffer, and Chainalysis compliance datasets warm independently
of risk assessments. Runs every 6 hours with 5-minute randomized jitter.

### Dataset Refresh Files

- `deploy/risk/dataset_refresh_process.py` — standalone Python refresher
- `deploy/risk/dataset-refresh.service` — systemd oneshot unit
- `deploy/risk/dataset-refresh.timer` — systemd timer (every 6h at :15 past)

### Dataset Refresh Install

```bash
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/dataset-refresh.service /etc/systemd/system/dataset-refresh.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/dataset-refresh.timer /etc/systemd/system/dataset-refresh.timer
sudo systemctl daemon-reload
sudo systemctl enable --now dataset-refresh.timer
sudo systemctl list-timers --all | grep dataset-refresh
```

### Dataset Refresh Manual One-shot

```bash
sudo /opt/defi-risk/app/.venv/bin/python \
    /opt/hodler-suite/web_portal/deploy/risk/dataset_refresh_process.py \
    --engine-root /opt/defi-risk/app/scripts/v2.0 \
    --env-file /opt/hodler-suite/.env
```

### Dataset Refresh Env Keys (Optional)

These are already read from `web_portal.env` by the service unit:

- `RISK_ENGINE_ROOT` — path to the legacy engine scripts/v2.0 directory
- `RISK_ENGINE_ENV_FILE` — path to .env with API keys

## Token Cache Warmer (Season 4)

Proactively refreshes stale token data in `real_data_cache.json` so that on-demand
assessments start with warm caches. Runs every 2 hours with 10-minute jitter. Inherits
rate limiting from the engine's `robust_request` and `EnhancedCacheManager`.

### Cache Warmer Files

- `deploy/risk/cache_warmer_process.py` — standalone Python warmer
- `deploy/risk/cache-warmer.service` — systemd oneshot unit
- `deploy/risk/cache-warmer.timer` — systemd timer (every 2h at :30 past)

### Cache Warmer Install

```bash
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/cache-warmer.service /etc/systemd/system/cache-warmer.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/risk/cache-warmer.timer /etc/systemd/system/cache-warmer.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cache-warmer.timer
sudo systemctl list-timers --all | grep cache-warmer
```

### Cache Warmer Manual One-shot

```bash
sudo /opt/defi-risk/app/.venv/bin/python \
    /opt/hodler-suite/web_portal/deploy/risk/cache_warmer_process.py \
    --engine-root /opt/defi-risk/app/scripts/v2.0 \
    --env-file /opt/hodler-suite/.env \
    --max-tokens 10 \
    --max-runtime-seconds 300
```

### Cache Warmer Env Keys (Optional)

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `RISK_ENGINE_ROOT` — path to the legacy engine scripts/v2.0 directory
- `RISK_ENGINE_ENV_FILE` — path to .env with API keys
- `CACHE_WARMER_MAX_TOKENS=10` — max tokens to refresh per run (default 10)
- `CACHE_WARMER_MAX_RUNTIME_SECONDS=300` — hard runtime cap in seconds (default 300)

## Data Plane Freshness (Season 4 - Status Dashboard)

The Services Status page now includes a "Data Plane Freshness" section that reads
cache files from the engine's data directory and surfaces:

- **Token Data Cache** card: total/fresh/stale/expired token counts, freshness bar
- **Compliance Datasets** card: age of OFAC, ScamSniffer, and Chainalysis files

Operational alerts fire when:

- Fresh token ratio drops below 50% (warning) or 25% (critical)
- Any compliance dataset exceeds its expected refresh interval
- Cache files are missing or unreadable

No additional env vars needed; the status page reads `RISK_ENGINE_ROOT` to locate
the data directory.

## Timer Schedule Summary

| Timer | Schedule | Jitter | Purpose |
| --- | --- | --- | --- |
| `risk-worker.timer` | Every 30s | None | Poll for queued risk jobs |
| `dataset-refresh.timer` | Every 6h at :15 | 5 min | Refresh compliance datasets |
| `cache-warmer.timer` | Every 2h at :30 | 10 min | Warm stale token cache entries |

Verify all timers with:

```bash
sudo systemctl list-timers --all | grep -E 'risk-worker|dataset-refresh|cache-warmer'
```
