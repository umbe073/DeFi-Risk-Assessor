# DeFi Complete Risk Assessment Suite

> **Status**: Pre-release – APIs, scoring weights and configuration surfaces may change.

The **DeFi Complete Risk Assessment Suite** is a Python-based engine for automated,
explainable token risk assessments. It is designed for **AML analysts, hedge funds,
listing managers, exchanges and institutional risk teams** who need a consistent way
to evaluate DeFi tokens across multiple chains and data providers.

This documentation corresponds to the `scripts/v2.0/defi_complete_risk_assessment_clean.py`
implementation and its companion tools in `scripts/v2.0/`.

---

## What this engine does

- **Aggregates many external services** (on‑chain explorers, RPCs, market data,
  blockchain analytics, sanctions/compliance and social/news sources).
- **Normalizes them into behavioral categories** (market structure, smart‑contract
  safety, governance/transparency, regulatory posture, social reputation).
- **Computes a numeric risk score** plus component scores and red‑flag boosts,
  suitable for onboarding decisions, watchlists and surveillance.
- **Provides EU‑specific and global risk profiles** through a configurable EU‑mode.
- **Produces machine‑readable outputs** (CSV, JSON, XLSX) for dashboards and
  downstream analytics.

For a narrative overview of the system and its value proposition, see the
_“DeFi Risk Assessment Suite – Pre‑Release Whitepaper”_ PDF in the repository root.

---

## Documentation map

This site mirrors the internal structure of the engine:

- **Architecture**
  - **[Core Engine & Workflow](architecture.md)** – main entrypoints, batching,
    concurrency, and how a token flows through the pipeline.
  - **[Data Fetching & Caching](data-fetching-and-caching.md)** – HTTP layer,
    request policies, disk caches, fallbacks and rate‑limit handling.
- **Risk Scoring**
  - **[Scoring Model & Categories](scoring-model.md)** – component scores,
    weights, red‑flag framework, credibility signal.
  - **[EU Mode vs Global Mode](eu-mode-and-global-mode.md)** – MiCA/EU profile
    and global profile, JSON configuration and allow‑listed stablecoins.
  - **[Social Score System](social-score.md)** – social_data model, sources,
    keyword oracle and social score report.
- **Market Data**
  - **[Token Data Viewer](token-data-viewer.md)** – snapshot CSV, loading logic
    and how it guides when to run assessments.
- **Operations**
  - **[Running the Assessment](running-and-configuration.md)** – CLI usage,
    environment variables, settings files and batch workflows.
  - **[Outputs & Dashboards](dashboard-and-outputs.md)** – JSON/CSV/XLSX outputs,
    latest‑report symlinks and webhook integration for dashboards.
- **Security**
  - **[Secure Credentials System](secure-credentials.md)** – encrypted
    credentials store, GUI credential manager and key‑management practices.

Each page aims to describe:

1. **High‑level purpose** – why the feature exists.
2. **Logic‑level behavior** – how the data flows and which decisions are made.
3. **Code‑level structure** – important classes, functions and configuration
   files that implement the behavior.

---

## Target audience

These docs are written for:

- **AML / Compliance analysts** who need to interpret scores and understand why a
  token is flagged.
- **Quant and DeFi researchers** who want to audit or extend scoring logic.
- **Exchange listing / risk teams** who need repeatable onboarding criteria.
- **Engineers** integrating the suite into dashboards, monitoring pipelines or
  case‑management tools.

If you are just getting started, begin with:

1. **[Core Engine & Workflow](architecture.md)** – to understand the big picture.
2. **[Scoring Model & Categories](scoring-model.md)** – to understand how scores
   are computed.
3. **[Running the Assessment](running-and-configuration.md)** – to execute end‑to‑end runs.

---

## Website build tooling

The documentation site now uses **Zensical** as the preferred generator.

Build and serve commands:

```bash
./scripts/build_website_docs.sh
./scripts/serve_website_docs.sh
```

Equivalent direct commands:

```bash
./bin/zensical build -f mkdocs.yml
./bin/zensical serve -f mkdocs.yml -a 127.0.0.1:8000
```
