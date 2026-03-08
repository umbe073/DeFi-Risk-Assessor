> **Public security notice:** This documentation is intentionally redacted. Sensitive server paths, private keys, secret tokens, and origin network details are removed.

# Social Score System

This page describes how the engine collects and analyzes social and news data,
and how it turns that into the `social_data` component and separate social
effectiveness reports.

---

## Sources and data model

The engine draws from a variety of community and media sources, including:

- Twitter / X  
- Telegram  
- Discord  
- Reddit  
- CoinDesk  
- The Block  
- Decrypt  
- Bitcointalk  
- Cointelegraph

For each token, these payloads are aggregated into a `social_data` structure
attached to the final report entry.

---

## Social_data in the main report

When generating the consolidated risk report JSON, each token’s entry may
contain:

- `social_data`: direct social payload attached to the token.  
- `enhanced.social_data`: additional or alternative social payload.  
- Individual source keys under `enhanced` (e.g. `coindesk`, `theblock`).

The scoring engine treats `social_data` as a first-class behavioral component
(`social_data`) with its own weight, and independently tracks how much the
final risk score is influenced by social signals (see
**[Scoring Model & Categories](scoring-model.md)**).

---

## Social score analysis report

The function `generate_social_score_report()` walks the latest risk report JSON
and creates a textual analysis file under `SOCIAL_REPORT_DIR`:

```21225:21257:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def generate_social_score_report():
    \"\"\"Generate a comprehensive social score analysis report from the JSON report (which has full social data).\"\"\"
    ...
    social_analysis = {
        'total_tokens': len(report_entries),
        'analyzable_tokens': 0,
        'skipped_tokens': 0,
        'source_report': json_file,
        'social_sources': {
            'twitter': {'found': 0, 'not_found': 0, 'words': {}},
            'telegram': {'found': 0, 'not_found': 0, 'words': {}},
            ...
        },
        'word_frequency': {},
        'replacement_words': {},
        'most_effective_queries': [],
        'least_effective_queries': []
    }
```

It then:

1. Locates the newest `risk_report_*.json` (or falls back to `risk_report_latest.json`).  
2. Iterates all token entries, normalizing nested `social_data` structures.  
3. For each source (twitter, telegram, etc.), determines whether meaningful
   data exists and collects words via `_extract_words`.  
4. Updates per-source and global `word_frequency` maps.

---

## Determining meaningful social payloads

The helper `_has_real_data(entry)` filters out empty or error-only payloads:

```21299:21336:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _has_real_data(entry):
    \"\"\"Check if a social source entry has meaningful data (not just empty dicts/errors).\"\"\"
    if not entry:
        return False
    if isinstance(entry, dict):
        if entry.get('error') or entry.get('skipped'):
            return False
        if entry.get('mention_count', 0) > 0:
            return True
        if entry.get('article_count', 0) > 0:
            return True
        ...
        # Any non-trivial nested content
        for v in entry.values():
            if isinstance(v, (list, dict)) and v:
                return True
        return False
```

This ensures that:

- Neutral or empty sentiment markers are not treated as strong signals.  
- Only payloads with actual mentions, articles, or structured data contribute
  to the analysis.

---

## Keyword extraction and dictionary tuning

`_extract_words` standardizes tokens extracted from arbitrary nested structures:

```21274:21285:<PROJECT_ROOT>/scripts/v2.0/defi_complete_risk_assessment_clean.py
def _extract_words(value):
    \"\"\"Recursively pull meaningful words from nested social data structures.\"\"\"
    words = []
    if isinstance(value, str):
        words = re.findall(r\"[a-zA-Z][a-zA-Z0-9_/-]{2,24}\", value.lower())
    elif isinstance(value, dict):
        for v in value.values():
            words.extend(_extract_words(v))
    elif isinstance(value, list):
        for item in value:
            words.extend(_extract_words(item))
    return words
```

These words are aggregated at two levels:

- per-source `social_analysis['social_sources'][source]['words']`  
- global `social_analysis['word_frequency']`

The resulting report file highlights:

- overall token coverage,  
- per-source hit/miss ratios,  
- the most frequent words across sources.

This allows operators to:

- identify queries that rarely produce useful data,  
- experiment with alternative keyword sets,  
- understand which news and social channels are informative for a given token
  universe.

---

## Relationship to the risk score

The social analysis report itself does **not** directly modify the risk scores.
Instead, it informs how operators maintain and tune:

- keyword dictionaries used for crawling,  
- which social / news APIs are enabled,  
- how heavily the `social_data` component should be weighted.
- keyword dictionaries used for crawling,  
- which social / news APIs are enabled,  
- how heavily the `social_data` component should be weighted.
+ keyword dictionaries used for crawling,  
+ which social / news APIs are enabled,  
+ how heavily the `social_data` component should be weighted.

In other words, the report is a tool for improving the **quality** of social
signals feeding into the risk engine over time.

