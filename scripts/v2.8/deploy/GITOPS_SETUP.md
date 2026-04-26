# v2.8 Migration + GitOps Setup

This guide keeps server runtime on `scripts/v2.0`, while local development and GitHub source of truth move to
`scripts/v2.8`. Deploy sync copies `scripts/v2.8` into server runtime `scripts/v2.0` with backup and rollback.

**Day-to-day workflow (app vs web_portal):** see `OPERATING_MODEL.md` in this folder.

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

## 5) GitHub Actions deploy secrets (step-by-step)

Use a **dedicated deploy key** (not your personal day-to-day SSH key). Empty passphrase only for this automation key; restrict what it can do on the server with normal `authorized_keys` / user permissions.

### A) On your Mac (generate key pair)

1. Open Terminal.
2. Pick a folder **outside** the repo for key files (so they are never committed), e.g. `mkdir -p ~/.ssh/hodler-gha && cd ~/.ssh/hodler-gha`.
3. Generate an **Ed25519** key with **no passphrase** (required for the current workflow):

   ```bash
   ssh-keygen -t ed25519 -f ./gha-deploy-ed25519 -N "" -C "github-actions-deploy"
   ```

4. You now have:
   - **`gha-deploy-ed25519`** — **private** key (goes into GitHub secret `DEPLOY_SSH_PRIVATE_KEY` later). **Never commit this file.**
   - **`gha-deploy-ed25519.pub`** — **public** key (goes on the server in `authorized_keys`).

5. Verify the private key is **multi-line** (sanity check):

   ```bash
   wc -l ./gha-deploy-ed25519
   head -1 ./gha-deploy-ed25519
   tail -1 ./gha-deploy-ed25519
   ```

   You should see `-----BEGIN OPENSSH PRIVATE KEY-----` on the first line and `-----END OPENSSH PRIVATE KEY-----` on the last. If the whole key is one long line, do not use it — regenerate or fix the file.

### B) On the server (install public key once)

SSH in the way you already use for admin (your normal user/key), then run **as the same Linux user GitHub will use** (`DEPLOY_USER`, e.g. `linuxuser`). Replace paths if your home directory differs.

1. `ssh YOUR_ADMIN_USER@YOUR_SERVER`
2. `sudo su - linuxuser` **or** log in directly as `linuxuser` if that is how you operate.
3. Ensure `~/.ssh` exists and permissions are strict:

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   touch ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

4. On your **Mac**, print the **public** key and copy it to the clipboard (or paste into a notes file you trust):

   ```bash
   cat ~/.ssh/hodler-gha/gha-deploy-ed25519.pub
   ```

5. On the **server**, append **exactly one line** (the whole `.pub` line) to `~/.ssh/authorized_keys`:

   ```bash
   nano ~/.ssh/authorized_keys
   ```

   Paste the line, save, exit. Do not break the line across multiple rows.

6. Optional hardening: in `/etc/ssh/sshd_config`, ensure `PubkeyAuthentication yes` and reload `sshd` only if you know you need to change it (often already correct).

7. **Test from your Mac** before touching GitHub (must succeed):

   ```bash
   ssh -i ~/.ssh/hodler-gha/gha-deploy-ed25519 -o IdentitiesOnly=yes linuxuser@YOUR_SERVER_IP "echo ok"
   ```

   If this fails, fix server `authorized_keys`, user, host, or firewall **before** storing the private key in GitHub.

### C) In GitHub (repository secrets)

1. Open the repo: `https://github.com/ddos-revenge/DeFi-Risk-Assessor` (or your fork URL).
2. **Settings** → **Secrets and variables** → **Actions**.
3. For each row below: **New repository secret** (or **Update** if it exists). Names must match **exactly** (case-sensitive).

