# Web Port Security Implementation Plan (2026)

Last updated: 2026-03-04

## Goal

Port the current desktop-oriented toolchain to a production-grade web product with:

- strong API and infrastructure security,
- role-based account separation (master/admin vs end-user),
- subscription billing with crypto checkout,
- low operational complexity for v1.

This plan is mapped to the current codebase so implementation can start immediately.

## Product scope for web v1

Pages to deliver:

- Homepage: left-side menu, interactive media blocks, trailer video, product summary, social/help links.
- Main Dashboard: status, cache health, token metrics, quick actions.
- Live Assessment page: live logs + progress bar (move current ad-hoc `/tmp` output into a productized page).
- Settings page: runtime settings and operational toggles.
- Account page: master/admin controls plus standard user profile/security/preferences.
- Help Center page: ticket intake + AI pre-triage assistant.
- FAQ page.
- Docs page: integrate existing docs after sensitive-data redaction pass.
- Checkout page: subscription plan selection and redirect flow to payment gateway.

## Recommended implementation path

For secure and straightforward delivery from current state:

- Backend/UI: Flask app factory + server-rendered pages (Jinja2 + HTMX).
- Jobs: background queue for risk runs, cache refresh, and report generation.
- Auth: OIDC + mandatory MFA + RBAC.
- Billing: gateway adapter with NOWPayments-first implementation.
- Infra: Kamatera VPS with segmented services behind reverse proxy and strict firewall policy.

Why this path:

- fastest path from your current Flask/webhook architecture,
- reduced attack surface versus a large SPA + public API-first rollout,
- clear security boundaries before exposing billing endpoints.

## Current-state findings mapped to code

1. Legacy webhook endpoints were previously unauthenticated and state-changing (now mitigated with shared-secret auth + signed requests):
   - [scripts/v2.0/webhook_server.py:3582](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py:3582)
   - [scripts/v2.0/webhook_server.py:3653](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py:3653)
2. Full cache dump endpoint existed as an unprotected surface (now gated by authenticated access when webhook security mode is enabled):
   - [scripts/v2.0/webhook_server.py:3744](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py:3744)
3. Legacy launcher still contains host-specific environment coupling:
   - [scripts/v2.0/run_risk_assessment.sh:10](<PROJECT_ROOT>/scripts/v2.0/run_risk_assessment.sh:10)
4. Flask development server used directly (no production WSGI process manager):
   - [scripts/v2.0/webhook_server.py:3785](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py:3785)
5. Assessment script already produces stable report artifacts usable via API:
   - [scripts/v2.0/defi_complete_risk_assessment_clean.py:335](<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py:335)
   - [scripts/v2.0/defi_complete_risk_assessment_clean.py:17313](<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py:17313)
6. Legacy payload mismatch path identified and now backward-compatible:
   - caller now sends both keys (`address` + `token_address`): [scripts/v2.0/defi_complete_risk_assessment_clean.py:114](<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py:114)
   - webhook accepts either key: [scripts/v2.0/webhook_server.py:3662](<PROJECT_ROOT>/scripts/v2.0/webhook_server.py:3662)
7. Tests include absolute-path assumptions:
   - [scripts/v2.0/tests/integration/test_dashboard_data_fetching.py:13](<PROJECT_ROOT>/scripts/v2.0/tests/integration/test_dashboard_data_fetching.py:13)

## Account and permission model

Roles:

- `super_admin` (master account): global settings, credentials lifecycle, billing ownership, user/role management, incident controls.
- `ops_admin`: runtime and assessment controls, report access, no payout-wallet or API-key operations.
- `billing_admin`: subscription plans, invoices, payment status, no operational runtime mutation.
- `customer_user`: profile, password, 2FA, notification settings, subscription visibility/management.

Security constraints:

- all role elevation changes require step-up MFA and audit log.
- no raw API keys or secrets rendered in web UI.
- account-critical changes require re-authentication window.

## Site map and feature breakdown

## Homepage

Includes:

