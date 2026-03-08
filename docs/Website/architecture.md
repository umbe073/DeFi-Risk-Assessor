# Core Engine & Workflow

This page describes how the v2.0 engine orchestrates a full DeFi token risk
assessment, from command-line entrypoint to final reports.

The reference implementation lives primarily in:

- `scripts/v2.0/defi_complete_risk_assessment_clean.py`

Additional helper scripts (for example, `update_token_data_viewer.py`,
`refresh_token_data_viewer.py`, and dashboard helpers) plug into the same data
directories and report outputs.

---

## High-level flow

At a high level, a full run does the following:

1. **Initializes environment and paths**  
   - Determines `PROJECT_ROOT`, `DATA_DIR`, `LOGS_DIR`.  
   - Ensures these directories exist.  
   - Sets timestamped paths such as:
     - `RISK_REPORT_DIR`
     - `EXCEL_REPORT_PATH`, `RISK_REPORT_JSON`, `RISK_REPORT_CSV`
     - `*_LATEST` aliases for dashboards.

2. **Initializes shared services**  
   - Optional `cache_manager` from `cache_manager.get_cache_manager(DATA_DIR)`  
   - Optional `error_handler` from `api_error_handler.get_error_handler(DATA_DIR)`  
   - `SharedAPIScheduler` with global worker pool and per-service semaphores  
   - HTTP request state and rate-limit tracking structures.

3. **Loads configuration and datasets**  
   - Token universe from `DATA_DIR/tokens.csv`.  
   - Fallback definitions from `DATA_DIR/fallbacks/fallbacks.json`.  
   - Token Data Viewer snapshot from `DATA_DIR/token_data_viewer.csv`.  
   - EU-mode configuration and regulated stablecoin allow-list.  
   - Caching and request policy from `DATA_DIR/settings.json`.

4. **Processes tokens in batches**  
   - For each token (address + symbol + chain), the engine:
     1. Builds a per-token context (chain, symbol, tags, maybe allow-list status).  
     2. Submits many data-fetch tasks through the shared scheduler.  
     3. Applies caching and rate-limit-aware HTTP logic.  
     4. Normalizes responses into an internal `token_entry` structure.

5. **Calculates scores and red flags**  
   - Derives component quality scores (1–10) for behavioral categories.  
   - Converts them into risk contributions (0–10) using weights.  
   - Applies red-flag boosts and market-structure penalties.  
   - Aggregates into a final risk score and credibility signals.

6. **Persists reports**  
   - Writes JSON, CSV and XLSX reports to timestamped files.  
   - Updates `*_latest` aliases for dashboards and downstream tooling.  
   - Optionally generates a social score analysis report.

---

## SharedAPIScheduler & concurrency model

The engine avoids per-token thread pools and instead uses a **shared scheduler**
so that concurrency limits are enforced globally.

Key object (simplified):

```200:211:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
class SharedAPIScheduler:
    def __init__(self, max_workers: int = 12, api_caps: Optional[Dict[str, int]] = None) -> None:
        self.max_workers = max(1, int(max_workers))
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.api_caps: Dict[str, int] = dict(api_caps or {})
        self._semaphores = {
            str(api).lower(): threading.BoundedSemaphore(max(1, int(cap)))
            for api, cap in self.api_caps.items()
        }

    def submit(self, api_name: str, fn: Callable[..., Any], *args, **kwargs):
        ...
        return self.executor.submit(wrapped)
```

Usage pattern:

- Heavy data-fetch tasks call `get_shared_api_scheduler().submit("service_name", fn, ...)`.
- The scheduler enforces both:
  - a global thread limit (`max_workers`), and  
  - per-service concurrency caps via semaphores in `_semaphores`.

### Why this matters

- Prevents nested executors from oversubscribing CPU/network.  
- Ensures that sensitive APIs (e.g. TRM, Arkham, sanctions datasets) have strict
  concurrency caps even when many tokens are processed at once.  
- Keeps CPU and I/O usage more predictable in production environments.

---

## Token processing lifecycle

Conceptually, each token goes through the following stages:

1. **Discovery**: read from `tokens.csv` (address, symbol, chain, labels).  
2. **Bootstrap**: attach cached viewer/fallback data if available.  
3. **Data fetch**: schedule multiple API calls through the scheduler.  
4. **Normalization**: consolidate raw responses into a uniform internal model.  
5. **Scoring**: compute behavioral component scores and overall risk.  
6. **Persistence**: write to JSON/CSV/XLSX and, optionally, social reports.

The implementation is structured so that the scoring pipeline can be reused with
different data sources (e.g. live-only vs. cache-heavy modes) without changing
the core model.

---

## Cache manager and error handler integration

Two plug-in style components enhance the core script:

- **cache_manager** – centralizes cache operations and policies.  
- **error_handler** – manages per-service health, cooldowns and error logging.

When available, `cache_manager` is preferred over the legacy JSON cache helpers:

```356:362:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
try:
    from cache_manager import get_cache_manager
    cache_manager = get_cache_manager(DATA_DIR)
    print("✅ Enhanced cache manager initialized")
except ImportError:
    print("⚠️ Enhanced cache manager not available, using basic cache")
    cache_manager = None
```

Similarly, the enhanced API error handler is loaded if present:

```365:371:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
try:
    from api_error_handler import get_error_handler
    error_handler = get_error_handler(DATA_DIR)
    print("✅ Enhanced API error handler initialized")
except ImportError:
    print("⚠️ Enhanced API error handler not available, using basic error handling")
    error_handler = None
```

If these modules are not importable, the engine falls back to embedded basic
cache and error-handling logic.

---

## Where to go next

- See **[Data Fetching & Caching](data-fetching-and-caching.md)** for a deep dive
  into HTTP handling, rate limits and cache layout.
- See **[Scoring Model & Categories](scoring-model.md)** for how token entries
  are turned into numeric scores and red flags.

