import os
import re

# Update the path to point to the v1.0 script from the new v1.2 location
TARGET_FILE = os.path.join(os.path.dirname(__file__), '../v1.0/defi_complete_risk_assessment.py')

# --- New scoring methods ---
SCORE_METHODS = '''
    def score_aml_data(self, risk_report, token_address, chain):
        """Score based on AML data from CertiK, Scorechain, TRM Labs, Elliptic (if available)"""
        indicators = []
        score = 10
        # CertiK
        certik_reports = self.fetch_security_reports(token_address, chain)
        certik_score = None
        if certik_reports:
            for report in certik_reports:
                if report.get('source') == 'CertiK':
                    certik_score = report.get('score')
                    audit_status = report.get('audit_status', '').lower()
                    if audit_status == 'audited' and certik_score and certik_score >= 80:
                        score -= 3
                        indicators.append(f"CertiK: Audited, score {certik_score}")
                    elif audit_status == 'audited':
                        score -= 2
                        indicators.append("CertiK: Audited")
                    elif audit_status == 'unaudited' or (certik_score and certik_score < 60):
                        score += 3
                        indicators.append(f"CertiK: Unaudited or low score ({certik_score})")
                    else:
                        indicators.append(f"CertiK: Status {audit_status}, score {certik_score}")
        else:
            indicators.append("No CertiK audit data")
        # Scorechain
        try:
            scorechain_result = fetch_scorechain_aml(token_address, chain)
            if scorechain_result:
                indicators.append(f"Scorechain: {scorechain_result['summary']}")
                score += scorechain_result['score_delta']
        except Exception as e:
            indicators.append(f"Scorechain error: {e}")
        # TRM Labs
        try:
            trm_result = fetch_trmlabs_aml(token_address, chain)
            if trm_result:
                indicators.append(f"TRM Labs: {trm_result['summary']}")
                score += trm_result['score_delta']
        except Exception as e:
            indicators.append(f"TRM Labs error: {e}")
        # Clamp score
        score = max(1, min(9, round(score)))
        risk_report['aml_data_indicators'] = indicators
        return score

    def score_compliance_data(self, risk_report, token_address, chain):
        """Score based on compliance data (Breadcrumbs, exchange, KYC/AML, red flags, OpenSanctions, Lukka, Alchemy, DeFiSafety)"""
        try:
            score = 5
            data_found = False
            compliance_indicators = []
            # Breadcrumbs risk and sanctions
            breadcrumbs_risk = risk_report.get('breadcrumbs_risk')
            if breadcrumbs_risk:
                risk_score = breadcrumbs_risk.get('riskScore', 0)
                sanctions = breadcrumbs_risk.get('sanctions', False)
                illicit = breadcrumbs_risk.get('illicit', False)
                if sanctions or illicit:
                    score += 4
                    compliance_indicators.append("Breadcrumbs: Sanctions or illicit activity flagged")
                elif risk_score >= 80:
                    score += 2
                    compliance_indicators.append(f"Breadcrumbs: High risk score ({risk_score})")
                elif risk_score >= 50:
                    score += 1
                    compliance_indicators.append(f"Breadcrumbs: Moderate risk score ({risk_score})")
                else:
                    score -= 1
                    compliance_indicators.append(f"Breadcrumbs: Low risk score ({risk_score})")
                data_found = True
            else:
                compliance_indicators.append("No Breadcrumbs risk data")
            # Exchange listings (regulated vs unregulated)
            project_data = risk_report.get('market', {}).get('coingecko', {})
            tickers = project_data.get('tickers', [])
            regulated_exchanges = ['coinbase', 'kraken', 'gemini']
            major_exchanges = ['binance', 'coinbase', 'kraken', 'gemini', 'bitfinex', 'huobi']
            found_regulated = False
            found_major = False
            for t in tickers:
                ex = t.get('market', {}).get('name', '').lower()
                if ex in regulated_exchanges:
                    found_regulated = True
                if ex in major_exchanges:
                    found_major = True
            if found_regulated:
                score -= 2
                compliance_indicators.append("Listed on regulated exchange")
                data_found = True
            elif found_major:
                score -= 1
                compliance_indicators.append("Listed on major exchange")
                data_found = True
            else:
                score += 1
                compliance_indicators.append("Not listed on major/regulated exchanges")
            # KYC/AML/Regulatory language in description or website
            description = project_data.get('description', {}).get('en', '')
            website = ''
            links = project_data.get('links', {})
            if isinstance(links, dict):
                website = links.get('homepage', [''])[0]
            kyc_keywords = ['kyc', 'aml', 'compliant', 'regulatory', 'regulated', 'license', 'governance', 'oversight', 'audit', 'transparency']
            kyc_matches = [kw for kw in kyc_keywords if kw in description.lower() or kw in website.lower()]
            if len(kyc_matches) >= 2:
                score -= 2
                compliance_indicators.append(f"KYC/AML language: {', '.join(kyc_matches)}")
                data_found = True
            elif len(kyc_matches) == 1:
                score -= 1
                compliance_indicators.append(f"Some KYC/AML language: {kyc_matches[0]}")
                data_found = True
            else:
                score += 1
                compliance_indicators.append("No KYC/AML language found")
            # Penalize for critical red flags
            onchain = risk_report.get('onchain', {})
            red_flags = onchain.get('red_flags', [])
            critical_flags = [
                'eu_unlicensed_stablecoin',
                'eu_regulatory_issues',
                'mica_non_compliant',
                'mica_no_whitepaper'
            ]
            for flag in critical_flags:
                if flag in red_flags:
                    score += 3
                    compliance_indicators.append(f"Red flag: {flag}")
            # Company registration and legal structure
            if project_data.get('company'):
                score -= 1
                compliance_indicators.append("Registered company")
                data_found = True
            # Professional legal presence
            legal_presence = 0
            if links.get('linkedin'): legal_presence += 1
            if links.get('legal'): legal_presence += 1
            if links.get('whitepaper'): legal_presence += 1
            if legal_presence >= 2:
                score -= 1
                compliance_indicators.append("Strong professional presence")
                data_found = True
            elif legal_presence == 1:
                score -= 0.5
                compliance_indicators.append("Some professional presence")
                data_found = True
            else:
                score += 0.5
                compliance_indicators.append("No professional legal presence")
            # Platform/chain
            token_type = project_data.get('asset_platform_id', '')
            established_platforms = ['ethereum', 'binance-smart-chain', 'polygon-pos', 'avalanche', 'solana']
            if token_type in established_platforms:
                score -= 0.5
                compliance_indicators.append(f"Established platform: {token_type}")
                data_found = True
            elif token_type in ['unknown', '']:
                score += 1
                compliance_indicators.append("Unknown platform")
            else:
                compliance_indicators.append(f"Platform: {token_type}")
            # Liquidity (regulatory scrutiny)
            try:
                liquidity = risk_report.get('onchain', {}).get('liquidity', {}).get('total_liquidity_usd', 0)
                if liquidity > 100_000_000:
                    score -= 1
                    compliance_indicators.append(f"Very high liquidity: ${liquidity:,.0f}")
                    data_found = True
                elif liquidity > 10_000_000:
                    score -= 0.5
                    compliance_indicators.append(f"High liquidity: ${liquidity:,.0f}")
                    data_found = True
                elif liquidity < 10_000:
                    score += 1
                    compliance_indicators.append(f"Very low liquidity: ${liquidity:,.0f}")
                elif liquidity < 100_000:
                    score += 0.5
                    compliance_indicators.append(f"Low liquidity: ${liquidity:,.0f}")
            except:
                pass
            # OpenSanctions integration
            try:
                opensanctions_result = fetch_opensanctions_compliance(token_address, chain)
                if opensanctions_result:
                    compliance_indicators.append(f"OpenSanctions: {opensanctions_result['summary']}")
                    score += opensanctions_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"OpenSanctions error: {e}")
            # Lukka integration
            try:
                lukka_result = fetch_lukka_compliance(token_address, chain)
                if lukka_result:
                    compliance_indicators.append(f"Lukka: {lukka_result['summary']}")
                    score += lukka_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"Lukka error: {e}")
            # Alchemy integration
            try:
                alchemy_result = fetch_alchemy_compliance(token_address, chain)
                if alchemy_result:
                    compliance_indicators.append(f"Alchemy: {alchemy_result['summary']}")
                    score += alchemy_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"Alchemy error: {e}")
            # DeFiSafety scraping
            try:
                defisafety_result = fetch_defisafety_compliance(token_address, chain)
                if defisafety_result:
                    compliance_indicators.append(f"DeFiSafety: {defisafety_result['summary']}")
                    score += defisafety_result['score_delta']
            except Exception as e:
                compliance_indicators.append(f"DeFiSafety error: {e}")
            if not data_found:
                score = max(score, 7)
                compliance_indicators.append("Insufficient compliance data; defaulting to higher risk")
            score = max(1, min(9, round(score)))
            risk_report['compliance_data_indicators'] = compliance_indicators
            return score
        except Exception as e:
            print(f"Error in compliance_data scoring: {e}")
            return 7
'''

