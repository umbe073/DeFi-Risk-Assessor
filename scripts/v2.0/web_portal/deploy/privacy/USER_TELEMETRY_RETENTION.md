# User Telemetry Retention Purge

This deploy pack enforces retention windows for user telemetry tables in `web_portal_auth.db`:

- `user_operation_logs`
- `user_devices`
- `user_login_contexts`

## Files

- `purge_user_telemetry.py`
- `user_telemetry_retention.sh`
- `user-telemetry-retention.service`
- `user-telemetry-retention.timer`

## Install On Server

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/privacy/user_telemetry_retention.sh /usr/local/sbin/hodler_user_telemetry_retention.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/privacy/user-telemetry-retention.service /etc/systemd/system/user-telemetry-retention.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/privacy/user-telemetry-retention.timer /etc/systemd/system/user-telemetry-retention.timer
sudo systemctl daemon-reload
sudo systemctl enable --now user-telemetry-retention.timer
sudo systemctl start user-telemetry-retention.service
sudo systemctl status --no-pager user-telemetry-retention.service
sudo systemctl list-timers --all | grep user-telemetry-retention
```

## Required Env Keys

Set in `/opt/hodler-suite/web_portal/web_portal.env`:

- `WEB_PORTAL_AUTH_DB=/opt/hodler-suite/web_portal/data/web_portal_auth.db`
- `USER_OPERATION_RETENTION_DAYS=180`
- `USER_DEVICE_RETENTION_DAYS=180`
- `USER_LOGIN_CONTEXT_RETENTION_DAYS=90`

Optional:

- `USER_TELEMETRY_RETENTION_ENABLED=true`
- `USER_TELEMETRY_PURGE_DRY_RUN=false`
- `USER_TELEMETRY_PURGE_ON_STARTUP=true` (applies purge once at app startup too)

## Manual One-Shot

```bash
sudo /usr/local/sbin/hodler_user_telemetry_retention.sh
```

Dry-run example:

```bash
sudo USER_TELEMETRY_PURGE_DRY_RUN=true /usr/local/sbin/hodler_user_telemetry_retention.sh
```
