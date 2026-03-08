# Web Portal Scaffold

This directory contains a secure starter scaffold for the 2026 web-port effort.

Current status:

- UI routes for required pages are present.
- Billing endpoints support live NOWPayments invoice creation when enabled.
- NOWPayments webhook signature verification helper is implemented.
- Support triage API is scaffolded with a local placeholder classifier.
- Support ticket endpoint can create tickets and send email notifications.
- Optional Slack notifications are available for new tickets and customer inbound replies.
- Trustpilot review webhooks can be relayed to Slack via `POST /api/v1/support/webhook/trustpilot`.
- Support ticket endpoint includes per-IP and per-email rate limiting.
- Admin/master ticket operations page is available at `/support-tickets`.
- Support ticket operations include bulk status updates and support-agent replies with conversation history.
- Inbound customer email replies can be ingested at `POST /api/v1/support/inbound-email` (secret required).
- Resend inbound adapter is available at `POST /api/v1/support/inbound-email/resend` for `email.received` events.
- Resend inbound webhook idempotency is now persisted in `support_tickets.db` (survives restarts, 30-day retention).
- Resend fallback sync now separates orphan replies (`unmapped`) from hard failures and can alert on unmapped spikes.
- Resend fallback sync now persists per-run metrics and flags sustained unmapped breaches across consecutive runs.
- Operational alerts are persisted in DB and exposed in `/support-tickets` for admin/master triage.
- Public sign-up flow includes email ownership verification (6-digit code, manual send, 30-minute expiry by default).
- Password reset flow is available at `/password-reset` and `/password-reset/confirm`.
- Email change and 2FA reset now require email-based verification codes.
- Optional full-site human verification can be enforced with Cloudflare Turnstile (`/human-check`).
- Auth gateway is enabled for workflow routes with role-based account controls.
- 2FA (TOTP) setup/challenge flows are available for account security.
- Admin/master Services Status panel is available at `/services-status` with live service/chain health checks.
- Services Status now persists real uptime samples in DB (24h/7d) and exposes Script API deep probes.
- Protected internal sampler endpoint is available at `POST /api/v1/internal/status-sample` for timer-driven background sampling.
- Admin/master NOWPayments currency capability sync/override controls are available in Billing Reconciliation.
- Admin/master billing reconciliation board is available at `/billing-reconciliation`.
- Checkout now auto-filters/fallbacks unavailable NOWPayments currencies to reduce provider failures.
- Homepage sidebar CTA no longer shows “Register Free Account” for authenticated users.
- Collapsed sidebar nav icons now show native hover tooltips with page labels.
- Account/security and support HTML emails now include configurable Hodler Suite logo branding.
- Host-split routing now keeps anonymous traffic on marketing domain and redirects authenticated sessions to app domain.
- Risk orchestration API scaffold is available at `/api/v1/risk/jobs` with persisted job/event/artifact state.

## Sprint Backlog (Active)

Recently completed (implemented):

- [x] Added inbound customer-reply fallback sync endpoint (`POST /api/v1/support/inbound-email/resend/sync`) with Resend list/fetch replay behavior and DB-backed idempotency checks.
- [x] Added deployable `support-resend-sync` timer/service/script pack for periodic fallback ingestion recovery.
- [x] Added billing reconciliation auto-repair actions (reapply webhook, manual activation, close false-positive) with mandatory reason capture and immutable action audit.
- [x] Added auth/session hardening increment (new IP/device anomaly prompts, optional step-up TOTP policy for sensitive mutations, session-version invalidation on high-risk account changes).
- [x] Added Trustpilot webhook relay endpoint with secret validation, event deduplication, and Slack delivery.
- [x] Added Script API private-probe auth headers + optional timestamped HMAC signatures for health/deep-probe checks.
- [x] Added deploy-pack verification helper (`deploy/verify_deploy_packs.sh`) + runbook (`deploy/VERIFY_DEPLOY_PACKS.md`) for timer/service health evidence capture.
- [x] Added retention windows + purge jobs for user operation/device telemetry (`deploy/privacy/` service/timer/script pack + startup retention enforcement).
- [x] Added failed-auth counters + lockout telemetry for login/2FA and audit logging for privileged support/billing actions.
- [x] Added collapsed-sidebar icon hover tooltips (labels shown only in icon-only mode).
- [x] Added configurable branded logo block in outgoing HTML account/support emails (`EMAIL_BRAND_LOGO_URL`).
- [x] Completed production deploy-pack strict verification evidence run (`fail=0`, `warn=0`) for `status-sampler`, `support-resend-sync`, `cloudflare-ufw-sync`, `crowdsec-slack-alerts`, `uptimerobot-slack-relay`, `user-telemetry-retention`.
- [x] Added support-resend-sync unmapped classification + threshold alerting (`ticket_not_found` no longer counted as hard failure).
- [x] Added support-resend-sync sustained-unmapped policy guard (consecutive-run breach detection) and drill runner script.
- [x] Executed delayed-webhook/orphan-reply drill in production with sustained policy evidence (`drill_exit_code=2`, `failed=0`, sustained orphan condition confirmed).
- [x] Added Season-1 risk-worker orchestration scaffold (`RiskJobStore` + `/api/v1/risk/jobs` + internal worker-event secret gate).

