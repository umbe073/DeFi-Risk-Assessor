# Web portal and script API (production)

Hodler Suite production splits the **customer-facing site** from the **legacy script API** that serves chain cache and internal tooling. They are separate processes and deploy units.

## Components

| Piece | Role | Typical unit |
| --- | --- | --- |
| **Web portal** | Flask app: accounts, billing, Live Assessment orchestration, support APIs | `hodler-web-portal.service` (Gunicorn), app root e.g. `/opt/hodler-suite/web_portal/` |
| **Script API** | `webhook_server:app` — cache health, token refresh hooks, deep health by chain | `hodler-script-api.service` (Gunicorn), working directory pointing at `scripts/v2.0` |

The portal **does not** import or run `webhook_server` inside the same worker. It talks to risk workers and optional HTTP helpers via configured base URLs and shared secrets, as documented in `deploy/risk/RISK_WORKER_RUNTIME.md` and related deploy packs.

## Supported deploy path

Only the repository **deploy scripts** (rsync to the server layout + `systemctl restart …`) are supported for production updates—manual copies of trees or ad hoc `flask run` on the VPS are out of scope for support.

- Web portal: `scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh`
- Script API: `scripts/v2.0/web_portal/deploy/deploy_script_api_safe.sh` (see `deploy/status/SCRIPT_API_RUNTIME.md`)

The web portal promote step uses `rsync --delete` **with excludes** for `venv/`, `.venv/`, `pydeps/`, `.env`, `data/`, and databases so production-only paths are not wiped by a normal deploy.

### Recover a destroyed portal venv (missing `venv/bin/gunicorn`)

If `ls /opt/hodler-suite/web_portal/venv/bin/gunicorn` fails, the interpreter environment must be recreated **on the VPS** (not on your laptop).

1. Copy the pinned dependency list to the server from your repo checkout (**run `git pull` first** so the file exists):

   `docs/Website/web-portal-runtime-requirements.txt` → `/opt/hodler-suite/web_portal/requirements-production.txt`

   ```bash
   cd /path/to/venv/repo
   scp docs/Website/web-portal-runtime-requirements.txt linuxuser@YOUR_HOST:/opt/hodler-suite/web_portal/requirements-production.txt
   ```

2. On the server:

```bash
sudo systemctl stop hodler-web-portal.service || true
cd /opt/hodler-suite/web_portal
# Ubuntu: ensure venv support and headers for cryptography wheels
sudo apt-get update && sudo apt-get install -y python3-venv python3-dev build-essential libssl-dev libffi-dev
python3 -m venv venv
./venv/bin/pip install -U pip wheel setuptools
./venv/bin/pip install -r requirements-production.txt
./venv/bin/python -c "import flask, gunicorn; print('imports OK')"
sudo systemctl start hodler-web-portal.service
systemctl is-active hodler-web-portal.service
```

3. If systemd still reports **`Failed to load environment files`**, fix paths only (rsync does not remove `/etc`):

```bash
systemctl cat hodler-web-portal.service
sudo ls -la /etc/hodler-suite/
```

Every `EnvironmentFile=` line must point at an existing file (commonly `/etc/hodler-suite/web_portal.env`). Restore that file from backup or your secrets store, then `sudo systemctl restart hodler-web-portal.service` again.

## Hosted documentation and TLS

Public docs should live on a **stable hostname** (e.g. `docs.example.com`) with TLS terminated at the edge (Nginx/Caddy/Cloudflare). DNS and certificate lifecycle are operator responsibilities; point the hostname at the docs static host or MkDocs output as you standardize.

## Optional: MkDocs / Zensical

A **non-production spike** to evaluate Zensical (or MkDocs 2.x) can live on a branch; keep the main docs pipeline unchanged until you cut over deliberately.
