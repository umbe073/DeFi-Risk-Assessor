# v2.8 Migration + GitOps Setup

This guide keeps server runtime on `scripts/v2.0`, while local development and GitHub source of truth move to
`scripts/v2.8`. Deploy sync copies `scripts/v2.8` into server runtime `scripts/v2.0` with backup and rollback.

## 1) Detect canonical server runtime (required first)

```bash
bash /opt/hodler-suite/scripts/v2.8/deploy/runtime_discovery.sh
```

If `v2.8` files are not on server yet, copy this script first and run it from `/tmp`.

## 2) Local migration (development machine only)

Copy local `scripts/v2.0` into local `scripts/v2.8`:

```bash
rsync -a --delete \
  --exclude "data/" \
  --exclude "deploy/" \
  /Users/amlfreak/Desktop/venv/scripts/v2.0/ \
  /Users/amlfreak/Desktop/venv/scripts/v2.8/
```

## 3) Optional one-time server migration (skip if server stays on v2.0)

```bash
INCLUDE_WEB_PORTAL=false bash /opt/hodler-suite/scripts/v2.8/deploy/bootstrap_v2_8_from_v2_0.sh /opt/hodler-suite
```

Behavior:

- creates a timestamped backup under `/opt/hodler-suite/backups/v2_8_migration/`
- syncs `scripts/v2.0` -> `scripts/v2.8` (excluding website by default)
- rewrites hardcoded `v2.0`/legacy report paths
- creates `scripts/v2.8/data/risk_reports` and `scripts/v2.8/data/social_reports`

## 4) Smoke verification

```bash
bash /opt/hodler-suite/scripts/v2.8/deploy/verify_v2_8_smoke.sh /opt/hodler-suite
```

## 5) GitHub Actions deploy secrets

Configure:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_PORT`
- `DEPLOY_SSH_PRIVATE_KEY`
- `DEPLOY_PATH` (for example `/opt/hodler-suite`)
- `DEPLOY_WEB_SERVICE` (default `hodler-web-portal.service`)
- `DEPLOY_SCRIPT_SERVICE` (default `defirisk-webhook.service`)
- `DEPLOY_RUNTIME_TARGET_DIR` (default `${DEPLOY_PATH}/scripts/v2.0`)
- `DEPLOY_HEALTH_URL_APP` (default `http://127.0.0.1/healthz`)
- `DEPLOY_HEALTH_URL_SCRIPT` (default `http://127.0.0.1:5001/webhook/health/deep/polygon`)

## 6) Auto-deploy operation

On merge to `main`, workflow runs `scripts/v2.8/deploy/auto_sync_and_deploy.sh` on server:

- creates pre-deploy backup
- fetch/reset to `origin/main`
- syncs `scripts/v2.8` into runtime target (default server `scripts/v2.0`)
- restarts services
- runs health checks
- rolls back on failure

## 7) Security scope

- only `scripts/v2.8/**` is in-scope for push
- `scripts/v2.8/web_portal/**` is excluded from push scope
- `.env`/secrets/DB/runtime files are blocked by ignore + CI guards
