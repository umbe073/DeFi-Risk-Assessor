# Nginx Deployment Notes

Use this when deploying `scripts/v2.0/web_portal` behind Nginx.

## 1) Flask runtime env

Set these variables in the portal runtime environment:

- `WEB_PORTAL_FORCE_HTTPS=true`
- `WEB_PORTAL_HOST=127.0.0.1`
- `WEB_PORTAL_PORT=5050`
- `WEB_PORTAL_SECRET_KEY=<strong-random-secret>`
- `WEB_PORTAL_AUTH_DB=<path-to-web-portal-auth.db>`
- `WEB_PORTAL_SUPPORT_DB=<path-to-support-tickets.db>`
- `WEB_PORTAL_BILLING_DB=<path-to-billing.db>`
- `SENSITIVE_OPS_REQUIRE_2FA=false` (set `true` to require step-up TOTP for sensitive account/admin mutations)
- `AUTH_ANOMALY_PROMPT_ENABLED=true` (show new IP/device sign-in notice prompts)
- `AUTH_FAILED_LOGIN_WINDOW_MINUTES=15` (rolling window for failed sign-in attempts)
- `AUTH_FAILED_LOGIN_MAX_ATTEMPTS=6` (max failed attempts before temporary lockout)
- `AUTH_FAILED_LOGIN_LOCKOUT_MINUTES=15` (temporary lockout duration)
- `IP_INTEL_LOOKUP_URL=` (optional HTTPS API endpoint for IP reputation/geolocation lookup; supports `{ip}` token or `?ip=` query mode)
- `IP_INTEL_API_KEY=` (optional bearer token for IP intel API)
- `IP_INTEL_TIMEOUT_SECONDS=4` (short timeout so auth flows do not stall on external lookups)
- `USER_OPERATION_RETENTION_DAYS=180` (retention window for `user_operation_logs`)
- `USER_DEVICE_RETENTION_DAYS=180` (retention window for `user_devices`)
- `USER_LOGIN_CONTEXT_RETENTION_DAYS=90` (retention window for `user_login_contexts`)
- `USER_TELEMETRY_PURGE_ON_STARTUP=true` (apply telemetry retention once during app startup)
- `USER_TELEMETRY_RETENTION_ENABLED=true` (enable periodic retention timer job)
- `USER_TELEMETRY_PURGE_DRY_RUN=false` (set `true` to verify retention candidates without deleting rows)
- `NOWPAYMENTS_ENABLED=true` (only after API key + IPN secret are set)
- `NOWPAYMENTS_API_KEY=<nowpayments-api-key>`
- `NOWPAYMENTS_IPN_SECRET=<nowpayments-ipn-secret>`
- `NOWPAYMENTS_SUCCESS_URL=https://app.hodler-suite.com/checkout?state=success`
- `NOWPAYMENTS_CANCEL_URL=https://app.hodler-suite.com/checkout?state=cancel`
- `NOWPAYMENTS_PLAN_CATALOG={"basic-monthly":49.99,"pro-monthly":299.99}`
- `NOWPAYMENTS_PAY_CURRENCIES=[{"code":"usdttrc20","label":"USDT (TRC-20)"},{"code":"usdcerc20","label":"USDC (ERC-20)"}]`
- `WEB_PORTAL_APP_BASE_URL=https://app.hodler-suite.com` (authenticated app host)
- `WEB_PORTAL_MARKETING_BASE_URL=https://hodler-suite.com` (public/anonymous host)
- `WEB_PORTAL_SESSION_COOKIE_DOMAIN=.hodler-suite.com` (recommended for cross-subdomain login continuity)
- `WEB_PORTAL_SESSION_COOKIE_NAME=hs_portal_session` (recommended to avoid legacy `session` cookie collisions)
- `WEB_PORTAL_RISK_JOB_DB=/opt/hodler-suite/web_portal/data/risk_jobs.db`
- `SCRIPT_API_HEALTH_URL=` (optional Script API health endpoint)
- `SCRIPT_API_ETH_HEALTH_URL=` (optional deep probe URL)
- `SCRIPT_API_BSC_HEALTH_URL=` (optional deep probe URL)
- `SCRIPT_API_TRON_HEALTH_URL=` (optional deep probe URL)
- `SCRIPT_API_PROBE_SHARED_SECRET=` (optional; used as bearer/token auth for private probe URLs)
- `SCRIPT_API_PROBE_SIGNED=true` (default true; attach `X-Webhook-Timestamp` + `X-Webhook-Signature` HMAC headers)
  - configure only for trusted first-party probe URLs.
