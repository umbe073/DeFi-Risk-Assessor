# Hodler Suite

Hodler Suite is proprietary SaaS software owned by **Hodler Suite UAB**.

This repository contains application code for the risk engine and script API,
CI/CD workflows, and documentation used to build and operate Hodler Suite.
Operational assets (Flask web portal tree, VPS bootstrap/playbooks, and
server-side deploy scripts under `scripts/v2.0/web_portal`, `scripts/v2.0/deploy`,
and `scripts/v2.8/deploy`) are **not** published here — maintain those locally
or on approved private storage. It is not an open-source
project and is not licensed for public redistribution, reuse, resale, or
self-hosting.

## Access And Use

Access is limited to authorized Hodler Suite UAB employees, contractors,
service providers, and approved integration partners. Do not share, fork,
mirror, publish, or copy repository contents outside approved company systems.

See `LICENSE` for proprietary use restrictions.

## Product Summary

Hodler Suite provides automated and explainable token-risk assessment workflows
for digital-asset risk, AML, listing review, and monitoring teams.

The platform:

- Aggregates on-chain, market, security, compliance, and social/news signals.
- Normalizes provider data into risk categories and operational summaries.
- Computes token-level risk scores, confidence signals, and red flags.
- Supports EU-specific and global risk profiles.
- Produces machine-readable reports and SaaS dashboard outputs.
- Provides operator tooling for API health, service status, support workflows,
  billing reconciliation, and deployment observability.

## Repository Layout

- `scripts/v2.8/` is the GitHub source-of-truth for app/risk code.
- The Flask web portal, `scripts/v2.0/deploy`, and `scripts/v2.8/deploy` are
  excluded from Git scope (manual / private ops).
- `.github/workflows/` contains CI, deploy, CodeQL, Slack, and automation
  workflows.
- `docs/` contains internal and public-documentation source material where
  applicable.

## Contribution Model

This is a private-company repository. Contributions are accepted only from
authorized contributors who are covered by the required confidentiality,
employment, contractor, vendor, and intellectual-property agreements with
Hodler Suite UAB.

See `CONTRIBUTING.md` for engineering workflow expectations.

## Security

Do not open public issues for suspected vulnerabilities, secrets exposure,
authentication bypasses, payment issues, or data-handling risks.

See `SECURITY.md` for the private reporting and triage process.