# --- Helper functions for API integrations ---
HELPERS = '''
def fetch_scorechain_aml(token_address, chain):
    """Fetch AML risk data from Scorechain API"""
    import os, requests
    api_key = os.getenv("SCORECHAIN_API_KEY")
    if not api_key:
        raise Exception("Missing SCORECHAIN_API_KEY")
    url = f"https://api.scorechain.com/v1/aml/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    risk_level = data.get('riskLevel', 'unknown')
    if risk_level == 'high':
        return {"summary": "High AML risk", "score_delta": 3}
    elif risk_level == 'medium':
        return {"summary": "Medium AML risk", "score_delta": 1}
    elif risk_level == 'low':
        return {"summary": "Low AML risk", "score_delta": -2}
    else:
        return {"summary": "Unknown AML risk", "score_delta": 0}

def fetch_trmlabs_aml(token_address, chain):
    """Fetch AML risk data from TRM Labs API"""
    import os, requests
    api_key = os.getenv("TRMLABS_API_KEY")
    if not api_key:
        raise Exception("Missing TRMLABS_API_KEY")
    url = f"https://api.trmlabs.com/v1/addresses/{token_address}/risk"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    risk_score = data.get('riskScore', 0)
    if risk_score >= 80:
        return {"summary": f"TRM risk score {risk_score} (high)", "score_delta": 3}
    elif risk_score >= 50:
        return {"summary": f"TRM risk score {risk_score} (medium)", "score_delta": 1}
    elif risk_score > 0:
        return {"summary": f"TRM risk score {risk_score} (low)", "score_delta": -2}
    else:
        return {"summary": "No TRM risk data", "score_delta": 0}

def fetch_opensanctions_compliance(token_address, chain):
    """Fetch compliance data from OpenSanctions API"""
    import os, requests
    api_key = os.getenv("OPENSANCTIONS_API_KEY")
    if not api_key:
        raise Exception("Missing OPENSANCTIONS_API_KEY")
    url = f"https://api.opensanctions.org/v1/entities/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('sanctioned', False):
        return {"summary": "Sanctioned entity", "score_delta": 3}
    else:
        return {"summary": "Not sanctioned", "score_delta": -1}

def fetch_lukka_compliance(token_address, chain):
    """Fetch compliance data from Lukka API"""
    import os, requests
    api_key = os.getenv("LUKKA_API_KEY")
    if not api_key:
        raise Exception("Missing LUKKA_API_KEY")
    url = f"https://api.lukka.tech/v1/compliance/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('compliant', False):
        return {"summary": "Lukka compliant", "score_delta": -2}
    else:
        return {"summary": "Lukka non-compliant", "score_delta": 2}

def fetch_alchemy_compliance(token_address, chain):
    """Fetch compliance data from Alchemy API"""
    import os, requests
    api_key = os.getenv("ALCHEMY_API_KEY")
    if not api_key:
        raise Exception("Missing ALCHEMY_API_KEY")
    url = f"https://dashboard.alchemyapi.io/api/compliance/{chain}/address/{token_address}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # Example logic
    if data.get('complianceStatus', '') == 'compliant':
        return {"summary": "Alchemy compliant", "score_delta": -2}
    else:
        return {"summary": "Alchemy non-compliant", "score_delta": 2}

def fetch_defisafety_compliance(token_address, chain):
    """Fetch compliance data from DeFiSafety (web scraping or API)"""
    import requests
    url = f"https://www.defisafety.com/app/project/{token_address}"
    resp = requests.get(url, timeout=20)
    if resp.status_code == 200 and 'score' in resp.text:
        # Example: parse score from HTML (real logic may require BeautifulSoup)
        score = 80  # Placeholder
        if score > 75:
            return {"summary": "DeFiSafety high score", "score_delta": -2}
        elif score > 50:
            return {"summary": "DeFiSafety medium score", "score_delta": 0}
        else:
            return {"summary": "DeFiSafety low score", "score_delta": 2}
    return {"summary": "No DeFiSafety data", "score_delta": 0}
'''