Open work (next sprint targets):

- [ ] Reduce sustained orphan baseline by reconciling missing ticket references behind recurring `ticket_not_found` replies.
- [ ] Add weekly trend review for `unmapped` volumes and threshold-tuning governance evidence.

Next major integration roadmap:

- [ ] DeFi risk app full web integration sprint seasons are defined and tracked in:
  - `docs/Website/defi-risk-web-integration-sprint-seasons-2026.md`

## Run locally

1. Copy `.env.example` values into your environment or `.env` loader.
2. Start the app:

```bash
cd scripts/v2.0/web_portal
python3 run.py
```

3. Open `http://127.0.0.1:5050`.

## Authentication defaults

- Master account bootstrap values are read from env:
  - `MASTER_ACCOUNT_EMAIL`
  - `MASTER_ACCOUNT_PASSWORD`
- Default route protection:
  - public: `/`, `/help-center`, `/faq`, `/docs`, `/login`, `/signup`, `/signup/verify`
  - authenticated: `/dashboard`, `/live-assessment`, `/account`, `/checkout`
  - admin-only: `/settings`, `/support-tickets`

## NOWPayments checkout

- Checkout API endpoint: `POST /api/v1/billing/checkout-session` (authenticated + CSRF protected)
- Webhook endpoint: `POST /api/v1/billing/webhook`
- Required env:
  - `NOWPAYMENTS_ENABLED=true`
  - `NOWPAYMENTS_API_KEY=<api-key>`
  - `NOWPAYMENTS_IPN_SECRET=<ipn-secret>`
  - `NOWPAYMENTS_SUCCESS_URL=https://app.hodler-suite.com/checkout?state=success`
  - `NOWPAYMENTS_CANCEL_URL=https://app.hodler-suite.com/checkout?state=cancel`
  - `NOWPAYMENTS_PLAN_CATALOG={"basic-monthly":49.99,"pro-monthly":299.99}`
  - `NOWPAYMENTS_PAY_CURRENCIES=[{"code":"usdttrc20","label":"USDT (TRC-20)"},{"code":"usdc","label":"USDC (ERC-20)"}]`
  - `WEB_PORTAL_BILLING_DB=/opt/hodler-suite/web_portal/data/billing.db`
  - `WEB_PORTAL_STATUS_DB=/opt/hodler-suite/web_portal/data/status_metrics.db`
  - `WEB_PORTAL_RISK_JOB_DB=/opt/hodler-suite/web_portal/data/risk_jobs.db`
  - `WEB_PORTAL_APP_BASE_URL=https://app.hodler-suite.com` (authenticated app host)
  - `WEB_PORTAL_MARKETING_BASE_URL=https://hodler-suite.com` (public/anonymous host)
  - `WEB_PORTAL_SESSION_COOKIE_DOMAIN=.hodler-suite.com` (recommended for cross-subdomain auth continuity; can be auto-derived)
  - `WEB_PORTAL_SESSION_COOKIE_NAME=hs_portal_session` (recommended to avoid legacy `session` cookie collisions during host split migration)
  - `EMAIL_BRAND_LOGO_URL=https://app.hodler-suite.com/static/brand/hodler-suite-email-logo.png` (optional; defaults to this path from `WEB_PORTAL_PUBLIC_BASE_URL`)
  - `STATUS_SAMPLER_SECRET=<long-random-secret>`
  - `RISK_WORKER_SHARED_SECRET=<long-random-secret-for-internal-worker-events>`
  - `STATUS_SAMPLER_BASE_URL=http://127.0.0.1:5050` (optional; used by sampler timer script)
  - `STATUS_SAMPLER_TIMEOUT_SECONDS=20` (optional; used by sampler timer script)
  - `STATUS_SAMPLER_WAIT_FOR_APP_SECONDS=20` (optional; wait-for-app gate before sampler POST)
  - `STATUS_SAMPLER_HTTP_ATTEMPTS=3` (optional; retries for transient sampler HTTP failures)
  - `SCRIPT_API_WATCHDOG_URL=http://127.0.0.1:5001/webhook/health`
  - `SCRIPT_API_WATCHDOG_TIMEOUT_SECONDS=6`
  - `SCRIPT_API_WATCHDOG_FAILURE_THRESHOLD=3`
  - `SCRIPT_API_WATCHDOG_HTTP_ATTEMPTS=3`
  - `SCRIPT_API_WATCHDOG_RETRY_DELAY_SECONDS=2`
  - `SCRIPT_API_WATCHDOG_UNIT=hodler-script-api.service`
  - `SCRIPT_API_WATCHDOG_STATE_FILE=/var/lib/hodler-suite/script_api_watchdog.state`
  - Optional deep probes:
    - `SCRIPT_API_HEALTH_URL=http://127.0.0.1:5001/webhook/health`
    - `SCRIPT_API_ETH_HEALTH_URL=http://127.0.0.1:5001/webhook/health/deep/eth`
    - `SCRIPT_API_BSC_HEALTH_URL=http://127.0.0.1:5001/webhook/health/deep/bsc`
    - `SCRIPT_API_TRON_HEALTH_URL=http://127.0.0.1:5001/webhook/health/deep/tron`
    - Deep probe payload details are surfaced in Services Status cards (coverage/freshness context).
  - Optional private-probe auth:
    - `SCRIPT_API_PROBE_SHARED_SECRET=<shared-secret>` (falls back to `WEBHOOK_SHARED_SECRET` when unset)
    - `SCRIPT_API_PROBE_SIGNED=true` (adds timestamped HMAC signature headers on probe calls)
    - Use only with trusted first-party Script API probe URLs.
  - Optional probe-alert thresholds:
    - `STATUS_PROBE_WINDOW_HOURS=6`
    - `STATUS_PROBE_MIN_SAMPLES=6`
    - `STATUS_PROBE_FAILURE_STREAK_THRESHOLD=3`
    - `STATUS_PROBE_ERROR_RATE_WARNING_PCT=35`
    - `STATUS_PROBE_ERROR_RATE_CRITICAL_PCT=60`
    - `STATUS_PROBE_LATENCY_WARNING_MS=2500`
    - `STATUS_PROBE_LATENCY_CRITICAL_MS=5000`
  - Optional risk-runtime thresholds:
    - `RISK_STATUS_QUEUE_WARN=10`
    - `RISK_STATUS_QUEUE_CRITICAL=40`
    - `RISK_STATUS_QUEUE_STALL_MINUTES=10`
    - `RISK_STATUS_STALE_RUNNING_MINUTES=20`
    - `RISK_STATUS_WINDOW_HOURS=24`
    - `RISK_STATUS_FAILURE_RATE_WARNING_PCT=25`
    - `RISK_STATUS_FAILURE_RATE_CRITICAL_PCT=50`
    - `RISK_STATUS_FAILURE_RATE_MIN_COMPLETED=4`
  - Optional infra/public-edge thresholds:
    - `STATUS_PUBLIC_EDGE_TIMEOUT_SECONDS=6`
    - `STATUS_NGINX_LOCAL_URL=http://127.0.0.1/healthz`
    - `STATUS_NGINX_LOCAL_TIMEOUT_SECONDS=3`
    - `STATUS_TLS_TIMEOUT_SECONDS=4`
    - `STATUS_DISK_FREE_WARNING_PCT=15`
    - `STATUS_DISK_FREE_CRITICAL_PCT=8`
    - `STATUS_DB_SIZE_WARNING_MB=1024`
    - `STATUS_DB_SIZE_CRITICAL_MB=4096`
  - Telemetry retention:
    - `USER_OPERATION_RETENTION_DAYS=180`
    - `USER_DEVICE_RETENTION_DAYS=180`
    - `USER_LOGIN_CONTEXT_RETENTION_DAYS=90`
    - `USER_TELEMETRY_PURGE_ON_STARTUP=true`
    - `USER_TELEMETRY_RETENTION_ENABLED=true`
    - `USER_TELEMETRY_PURGE_DRY_RUN=false`

