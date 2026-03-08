> **Public security notice:** This documentation is intentionally redacted. Sensitive server paths, private keys, secret tokens, and origin network details are removed.

# EU Mode vs Global Mode

This page explains how the engine supports an **EU-centric compliance profile**
and a more permissive **Global profile**, controlled via `data/settings.json`.

---

## Configuration structure

EU-mode settings are loaded with safe defaults and then overridden by
`data/settings.json` if present:

```11546:11559:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _load_eu_mode_settings(self, force=False):
    \"\"\"Load EU-mode settings from data/settings.json with safe defaults.\"\"\"
    default_cfg = {
        'enabled': True,
        'enable_eu_unlicensed_stablecoin': True,
        'enable_eu_regulatory_issues': True,
        'enable_mica_non_compliant': True,
        'enable_mica_no_whitepaper': True,
        'dynamic_allowlist_enabled': True,
        'allowlist_registry_file': 'eu_regulated_stablecoins.json',
        'allowlist_extra_symbols': [],
    }
    settings_path = os.path.join(DATA_DIR, 'settings.json')
```

Expected JSON snippet:

```json
{
  "eu_mode": {
    "enabled": true,
    "enable_eu_unlicensed_stablecoin": true,
    "enable_eu_regulatory_issues": true,
    "enable_mica_non_compliant": true,
    "enable_mica_no_whitepaper": true,
    "dynamic_allowlist_enabled": true,
    "allowlist_registry_file": "eu_regulated_stablecoins.json",
    "allowlist_extra_symbols": ["EUROe", "EURS"]
  }
}
```

If `settings.json` is missing or fields are absent, defaults from `default_cfg`
are used instead.

---

## Enabling and querying EU-mode

Two helpers expose EU-mode state:

```11602:11620:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _is_eu_mode_enabled(self):
    cfg = self._load_eu_mode_settings()
    return self._coerce_bool_setting(cfg.get('enabled'), True)

def _is_eu_flag_enabled(self, flag_name):
    \"\"\"Check whether a specific EU flag is enabled by settings.\"\"\"
    if not self._is_eu_mode_enabled():
        return False
    key_map=<REDACTED>
        'eu_unlicensed_stablecoin': 'enable_eu_unlicensed_stablecoin',
        'eu_regulatory_issues': 'enable_eu_regulatory_issues',
        'mica_non_compliant': 'enable_mica_non_compliant',
        'mica_no_whitepaper': 'enable_mica_no_whitepaper',
    }
    ...
```

Logic:

- If `eu_mode.enabled` is `false`, all EU-specific flags evaluate to disabled.  
- If enabled, individual flags can still be toggled off.

---

## Dynamic allow-list of regulated stablecoins

EU-mode uses a registry of EU-regulated stablecoin symbols:

```11622:11637:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _resolve_eu_allowlist_registry_path(self):
    cfg = self._load_eu_mode_settings()
    filename = str(cfg.get('allowlist_registry_file', 'eu_regulated_stablecoins.json') or '').strip()
    ...
    return os.path.join(DATA_DIR, os.path.basename(filename))

def _load_eu_allowlisted_symbols(self):
    \"\"\"Load EU regulated stablecoin symbols from configurable data registry.\"\"\"
    cfg = self._load_eu_mode_settings()
    extra_symbols = set(self._normalize_symbol_collection(cfg.get('allowlist_extra_symbols', [])))
    dynamic_enabled = self._coerce_bool_setting(cfg.get('dynamic_allowlist_enabled'), True)
    ...
```

The runtime behavior:

- If `dynamic_allowlist_enabled` is `true`, the engine reads the registry file
  and caches its contents (with mtime checks).  
- `allowlist_extra_symbols` is always merged into the dynamic set, allowing ad‑hoc
  approvals beyond the main registry.

This allows operations teams to:

- Source stablecoin lists from official registers or internal databases.  
- Update EU-regulated symbols without code changes.

---

## Impact on scoring

EU-mode interacts with the scoring model primarily through:

- red flags `eu_unlicensed_stablecoin`, `eu_regulatory_issues`,  
  `mica_non_compliant` and `mica_no_whitepaper`.  
- allow-list checks for stablecoins.

When EU-mode is enabled:

- Non-allow-listed stablecoins may be flagged as `eu_unlicensed_stablecoin` and
  receive a **hard risk boost**.  
- Tokens with known EU regulatory issues or MiCA non-compliance can accrue
  further additive risk in the scoring pipeline.

When EU-mode is disabled:

- These EU-specific red flags are treated as inactive, and the engine behaves
  more like a global profile where jurisdiction-specific rules are not enforced.

---

## Using EU-mode in practice

Typical usage patterns:

- **EU-focused exchange** – keep EU-mode enabled and maintain the allow-list
  registry as part of listing governance.  
- **Global hedge fund** – run assessments in both EU-mode and Global-mode and
  compare the scores as part of due diligence.  
- **Non-EU venue** – disable EU-mode but keep other regulatory / sanctions
  checks active.

Configuration can be changed without altering the code, making it easy to adapt
the same engine to multiple compliance regimes.

