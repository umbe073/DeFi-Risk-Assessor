# Services Status Background Sampler

This deploy pack records regular status samples into `status_metrics.db` so uptime graphs keep updating even without `/services-status` page visits.

Related Season 2 runtime pack:

- `SCRIPT_API_RUNTIME.md` (24/7 Script API service + watchdog timer)

## Files

- `status_sampler.sh`
- `status-sampler.service`
- `status-sampler.timer`

## Install On Server

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/status/status_sampler.sh /usr/local/sbin/hodler_status_sampler.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/status/status-sampler.service /etc/systemd/system/status-sampler.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/status/status-sampler.timer /etc/systemd/system/status-sampler.timer
sudo systemctl daemon-reload
sudo systemctl enable --now status-sampler.timer
sudo systemctl start status-sampler.service
sudo systemctl status --no-pager status-sampler.service
sudo systemctl list-timers --all | grep status-sampler
```

## Required Env Keys

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `STATUS_SAMPLER_SECRET=<long-random-secret>`

Optional:

- `STATUS_SAMPLER_BASE_URL=http://127.0.0.1:5050`
- `STATUS_SAMPLER_TIMEOUT_SECONDS=20`

The app endpoint sampled by this runner is:

- `POST /api/v1/internal/status-sample`

## Manual One-Shot

```bash
sudo /usr/local/sbin/hodler_status_sampler.sh
```