- `STATUS_PROBE_WINDOW_HOURS=6` (status-probe rolling window used for alert thresholds)
- `STATUS_PROBE_MIN_SAMPLES=6` (minimum samples before error-rate/latency alerts)
- `STATUS_PROBE_FAILURE_STREAK_THRESHOLD=3` (consecutive degraded/offline samples before streak alert)
- `STATUS_PROBE_ERROR_RATE_WARNING_PCT=35`
- `STATUS_PROBE_ERROR_RATE_CRITICAL_PCT=60`
- `STATUS_PROBE_LATENCY_WARNING_MS=2500`
- `STATUS_PROBE_LATENCY_CRITICAL_MS=5000`
- `EMAIL_BRAND_LOGO_URL=https://app.hodler-suite.com/static/brand/hodler-suite-email-logo.png` (optional; defaults to this path from `WEB_PORTAL_PUBLIC_BASE_URL`)
- `ACCOUNT_EMAIL_FROM=no_reply@hodler-suite.com`
- `ACCOUNT_EMAIL_SUBJECT_PREFIX=[Hodler Suite]`
- `SUPPORT_EMAIL_FROM=support@hodler-suite.com`
- `SUPPORT_EMAIL_NOTIFY_TO=support@hodler-suite.com`
- `SUPPORT_INBOUND_REPLY_TO=tickets@inbound.hodler-suite.com`
- `SUPPORT_INBOUND_ROUTING_ACTIVE=false` (set `true` only after inbound receiving/webhook is confirmed working)
- `SUPPORT_AGENT_EMAILS=support@hodler-suite.com,admin@hodler-suite.com`
- `SUPPORT_SMTP_HOST=<smtp-host>`
- `SUPPORT_SMTP_PORT=<587-or-465>`
- `SUPPORT_SMTP_USERNAME=<smtp-user>`
- `SUPPORT_SMTP_PASSWORD=<smtp-password>`
- `SUPPORT_SMTP_USE_TLS=true` for STARTTLS on 587
- `SUPPORT_SMTP_USE_SSL=true` for SMTPS on 465
- `SUPPORT_INBOUND_WEBHOOK_SECRET=<long-random-secret>`
- `SUPPORT_RESEND_API_KEY=<resend-api-key-for-receiving>`
- `SUPPORT_RESEND_FETCH_TIMEOUT_SECONDS=15`
- `SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD=5` (warning alert threshold for orphan inbound replies in fallback sync)
- `SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS=3` (consecutive over-threshold runs before sustained critical alert)
- `STATUS_SAMPLER_SECRET=<long-random-secret-for-internal-status-sampler>`
- `RISK_WORKER_SHARED_SECRET=<long-random-secret-for-internal-risk-worker-events>`
- `RISK_WORKER_BASE_URL=http://127.0.0.1:5050`
- `RISK_WORKER_TIMEOUT_SECONDS=40`
- `RISK_WORKER_WAIT_FOR_APP_SECONDS=20`
- `RISK_WORKER_ID=<optional-stable-worker-id>`
- `STATUS_SAMPLER_BASE_URL=http://127.0.0.1:5050`
- `STATUS_SAMPLER_TIMEOUT_SECONDS=20`
- `STATUS_SAMPLER_WAIT_FOR_APP_SECONDS=20`
- `STATUS_SAMPLER_HTTP_ATTEMPTS=3`
- `SCRIPT_API_WATCHDOG_URL=http://127.0.0.1:5001/webhook/health`
- `SCRIPT_API_WATCHDOG_TIMEOUT_SECONDS=6`
- `SCRIPT_API_WATCHDOG_FAILURE_THRESHOLD=3`
- `SCRIPT_API_WATCHDOG_HTTP_ATTEMPTS=3`
- `SCRIPT_API_WATCHDOG_RETRY_DELAY_SECONDS=2`
- `SCRIPT_API_WATCHDOG_UNIT=hodler-script-api.service`
- `SCRIPT_API_WATCHDOG_STATE_FILE=/var/lib/hodler-suite/script_api_watchdog.state`
- `RISK_STATUS_QUEUE_WARN=10`
- `RISK_STATUS_QUEUE_CRITICAL=40`
- `RISK_STATUS_QUEUE_STALL_MINUTES=10`
- `RISK_STATUS_STALE_RUNNING_MINUTES=20`
- `RISK_STATUS_WINDOW_HOURS=24`
- `RISK_STATUS_FAILURE_RATE_WARNING_PCT=25`
- `RISK_STATUS_FAILURE_RATE_CRITICAL_PCT=50`
- `RISK_STATUS_FAILURE_RATE_MIN_COMPLETED=4`
- `STATUS_PUBLIC_EDGE_TIMEOUT_SECONDS=6`
- `STATUS_NGINX_LOCAL_URL=http://127.0.0.1/healthz`
- `STATUS_NGINX_LOCAL_TIMEOUT_SECONDS=3`
- `STATUS_TLS_TIMEOUT_SECONDS=4`
- `STATUS_DISK_FREE_WARNING_PCT=15`
- `STATUS_DISK_FREE_CRITICAL_PCT=8`
- `STATUS_DB_SIZE_WARNING_MB=1024`
- `STATUS_DB_SIZE_CRITICAL_MB=4096`
- `TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>`
- `TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret-key>`
- `TURNSTILE_ENFORCE=true` (enforce verification for web pages)