| Secret name | What to paste |
|-------------|----------------|
| `DEPLOY_HOST` | Server hostname or IP only (no `user@`, no `ssh://`). Example: `80.240.31.172` |
| `DEPLOY_USER` | SSH login name GitHub uses. Example: `linuxuser` |
| `DEPLOY_SSH_PORT` | Port number as string if not 22. Example: `22` |
| `DEPLOY_SSH_PRIVATE_KEY_B64` | **Preferred.** Base64 of the private key file (one line, no wrapping). Generate with the command below. |
| `DEPLOY_SSH_PRIVATE_KEY` | Fallback only. Entire contents of **`gha-deploy-ed25519`** (private file), from first `-----BEGIN …-----` line through last `-----END …-----` line, including line breaks. Do not wrap in quotes. |
| `DEPLOY_PATH` | Git repo root on server (where `scripts/v2.8` lives after clone). Example: `/opt/hodler-suite` or `/opt/defi-risk/app` |
| `DEPLOY_RUNTIME_TARGET_DIR` | Directory rsync targets (often `…/scripts/v2.0`). Example: `/opt/defi-risk/app/scripts/v2.0` |
| `DEPLOY_WEB_SERVICE` | systemd unit for portal. Example: `hodler-web-portal.service` |
| `DEPLOY_SCRIPT_SERVICE` | systemd unit for script API / webhook. Example: `defirisk-webhook.service` |
| `DEPLOY_HEALTH_URL_APP` | URL the runner curls after deploy. Example: `http://127.0.0.1:5050/healthz` |
| `DEPLOY_HEALTH_URL_SCRIPT` | Second health URL. Example: `http://127.0.0.1:5001/webhook/health/deep/polygon` |

4. For **`DEPLOY_SSH_PRIVATE_KEY_B64`** (preferred): on your Mac, run:

   ```bash
   base64 -i ~/.ssh/hodler-gha/gha-deploy-ed25519 | tr -d '\n'
   ```

   Copy the **entire one-line output** into the GitHub secret value and save. This avoids multiline copy/paste corruption and is the recommended fix for `error in libcrypto`.

5. If you cannot use base64, fallback to **`DEPLOY_SSH_PRIVATE_KEY`**: open the private key in a **plain-text** editor (VS Code / `nano` on Mac). Copy **all** lines. In GitHub’s secret value box, paste once. Save. If GitHub ever shows the value as one line in the UI, that is normal for display — the important part is that the stored secret preserves newlines (GitHub Actions does preserve them in `${{ secrets.DEPLOY_SSH_PRIVATE_KEY }}`).

6. **Passphrase**: if you generated the key with `-N ""` as above, there is no passphrase. Passphrase-protected keys will **not** work with the current workflow.

### D) Confirm workflow and re-run

1. Ensure `main` contains `.github/workflows/deploy.yml` (the version that prefers `DEPLOY_SSH_PRIVATE_KEY_B64`, falls back to `DEPLOY_SSH_PRIVATE_KEY`, and runs an `ssh-keygen` check).
2. **Actions** → **Deploy to Production** → open the latest run → **Re-run all jobs** (or push a small commit to `main`).

### E) If it still fails

- **`error in libcrypto` / `ssh-keygen` fails in “Configure SSH”**: the private key secret is malformed (wrong file, truncated, literal `\n` instead of newlines). Use `DEPLOY_SSH_PRIVATE_KEY_B64` generated directly from the private key file.
- **`Permission denied (publickey)`** after libcrypto is gone: wrong `DEPLOY_USER` / `DEPLOY_HOST` / port, or public key not in that user’s `authorized_keys`, or wrong key in secret (e.g. pasted `.pub` into private secret by mistake).
- **Never** paste the private key into issues, chat logs, or commits.

### `DEPLOY_SSH_PRIVATE_KEY_B64` / `DEPLOY_SSH_PRIVATE_KEY` (quick reference)

The workflow prefers **`DEPLOY_SSH_PRIVATE_KEY_B64`** and decodes it into `~/.ssh/deploy_key`. If that secret is empty, it falls back to raw **`DEPLOY_SSH_PRIVATE_KEY`**. The decoded/written key must be a **valid OpenSSH or PEM private key**. The matching public key must be in `authorized_keys` for `DEPLOY_USER`.

## 6) Auto-deploy operation

On merge to `main`, workflow runs `scripts/v2.8/deploy/auto_sync_and_deploy.sh` on server:

- creates pre-deploy backup
- initializes `DEPLOY_PATH` as a git checkout if it is not one yet
- fetch/reset to `origin/main`
- syncs `scripts/v2.8` into runtime target (default server `scripts/v2.0`)
- restarts services
- runs health checks
- rolls back on failure

## 7) Security scope

- only `scripts/v2.8/**` is in-scope for push
- `scripts/v2.8/web_portal/**` is excluded from push scope
- `.env`/secrets/DB/runtime files are blocked by ignore + CI guards
