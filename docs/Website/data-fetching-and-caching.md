# Data Fetching & Caching

This page explains how the engine talks to external APIs, honors rate limits and
uses multiple layers of caching and fallbacks to keep runs fast and stable.

---

## Legacy cache helpers

At the top of `defi_complete_risk_assessment_clean.py` a basic JSON-based cache
is defined for tokens:

```24:62:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
cache_manager = None

def load_cached_data(token_address):
    \"\"\"Load cached data for a token, fallback to real-time if not available\"\"\"
    if cache_manager:
        return cache_manager.get_cached_data(token_address)
    ...
    cache_file = os.path.join(DATA_DIR, 'real_data_cache.json')
    ...
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        tokens = cache_data.get('tokens', {})
        ...
        if token_address in tokens and cache_age_hours < 2:
            return cached_data
```

The matching writer updates this JSON cache and triggers a local webhook:

```62:96:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def update_cache_with_real_time_data(token_address, real_time_data):
    \"\"\"Update cache with real-time data\"\"\"
    if cache_manager:
        cache_manager.update_cache_with_real_time_data(token_address, real_time_data)
        return
    ...
    cache_file = os.path.join(DATA_DIR, 'real_data_cache.json')
    ...
    cache_data['tokens'][token_address] = real_time_data
    cache_data['last_updated'] = time.time()
    ...
    requests.post('http://localhost:5001/webhook/update_token',
                  json={'token_address': token_address}, timeout=5)
```

This legacy layer is still used as a **fallback** when the enhanced cache manager
is not available.

---

## Intelligent cache wrapper

The higher-level helper `fetch_data_with_cache_fallback` encapsulates the main
fetch strategy:

```99:141:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def fetch_data_with_cache_fallback(token_address, fetch_function):
    \"\"\"Fetch data with priority-based strategy:
    1. Run assessment -> API works, no rate limitation -> Obtain real-time data and use it
    2. Run assessment -> API works, rate limitation -> Get data until rate limited, then use fallback
    3. Run assessment -> API does not work -> fetch fallback data directly
    \"\"\"
    if cache_manager:
        return cache_manager.fetch_data_with_intelligent_cache(token_address, fetch_function)
    ...
    cached_data = load_cached_data(token_address)
    if cached_data:
        return cached_data
    ...
    real_time_data = fetch_function(token_address)
    if real_time_data:
        update_cache_with_real_time_data(token_address, real_time_data)
        return real_time_data
    ...
    if \"rate limit\" in str(e).lower() or \"429\" in str(e):
        # Priority 2: API works but rate limited
        ...
```

If an enhanced `cache_manager` is provided, the function hands control to
`fetch_data_with_intelligent_cache`, which can apply additional policies such as:

- cache retention windows per metric,  
- metric-drift thresholds (only refresh when values move by X%),  
- provenance tracking (live vs cache vs fallback).

---

## Disk-backed APICache

For generalized HTTP responses and intermediate values, the engine uses
`diskcache.Cache` through an `APICache` wrapper:

```2039:2055:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
class APICache:
    def __init__(self, filename='api_cache.db'):
        self.filename = os.path.join(DATA_DIR, filename)
        self.cache = None
        ...
        self.cache = Cache(self.filename)
        ...
        self.cache.set('test', 'test', expire=1)
        test_result = self.cache.get('test')
```

Methods like `get`, `set` and `close` wrap calls to `diskcache.Cache` with
defensive error handling so that cache failures never break a run.

The main engine instantiates `APICache` inside a controller/manager class that
also tracks:

- cache hits / misses,  
- number of successful vs failed assessments,  
- various error lists and diagnostics.

---

## HTTP request policy & rate-limit tracking

The HTTP layer goes beyond naive `requests.get`. It maintains a structured
**request policy** and **per-service rate-limit state**.

Key pieces:

- `_service_rate_limit_state`: in-memory dict keyed by service name.  
- `_http_request_state_file`: JSON on disk (`http_request_state.json`) used to
  persist ETag / Last-Modified and small response bodies.  
- `_service_toggle_cache` and `settings.json`: allow per-service enable/disable
  and rate-limit policy tweaks.

Request policy loader (simplified):

```3448:3477:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _load_request_policy_from_settings():
    ...
    cache_cfg = loaded_settings.get('cache', {}) if isinstance(loaded_settings, dict) else {}
    ...
    policy = {
        'rate_limiting': bool(api_cfg.get('rate_limiting', True)),
        'metric_drift_threshold_pct': max(0.0, float(cache_cfg.get('metric_drift_threshold_pct', 2.0) or 2.0)),
        ...
    }
    _request_policy_cache['ts'] = now_ts
    _request_policy_cache['policy'] = policy
```

Before issuing a request, `_preemptive_rate_limit_gate` checks whether a service
is currently in a cooldown window and, if so, returns a synthetic rate-limited
response instead of hitting the network again.

After each response, `_update_service_rate_limit_state` updates that service’s
cooldown and usage metrics, honoring headers like `Retry-After` when present.

---

## Conditional requests & cached bodies

To reduce bandwidth and avoid burning rate limits on unchanged data, the HTTP
layer supports conditional requests:

- Stores ETag and Last-Modified per URL.  
- Sends `If-None-Match` / `If-Modified-Since` when re-requesting.  
- On a `304 Not Modified`, reuses the cached body (if stored).

Cached conditional entries live in `HTTP_REQUEST_STATE_FILE` and contain:

- URL,  
- last status,  
- ETag / Last-Modified headers,  
- optionally a small `cached_body` for JSON payloads under a size threshold.

When a service is in cooldown but a previous conditional entry exists, the
engine can return a synthetic “rate-limited” response with the cached body
instead of failing outright.

---

## Webhook integration

Whenever new real-time token data is written to the legacy JSON cache, the
engine optionally triggers a local webhook:

- URL: `http://localhost:5001/webhook/update_token`  
- Payload: `{"token_address": "<address>"}`  
- Timeout: 5 seconds, best-effort only.

This allows:

- lightweight dashboards to update without polling the filesystem,  
- incremental refresh of a subset of tokens after a long run.

Consumers are free to ignore this webhook or replace it with a different
notification mechanism.

---

## Summary

Data fetching and caching in the DeFi Risk Assessment Suite are intentionally
conservative:

- Always prefer cached or conditional data when fresh enough.  
- Automatically back off when rate limits or transient errors occur.  
- Persist enough state on disk to make subsequent runs cheaper and more stable.  
- Expose configuration in `settings.json` so operators can tune the balance
  between freshness, cost and rate-limit pressure.