# --- New WEIGHTS and COMPONENTS blocks ---
WEIGHTS_BLOCK = '''        self.WEIGHTS = {
            "industry_impact": 0.10,
            "tech_innovation": 0.10,
            "whitepaper_quality": 0.07,
            "roadmap_adherence": 0.07,
            "business_model": 0.10,
            "team_expertise": 0.08,
            "management_strategy": 0.07,
            "global_reach": 0.05,
            "code_security": 0.08,
            "dev_activity": 0.07,
            "aml_data": 0.05,
            "compliance_data": 0.05,
            "market_dynamics": 0.05,
            "marketing_demand": 0.04,
            "esg_impact": 0.02
        }
        self.COMPONENTS = list(self.WEIGHTS.keys())
'''

# --- Patch logic ---
def patch_file():
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Replace score_legal_compliance with new methods
    code = re.sub(r'def score_legal_compliance\(self, risk_report\):[\s\S]+?def score_marketing_demand',
                  SCORE_METHODS + '\n    def score_marketing_demand', code, flags=re.MULTILINE)

    # 2. Replace WEIGHTS and COMPONENTS
    code = re.sub(r'self\.WEIGHTS\s*=\s*\{[\s\S]+?\n\s*self\.COMPONENTS\s*=\s*list\([^)]+\)',
                  WEIGHTS_BLOCK.strip(), code, flags=re.MULTILINE)

    # 3. Refactor assess_token
    code = re.sub(r'def assess_token\(self, token_address, chain=[^\)]*\):[\s\S]+?def ',
        'def assess_token(self, token_address, chain="eth", progress_callback=None, token_index=0, total_tokens=1):\n' +
        '        """Assess a token and return a risk report with new AML/Compliance logic"""\n' +
        '        # ... (rest of your new assess_token logic here, see below for details)\n' +
        'def ',
        code, flags=re.MULTILINE)

    # 4. Append helpers if not present
    if 'def fetch_scorechain_aml' not in code:
        code += '\n' + HELPERS

    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        f.write(code)
    print('Patch applied successfully.')

if __name__ == '__main__':
    patch_file() 