Notes:
- Server enforces plan pricing from `NOWPAYMENTS_PLAN_CATALOG` (client-supplied price is ignored).
- Webhook idempotency is persisted, so duplicate NOWPayments callbacks are ignored safely.
- Checkout plans:
  - `free-30d`: 30-day trial, then access becomes inactive until upgrade.
  - `basic-monthly`: EUR 49.99 / month.
  - `pro-monthly`: EUR 299.99 / month.
  - `enterprise-custom`: amount + limits by enterprise code generated from Checkout (admin/master only).

## Risk Job Orchestration API (Season 3 Kickoff)

- Create job (authenticated): `POST /api/v1/risk/jobs`
- List jobs (authenticated): `GET /api/v1/risk/jobs`
- Get job (authenticated): `GET /api/v1/risk/jobs/<job_id>`
- Cancel job (authenticated): `POST /api/v1/risk/jobs/<job_id>/cancel`
- Worker stage/event ingestion (internal secret): `POST /api/v1/risk/jobs/<job_id>/events`
- Worker queue claim (internal secret): `POST /api/v1/risk/internal/claim`
- Worker run once (internal secret): `POST /api/v1/risk/internal/run-once`

Internal worker event auth:

- `Authorization: Bearer <RISK_WORKER_SHARED_SECRET>`
- or `X-Risk-Worker-Secret: <RISK_WORKER_SHARED_SECRET>`

