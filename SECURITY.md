# Security Policy

This policy applies to the proprietary Hodler Suite SaaS platform and related
internal tooling owned by **Hodler Suite UAB**.

## Supported Versions

Hodler Suite is developed from the current `main` branch. Security fixes target:

| Version / Area | Supported |
| --- | --- |
| Current `main` branch | Yes |
| Production app runtime deployed from `scripts/v2.8` | Yes |
| Manual web portal deployment under `scripts/v2.0/web_portal` | Yes |
| Historical snapshots, local experiments, and archived scripts | No |

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities, secrets
exposure, authentication bypasses, payment issues, or data-handling problems.

Preferred reporting paths:

1. Use GitHub private vulnerability reporting or a GitHub Security Advisory when available.
2. If you are an internal operator, report through the private Hodler Suite UAB support/security Slack workflow.
3. If neither path is available, contact `compliance@hodler-suite.com` and clearly mark the report as `Security`.

Include as much detail as you safely can:

- Affected route, script, workflow, or deployment component.
- Reproduction steps and expected impact.
- Whether authentication, billing, Slack, email, API credentials, webhooks, uploads, or personal data are involved.
- Logs or screenshots with tokens, cookies, private keys, webhook URLs, and customer data removed.

## Response Expectations

We aim to acknowledge high-impact reports quickly and triage based on severity:

- Critical: active exploitation, auth bypass, secret exposure, payment manipulation, or remote code execution.
- High: privilege escalation, stored XSS, SSRF, data exposure, webhook forgery, or unsafe file handling.
- Medium/Low: hardening gaps, misconfiguration, information disclosure, or defense-in-depth improvements.

Security fixes should include focused tests where practical and should not expose exploit details publicly before mitigation.

## Security Scope

In scope:

- Flask routes and blueprints under `scripts/v2.0/web_portal/app/`.
- GitHub Actions, deployment scripts, systemd units, and SSH deploy flow.
- Webhook verification, Slack/email integrations, billing callbacks, and Turnstile/browser integrity flows.
- Credential handling, `.env` examples, API key validation, logging redaction, and SQLite data stores.
- File upload, attachment, ClamAV, and support-ticket paths.

Out of scope:

- Denial-of-service testing without prior approval.
- Social engineering or phishing.
- Attacks against third-party services themselves.
- Public disclosure of private customer, operator, or credential data.

## GitHub: reducing code scanning alerts (Copilot Autofix and related)

GitHub’s [Copilot Autofix for code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/copilot-autofix-for-code-scanning) suggests patches for many CodeQL alerts. It does **not** replace review: suggestions can be wrong, incomplete, or unsafe. Follow GitHub’s [responsible use](https://docs.github.com/en/code-security/responsible-use/responsible-use-autofix-code-scanning) guidance—treat every suggestion like a junior PR, run CI/tests, and confirm the alert clears before merging.

### Repository checklist (owners)

1. **Code scanning** is on (this repo uses `.github/workflows/codeql.yml` plus `.github/codeql/codeql-config.yml`).
2. **Copilot Autofix** for security results is allowed: **Settings → Code security and analysis → Code scanning → Copilot Autofix** (or **Settings → Advanced Security** on org-owned repos). If org/enterprise policy disabled it, re-enable there first.
3. **Dependabot security updates** and **Dependabot version updates** (`.github/dependabot.yml`) reduce future supply-chain alerts; review and merge those PRs like any other change.
4. **Dependency Review** (`.github/workflows/dependency-review.yml`) flags known-vulnerable dependency changes on PRs; optionally tighten `fail-on-severity` once the backlog is under control.
5. **OSV-Scanner** (`.github/workflows/osv-scanner.yml`) adds an additional vulnerability signal on `main` and PRs.

### Operational loop (recommended)

- Weekly (or after large merges): open **Security → Code scanning**, sort by severity, work down open alerts.
- For each alert with a **suggested fix**: open a branch or “Apply suggestion”, adjust if needed, open a PR, wait for **CodeQL** + **PR Checks** + human review, then merge.
- Re-run analysis from **Actions → CodeQL Advanced → Run workflow** after changing Code scanning settings so suggestions refresh.

There is **no supported “auto-merge all CodeQL fixes”** mode for this private
SaaS codebase: automation should stop at opening vetted PRs, not at bypassing
review.

## Operator Notes

- Never commit `.env`, private keys, SQLite databases, logs, or raw runtime caches.
- Rotate any credential suspected of being exposed.
- Keep deployment secrets in GitHub Actions secrets or server environment files, not in the repository.
- Prefer HMAC/signature verification for incoming webhooks.
