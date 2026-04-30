# Contributing to Hodler Suite

Thanks for helping improve Hodler Suite. This repository contains DeFi risk-assessment code, deployment automation, and a manually deployed Flask web portal. Please keep changes focused, tested, and safe for production.

## Project Layout

- `scripts/v2.8/` is the GitHub source-of-truth for app/risk code and GitOps deploy assets.
- `scripts/v2.8/data/` may contain reviewed v2.8 placeholder or report data; runtime databases and caches stay ignored.
- `scripts/v2.0/web_portal/` is the manually deployed website/web portal path.
- `.github/workflows/` contains CI, deploy, security scanning, and automation workflows.

## Development Rules

- Use Python, Flask, Jinja2, vanilla JavaScript, and hand-written CSS.
- Do not introduce React, Tailwind, Node production services, or an ORM unless explicitly requested.
- Keep changes scoped to the feature or bug being fixed.
- Avoid unrelated formatting churn.
- Never commit secrets, `.env` files, private keys, SQLite databases, logs, or raw runtime caches.
- Treat support attachments and user-provided data as untrusted.

## Local Workflow

From the repository root:

```bash
cd /Users/amlfreak/Desktop/venv
git status
```

For web portal work:

```bash
cd /Users/amlfreak/Desktop/venv/scripts/v2.0/web_portal
python3 -m pytest tests/
python3 -m flake8 app tests tools --max-line-length=120 --extend-ignore=E501,W503,E203
```

For targeted changes, run the narrowest relevant tests first, then expand if the change touches shared behavior.

## Commit Guidelines

Use Conventional Commits:

- `feat:` for new user-facing capability.
- `fix:` for bug fixes.
- `docs:` for documentation.
- `test:` for test-only changes.
- `ci:` for GitHub Actions.
- `chore:` for maintenance.

Stage only files relevant to the change. Avoid `git add -A` when the working tree contains unrelated WIP.

## Pull Request Checklist

Before opening a pull request:

- Confirm the change is scoped and does not include unrelated local WIP.
- Run relevant tests and lint checks.
- Confirm no secrets or runtime data are included.
- Update docs or deployment notes when behavior changes.
- Include screenshots for visible UI changes.
- Include rollback notes for deployment-sensitive changes.

## Deployment Notes

App/risk changes under `scripts/v2.8/` are deployed by GitHub Actions to the configured server runtime target.

Website/web portal changes under `scripts/v2.0/web_portal/` are deployed manually:

```bash
cd /Users/amlfreak/Desktop/venv
WEB_PORTAL_HEALTH_URL="http://127.0.0.1:5050/healthz" \
  bash scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh linuxuser@80.240.31.172
```

After deployment, verify the server health endpoint and relevant user-facing page.

## Security and Privacy

See `SECURITY.md` for vulnerability reporting.

Do not post private report details, customer data, credentials, webhook URLs, signed URLs, cookies, or tokens in public issues or pull requests.