- left navigation equivalent to current desktop dropdown,
- hero media (interactive images/cards),
- embedded trailer video,
- concise product description,
- social and help links in footer area.

Security notes:

- no operational data on anonymous homepage.
- static media served through strict CSP.

## Main Dashboard

Includes:

- service health, cache freshness, token counts,
- quick actions: refresh cache, run assessment, open reports,
- links to live logs page.

Security notes:

- authenticated only.
- operator actions require CSRF protection and RBAC.

## Live Assessment

Includes:

- real-time run progress,
- streaming logs,
- state transitions and completion artifacts.

Security notes:

- logs redacted before client broadcast.
- tenant/user scoping on run visibility.

## Settings

Includes:

- safe runtime toggles,
- read-only credential health indicators,
- environment diagnostics without secret disclosure.

## Accounts

Includes:

- master/admin panel for global controls,
- standard user panel for profile/email/password/2FA/picture,
- notification preferences (desktop/browser),
- subscription management view.

## Help Center and FAQ

Includes:

- ticket intake form,
- AI pre-triage assistant,
- FAQ knowledge navigation.

Security notes:

- abuse protections (rate-limit + CAPTCHA on public forms).
- prompt/response filtering to avoid secret leakage.

## Docs

Includes:

- integration of existing documentation.

Mandatory pre-publication step:

- automated redaction scan across docs for local paths and secrets.

## Checkout

Includes:

- plan picker,
- secure handoff to payment provider,
- post-payment verification and subscription state sync.

Security notes:

- no trust in client redirect alone.
- subscription activated only after verified provider callback.

## External platform choices (validated for early 2026)

## Crypto payments (NOWPayments)

Recommendation for v1:

- use NOWPayments invoice/checkout flow first,
- implement webhook verification and idempotent state updates,
- keep adapter interface so migration remains possible.

Why:

- fastest integration path with lower operational burden than self-hosted payment processing.

Known constraints from vendor docs:

- IPN requires generated IPN secret; without it callbacks may not be sent.
- verify `x-nowpayments-sig` using HMAC-SHA512 over sorted JSON body.
- callback endpoint must be internet-reachable (not localhost) and respond quickly.
- payout protections include IP whitelisting, wallet whitelisting, and 2FA.

## Business email (minimum 3 addresses, lowest cost)

Practical options:

- Option A (recommended free baseline): Cloudflare Email Routing.
  - Pros: free, private-by-design, supports many custom addresses, simple setup.
  - Cons: forwarding-only, not a full outbound mailbox system.
- Option B (if full mailboxes needed and available in your region): Zoho Mail Free.
  - Pros: up to 5 users on one domain, true hosted inboxes.
  - Cons: region-limited availability, web-only on free tier, no IMAP/POP/ActiveSync.

Decision:

- start with Cloudflare Email Routing for at least 3 role addresses (`security@`, `support@`, `billing@`).
- if true mailbox collaboration is needed, move to paid mailbox plan.

## Domain and DNS

Recommendation:

- register domain through Cloudflare Registrar when available for target TLD.

Why:

- at-cost renewals (no registrar markup), DNSSEC support, redacted WHOIS, and tight DNS/security integration.

Initial domain structure:

- `app.<domain>`: web app.
- `docs.<domain>`: docs portal.
- `status.<domain>`: status page (optional in v1).

## AI-assisted ticket pre-triage

Recommendation:

- self-host Chatwoot Community Edition for support inbox/tickets,
- pair with a small AI triage service (Dify or internal LLM worker) via webhook.

Rationale:

- Chatwoot Community is free self-hosted and keeps data under your infrastructure control.
- Chatwoot cloud free plan has strong limits; AI features are paid.

## Docs generator trajectory (MkDocs context)

Because MkDocs ecosystem direction changed (MkDocs 2.0 pre-release and Material maintenance mode), plan includes:

- keep current docs pipeline stable for now,
- add migration spike to evaluate Zensical compatibility in a non-production branch.

## Epics

## Epic 1: Web foundation and route boundaries

Outcome:

- clear split between public pages, authenticated app routes, and internal operations API.

