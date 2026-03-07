# DeFi-Risk-Assessor
The DeFi Complete Risk Assessment Suite is a Python-based engine for automated, explainable token risk assessments. It is designed for AML analysts, hedge funds, listing managers, exchanges, and institutional risk teams who need a consistent way to evaluate DeFi tokens across multiple chains and data providers.

What this engine does?

- Aggregates many external services (on‑chain explorers, RPCs, market data, blockchain analytics, sanctions/compliance and social/news sources).
- Normalizes them into behavioral categories (market structure, smart‑contract safety, governance/transparency, regulatory posture, social reputation).
- Computes a numeric risk score plus component scores and red‑flag boosts, suitable for onboarding decisions, watchlists and surveillance.
- Provides EU‑specific and global risk profiles through a configurable EU‑mode.
- Produces machine‑readable outputs (CSV, JSON, XLSX) for dashboards and downstream analytics.
- For a narrative overview of the system and its value proposition, see the “DeFi Risk Assessment Suite – Pre‑Release Whitepaper” PDF in the repository root.

Target audience:

AML / Compliance analysts who need to interpret scores and understand why a token is flagged.
Quant and DeFi researchers who want to audit or extend scoring logic.
Exchange listing / risk teams who need repeatable onboarding criteria.
Engineers integrating the suite into dashboards, monitoring pipelines or case‑management tools.

## GitHub auto-PR workflow setup

The `Auto Open PR From Cursor Branches` workflow can create pull requests from `cursor/**` branches.
If your repository blocks PR creation by `GITHUB_TOKEN`, configure one of the following:

- Preferred workaround: add repository secret `CURSOR_PR_AUTOMATION_TOKEN` with a PAT that can open PRs in this repo.
- Alternative: in repository settings, enable **Allow GitHub Actions to create and approve pull requests**.

## Manual PR approval from Slack reaction

The `Approve PR From Slack Reaction` workflow approves an open pull request when it receives a Slack reaction payload containing `:white_check_mark:` (also accepts `✅`, `:heavy_check_mark:`, and `:check_mark:` aliases).

- Accepted trigger events:
  - `repository_dispatch` (event type can be chosen by your Slack bridge)
  - `workflow_dispatch` for manual testing
- Required payload fields:
  - `pr_number` (or `pull_request.number`)
  - `reaction` (or `emoji` / `reaction_name`)
- Optional fields:
  - `slack_user` and `slack_channel` for audit text in the approval review

Default channel filter is `github_pull_requests`. If your Slack integration sends a different channel name or ID, update `ALLOWED_SLACK_CHANNELS` in `.github/workflows/approve-pr-from-slack-reaction.yml`.
