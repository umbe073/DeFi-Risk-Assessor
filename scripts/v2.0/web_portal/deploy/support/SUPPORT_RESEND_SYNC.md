# Support Inbound Resend Fallback Sync

This fallback runner ingests recently received Resend emails in case webhook delivery is delayed or dropped.

## Files

- `support_resend_sync.sh`
- `support_resend_sync_drill.sh`
- `support-resend-sync.service`
- `support-resend-sync.timer`

## Install On Server

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/support/support_resend_sync.sh /usr/local/sbin/hodler_support_resend_sync.sh
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/support/support_resend_sync_drill.sh /usr/local/sbin/hodler_support_resend_sync_drill.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/support/support-resend-sync.service /etc/systemd/system/support-resend-sync.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/support/support-resend-sync.timer /etc/systemd/system/support-resend-sync.timer
sudo systemctl daemon-reload
sudo systemctl enable --now support-resend-sync.timer
sudo systemctl start support-resend-sync.service
sudo systemctl status --no-pager support-resend-sync.service
sudo systemctl list-timers --all | grep support-resend-sync
```

## Required Env Keys

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `SUPPORT_INBOUND_ROUTING_ACTIVE=true`
- `SUPPORT_INBOUND_WEBHOOK_SECRET=<same secret used by inbound webhook>`

Optional:

- `SUPPORT_RESEND_SYNC_BASE_URL=http://127.0.0.1:5050`
- `SUPPORT_RESEND_SYNC_LIMIT=50`
- `SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD=5` (creates warning alert when one run finds too many orphan replies)
- `SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS=3` (consecutive over-threshold runs required for sustained critical alert)
- `SUPPORT_SYNC_WAIT_FOR_APP_SECONDS=20` (wait time for local app readiness before sync/drill request)
- `SUPPORT_SYNC_HTTP_ATTEMPTS=3` (retry count for transient HTTP/connectivity issues)

## Result Semantics

The sync endpoint now reports:

- `processed`: replies ingested into known tickets.
- `duplicates`: already-seen Resend emails.
- `unmapped`: replies that contain a ticket reference not found in local DB (`ticket_not_found`).
- `failed`: hard failures (fetch/ingest/storage errors excluding unmapped).
- `failed_total`: `failed + unmapped`.

Policy behavior:

- if `unmapped >= SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD`, a warning operational alert is raised.
- if threshold breach persists for `SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS` consecutive runs, a critical sustained alert is raised.
- warning/critical alerts are emitted on breach-state transitions (not on every run), so recurring unchanged breach state does not continuously recreate alerts.

Long-term handling policy:

- `unmapped` replies are treated as orphan inbound traffic, not service failures.
- hard failures (`failed`) are still treated as operational faults and should page the on-call path.
- sustained orphan traffic (`critical` sustained alert) enters manual triage workflow:
  - inspect `unmapped_ticket_ids` and sampled errors,
  - recover/restore missing ticket refs where possible,
  - keep/adjust threshold values if expected campaign/legacy traffic changes.

## Production Drill Evidence (2026-03-04 UTC)

Observed in production delayed-webhook/orphan drill (`runs=3`, `sleep=5s`, `limit=50`):

- run 1: `checked=10 processed=0 duplicates=4 unmapped=6 failed=0 failed_total=6 breach=1 sustained=1`
- run 2: `checked=10 processed=0 duplicates=4 unmapped=6 failed=0 failed_total=6 breach=1 sustained=1`
- run 3: `checked=10 processed=0 duplicates=4 unmapped=6 failed=0 failed_total=6 breach=1 sustained=1`
- drill result: `policy=ALERT sustained_unmapped_detected`, `drill_exit_code=2`

Interpretation:

- policy guard is operating as designed (sustained orphan condition detected),
- no hard ingest/runtime failure was observed (`failed=0` in all runs).

## Finalized Sustained-Unmapped Policy (Long-Term)

1. Classification
   - Treat `ticket_not_found` as `unmapped` (orphan traffic), not hard failure.
2. Service health
   - Treat `failed > 0` as operational failure and page on-call workflow.
3. Warning threshold
   - If `unmapped >= SUPPORT_RESEND_SYNC_UNMAPPED_ALERT_THRESHOLD`, emit warning alert.
4. Sustained threshold
   - If threshold breach persists for `SUPPORT_RESEND_SYNC_UNMAPPED_SUSTAINED_RUNS` consecutive runs, emit critical sustained alert.
5. Triage workflow
   - Inspect `unmapped_ticket_ids` and sampled errors.
   - Recover/restore missing ticket references when feasible.
   - Document expected orphan sources (legacy/imported campaigns/mailbox forwarding edge cases).
6. Tuning and governance
   - Keep threshold/runs values unchanged unless trend evidence supports adjustment.
   - Review orphan trend weekly; if stable and expected, tune threshold conservatively.
   - If orphan volume increases suddenly, open incident and validate routing/mapping integrity.

## Manual One-Shot

```bash
sudo /usr/local/sbin/hodler_support_resend_sync.sh
```

## Delayed-Webhook/Orphan Drill

Run multi-iteration drill against live endpoint:

```bash
sudo SUPPORT_SYNC_DRILL_RUNS=3 SUPPORT_SYNC_DRILL_SLEEP_SECONDS=5 /usr/local/sbin/hodler_support_resend_sync_drill.sh
```

Exit semantics:

- `0`: no sustained unmapped condition detected.
- `2`: sustained unmapped condition detected (policy alert state).
- `1`: request/runtime failure.
