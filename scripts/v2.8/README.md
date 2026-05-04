# DeFi Risk Assessment Suite v2.8

## Overview

`scripts/v2.8` is the GitHub source-of-truth for the app/risk-assessment code that is deployed by GitHub Actions (using a **server-side** deploy driver maintained outside this repository).
It was migrated forward from the older `scripts/v2.0` desktop-oriented tree, but the production runtime can still stay on
`scripts/v2.0` on the server.

The current model is:

- Develop app/risk/script changes locally under `scripts/v2.8`.
- Commit and push those changes to GitHub.
- GitHub Actions runs the production deploy workflow.
- The server deploy script syncs `scripts/v2.8` into the configured runtime target (often a server-side `scripts` tree kept for backward-compatible service paths).
- The `web_portal` / website tree remains a manual deployment path and is intentionally not published from this folder.

## What Changed From v2.0

### v2.0 Desktop Tree

The `scripts/v2.0` tree was originally organized around local/desktop operation:

- macOS dashboard launchers and system tray utilities
- tkinter and PyObjC compatibility helpers
- local credential-management GUIs
- local report generation and desktop token-list workflows

### v2.8 App + GitOps Tree

The `scripts/v2.8` tree keeps the risk engine and app-facing automation, but adapts the workflow for server deployment:

- `scripts/v2.8` is the repo-tracked source for app/risk code.
- GitHub Actions deploys from `scripts/v2.8` to a server runtime directory.
- The server runtime directory can remain `scripts/v2.0` for service compatibility.
- Deployment includes backup, rollback, service restart, and health checks.
- Web portal and website assets are excluded from this GitHub publish path unless explicitly handled by the manual portal deploy.

## Deployment Model

The main production workflow is `.github/workflows/deploy.yml`.

On a push to `main`, GitHub Actions:

1. Checks out the repository.
2. Configures SSH from GitHub Actions secrets.
3. Runs the **server-side** `auto_sync_and_deploy.sh` (maintained in private ops on the server — it is **not** copied from this repository).
4. That script fetches `origin/main`, resets the checkout, backs up the runtime target, syncs `scripts/v2.8` to the runtime target, restarts services, and runs health checks.

Important deploy paths (documented in internal runbooks, not in Git):

- `DEPLOY_PATH`: Git checkout root on the server, for example `/opt/defi-risk/app`.
- `DEPLOY_RUNTIME_TARGET_DIR`: runtime target, for example `/opt/defi-risk/app/scripts/v2.8`.
- `SOURCE_DIR`: defaults to `${DEPLOY_PATH}/scripts/v2.8`.

Do not set `DEPLOY_RUNTIME_TARGET_DIR` to `DEPLOY_PATH` itself. The runtime target must be the app `scripts` subtree used by services, not the repository root.

Operational docs (`GITOPS_SETUP.md`, `OPERATING_MODEL.md`, bootstrap scripts) live next to the deploy driver on the server or in private storage — not in this repository.

## Website / Web Portal Scope

The web portal and website deployment path is still manual unless a separate decision is made to publish those files through GitHub.

In this repo, `scripts/v2.8/web_portal/` is excluded from normal GitHub scope. Portal changes should be deployed with the existing safe portal deployment script, then verified on the server.

Manual portal deploy uses your **private** web portal checkout and internal SSH targets (not documented here).

## Data Publication

`scripts/v2.8/data/` is the publishable data folder for v2.8. It is allowed into Git for non-secret project data, placeholder directories, and lightweight report artifacts. Runtime, sensitive, and oversized generated files remain blocked by `.gitignore`, including:

- SQLite / DB files
- Python bytecode and `__pycache__`
- logs, PID files, temp files, corrupt cache fragments, and backup cache copies
- `.env`, private keys, certificates, and key material
- runtime cache directories
- huge raw CSV/JSON risk-report exports that exceed or approach GitHub file-size limits
- API runtime/fallback caches that may contain provider URLs or embedded API keys

This lets safe v2.8 reports, JSON registries, CSV token lists, social report text files, and similar source/report data travel with the repo while keeping unsafe runtime state out of Git. Large raw report exports should be stored outside Git or moved to a release artifact/object-storage process if they need long-term publication.

The deploy script still excludes `data/` when syncing `scripts/v2.8` into the server runtime target, so server runtime data is not overwritten during app deploys. Publishing `scripts/v2.8/data/` is for repository visibility and local development, not for replacing production runtime data.

## Local Development

From the repository root:

```bash
cd /path/to/DeFi-Risk-Assessor
python3 scripts/v2.8/defi_complete_risk_assessment_clean.py
```

Use `scripts/v2.8/data/risk_reports/` and `scripts/v2.8/data/social_reports/` for v2.8-local output paths where applicable. Root `/data/` remains outside this publish policy unless it is explicitly reviewed and requested separately.

## Server Verification

After a successful GitHub deploy, verify on the server:

```bash
cd /opt/defi-risk/app
git log -1 --oneline
test -d scripts/v2.0 && echo "OK runtime target exists"
curl -fsS -m 12 "http://127.0.0.1:5050/healthz" && echo " OK portal"
curl -fsS -m 12 "http://127.0.0.1:5001/webhook/health/deep/polygon" && echo " OK script API"
```

Adjust `/opt/defi-risk/app` if `DEPLOY_PATH` is different.

## Requirements

The repository root `requirements.txt` currently contains the core risk-assessment dependencies. Portal/server extras may be installed separately in the server environment or represented by future split requirement files.

## Support

For deployment issues:

1. Check GitHub Actions logs for the `Deploy to Production` workflow.
2. Check `deploy/GITOPS_SETUP.md` for secret and SSH setup.
3. Check `deploy/OPERATING_MODEL.md` for the app-vs-portal operating model.
4. Check server logs with `sudo journalctl -u hodler-web-portal.service -n 120 --no-pager` and the configured script API service.