## Help Desk ticket flow

- Endpoint: `POST /api/v1/support/tickets`
- Required payload:
  - `email`
  - `subject`
  - `message`
- Server behavior:
  - Creates a ticket reference in `support_tickets.db`
  - Sends auto-acknowledgement to customer from `SUPPORT_EMAIL_FROM` (recommended: `support@hodler-suite.com`)
  - Sends summary notification to `SUPPORT_EMAIL_NOTIFY_TO`
  - Uses `ACCOUNT_EMAIL_FROM` (recommended: `no_reply@hodler-suite.com`) for account-security mails only

Configure SMTP using:

- `SUPPORT_SMTP_HOST`
- `SUPPORT_SMTP_PORT`
- `SUPPORT_SMTP_USERNAME`
- `SUPPORT_SMTP_PASSWORD`
- `SUPPORT_SMTP_USE_TLS`
- `SUPPORT_SMTP_USE_SSL`
- `ACCOUNT_EMAIL_FROM`
- `ACCOUNT_EMAIL_SUBJECT_PREFIX`
- `EMAIL_BRAND_LOGO_URL`
- `SUPPORT_EMAIL_FROM`
- `SUPPORT_EMAIL_NOTIFY_TO`
- `SUPPORT_INBOUND_WEBHOOK_SECRET`
- `SUPPORT_INBOUND_REPLY_TO`
- `SUPPORT_INBOUND_ROUTING_ACTIVE`
- `SUPPORT_AGENT_EMAILS`
- `SUPPORT_RESEND_API_KEY`
- `SUPPORT_RESEND_FETCH_TIMEOUT_SECONDS`
- `SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD`
- `SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS`
- `STATUS_SAMPLER_SECRET`
- `RISK_WORKER_SHARED_SECRET`
- `RISK_WORKER_BASE_URL`
- `RISK_WORKER_TIMEOUT_SECONDS`
- `RISK_WORKER_WAIT_FOR_APP_SECONDS`
- `RISK_WORKER_ID`
- `STATUS_SAMPLER_BASE_URL`
- `STATUS_SAMPLER_TIMEOUT_SECONDS`
- `STATUS_SAMPLER_WAIT_FOR_APP_SECONDS`
- `STATUS_SAMPLER_HTTP_ATTEMPTS`
- `SCRIPT_API_WATCHDOG_URL`
- `SCRIPT_API_WATCHDOG_TIMEOUT_SECONDS`
- `SCRIPT_API_WATCHDOG_FAILURE_THRESHOLD`
- `SCRIPT_API_WATCHDOG_HTTP_ATTEMPTS`
- `SCRIPT_API_WATCHDOG_RETRY_DELAY_SECONDS`
- `SCRIPT_API_WATCHDOG_UNIT`
- `SCRIPT_API_WATCHDOG_STATE_FILE`
- `SCRIPT_API_PROBE_SHARED_SECRET`
- `SCRIPT_API_PROBE_SIGNED`
- `STATUS_PROBE_WINDOW_HOURS`
- `STATUS_PROBE_MIN_SAMPLES`
- `STATUS_PROBE_FAILURE_STREAK_THRESHOLD`
- `STATUS_PROBE_ERROR_RATE_WARNING_PCT`
- `STATUS_PROBE_ERROR_RATE_CRITICAL_PCT`
- `STATUS_PROBE_LATENCY_WARNING_MS`
- `STATUS_PROBE_LATENCY_CRITICAL_MS`
- `RISK_STATUS_QUEUE_WARN`
- `RISK_STATUS_QUEUE_CRITICAL`
- `RISK_STATUS_QUEUE_STALL_MINUTES`
- `RISK_STATUS_STALE_RUNNING_MINUTES`
- `RISK_STATUS_WINDOW_HOURS`
- `RISK_STATUS_FAILURE_RATE_WARNING_PCT`
- `RISK_STATUS_FAILURE_RATE_CRITICAL_PCT`
- `RISK_STATUS_FAILURE_RATE_MIN_COMPLETED`
- `STATUS_PUBLIC_EDGE_TIMEOUT_SECONDS`
- `STATUS_NGINX_LOCAL_URL`
- `STATUS_NGINX_LOCAL_TIMEOUT_SECONDS`
- `STATUS_TLS_TIMEOUT_SECONDS`
- `STATUS_DISK_FREE_WARNING_PCT`
- `STATUS_DISK_FREE_CRITICAL_PCT`
- `STATUS_DB_SIZE_WARNING_MB`
- `STATUS_DB_SIZE_CRITICAL_MB`
- `AUTH_FAILED_LOGIN_WINDOW_MINUTES`
- `AUTH_FAILED_LOGIN_MAX_ATTEMPTS`
- `AUTH_FAILED_LOGIN_LOCKOUT_MINUTES`
- `USER_OPERATION_RETENTION_DAYS`
- `USER_DEVICE_RETENTION_DAYS`
- `USER_LOGIN_CONTEXT_RETENTION_DAYS`
- `USER_TELEMETRY_PURGE_ON_STARTUP`
- `USER_TELEMETRY_RETENTION_ENABLED`
- `USER_TELEMETRY_PURGE_DRY_RUN`
- `SUPPORT_RATE_LIMIT_IP_PER_5M`
- `SUPPORT_RATE_LIMIT_EMAIL_PER_5M`
- `SUPPORT_RATE_LIMIT_IP_PER_HOUR`
- `SUPPORT_RATE_LIMIT_EMAIL_PER_HOUR`
- `SUPPORT_SLACK_ENABLED`
- `SUPPORT_SLACK_WEBHOOK_URL`
- `SUPPORT_SLACK_TIMEOUT_SECONDS`
- `SUPPORT_BUG_CURSOR_ENABLED`
- `SUPPORT_BUG_CURSOR_POST_MODE`
- `SUPPORT_BUG_CURSOR_WEBHOOK_URL`
- `SUPPORT_BUG_CURSOR_USER_TOKEN`
- `SUPPORT_BUG_CURSOR_CHANNEL_ID`
- `SUPPORT_BUG_CURSOR_MENTION`
- `SUPPORT_BUG_CURSOR_TIMEOUT_SECONDS`
- `SLACK_EVENTS_SIGNING_SECRET`
- `SLACK_BOT_TOKEN`
- `SLACK_GITHUB_PULL_REQUESTS_CHANNEL_ID`
- `SLACK_GITHUB_APPROVER_USER_IDS`
- `GITHUB_TOKEN`
- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_SLACK_AUTO_MERGE`
- `GITHUB_SLACK_MERGE_METHOD`
- `TRUSTPILOT_WEBHOOK_SECRET`
- `TRUSTPILOT_SLACK_ENABLED`
- `TRUSTPILOT_SLACK_WEBHOOK_URL`
- `TRUSTPILOT_SLACK_TIMEOUT_SECONDS`
- `ACCOUNT_SECURITY_CODE_EXPIRY_MINUTES`
- `ACCOUNT_SECURITY_CODE_RESEND_COOLDOWN_SECONDS`
- `PASSWORD_RESET_EXPIRY_MINUTES`
- `SIGNUP_CODE_EXPIRY_MINUTES`
- `SIGNUP_CODE_RESEND_COOLDOWN_SECONDS`
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`
- `TURNSTILE_ENFORCE`