Deliverables:

- Flask app factory and blueprint structure.
- strict request validation and response schemas.
- no direct exposure of internal webhook controls.

## Epic 2: Page delivery (homepage + core app pages)

Outcome:

- complete web navigation parity with desktop flows plus new account/help/checkout surfaces.

Deliverables:

- homepage, dashboard, live-assessment, settings, accounts, help, FAQ, docs, checkout.

## Epic 3: Identity and authorization

Outcome:

- role model enforced across all routes and actions.

Deliverables:

- OIDC + MFA, role middleware, audit trails, session security policies.

## Epic 4: Assessment orchestration and live logs

Outcome:

- non-blocking run execution and auditable run history.

Deliverables:

- queued run execution, progress endpoint/SSE, log sanitization pipeline.

## Epic 5: Billing and subscription enforcement

Outcome:

- verified payment events drive entitlement state machine.

Deliverables:

- checkout session endpoint,
- webhook ingestion with signature verification and replay protection,
- subscription status API and feature-gating.

## Epic 6: Help center and AI triage

Outcome:

- bug reports and support requests pre-classified before human handling.

Deliverables:

- ticket intake API,
- AI pre-triage worker,
- confidence/routing labels and escalation rules.

## Epic 7: Security hardening and launch readiness

Outcome:

- production passes security gate before internet exposure.

Deliverables:

- infra hardening, SAST/DAST gates, incident runbooks, restore drills.

## Implementation status snapshot (2026-03-04)

## Completed implementation

- Web portal scaffold is live with route separation for public pages, authenticated pages, and workflow APIs.
- Role-aware account model is live for local auth store (`master`, `admin`, `child`) with session guards and CSRF checks.
- 2FA TOTP setup/challenge is operational, with account and login recovery via email verification code.
- Core pages are delivered: homepage, dashboard, live assessment, settings, account, help center, FAQ, docs, checkout, terms, privacy.
- Homepage UX refresh shipped (interactive rotators, media sections, authenticated-aware CTA/menu behavior).
- Help center ticket intake API is delivered for registered and unregistered users.
- Ticketing and support operations expanded:
  - admin/master support queue with bulk status updates and threaded conversation history,
  - support-agent reply flow from web portal,
  - unread-customer counters and operational-alert counters in UI.
- Email automation delivered:
  - account-security flows from `no_reply@hodler-suite.com` (signup verification, reset, email/2FA change flows),
  - support acknowledgment/notifications from `support@hodler-suite.com`.
- Inbound customer reply ingestion delivered:
  - generic inbound webhook + Resend adapter endpoints,
  - persistent webhook idempotency and short retry/backoff for delayed provider availability,
  - periodic fallback sync endpoint and deploy pack (`support-resend-sync` systemd timer/service/script).
- Trustpilot monitoring integration delivered:
  - authenticated Trustpilot webhook relay endpoint (`POST /api/v1/support/webhook/trustpilot`),
  - event deduplication and Slack notification delivery for review events.
- Public ticket abuse protection delivered:
  - per-IP/per-email rate limiting windows with API `429` + `Retry-After`,
  - optional Cloudflare Turnstile full-site human verification gate (`/human-check` + app-wide enforcement toggle).
- Services Status operations board delivered:
  - persisted health samples in `status_metrics.db`,
  - 24h/7d uptime/error-rate summaries,
  - Script API deep probes and chain endpoint health cards.
- Services Status background sampling delivered:
  - protected internal sampler endpoint (`POST /api/v1/internal/status-sample`),
  - deployable `status-sampler` systemd service/timer/script pack for periodic sampling without page visits.
- Script API private-probe hardening delivered:
  - Script API health/deep-probe checks now support shared-secret auth headers for private endpoints,
  - optional timestamped HMAC signature headers on probe requests for signed endpoint verification.
- Billing hardening delivered:
  - NOWPayments webhook signature verification + persisted idempotency,
  - checkout currency availability filtering/fallback,
  - billing reconciliation board,
  - admin/master NOWPayments currency sync + manual override controls,
  - enterprise code creation and reservation lifecycle support.
