# Security Policy

## Supported Versions

Hodler Suite is developed from the current `main` branch. Security fixes target:

| Version / Area | Supported |
| --- | --- |
| Current `main` branch | Yes |
| Production app runtime deployed from `scripts/v2.8` | Yes |
| Manual web portal deployment under `scripts/v2.0/web_portal` | Yes |
| Historical snapshots, local experiments, and archived scripts | No |

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities, secret exposure, authentication bypasses, payment issues, or data handling problems.

Preferred reporting paths:

1. Use GitHub private vulnerability reporting or a GitHub Security Advisory when available.
2. If you are an internal operator, report through the private support/security Slack workflow.
3. If neither path is available, use the Hodler Suite support channel and clearly mark the report as `Security`.

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

## Operator Notes

- Never commit `.env`, private keys, SQLite databases, logs, or raw runtime caches.
- Rotate any credential suspected of being exposed.
- Keep deployment secrets in GitHub Actions secrets or server environment files, not in the repository.
- Prefer HMAC/signature verification for incoming webhooks.