Nginx reverse-proxy template:

- `deploy/nginx.hodler-suite.conf`
- deployment notes: `deploy/DEPLOY_NGINX.md`
- safe app deploy helper (preserves `.venv/.env/web_portal.env/data`): `deploy/deploy_web_portal_safe.sh`
- emergency account recovery helper: `deploy/reset_user_password.py`
- Cloudflare UFW auto-sync pack: `deploy/security/` + `deploy/security/CLOUDFLARE_UFW_AUTOSYNC.md`
- Services status sampler pack: `deploy/status/` + `deploy/status/STATUS_SAMPLER.md`
- Public docs publish workflow: `deploy/PUBLIC_DOCS_PUBLISH.md`
- CrowdSec rollout guide: `deploy/CROWDSEC_SETUP.md`
- Deploy-pack verification runbook: `deploy/VERIFY_DEPLOY_PACKS.md`
- User telemetry retention pack: `deploy/privacy/` + `deploy/privacy/USER_TELEMETRY_RETENTION.md`

Example emergency password reset:

```bash
cd scripts/v2.0/web_portal
python3 deploy/reset_user_password.py \
  --db /opt/hodler-suite/web_portal/data/web_portal_auth.db \
  --email admin@hodler-suite.com
```

## Resend inbound webhook flow