- Billing reconciliation auto-repair delivered:
  - admin-only row actions on reconciliation board (reapply webhook, manual activation, close false-positive),
  - mandatory reason capture and immutable action-audit rows,
  - false-positive closures now suppress resolved rows from active reconciliation views.
- Auth/session hardening increment delivered:
  - optional step-up TOTP policy gate for sensitive account/admin mutations,
  - session-version invalidation on high-risk account changes (password/email/2FA/admin credential changes),
  - anomaly prompts for new login IP/device contexts.
- User intelligence and secure user-details views delivered:
  - sign-up now captures required profile fields (name/surname, DOB, gender, account type, base region),
  - registration context persistence now stores IP/country/proxy/device fingerprint attributes,
  - operation audit baseline stores unique operation ID + timestamp + IP/device/country/proxy signals for login and sensitive account/admin actions,
  - Account page now includes `Info` action that opens dedicated user-details page with RBAC + short-lived session access token gate (token must be issued from Account flow).
- Telemetry retention controls delivered:
  - configurable retention windows for `user_operation_logs`, `user_devices`, and `user_login_contexts`,
  - startup retention enforcement hook in web app bootstrap,
  - deployable telemetry-retention purge pack (`deploy/privacy/` timer/service/script + runbook).
- Auth failure telemetry + lockout controls delivered:
  - failed-auth counters and temporary lockout policy for login and 2FA challenge paths,
  - configurable lockout policy env controls (window/max-attempts/lockout duration),
  - privileged support/billing mutation routes now emit user-operation audit records with request context.
- Legacy webhook surface hardening delivered:
  - `scripts/v2.0/webhook_server.py` now enforces token auth + timestamped HMAC signatures on mutating endpoints,
  - status/cache/update-all-status endpoints now require authenticated access when security mode is enabled,
  - `update_token` now accepts both `address` and legacy `token_address` payload keys,
  - internal callers (assessment/cache-manager/risk-fetcher + dashboard/system-tray flows) now attach auth/signature headers when `WEBHOOK_SHARED_SECRET` is configured.
- Operational alerting delivered:
  - DB-backed operational alerts for support/billing failures,
  - optional Slack notifications for new tickets and inbound replies,
  - deploy packs for CrowdSec-to-Slack and UptimeRobot-to-Slack relays.
- Production deployment baseline delivered:
  - Nginx reverse proxy + Gunicorn runtime guidance,
  - Cloudflare-origin UFW auto-sync pack,
  - CrowdSec setup and optional alert digest tooling,
  - deploy-pack verification helper + runbook (`deploy/verify_deploy_packs.sh`, `deploy/VERIFY_DEPLOY_PACKS.md`).
- Session consistency fix remains in place for public pages via HTML no-store + `Vary: Cookie`.

## Priority backlog (security first)

1. Roll out webhook security policy in deployed environments:
   - set and distribute `WEBHOOK_SHARED_SECRET`,
   - enforce `WEBHOOK_REQUIRE_AUTH=1` and `WEBHOOK_REQUIRE_SIGNATURE=1`,
   - validate signed caller traffic for `/webhook/update_all` and `/webhook/update_token`.
2. Secret hygiene hardening:
   - rotate exposed API keys/passwords,
   - move runtime secrets into a restricted secrets store,
   - remove any plaintext credentials from operational shells/history.
3. Extend security/audit coverage beyond account flows:
   - add failed-auth counters + lockout telemetry,
   - include support/billing privileged actions in user operation audit stream,
   - define retention policy and archival path for `user_operation_logs`.
4. Resilience baseline:
   - encrypted backups for auth/ticket DBs,
   - restore drill with documented RTO/RPO,
   - alerting for service restart loops and failed SMTP sends.
5. Enforce Turnstile policy for public intake paths in production:
   - decide enforcement mode (`TURNSTILE_ENFORCE=true` baseline vs risk-based conditional),
   - publish abuse-response SOP for support intake.
