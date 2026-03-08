# Risk Worker Runtime (Season 3)

This deploy pack runs queued risk jobs from `risk_jobs.db` using the internal endpoint:

- `POST /api/v1/risk/internal/run-once`

## Files

- `deploy/risk/risk_worker_run_once.sh`
- `deploy/risk/risk-worker.service`
- `deploy/risk/risk-worker.timer`

## Install On Server

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

## Required Env Keys

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `RISK_WORKER_SHARED_SECRET=<same value used by internal risk worker endpoints>`

Optional:

- `RISK_WORKER_BASE_URL=http://127.0.0.1:5050`
- `RISK_WORKER_TIMEOUT_SECONDS=40`
- `RISK_WORKER_WAIT_FOR_APP_SECONDS=20`
- `RISK_WORKER_ID=<stable node id>`

Fallback behavior:

- if `RISK_WORKER_SHARED_SECRET` is empty, script falls back to `WEBHOOK_SHARED_SECRET`.

## Manual One-shot

```bash
sudo /usr/local/sbin/hodler_risk_worker_run_once.sh
```

Expected output examples:

- idle queue: `[risk-worker] status=idle processed=False claimed=False`
- processed job: `[risk-worker] status=processed processed=True claimed=True job_id=RJ-... job_status=succeeded risk_score=...`