1. Configure Resend Receiving and point inbound route webhook to:
   - `https://app.hodler-suite.com/api/v1/support/inbound-email/resend`
2. Protect webhook with `SUPPORT_INBOUND_WEBHOOK_SECRET` in one of:
   - `X-Support-Inbound-Secret: <secret>`
   - `Authorization: Bearer <secret>`
   - `?secret=<secret>`
3. Set `SUPPORT_RESEND_API_KEY` so the adapter can fetch message content from Resend Receiving API using `data.email_id`.
4. Set `SUPPORT_INBOUND_REPLY_TO` to a receiving address on the inbound subdomain (for example, `tickets@inbound.hodler-suite.com`) so customer replies are routed into webhook ingestion.
   - Enable this routing only when inbound receiving is truly active by setting `SUPPORT_INBOUND_ROUTING_ACTIVE=true`.
   - Keep it `false` to route customer replies back to `support@...` and avoid losing messages.
5. Set `SUPPORT_AGENT_EMAILS` (comma separated) so forwarded mailbox replies from support agents are tracked as support-side messages in the same ticket thread.
6. Free mailbox workflow (no automatic BCC required):
   - support notifications use `Reply-To: SUPPORT_INBOUND_REPLY_TO`
   - agent email replies are ingested, stored in ticket thread, and relayed to customer from support sender
   - customer inbound replies trigger a support follow-up notification email

## Trustpilot review webhook relay

1. Configure Trustpilot webhook target:
   - `https://app.hodler-suite.com/api/v1/support/webhook/trustpilot?secret=<TRUSTPILOT_WEBHOOK_SECRET>`
2. Configure env:
   - `TRUSTPILOT_WEBHOOK_SECRET=<long-random-secret>`
   - `TRUSTPILOT_SLACK_ENABLED=true`
   - `TRUSTPILOT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...`
   - `TRUSTPILOT_SLACK_TIMEOUT_SECONDS=8`
3. The endpoint deduplicates events by `eventId` (or deterministic payload hash fallback) and posts a compact review summary into Slack.

## Bug report -> Cursor -> PR automation

When a new support ticket is categorized as `Bug Report`, the notifier can post a Cursor-tagged implementation prompt into your dedicated PR channel.

1. Configure env:
   - `SUPPORT_BUG_CURSOR_ENABLED=true`
   - `SUPPORT_BUG_CURSOR_POST_MODE=chat_post_message` (recommended) or `webhook`
   - For `chat_post_message` mode:
     - `SUPPORT_BUG_CURSOR_USER_TOKEN=xoxp-...` (service user token)
     - `SUPPORT_BUG_CURSOR_CHANNEL_ID=C...` (channel id of `#github_pull_requests`)
   - For `webhook` mode:
     - `SUPPORT_BUG_CURSOR_WEBHOOK_URL=https://hooks.slack.com/services/...`
   - `SUPPORT_BUG_CURSOR_MENTION=<@UXXXXXXXX>` (preferred)
     - `@Cursor` plain text is accepted, but Slack only triggers an actual mention when it resolves to a real mention token.
     - The notifier now attempts auto-resolution from recent `#github_pull_requests` messages (and `users.list` when scope allows).
   - `SUPPORT_BUG_CURSOR_TIMEOUT_SECONDS=8`
