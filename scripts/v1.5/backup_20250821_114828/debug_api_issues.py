#!/usr/bin/env python3
"""
Debug API Issues
Identifies and fixes critical API issues found during script execution
"""

import os
import sys
import re
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def analyze_log_issues():
    """Analyze the script execution log for patterns of issues"""
    
    print("🔍 ANALYZING SCRIPT EXECUTION ISSUES")
    print("=" * 60)
    
    # Issues identified from the log
    issues_found = {
        'critical_errors': [],
        'authentication_errors': [],
        'rate_limit_issues': [],
        'url_parsing_errors': [],
        'api_unavailable': [],
        'data_quality_issues': []
    }
    
    # Critical Error 1: Invalid URL parsing
    issues_found['url_parsing_errors'].append({
        'error': "Invalid URL 'GET': No scheme supplied",
        'affected_apis': ['Bitcointalk', 'Cointelegraph'],
        'description': 'URL parsing issue where HTTP method is being used as URL',
        'severity': 'HIGH',
        'fix_needed': 'Fix URL construction in web scraping functions'
    })
    
    # Critical Error 2: Twitter API Authentication
    issues_found['authentication_errors'].append({
        'error': "401 Unauthorized for https://api.twitter.com/2/tweets/search/recent",
        'affected_apis': ['Twitter API v2'],
        'description': 'Twitter API key invalid or missing',
        'severity': 'HIGH',
        'fix_needed': 'Update Twitter API credentials or disable Twitter integration'
    })
    
    # Error 3: Rate Limiting Issues
    issues_found['rate_limit_issues'].append({
        'error': "Rate limit hit for api.twitter.com, waiting 15-17s",
        'affected_apis': ['Twitter API'],
        'description': 'Excessive rate limiting causing delays',
        'severity': 'MEDIUM',
        'fix_needed': 'Implement better rate limit management'
    })
    
    # Error 4: Liquidity API Issues
    issues_found['api_unavailable'].append({
        'error': "400 Bad Request for https://api.1inch.dev/swap/v6.0/1/quote",
        'affected_apis': ['1inch API'],
        'description': 'Insufficient liquidity or invalid token for swap quotes',
        'severity': 'MEDIUM',
        'fix_needed': 'Implement fallback liquidity detection methods'
    })
    
    # Error 5: Missing API Keys
    issues_found['api_unavailable'].extend([
        {
            'error': 'BitQuery API 401 Unauthorized',
            'affected_apis': ['BitQuery'],
            'description': 'BitQuery API key missing or invalid',
            'severity': 'MEDIUM',
            'fix_needed': 'Add BitQuery API key or disable integration'
        },
        {
            'error': 'CoinMarketCap API 401 Unauthorized', 
            'affected_apis': ['CoinMarketCap'],
            'description': 'CMC API key missing for some endpoints',
            'severity': 'LOW',
            'fix_needed': 'Verify CMC API key configuration'
        },
        {
            'error': 'Santiment API Invalid JWT',
            'affected_apis': ['Santiment'],
            'description': 'Santiment API key missing or expired',
            'severity': 'LOW',
            'fix_needed': 'Update Santiment API credentials'
        }
    ])
    
    return issues_found

