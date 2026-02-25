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