2. Existing support Slack notifications can remain enabled in parallel:
   - `SUPPORT_SLACK_ENABLED=true`
   - `SUPPORT_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...`
3. Result:
   - Every new `Bug Report` ticket triggers a detailed `@Cursor` request in the PR channel (`#github_pull_requests`) with subject/message and support link.
   - `chat_post_message` mode is preferred when Slack apps ignore bot/webhook-origin mentions.
   - The generated prompt now includes a PR-description template with:
     - Bug Report N.
     - Submitted by (masked user/email)
     - Date of Submission
     - Subject
     - Description
   - Security gate: if bug-report subject/body matches suspicious command-injection or SQL-injection patterns (for example `rm -rf`, `curl | bash`, `UNION SELECT`, `DROP TABLE`), Cursor relay is blocked automatically and an operational alert is recorded.

## Slack ✅ reaction -> GitHub PR approval (optional auto-merge)

The app exposes a signed Slack Events endpoint that can turn a ✅ reaction on PR messages into GitHub PR approval.

1. Configure Slack App:
   - Enable Events API
   - Request bot scopes: `channels:history`, `chat:write`, `reactions:read`
   - Set Request URL to:
     - `https://app.hodler-suite.com/api/v1/support/slack/events`
   - Subscribe to bot event:
     - `reaction_added`
2. Configure env:
   - `SLACK_EVENTS_SIGNING_SECRET=<from Slack app>`
   - `SLACK_BOT_TOKEN=xoxb-...`
   - `SLACK_GITHUB_PULL_REQUESTS_CHANNEL_ID=<channel id of #github_pull_requests>` (optional hard restriction)
   - `SLACK_GITHUB_APPROVER_USER_IDS=U123...,U456...` (optional allowlist of users allowed to approve via ✅)
   - `GITHUB_TOKEN=<fine-grained token with pull-requests:write>`
   - `GITHUB_OWNER=<repo owner>`
   - `GITHUB_REPO=<repo name>`
   - `GITHUB_SLACK_AUTO_MERGE=false` (set `true` if you also want immediate merge)
   - `GITHUB_SLACK_MERGE_METHOD=squash` (`merge|squash|rebase`)
3. Behavior:
   - ✅ on a PR message in the configured channel => app parses PR URL, submits GitHub `APPROVE` review, and posts thread confirmation.
   - If `GITHUB_SLACK_AUTO_MERGE=true`, it also attempts to merge.

## IP intelligence (signup/login/operations)

- Country baseline uses Cloudflare header `CF-IPCountry` when available.
- Optional direct provider lookup enriches VPN/proxy/datacenter/hosting flags and is cached in-memory by IP.
- Configure:
  - `IP_INTEL_LOOKUP_URL` (IP placeholder: `{ip}`; API key placeholder: `{api_key}`)
  - `IP_INTEL_API_KEY`
  - `IP_INTEL_TIMEOUT_SECONDS`
  - `IP_INTEL_CACHE_TTL_SECONDS`
- If `IP_INTEL_LOOKUP_URL` is empty but `IP_INTEL_API_KEY` is set, the app now defaults to:
  - `https://api.ip2location.io/?key={api_key}&ip={ip}&format=json`
- IP2Location example URL:
  - `https://api.ip2location.io/?key={api_key}&ip={ip}&format=json`
- For VPN/proxy/datacenter flags, ensure your IP2Location plan exposes Security fields (`proxy.*`, `is_proxy`, `proxy_type`).

## Security notes

- Keep `NOWPAYMENTS_ENABLED=false` until checkout implementation is completed and reviewed.
- Do not expose webhook endpoints publicly without TLS, rate limiting, and request logging.
- Webhook idempotency is stored in the support DB; keep DB backups enabled and monitor table growth.
- Billing webhook and checkout session state are persisted in `billing.db`; keep DB backups enabled.
