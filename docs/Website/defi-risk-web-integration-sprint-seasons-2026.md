# DeFi Risk App Web Integration Sprint Seasons (2026)

Last updated: 2026-03-05

## Purpose

Integrate the legacy desktop-oriented DeFi risk stack into the production web product without breaking scoring logic, while meeting production reliability and confidentiality targets.

Primary targets:

- Availability target: 99.9% online time for critical API/runtime surfaces.
- Confidentiality target: >=95% API/security score for exposed services.
- Web UX target: assessment and settings flows are fully web-native and plan-aware.

## Legacy Inputs To Integrate

Key legacy components and required web adaptation:

1. [`scripts/v2.0/run_risk_assessment.sh`](<PROJECT_ROOT>/scripts/v2.0/run_risk_assessment.sh)
   - Desktop launcher behavior must be decomposed into server services and scheduled jobs.
2. [`scripts/v2.0/webhook_server.py`](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py)
   - Must run 24/7 with health visibility in Services Status.
3. [`scripts/v2.0/defi_complete_risk_assessment_clean.py`](<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py)
   - Must be wrapped for async web execution while preserving calculation/output parity.
4. [`scripts/v2.0/working_progress_bar.py`](<PROJECT_ROOT>/scripts/v2.0/working_progress_bar.py)
   - Must be mapped into `/live-assessment` with better stage detection and progress fidelity.
5. `/settings` IA split requirements
   - `/settings/overview`
   - `/settings/api-center`
   - `/settings/crypto-list`

## Permission And Plan Rules (Contract)

Role invariants:

- `master` and `admin`: always see and can access Settings family routes.
- `child` accounts: access controlled by plan entitlements.

Plan entitlements:

1. `Settings` (`/settings`, `/settings/overview`)
   - `child`: Basic/Pro/Enterprise only.
   - `admin/master`: always allowed.
2. `API Center` (`/settings/api-center`)
   - `child`: Basic/Pro/Enterprise only.
   - `admin/master`: always allowed.
3. `Crypto List / Token Editor` (`/settings/crypto-list`)
   - visible for all plans/roles.
   - action-level limits must be plan-based (not only UI-based).

Enforcement rule:

- all plan gates and limits must be server-side (backend authorization + quota checks), not client-only.

## Sprint Seasons

## Season 1: Monolith Decomposition + Runtime Contracts

Goal:

- Split desktop launcher responsibilities into web-runtime services.

Deliverables:

- service contract map: `web_portal`, `script_api`, `risk_worker`, `cache_worker`, `scheduler`.
- normalized job request/response schema for risk runs.
- explicit artifact contract (log/output/report locations and retention).
- compatibility shim list for legacy entrypoints.

Exit criteria:

- no production flow depends directly on desktop launcher orchestration.

## Season 2: 24/7 Script API Runtime + Status Telemetry

Goal:

- Run `webhook_server.py` continuously with first-class observability.

Deliverables:

- hardened systemd service + restart policy + watchdog thresholds.
- status ingestion into Services Status page (uptime/latency/error trend).
- structured health probes and alert thresholds.

Exit criteria:

- 7-day stability run with tracked uptime and failure reasons.

## Season 3: Risk Engine Worker Adapter

Goal:

- Execute `defi_complete_risk_assessment_clean.py` in async web workflows without logic drift.

Deliverables:

- queue-backed execution wrapper with job IDs and stages.
- input normalization (`address`/`token_address` compatibility preserved).
- standardized result payload mapping to dashboard and live-assessment pages.
- regression harness comparing web outputs vs desktop baseline samples.

Exit criteria:

- parity checks pass for representative token set and failure taxonomy is stable.

## Season 4: Perpetual Data Plane (Oracles/Modules/Smart-Cache)

Goal:

- Keep data dependencies warm and resilient in background.

Deliverables:

- cache warmers and refresh schedulers with jitter/backoff.
- upstream fallback policy and stale-data safeguards.
- runtime metrics: freshness lag, fallback usage, provider error rates.

Exit criteria:

- sustained freshness SLO with no single-provider hard dependency.

## Season 5: Live Assessment UX Rebuild

Goal:

- Replace legacy progress rendering with reliable web-native progress at `/live-assessment`.

Deliverables:

- stage detector bound to worker events (not weak log scraping only).
- deterministic progress transitions and timeout/error states.
- UI footer section:
  - text: `Our results are based on the following services:`
  - provider logos below the text as attestations.

Exit criteria:

- user-visible progress aligns with backend stage transitions in test scenarios.

## Season 6: Dashboard Binding + Output Reliability

Goal:

- Fully wire dashboard to live runtime outputs.

Deliverables:

- dashboard cards for latest run status, risk summary, cache freshness, and service health.
- deterministic empty/error states with operational context.
- links to underlying artifacts/log slices where safe.

Exit criteria:

- dashboard is fully data-driven and accurate under normal + degraded conditions.

## Season 7: Settings IA + Entitlement Middleware

Goal:

- Implement settings route split and centralized entitlements.

Deliverables:

- route/view split:
  - `/settings/overview`
  - `/settings/api-center`
  - `/settings/crypto-list`
- backend entitlement middleware for role+plan gates.
- token editor limits and action guardrails by plan.

Exit criteria:

- permission matrix enforced server-side and validated with role/plan tests.

## Season 8: Quotas, Limits, And Abuse Controls

Goal:

- Enforce product limits and protect runtime stability.

