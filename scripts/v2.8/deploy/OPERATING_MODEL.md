# Deployment operating model (lessons)

This is the **canonical workflow** for Hodler / DeFi Risk work split between **app code on Git** (`scripts/v2.8`) and **website / web_portal** material that may stay out of GitHub scope.

## A) App-related material (`scripts/v2.8/` on `main`)

1. **Develop locally** under `scripts/v2.8/` (source of truth for what auto-deploy syncs to server runtime).
2. **Commit and push to GitHub** on `main`.
3. **GitHub Actions** runs **Deploy to Production** (see `.github/workflows/deploy.yml`): the server runs `auto_sync_and_deploy.sh`, which resets the app repo to `origin/main`, **rsyncs `scripts/v2.8/` → `DEPLOY_RUNTIME_TARGET_DIR`** (typically `…/scripts/v2.0`), restarts the configured services, and rolls back on failed health checks.

**Caveat:** Only what is **tracked and present in `scripts/v2.8/` on `main`** is what the rsync step deploys to the runtime tree. Changes kept only under `scripts/v2.0/` locally are not deployed by this path unless you mirror them into `v2.8` and push.

### After every successful auto-deploy — verify on the server

SSH to the host and run (adjust `APP_ROOT`, ports, and paths to match your secrets; examples use common defaults):

```bash
# Repo at expected root + short SHA on server
cd /opt/defi-risk/app 2>/dev/null || cd /opt/hodler-suite
git fetch origin -q && git rev-parse --short HEAD && git log -1 --oneline

# Portal (Gunicorn) — use bind URL, not nginx-only /healthz if that returns 301
curl -fsS -m 12 "http://127.0.0.1:5050/healthz" && echo " OK portal"

# Script API / webhook (chain slug as you configured in CI secrets)
curl -fsS -m 12 "http://127.0.0.1:5001/webhook/health/deep/polygon" && echo " OK script API"

# Optional: unit state
systemctl is-active hodler-web-portal.service defirisk-webhook.service 2>/dev/null || true
```

If any check fails, inspect logs: `sudo journalctl -u hodler-web-portal.service -n 120 --no-pager` (and the script API unit name you use).

---

## B) Website / web_portal material (manual path)

1. **Develop locally** in your web_portal tree (often `scripts/v2.0/web_portal/` on disk; `scripts/v2.8/web_portal/` may be **gitignored** and not pushed — see `.gitignore` and `GITOPS_SETUP.md`).
2. **Deploy manually** using the existing safe helper, e.g. from the machine that has the portal tree:

   ```bash
   bash scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh
   ```

   Pass SSH host / tmp / remote app dir / service name as documented in that script’s header.

3. **Verification** is run **at the end of `deploy_web_portal_safe.sh`** (HTTP health check + prior `systemctl status`). Override the check URL if needed:

   ```bash
   WEB_PORTAL_HEALTH_URL="http://127.0.0.1:5050/healthz" \
     bash scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh 'your-ssh-target'
   ```

---

## Summary

| Area | Local work | GitHub | Server |
|------|------------|--------|--------|
| App / risk / scripts in **`scripts/v2.8/`** | Edit → commit → push `main` | Yes | **Auto** via Actions + `auto_sync_and_deploy.sh` |
| **Website / web_portal** (outside or ignored on `main`) | Edit locally | Optional / not in scope | **Manual** `deploy_web_portal_safe.sh` + checks at end of script |

See also: `GITOPS_SETUP.md` for secrets, paths, and smoke script.
