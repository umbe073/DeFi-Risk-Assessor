> **Public security notice:** This documentation is intentionally redacted. Sensitive server paths, private keys, secret tokens, and origin network details are removed.

# Scoring Model & Categories

This page documents how the engine converts raw data into numeric risk scores,
including behavioral categories, weights, red flags and credibility.

---

## Component scores and weights

Internally, the engine maintains a dictionary of component scores, each
representing a behavioral category such as:

- contract / upgrade risk  
- liquidity and market structure  
- holder distribution and concentration  
- governance / transparency  
- regulatory posture  
- social reputation (`social_data`)

Each component is initially expressed as a **quality score** in the range
1–10 (higher is better). The final risk computation inverts these into a
0–10 risk axis and applies weights:

```12619:12631:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
print(f\"  📊 Calculating final risk score...\")
weighted_component_risk = 0.0
social_score_contribution = 0.0
weight_sum = sum(float(w) for w in self.WEIGHTS.values()) or 1.0

for component, weight in self.WEIGHTS.items():
    # Component scores are quality scores (1..10, higher=better).
    # Convert to risk axis (0..10, higher=worse).
    normalized_risk = ((10.0 - component_scores[component]) / 9.0) * 10.0
    normalized_risk = max(0.0, min(10.0, normalized_risk))
    weighted_risk = normalized_risk * float(weight)
    weighted_component_risk += weighted_risk
```

The final “base” risk score is then scaled into the configured range
`0..BASE_RISK_MAX`:

```12643:12645:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
base_risk_score = (weighted_component_risk / weight_sum) * (float(self.BASE_RISK_MAX) / 10.0)
social_score_contribution = (social_score_contribution / weight_sum) * (float(self.BASE_RISK_MAX) / 10.0)
```

The `social_score_contribution` is tracked separately for reporting.

---

## Red flags and additive boosts

Beyond structural component scores, the engine maintains a list of **red
flags**. Each flag has:

- a `check` key (e.g. `is_proxy_contract`, `eu_unlicensed_stablecoin`), and  
- a numeric `risk_boost`.

Default definition (excerpt):

```12647:12673:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
if not hasattr(self, 'RED_FLAGS') or not self.RED_FLAGS:
    self.RED_FLAGS = [
        {'check': 'is_proxy_contract', 'risk_boost': 20},
        {'check': 'has_honeypot_pattern', 'risk_boost': 30},
        ...
        {'check': 'eu_unlicensed_stablecoin', 'risk_boost': 50},
        {'check': 'eu_regulatory_issues', 'risk_boost': 40},
        {'check': 'mica_non_compliant', 'risk_boost': 35},
        {'check': 'mica_no_whitepaper', 'risk_boost': 0},
    ]
```

During scoring, the engine:

1. Computes `max_raw_red_flag_boost` as the sum of all positive boosts except
   the special `eu_unlicensed_stablecoin` override.  
2. Sums `raw_red_flag_boost` from all flags actually present for this token.  
3. Normalizes into `red_flag_score` in the range `0..RED_FLAG_MAX_ADDITIVE`.

```12677:12695:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
raw_red_flag_boost = 0.0
max_raw_red_flag_boost = 0.0
for rf in self.RED_FLAGS:
    flag_key=<REDACTED>
    boost = self.safe_float(rf.get('risk_boost', 0), 0.0)
    ...
    if flag_key in red_flags:
        raw_red_flag_boost += boost
...
if max_raw_red_flag_boost > 0:
    red_flag_score = (raw_red_flag_boost / max_raw_red_flag_boost) * float(self.RED_FLAG_MAX_ADDITIVE)
```

This additive score is then combined with the base score to produce the total
risk score.

---

## Market-structure penalties and native token discounts

The engine applies additional contextual modifiers:

- **Market-structure penalties** for low holders, low volume, small market cap
  with weak liquidity, etc.  
- **Native chain token discounts** when the token is the canonical gas / base
  asset for a chain.

Example:

```12696:12728:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
market_penalty_map = {
    'low_holders': ...,
    'very_low_holders': ...,
    'low_volume_24h': ...,
    'low_market_cap_weak_liquidity': ...,
    'low_market_cap_weak_liquidity_and_holders': ...,
}
...
if 'native_chain_token' in context_flags_set:
    native_chain_token_discount=<REDACTED>
        os.getenv('NATIVE_CHAIN_TOKEN_RISK_DISCOUNT', '3.0'),
        3.0
    )
```

These modifiers ensure that:

- Extremely thin or illiquid markets are treated as higher risk.  
- Legitimate chain-native tokens are not unfairly penalized by generic rules.

---

## Credibility / confidence

While the numeric score answers “how risky is this token?”, the **credibility**
dimension answers “how reliable is this score?”.

Credibility is influenced by:

- how many independent data sources contributed to each category,  
- whether values came from live APIs, cache, Token Data Viewer, or fallback data,  
- whether certain critical providers (sanctions / compliance) were reachable.

The engine tracks provenance for each metric, and the final JSON report includes
information about:

- which sources were used,  
- which were skipped or failed,  
- whether specific values are estimates.

Downstream dashboards can surface this as a confidence bar or label, prompting
analysts to manually review low-credibility assessments even if the numeric
score looks benign.

---

## Social score as a dedicated component

The social score (`social_data`) is treated as one of the weighted components,
but its contribution is also computed separately for transparency:

```12622:12635:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
weighted_component_risk = 0.0
social_score_contribution = 0.0
...
for component, weight in self.WEIGHTS.items():
    ...
    if component == 'social_data':
        social_score_contribution = weighted_risk
```

After scaling, `social_score_contribution` is stored alongside the total score,
so reports can show how much of the risk is driven purely by social / news
signals.

See **[Social Score System](social-score.md)** for a deeper explanation of how
social data is collected and analyzed.