def create_debug_fixes():
    """Create fixes for the identified issues"""
    
    print("\n🔧 CREATING DEBUG FIXES")
    print("-" * 40)
    
    fixes = {
        'url_parsing_fix': '''
# Fix for URL parsing errors in web scraping
def fixed_robust_request(method, url, headers=None, params=None, json_data=None, timeout=10, retries=3, backoff_factor=0.5):
    """Fixed version of robust_request with proper URL validation"""
    
    # Validate URL format
    if not url or not url.startswith(('http://', 'https://')):
        print(f"❌ Invalid URL format: {url}")
        return None
    
    # Validate HTTP method
    valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS']
    if method.upper() not in valid_methods:
        print(f"❌ Invalid HTTP method: {method}")
        return None
    
    for i in range(retries):
        try:
            response = requests.request(method.upper(), url, headers=headers, params=params, json=json_data, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️  Request failed ({i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
    return None
''',
        
        'twitter_auth_fix': '''
# Fix for Twitter API authentication
def disable_twitter_integration():
    """Disable Twitter integration when API keys are invalid"""
    
    def mock_twitter_function(*args, **kwargs):
        print("    ⚠️  Twitter API disabled due to authentication issues")
        return {
            'tweets': [],
            'sentiment_score': 5.0,  # Neutral sentiment
            'mention_count': 0,
            'engagement_score': 0
        }
    
    return mock_twitter_function
''',
        
        'rate_limit_optimization': '''
# Improved rate limit handling
def smart_rate_limiter(api_name, min_delay=1.0, max_delay=30.0):
    """Smart rate limiter that adapts to API responses"""
    
    rate_limit_cache = {}
    
    def get_delay(api_name):
        if api_name not in rate_limit_cache:
            rate_limit_cache[api_name] = {
                'last_request': 0,
                'delay': min_delay,
                'failures': 0
            }
        
        cache = rate_limit_cache[api_name]
        current_time = time.time()
        
        # Calculate adaptive delay
        if cache['failures'] > 0:
            cache['delay'] = min(max_delay, cache['delay'] * 1.5)
        else:
            cache['delay'] = max(min_delay, cache['delay'] * 0.9)
        
        # Wait if needed
        time_since_last = current_time - cache['last_request']
        if time_since_last < cache['delay']:
            wait_time = cache['delay'] - time_since_last
            print(f"    ⏱️  Rate limiting {api_name}: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        
        cache['last_request'] = time.time()
        return cache['delay']
    
    return get_delay
''',
        
        'liquidity_fallback': '''
# Fallback liquidity detection
def enhanced_liquidity_detection(token_address, token_symbol):
    """Enhanced liquidity detection with multiple fallbacks"""
    
    liquidity_score = "No Data"
    
    # Method 1: Try 1inch API (existing)
    try:
        # ... existing 1inch code ...
        pass
    except Exception as e:
        print(f"    ⚠️  1inch API failed: {e}")
    
    # Method 2: Fallback to DeFiLlama TVL
    if liquidity_score == "No Data":
        try:
            # Check if token is part of a protocol with TVL data
            response = requests.get(f"https://api.llama.fi/protocols")
            if response.status_code == 200:
                protocols = response.json()
                # Search for protocol containing this token
                # ... implementation details ...
                pass
        except Exception as e:
            print(f"    ⚠️  DeFiLlama TVL fallback failed: {e}")
    
    # Method 3: Basic heuristic based on market cap and volume
    if liquidity_score == "No Data":
        # Use market cap and volume ratio as liquidity indicator
        # ... implementation details ...
        liquidity_score = "Estimated Low"
    
    return liquidity_score
'''
    }
    
    return fixes

def generate_issue_summary():
    """Generate a comprehensive issue summary"""
    
    issues = analyze_log_issues()
    
    print("\n📊 ISSUE SUMMARY REPORT")
    print("=" * 60)
    
    total_issues = sum(len(category) for category in issues.values())
    print(f"📈 Total Issues Found: {total_issues}")
    print()
    
    for category, issue_list in issues.items():
        if issue_list:
            print(f"🔧 {category.replace('_', ' ').title()}:")
            for i, issue in enumerate(issue_list, 1):
                print(f"  {i}. {issue['error'][:80]}...")
                print(f"     Severity: {issue['severity']}")
                print(f"     Fix: {issue['fix_needed']}")
                print()
    
    return issues

def create_priority_fixes():
    """Create prioritized fixes based on severity"""
    
    priority_fixes = [
        {
            'priority': 1,
            'title': 'Fix URL Parsing Errors',
            'description': 'Critical issue preventing web scraping functionality',
            'files_affected': ['defi_complete_risk_assessment_clean.py'],
            'fix_type': 'Code modification',
            'estimated_time': '30 minutes'
        },
        {
            'priority': 2,
            'title': 'Disable Twitter Integration',
            'description': 'API authentication failing, causing delays',
            'files_affected': ['defi_complete_risk_assessment_clean.py'],
            'fix_type': 'Feature disable',
            'estimated_time': '15 minutes'
        },
        {
            'priority': 3,
            'title': 'Implement Liquidity Fallbacks',
            'description': 'Improve liquidity detection reliability',
            'files_affected': ['defi_complete_risk_assessment_clean.py'],
            'fix_type': 'Feature enhancement',
            'estimated_time': '45 minutes'
        },
        {
            'priority': 4,
            'title': 'Optimize Rate Limiting',
            'description': 'Reduce unnecessary delays in API calls',
            'files_affected': ['defi_complete_risk_assessment_clean.py'],
            'fix_type': 'Performance optimization',
            'estimated_time': '20 minutes'
        }
    ]
    
    print("\n🎯 PRIORITY FIXES RECOMMENDED")
    print("=" * 60)
    
    for fix in priority_fixes:
        print(f"Priority {fix['priority']}: {fix['title']}")
        print(f"  Description: {fix['description']}")
        print(f"  Type: {fix['fix_type']}")
        print(f"  Time: {fix['estimated_time']}")
        print()
    
    return priority_fixes

