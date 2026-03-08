# Script API Runtime + Watchdog (Season 2)

This deploy pack keeps `scripts/v2.0/webhook_server.py` online 24/7 and adds a timer-driven watchdog.

## Files

- `hodler-script-api.service`
- `script_api_watchdog.sh`
- `script-api-watchdog.service`
- `script-api-watchdog.timer`

## Install On Server

```bash
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/status/hodler-script-api.service /etc/systemd/system/hodler-script-api.service
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/status/script_api_watchdog.sh /usr/local/sbin/hodler_script_api_watchdog.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/status/script-api-watchdog.service /etc/systemd/system/script-api-watchdog.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/status/script-api-watchdog.timer /etc/systemd/system/script-api-watchdog.timer

sudo systemctl daemon-reload
sudo systemctl enable --now hodler-script-api.service
sudo systemctl enable --now script-api-watchdog.timer

sudo systemctl start script-api-watchdog.service
sudo systemctl status --no-pager -l hodler-script-api.service | sed -n '1,80p'
sudo systemctl list-timers --all | grep script-api-watchdog
```

## Required Paths/Assumptions

- Script API project path: `/opt/hodler-suite/scripts/v2.0`
- Python venv path: `/opt/hodler-suite/.venv`
- Runtime user/group in unit file: `linuxuser`
  - adjust before install if your server uses a different service user.

## Watchdog Env Keys

Set these in `/opt/hodler-suite/web_portal/web_portal.env`:

- `SCRIPT_API_WATCHDOG_URL=http://127.0.0.1:5001/webhook/health`
- `SCRIPT_API_WATCHDOG_TIMEOUT_SECONDS=6`
- `SCRIPT_API_WATCHDOG_FAILURE_THRESHOLD=3`
- `SCRIPT_API_WATCHDOG_HTTP_ATTEMPTS=3`
- `SCRIPT_API_WATCHDOG_RETRY_DELAY_SECONDS=2`
- `SCRIPT_API_WATCHDOG_UNIT=hodler-script-api.service`
- `SCRIPT_API_WATCHDOG_STATE_FILE=/var/lib/hodler-suite/script_api_watchdog.state`

If unset, the script uses the above defaults.

## Manual Checks

```bash
curl -fsS http://127.0.0.1:5001/webhook/health
curl -fsS http://127.0.0.1:5001/webhook/health/deep/eth
curl -fsS http://127.0.0.1:5001/webhook/health/deep/bsc
curl -fsS http://127.0.0.1:5001/webhook/health/deep/tron
sudo /usr/local/sbin/hodler_script_api_watchdog.sh
sudo journalctl -u hodler-script-api.service --no-pager -n 80
sudo journalctl -u script-api-watchdog.service --no-pager -n 80
```

## Operational Notes

- The watchdog increments a persisted failure counter and only restarts after threshold breaches.
- Successful probes reset the failure counter to `0`.
- The base Script API health endpoint is intentionally simple (`/webhook/health`) and expected to return HTTP 200.
- Chain deep probes are available at `/webhook/health/deep/<chain>` for `eth`, `bsc`, and `tron`.
- Deep-probe freshness can be tuned in the Script API project `.env`:
  - `SCRIPT_API_DEEP_HEALTH_MAX_AGE_SECONDS=21600`
  - `SCRIPT_API_DEEP_HEALTH_MIN_TOKENS=1`