Deliverables:

- daily scan limits by plan.
- API usage caps/feature toggles by plan tier.
- abuse controls, audit logs, and immutable entitlement decisions.

Exit criteria:

- limit enforcement cannot be bypassed via direct API calls.

## Season 9: SLO Gate + Production Readiness

Goal:

- Reach release quality gates for reliability, security, and operations.

Deliverables:

- SLO dashboards and error-budget tracking.
- incident runbooks for provider outage, queue backlog, and cache corruption.
- security verification cycle for public/API surfaces.

Exit criteria:

- 99.9% availability target tracking in place and confidentiality target >=95% validated by checklist.

## Phase Sequencing (Suggested)

1. Seasons 1-3 (foundation and adapter path).
2. Seasons 4-6 (data-plane reliability and UX/data binding).
3. Seasons 7-9 (entitlements hardening and release gates).

## Immediate Backlog (Kickoff For Season 1)

1. Create a service boundary diagram from current desktop scripts and web portal modules.
2. Define risk-run job schema (`job_id`, `token`, `mode`, `stage`, `progress`, `artifacts`, `error_code`).
3. Document compatibility requirements from existing script CLI/env assumptions.
4. Create migration checklist for launcher responsibilities currently inside `run_risk_assessment.sh`.
5. Add acceptance test list for baseline parity scenarios.

## Kickoff Progress (2026-03-05)

1. Completed: initial service boundary artifact drafted:
   - [defi-risk-season1-service-boundary-map-2026-03-05.md](<PROJECT_ROOT>/docs/Website/defi-risk-season1-service-boundary-map-2026-03-05.md)
2. Completed: initial risk-worker persistence and API scaffold in web portal:
   - `app/risk_job_store.py` (job/event/artifact schema + lifecycle methods),
   - `app/routes/risk.py` (`/api/v1/risk/jobs` create/list/get/cancel + internal worker event ingestion),
   - config/env wiring (`WEB_PORTAL_RISK_JOB_DB`, `RISK_WORKER_SHARED_SECRET`).
3. Next:
   - draft compatibility endpoint contract for legacy webhook callers,
   - wire `risk_worker` execution engine to push stage/progress events into `/api/v1/risk/jobs/<job_id>/events`.

## Season 2 Kickoff Progress (2026-03-05)

1. Completed: status telemetry key isolation fixes in web portal snapshot collector:
   - Script API card now uses `service_key=script_api`,
   - chain RPC cards now use dedicated keys (`chain_eth_rpc`, `chain_bsc_rpc`, `chain_tron_rpc`) instead of shared key collisions.
2. Completed: probe-threshold operational alerting wired for Script API and chain probes:
   - failure streak thresholds,
   - rolling error-rate thresholds,
   - rolling latency thresholds,
   - emitted as `status_probe` operational alerts with stable event keys.
3. Completed: Services Status card metrics expanded with short-window trend signals:
   - `error_rate_6h`,
   - `failure_streak` + streak state.
4. Completed: initial 24/7 Script API runtime deploy pack artifacts added:
   - `deploy/status/hodler-script-api.service`,
   - `deploy/status/script_api_watchdog.sh`,
   - `deploy/status/script-api-watchdog.service`,
   - `deploy/status/script-api-watchdog.timer`,
   - `deploy/status/SCRIPT_API_RUNTIME.md`.
5. Next:
   - deploy and enable Script API runtime + watchdog on staging/prod,
   - run 7-day stability sample window and tune threshold values based on observed baseline latency/error behavior.

## Season 3 Kickoff Progress (2026-03-05)

1. Completed: queue claim + worker execution path wired into risk job store/API:
   - atomic queue claim (`claim_next_job`) in `app/risk_job_store.py`,
   - internal secret-protected worker endpoints:
     - `POST /api/v1/risk/internal/claim`,
     - `POST /api/v1/risk/internal/run-once`,
   - staged progress/events and artifact emission for each processed job.
2. Completed: dashboard/live-assessment pages bound to real job state:
   - `/dashboard` now shows risk queue counters, 24h outcomes, active/latest links, and recent jobs table,
   - `/live-assessment` now supports in-page job creation, polling, progress rendering, event logs, and artifact display.
3. Completed: Season 3 deploy pack scaffold added:
   - `deploy/risk/risk_worker_run_once.sh`,
   - `deploy/risk/risk-worker.service`,
   - `deploy/risk/risk-worker.timer`,
   - `deploy/risk/RISK_WORKER_RUNTIME.md`,
   - deploy-pack verifier updated to include `risk-worker`.
4. Completed: Services Status board upgraded for risk pipeline observability:
   - new `Risk Engine Runtime` cards (queue depth, stale-running detection, throughput/failure-rate window),
   - status sampling now persists risk-runtime cards with same uptime/error telemetry stack,
   - CSP-safe external JS added for meter/chart rendering (inline script removed).
5. Completed: Services Status expanded with infra/public-edge monitors:
   - new `Public Edge` cards for `hodler-suite.com` and `app.hodler-suite.com`,
   - new `Infrastructure` cards for local Nginx proxy, TLS edge certificate lifetime, and storage/DB footprint thresholds,
   - infra alert hooks added for low disk/large DB footprint and TLS probe degradation.
6. Next:
   - replace deterministic placeholder result generation with direct adapter mapping from the legacy scoring engine,
   - add parity checks against baseline desktop output samples for representative tokens.