6. Complete rollout verification for deploy packs already shipped:
   - `status-sampler`, `support-resend-sync`, `cloudflare-ufw-sync`, `crowdsec-slack-alerts`, `uptimerobot-slack-relay`,
   - add runbook checks proving timer health and alert delivery.

## Remaining product work

1. Identity upgrade:
   - migrate from local auth to OIDC while preserving MFA + RBAC behavior.
2. Assessment orchestration:
   - move long-running assessments to queue workers,
   - ship sanitized live log streaming and run history.
3. Services monitoring rollout:
   - enable and verify `status-sampler.timer` in production,
   - add alerting for sampler failures and stale status samples.
4. Script API private-probe hardening:
   - add signed/authenticated health checks for non-public probe URLs.
5. Compliance controls for sensitive user telemetry:
   - enforce data retention windows and purge jobs for operation/device logs,
   - add field-level redaction/export support for privacy requests.
6. Help desk expansion:
   - SLA/assignment workflow and escalation rules from category + confidence.
7. Docs publication hardening:
   - add CI redaction gate for paths/secrets/private endpoints,
   - block docs publish when redaction checks fail.
8. Launch hardening:
   - load/performance test pass,
   - external security review and remediation,
   - incident runbook simulation.

## Next sprint execution plan (recommended order)

1. Completed: secure legacy webhook surface (`webhook_server.py`) (2026-03-02).
   - Delivered:
     - token auth + timestamped request signatures on mutating webhook routes,
     - authenticated read access for webhook status/cache surfaces,
     - payload compatibility for `token_address` and `address`,
     - caller updates in assessment and dashboard/tray modules.
2. Completed: add automated status sampling (2026-03-02).
   - Delivered:
     - protected internal status-sampling endpoint,
     - systemd timer/service/script deploy pack (`status-sampler`),
     - env-driven secret gate for sampler calls.
   - Exit criteria met:
     - service-status sampling can run without `/services-status` page visits.
3. Completed: build billing reconciliation repair actions (2026-03-03).
   - Delivered:
     - admin-only actions on reconciliation rows (reapply webhook, manual activate, close false-positive),
     - mandatory reason capture and immutable audit row for each action,
     - reconciliation report suppression for issues marked as false positives.
   - Validation:
     - local end-to-end scenario executed for each action type (reapply/manual activate/close false-positive).
   - Remaining verification:
     - run the same three scenarios in staging after deploy.
4. Completed: add auth/session hardening increment (2026-03-03).
   - Delivered:
     - anomaly prompts (new IP/device),
     - optional step-up 2FA policy for sensitive operations,
     - session invalidation on high-risk account changes.
   - Validation:
     - local regression scenarios passed for login/account paths (step-up enforcement, stale session rejection, anomaly prompt detection).
   - Remaining verification:
     - execute login/account regression checklist in staging after deploy.
5. Completed: add user telemetry capture + secure account info view (2026-03-03).
   - Delivered:
     - expanded signup profile capture and registration context persistence (IP/country/proxy/device),
     - operation-log tables for login + sensitive account/admin mutations with unique operation IDs,
     - new `Info` button in Account table and dedicated user-details page (profile + registration context + devices + operation history),
     - route-level protection so user-details pages are reachable only by master/admin and only through short-lived Account-issued access tokens.
   - Validation:
     - local test-client flow passed for Account->Info gating and sensitive-action operation logging (`user_info_flow=PASS`).
   - Remaining verification:
     - run same flow in staging/prod behind Nginx and confirm proxy headers/IP extraction correctness.
6. Completed: productionize support inbound resilience (completed 2026-03-04).
   - Delivered:
     - protected fallback sync endpoint (`POST /api/v1/support/inbound-email/resend/sync`),
     - deployable `support-resend-sync` timer/service/script pack,
     - production timer verification completed,
     - fallback sync now classifies orphan replies (`ticket_not_found`) as `unmapped` separately from hard failures,
     - configurable unmapped alert threshold (`SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD`).
     - sustained unmapped policy guard using consecutive run checks (`SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS`),
     - delayed-webhook/orphan drill runner script (`deploy/support/support_resend_sync_drill.sh`).
     - production delayed-webhook/orphan drill executed with sustained-condition evidence (`drill_exit_code=2`, `failed=0`),
     - long-term sustained-`unmapped` operational policy finalized.
