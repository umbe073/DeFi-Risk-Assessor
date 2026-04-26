# Hodler Suite — Agent Guide

This file is read by the **Codex extension** and any autonomous AI agent operating on this repository.
The same rules are available in `.cursor/rules/` for the Cursor IDE.

---

## Project

**Name**: Hodler Suite
**Purpose**: Automated, explainable token risk assessments across ETH, BSC, and TRON.
**Repo root**: `/Users/amlfreak/Desktop/venv` (local) · `https://github.com/ddos-revenge/DeFi-Risk-Assessor` (remote)

---

## Tech Stack (do not deviate without explicit instruction)

- **Backend**: Python 3.11, Flask 3.1.1, Gunicorn, SQLite (raw `sqlite3`, no ORM)
- **Frontend**: Jinja2 templates, hand-written CSS, vanilla JS — no React, no Tailwind, no Node
- **Infra**: Vultr VPS, Nginx, systemd, Cloudflare, Let's Encrypt
- **CI/CD**: GitHub Actions (`deploy.yml`, `pr-check.yml`, `codeql.yml`)

---

## Coding Standards

### Python

- PEP 8, `black` (88), `isort`, type hints on all function signatures
- `logging.getLogger(__name__)` — never bare `except:`
- Google-style docstrings on non-trivial functions
- Tests: `pytest`, files named `test_*.py`, fixtures in `conftest.py`

### JavaScript

- Vanilla ES6 modules, no frameworks, StandardJS style (no semicolons, 2-space indent)

### Git

- Conventional Commits: `feat:`, `fix:`, `docs:`, `style:`, `refactor:`, `test:`, `chore:`
- Branch naming: `cursor/<ticket-id>-short-description` for agent branches
- PR description must include `Fixes #issue-number` and a change summary

---

## What agents MUST do

1. **Plan first** for any task touching >3 files or involving architectural changes
2. **Run `pytest` and `flake8`** before marking any task done
3. **Never commit** `.env`, `*.db`, `*.key`, `*.pem`, or `logs/`. `scripts/v2.8/data/` may be committed when the user explicitly asks for v2.8 data publication and after `.gitignore` filters keep DBs, pyc, logs, temp/corrupt cache files, key material, env files, and runtime caches out of Git. Root `/data/` remains ignored unless explicitly requested separately.
4. **Never suggest** React, Tailwind, ORMs, or Node.js unless explicitly asked
5. **Fix CI failures** without being asked when you see them in the PR
6. **Commit and push repo-facing changes** when the task is done: stage **only** paths this task touched (e.g. `.github/workflows/`, `scripts/v2.8/**`, deploy docs), commit with Conventional Commits, run `git push origin main`. Do **not** leave workflow or `v2.8` fixes uncommitted (that produces “Everything up-to-date” with no deploy). Never `git add -A` unrelated WIP (bulk `scripts/v2.0/`, ignored portal trees). If push cannot be run here, tell the user explicitly and paste the exact `git add` / `git commit` / `git push` block.

---

## Context7 MCP (Cursor IDE)

**Compatibility**: Context7 runs via `npx` on the developer machine; **Node 18+** is required (e.g. Node v24.x is fine). This does **not** change the product stack — the portal stays **Jinja2 + hand-written CSS + vanilla JS** with no Node in production.

**When to use Context7** (when the MCP is enabled in `~/.cursor/mcp.json`): Prefer calling Context7 for **current, version-accurate** documentation instead of guessing from training data, especially for:

- **Flask**, **Jinja2**, **Werkzeug**, **Gunicorn**, and common Python deps used in this repo (`requests`, `pydantic`, `cryptography`, etc.)
- **Browser / vanilla JS**: Fetch, Web Crypto, `AbortController`, modules, relevant **MDN-level** APIs
- **Any third-party library** where API surface or defaults may have changed since training

**How**: Use the MCP tools (e.g. resolve library ID, then query docs) **early** in tasks that involve non-trivial framework or API usage — that cuts rework, bad signatures, and deprecated patterns.

**When to skip**: Trivial edits, project-internal code with no external API, or behavior fully defined in this repository.

---

## Manual web portal deploy (production VPS)

When the user asks to deploy **web portal** changes to production, give the **compiled** command (no placeholders). Default SSH target for this project:

- **User@host**: `linuxuser@80.240.31.172`

From repo root:

```bash
cd /Users/amlfreak/Desktop/venv && bash scripts/v2.0/web_portal/deploy/deploy_web_portal_safe.sh linuxuser@80.240.31.172
```

The script uses defaults: remote tmp `/tmp/hodler-suite-web-portal/`, app dir `/opt/hodler-suite/web_portal/`, service `hodler-web-portal.service`. It does **not** rsync `.env`, `web_portal.env`, or `data/`.

---

## Bug Report Pipeline

1. Receive report from `hodler-suite.com/help-center` via Slack → `#github_pull_requests`
2. Create branch: `cursor/<ticket-id>-description`
3. Implement fix, run `pytest` + `flake8`
4. Open PR with `Fixes #N`, no Slack thread references, no attachment embeds
5. Wait for `✅` reaction in Slack or manual approval on GitHub to merge

---

## Known Pitfalls

| Pitfall | Rule |
| --- | --- |
| Slack truncation | Bug summaries ≤ 200 characters |
| SQLite concurrency | WAL mode + connection timeouts; no blocking writes in the web process |
| API rate limits | Cache with `diskcache`; respect IP2Location + web3 provider limits |
| Background tasks | Long work → `risk-worker` systemd service, never block Gunicorn |
| Env vars | All validated via `Settings` dataclass in `config.py` at startup |
| ClamAV | Scan all ticket attachments; never embed user file content |

---

## Self-Improvement

After any correction: update `tasks/lessons.md` with the pattern.
Tag `@codex` in PR comments to flag updates needed to this file.