Do not set both `SUPPORT_SMTP_USE_TLS=true` and `SUPPORT_SMTP_USE_SSL=true`.

### Resend + Proton DNS note

If `hodler-suite.com` is already used by Proton Mail, keep only one SPF TXT
record at root and merge both providers in that same record. Example:

`v=spf1 include:_spf.protonmail.ch include:amazonses.com ~all`

Keep Proton MX records for mailbox delivery and keep DKIM/DMARC enabled.
Add Resend DKIM records exactly as shown in Resend domain setup.

## 2) Nginx vhost

Ready file:

- `deploy/nginx.hodler-suite.conf`

Before enabling docs host:

1. Add DNS record in Cloudflare:
   - `A docs -> 80.240.31.172` (Proxied/orange cloud)
2. Issue certificate:

```bash
sudo certbot --nginx -d docs.hodler-suite.com
```

3. Publish docs site files:

```bash
sudo mkdir -p /var/www/hodler-suite-docs
sudo rsync -a --delete ~/site_public/ /var/www/hodler-suite-docs/
```

Install steps (Ubuntu/Debian style):

```bash
sudo cp scripts/v2.0/web_portal/deploy/nginx.hodler-suite.conf /etc/nginx/sites-available/hodler-suite-web-portal.conf
sudo ln -s /etc/nginx/sites-available/hodler-suite-web-portal.conf /etc/nginx/sites-enabled/hodler-suite-web-portal.conf
sudo nginx -t
sudo systemctl reload nginx
```

Direct upload/reload commands for your server (`80.240.31.172`) using non-root SSH user:

```bash
scp scripts/v2.0/web_portal/deploy/nginx.hodler-suite.conf linuxuser@80.240.31.172:/tmp/hodler-suite-web-portal.conf
ssh linuxuser@80.240.31.172 "sudo mv /tmp/hodler-suite-web-portal.conf /etc/nginx/sites-available/hodler-suite-web-portal.conf && sudo ln -sfn /etc/nginx/sites-available/hodler-suite-web-portal.conf /etc/nginx/sites-enabled/hodler-suite-web-portal.conf && sudo nginx -t && sudo systemctl reload nginx"
```

## 3) Verify auth consistency

1. Login with a portal account.
2. Open `/help-center`, `/faq`, `/docs`.
3. Confirm `Sign in` is not shown and user identity remains visible.
4. Logout and confirm only public pages are shown.

## 4) Verify ticket emails

Submit from Help Center or API:

```bash
curl -sS -X POST http://127.0.0.1:5050/api/v1/support/tickets \
  -H "Content-Type: application/json" \
  -d '{"email":"customer@example.com","subject":"Login issue","message":"Cannot access dashboard"}'
```

Expected:

- `201` with `ticket_id` in response
- auto-ack email sent from `support@hodler-suite.com` to customer
- summary email sent to `support@hodler-suite.com`
- account security emails (signup/verification/reset) sent from `no_reply@hodler-suite.com`

For Resend Receiving inbound replies, configure webhook URL:

- `https://app.hodler-suite.com/api/v1/support/inbound-email/resend`

## 5) Push app changes and restart service

If the app lives at `/opt/hodler-suite/web_portal` and systemd service is
`hodler-web-portal.service`, use:

```bash
scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh linuxuser@80.240.31.172
```

This helper intentionally preserves runtime files on server:

- `.venv/`
- `.env`
- `web_portal.env`
- `data/`

Manual fallback (same safety profile):

```bash
rsync -avz --delete \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude 'web_portal.env' \
  --exclude 'data/' \
  scripts/v2.0/web_portal/ linuxuser@80.240.31.172:/tmp/hodler-suite-web-portal/

ssh linuxuser@80.240.31.172 "sudo rsync -av --delete \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude 'web_portal.env' \
  --exclude 'data/' \
  /tmp/hodler-suite-web-portal/ /opt/hodler-suite/web_portal/ && \
  sudo systemctl restart hodler-web-portal.service && \
  sudo systemctl status --no-pager hodler-web-portal.service"
```
