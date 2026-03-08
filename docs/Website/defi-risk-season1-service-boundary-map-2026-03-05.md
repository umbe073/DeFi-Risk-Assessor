# Season 1 Service Boundary Map (DeFi Web Integration)

Last updated: 2026-03-05

This document is the first implementation artifact for Season 1 (monolith decomposition + runtime contracts).

## Current-State Runtime Coupling

## Desktop launcher responsibilities (to be split)

Source: [`scripts/v2.0/run_risk_assessment.sh`](<PROJECT_ROOT>/scripts/v2.0/run_risk_assessment.sh)

Current script bundles multiple responsibilities in one entrypoint:

1. system tray UX launch (`dashboard/system_tray.py`).
2. webhook server lifecycle (start/stop on port `5001`).
3. cache refresh trigger (`POST http://localhost:5000/refresh_cache`).
4. token data viewer update helper (`update_token_data_viewer.py`).
5. credentials setup/validation orchestration (`credential_management/*`).

Implication:

- desktop launcher acts as orchestrator and runtime supervisor, which is incompatible with web production topology.

## Webhook server responsibilities

Source: [`scripts/v2.0/webhook_server.py`](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py)

Active API surfaces:

1. `POST /webhook/update_all` (sync/async full refresh)
2. `GET /webhook/update_all_status`
3. `POST /webhook/update_token`
4. `GET /webhook/status`
5. `GET /webhook/cache`
6. `GET /webhook/health`

Cross-cutting behavior:

- local cache/symbol/fallback persistence and cleanup,
- source-level metric skip/fallback logic,
- webhook auth/signature gate (`WEBHOOK_SHARED_SECRET`, signature timestamp/HMAC),
- in-process async background job for full cache refresh.

Implication:

- script currently mixes API transport, orchestration, cache persistence, and data-source logic.

## Web portal status surfaces

Source: [`scripts/v2.0/web_portal/app/routes/pages.py`](<PROJECT_ROOT>/scripts/v2.0/web_portal/app/routes/pages.py)

Current relevant route state:

1. `/dashboard` exists and is auth-gated.
2. `/live-assessment` exists and is auth-gated.
3. `/settings` currently single-route page, not split into:
   - `/settings/overview`
   - `/settings/api-center`
   - `/settings/crypto-list`

Implication:

- route/UX skeleton exists, but DeFi runtime contracts and settings segmentation are not yet bound.

## Target Service Boundaries

## Service A: `web_portal` (UI + auth + billing + support)

Scope:

- user-facing pages, RBAC/plan gating, CSRF/session, support, billing.

Non-goals:

- no heavy market/oracle computation in request thread.

## Service B: `script_api` (always-on internal API)

Scope:

- expose controlled endpoints for token refresh/status/cache reads.
- host compatibility endpoints required by legacy callers during transition.

Non-goals:

- no user auth UI responsibilities.

## Service C: `risk_worker`

Scope:

- execute `defi_complete_risk_assessment_clean.py` jobs asynchronously.
- emit normalized run-stage/progress events for `/live-assessment`.

Non-goals:

- no direct external internet exposure.

## Service D: `cache_worker`

Scope:

- scheduled cache warmup, fallback sync, source freshness checks.

Non-goals:

- no user request handling.

## Service E: `scheduler`

Scope:

- timer-driven orchestration of recurring jobs (`update_all`, warmers, cleanup).

Non-goals:

- no business/UI logic.

## Contract Draft (v0)

Minimum normalized job model for web integration:

1. `job_id` (unique id)
2. `token` (address + chain context)
3. `mode` (eu/global)
4. `stage` (queued/running/fetching/analyzing/finalizing/succeeded/failed)
5. `progress` (0-100 integer)
6. `artifacts` (report/log/cache refs)
7. `error_code` and `error_message` (if failed)
8. `started_at`, `finished_at`, `duration_ms`

## Decomposition Checklist (Season 1)

1. Extract launcher-only concerns from `run_risk_assessment.sh` into deploy/service scripts.
2. Define `script_api` compatibility layer for legacy webhook endpoints.
3. Move background refresh from in-process thread model into managed worker/scheduler path.
4. Define durable state storage for run/progress/events consumed by `/live-assessment`.
5. Add settings route split scaffold with backend entitlement middleware stubs.

## Exit Criteria For Season 1

1. service boundary document approved and versioned.
2. runtime contracts drafted for `script_api` and `risk_worker`.
3. migration checklist for launcher responsibilities completed.
4. implementation tickets created for Seasons 2-3 based on this map.

