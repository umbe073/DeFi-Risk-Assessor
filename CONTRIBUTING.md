# Contributing to Hodler Suite

This repository is private, proprietary, and owned by **Hodler Suite UAB**.
Contribution expectations apply only to employees, contractors, service
providers, and approved partners who are authorized to access this repository
and are covered by the required confidentiality and intellectual-property
agreements with Hodler Suite UAB.

If you do not have written authorization from Hodler Suite UAB, do not access
or contribute to this repository.

See `LICENSE` for ownership and use restrictions.

## Confidentiality

- Treat all code, issues, pull requests, CI logs, attachments, and internal links as **confidential**.
- Do **not** paste customer data, credentials, webhook secrets, production URLs with tokens, or regulated personal data into issues or PR descriptions.
- Do **not** mirror this repository, publish snippets, or disclose architecture details outside approved Hodler Suite UAB systems.
- Follow `SECURITY.md` for vulnerability reporting.

## Project layout

- `scripts/v2.8/` is the GitHub source-of-truth for app/risk code.
- `scripts/v2.8/data/` may contain reviewed v2.8 placeholder or report data; runtime databases and caches stay ignored.
- The web portal tree, `scripts/v2.0/deploy`, and `scripts/v2.8/deploy` are **not** committed — keep them local or on private ops storage only.
- `.github/workflows/` contains CI, deploy, security scanning, and automation workflows.

## Development rules

- Use Python, Flask, Jinja2, vanilla JavaScript, and hand-written CSS.
- Do not introduce React, Tailwind, Node production services, or an ORM unless explicitly requested.
- Keep changes scoped to the feature or bug being fixed.
- Avoid unrelated formatting churn.
- Never commit secrets, `.env` files, private keys, SQLite databases, logs, or raw runtime caches.
- Treat support attachments and user-provided data as untrusted.

## Local workflow

From the repository root:

```bash
git status
```

For web portal work, use your **private** checkout of the portal (not in this repository), then run the project’s `pytest` and `flake8` there per internal runbooks.

For targeted changes, run the narrowest relevant tests first, then expand if the change touches shared behavior.

## Commit guidelines

Use Conventional Commits:

- `feat:` for new user-facing capability.
- `fix:` for bug fixes.
- `docs:` for documentation.
- `test:` for test-only changes.
- `ci:` for GitHub Actions.
- `chore:` for maintenance.

Stage only files relevant to the change. Avoid `git add -A` when the working tree contains unrelated WIP.

## Pull request checklist

Before opening a pull request:

- Confirm the change is scoped and does not include unrelated local WIP.
- Run relevant tests and lint checks.
- Confirm no secrets or runtime data are included.
- Update docs or deployment notes when behavior changes.
- Include screenshots for visible UI changes.
- Include rollback notes for deployment-sensitive changes.

## Deployment notes

App/risk changes under `scripts/v2.8/` are deployed by GitHub Actions using the **server-side** deploy driver maintained in private ops (not from this repository).

Website/web portal and infra playbooks are deployed manually from private checkouts or server-side copies per internal runbooks.