7. Completed: add Trustpilot-to-Slack review relay (2026-03-04).
   - Delivered:
     - secret-validated Trustpilot webhook endpoint,
     - idempotent event handling,
     - Slack summary notifications for inbound review events.
8. Completed: add Script API probe auth/signed checks (2026-03-04).
   - Delivered:
     - Script API probe requests now attach shared-secret auth headers when configured,
     - probe requests can include timestamped HMAC signatures (`X-Webhook-Timestamp`, `X-Webhook-Signature`),
     - env controls added for deploy/runtime configuration (`SCRIPT_API_PROBE_SHARED_SECRET`, `SCRIPT_API_PROBE_SIGNED`).
9. Completed: add telemetry retention windows + purge jobs (2026-03-04).
   - Delivered:
     - retention policies for `user_operation_logs`, `user_devices`, and `user_login_contexts`,
     - startup retention purge hook using configured windows,
     - deploy pack with `user-telemetry-retention` timer/service/script and runbook.
10. Completed: add failed-auth lockout telemetry + privileged-action audit coverage (2026-03-04).
   - Delivered:
     - login and 2FA challenge now enforce failed-attempt counters with temporary network lockout,
     - lockout/failed-attempt policy made configurable via env,
     - privileged support/billing mutation routes now write operation audit records with context.
11. Completed: production deploy-pack strict verification evidence run (2026-03-04).
   - Delivered:
     - strict verification completed with `fail=0` and `warn=0` for `status-sampler`, `support-resend-sync`, `cloudflare-ufw-sync`, `crowdsec-slack-alerts`, `uptimerobot-slack-relay`, and `user-telemetry-retention`,
     - runbook/evidence logging path hardened (`/var/log/hodler-suite/`),
     - telemetry retention runner updated to prefer app venv python to avoid missing-module drift.

## Sprint season progress snapshot (2026-03-04)

1. Season 1 (items 1-5: webhook security, sampler, billing repair, auth/session hardening, Account->Info telemetry): **5/5 complete (100%)**.
2. Season 2 (items 6-8: inbound resilience, Trustpilot relay, Script API probe hardening): **3/3 complete (100%)**.
3. Season 3 (items 9-11: telemetry retention, auth lockout/audit coverage, deploy-pack production verification): **3/3 complete (100%)**.

## Next sprint targets (open implementation work)

1. Reduce sustained orphan baseline by reconciling recurring unmapped ticket references and documenting source categories.
2. Execute staging/prod verification for completed increments (billing reconciliation repair actions, auth/session hardening, Account->Info token-gated flow, telemetry retention timer outputs, auth lockout policy behavior).
3. Add recurring trend review for `unmapped` vs `failed` signals to keep alert thresholds calibrated.

## Next Program Kickoff (2026-03-05)

The next implementation stream focuses on full DeFi app integration into the website runtime (workerization, perpetual data-plane services, live-assessment UX fidelity, and settings/entitlements split).

Tracked roadmap:

- [defi-risk-web-integration-sprint-seasons-2026.md](<PROJECT_ROOT>/docs/Website/defi-risk-web-integration-sprint-seasons-2026.md)
- Initial Season 1 artifact:
  - [defi-risk-season1-service-boundary-map-2026-03-05.md](<PROJECT_ROOT>/docs/Website/defi-risk-season1-service-boundary-map-2026-03-05.md)

## Estimated effort and cost (early-2026 baseline)

Engineering effort:

- 12 to 16 weeks for secure v1 launch.
- Team baseline: 2 backend engineers, 1 full-stack engineer, 0.5 DevSecOps, fractional QA.

One-time launch costs:

- security test and remediation cycle: USD 8,000 to 35,000.
- legal/compliance review: USD 2,000 to 12,000.

