# Vultr Deployment Bundle (Ubuntu 24.04)

This folder contains a low-cost deployment baseline for your current stack:

- `bootstrap_vultr_ubuntu.sh`: OS hardening + base package setup.
- `install_app.sh`: venv + Python dependencies + gunicorn.
- `install_services.sh`: installs systemd + Nginx configs and starts services.
- `backup_runtime_config.sh`: snapshots live Nginx/env/systemd config for rollback.
- `defirisk-webhook.service`: gunicorn service for `scripts/v2.0/webhook_server.py`.
- `defirisk-webportal.service`: gunicorn service for `scripts/v2.0/web_portal`.
- `nginx-defirisk.conf`: reverse proxy template.

## End-to-end flow

1. Bootstrap server (run once):

```bash
sudo apt-get update && sudo apt-get install -y git
sudo mkdir -p /opt/defi-risk
sudo git clone <YOUR_REPO_URL> /opt/defi-risk/app
sudo bash /opt/defi-risk/app/scripts/v2.0/deploy/vultr/bootstrap_vultr_ubuntu.sh
```

2. Install Python runtime + deps:

```bash
sudo bash /opt/defi-risk/app/scripts/v2.0/deploy/vultr/install_app.sh
```

3. Edit env files:

```bash
sudo nano /etc/defi-risk/web_portal.env
sudo nano /etc/defi-risk/webhook.env
```

4. Install and start services:

```bash
sudo bash /opt/defi-risk/app/scripts/v2.0/deploy/vultr/install_services.sh
```

5. Verify:

```bash
curl -sS http://127.0.0.1:5050/healthz
curl -sS http://127.0.0.1:5001/webhook/health
sudo journalctl -u defirisk-webportal -n 100 --no-pager
sudo journalctl -u defirisk-webhook -n 100 --no-pager
```

6. Freeze runtime config before major changes:

```bash
sudo bash /opt/defi-risk/app/scripts/v2.0/deploy/vultr/backup_runtime_config.sh
```

## Before public launch

- Replace `app.example.com` in `nginx-defirisk.conf` and re-run `install_services.sh`.
- Configure DNS A record to Vultr public IP.
- Install TLS certs (`certbot --nginx`) and enforce HTTPS redirect.
- Set `MASTER_ACCOUNT_PASSWORD` in `/etc/defi-risk/web_portal.env` to a strong secret and restart portal service.
- Keep `NOWPAYMENTS_ENABLED=false` until billing webhook verification and idempotency persistence are production-tested.