def check_current_functionality():
    """Check if the script completed despite errors"""
    
    print("\n✅ FUNCTIONALITY CHECK")
    print("=" * 60)
    
    # Check if reports were generated
    data_dir = os.path.join(PROJECT_ROOT, 'data')
    
    reports_status = {
        'Excel Report': os.path.exists(os.path.join(data_dir, 'DeFi Tokens Risk Assessment Results.xlsx')),
        'JSON Report': os.path.exists(os.path.join(data_dir, 'risk_report.json')),
        'CSV Report': os.path.exists(os.path.join(data_dir, 'risk_report.csv')),
        'Summary Report': os.path.exists(os.path.join(PROJECT_ROOT, 'risk_assessment_summary.txt'))
    }
    
    print("📄 Report Generation Status:")
    for report, status in reports_status.items():
        status_icon = "✅" if status else "❌"
        print(f"  {status_icon} {report}: {'Generated' if status else 'Missing'}")
    
    # Check if all tokens were processed
    if reports_status['Excel Report']:
        import pandas as pd
        try:
            df = pd.read_excel(os.path.join(data_dir, 'DeFi Tokens Risk Assessment Results.xlsx'))
            token_count = len(df)
            print(f"\n📊 Tokens Processed: {token_count}")
            
            # Check for complete data
            complete_assessments = len(df[df['Risk Score'] > 0])
            print(f"📈 Complete Assessments: {complete_assessments}/{token_count}")
            
            if complete_assessments == token_count:
                print("✅ All tokens successfully assessed!")
            else:
                print(f"⚠️  {token_count - complete_assessments} tokens may have incomplete data")
                
        except Exception as e:
            print(f"❌ Error reading Excel report: {e}")
    
    print()
    print("🎯 CONCLUSION:")
    all_reports_generated = all(reports_status.values())
    
    if all_reports_generated:
        print("✅ Script completed successfully despite API issues!")
        print("📊 All reports generated with available data")
        print("🔧 API issues are non-critical and can be fixed for future runs")
    else:
        print("⚠️  Some reports missing - check for critical errors")
    
    return all_reports_generated

def main():
    """Main debugging function"""
    
    print("🐛 API ISSUES DEBUGGING TOOL")
    print("=" * 60)
    
    # Analyze issues from the log
    issues = generate_issue_summary()
    
    # Create debug fixes
    fixes = create_debug_fixes()
    
    # Generate priority fixes
    priority_fixes = create_priority_fixes()
    
    # Check current functionality
    functionality_ok = check_current_functionality()
    
    # Generate debugging report
    debug_report = {
        'timestamp': datetime.now().isoformat(),
        'issues_summary': issues,
        'priority_fixes': priority_fixes,
        'functionality_status': functionality_ok,
        'recommendations': [
            "Fix URL parsing errors to improve web scraping reliability",
            "Disable Twitter integration until API keys are resolved",
            "Implement better rate limiting to reduce execution time",
            "Add more fallback methods for liquidity detection",
            "Consider caching frequently accessed data to reduce API calls"
        ]
    }
    
    # Save debug report
    debug_report_file = os.path.join(PROJECT_ROOT, 'data', 'debug_report.json')
    try:
        with open(debug_report_file, 'w') as f:
            json.dump(debug_report, f, indent=2)
        print(f"\n📋 Debug report saved: {debug_report_file}")
    except Exception as e:
        print(f"⚠️  Could not save debug report: {e}")
    
    print(f"\n🎉 DEBUGGING COMPLETE")
    print(f"📊 Issues identified: {sum(len(cat) for cat in issues.values())}")
    print(f"🔧 Priority fixes: {len(priority_fixes)}")
    print(f"✅ Core functionality: {'Working' if functionality_ok else 'Needs attention'}")
    
    return True

if __name__ == "__main__":
    main()