Monthly infrastructure (Kamatera-focused baseline):

- MVP single-node with backups and monitoring: USD 40 to 120.
- Production split (proxy/app/worker/db/cache + backups): USD 150 to 600.
- CDN/WAF/domain/email extras: USD 0 to 120 depending on choices.

Payment costs:

- provider fee + chain/network fee, variable by coin/network and custody settings.

## Kamatera environment setup runbook

## Phase A: Server provisioning

1. Create 2 Ubuntu 24.04 servers in Kamatera:
   - `edge-01` (public): reverse proxy + TLS + WAF integration.
   - `app-01` (private network): Flask app + worker.
2. Start with:
   - `edge-01`: 2 vCPU, 2 GB RAM, 40 GB NVMe.
   - `app-01`: 4 vCPU, 8 GB RAM, 100 GB NVMe.
3. Enable Kamatera basic firewall and restrict ingress:
   - `edge-01`: 22/tcp (restricted), 80/tcp, 443/tcp.
   - `app-01`: no public ingress; allow only from `edge-01` private IP.

## Phase B: OS and access hardening

1. Create non-root admin user, disable password SSH login, enforce key auth.
2. Enable unattended security upgrades.
3. Install and configure `ufw` and `fail2ban`.
4. Disable unused services and close all non-required ports.

## Phase C: Runtime and deployment

1. Install Docker + Compose plugin.
2. Deploy app stack with pinned image digests.
3. Configure reverse proxy (Nginx or Caddy) with:
   - TLS certificates,
   - HSTS,
   - request size limits,
   - upstream timeout and rate limits.
4. Run Flask with gunicorn (not `app.run`).
5. Store secrets in env files readable only by service user.

## Phase D: Data and jobs

1. Add PostgreSQL + Redis services (private only).
2. Configure queue workers for assessment jobs.
3. Configure encrypted backups (daily full + hourly WAL/snapshots).
4. Test restore in isolated environment before go-live.

## Phase E: Domain, email, and docs

1. Register domain and move DNS to Cloudflare.
2. Enable DNSSEC and strict TLS mode.
3. Configure email addresses:
   - `security@`, `support@`, `billing@`.
4. Point `docs.<domain>` to docs deployment.
5. Add CI redaction gate before docs publish.

## Phase F: Payment and support readiness

1. Add NOWPayments API key and IPN secret to production secrets store.
2. Configure callback URL on public HTTPS endpoint.
3. Validate signature checks with test callbacks.
4. Configure support tool and AI pre-triage webhook.
5. Run end-to-end tests for checkout, callback, entitlement update, and refund path.

## Source links used for 2026 validation

- NOWPayments IPN/signature and setup:
  - https://nowpayments.zendesk.com/hc/en-us/articles/21395546303389-IPN-and-how-to-setup
  - https://nowpayments.zendesk.com/hc/en-us/articles/21341613323421-NOWPayments-Integration-Guide
  - https://nowpayments.io/help/dashboard/how-to-use-multiuser-access-for-nowpayments
- Kamatera pricing and trial:
  - https://www.kamatera.com/pricing/
  - https://www.kamatera.com/free-trial/
- Cloudflare domain/email baseline:
  - https://developers.cloudflare.com/registrar/
  - https://developers.cloudflare.com/email-routing/
  - https://developers.cloudflare.com/email-routing/limits/
- Zoho Mail free-plan constraints:
  - https://www.zoho.com/mail/pricing.html
  - https://www.zoho.com/mail/help/adminconsole/subscription.html
- Chatwoot pricing and self-host model:
  - https://www.chatwoot.com/pricing/
  - https://www.chatwoot.com/pricing/self-hosted-plans
  - https://github.com/chatwoot/chatwoot
- AI triage platform option:
  - https://dify.ai/pricing
  - https://github.com/langgenius/dify
- MkDocs/Zensical ecosystem status:
  - https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0/
  - https://squidfunk.github.io/mkdocs-material/blog/2025/11/05/zensical/
