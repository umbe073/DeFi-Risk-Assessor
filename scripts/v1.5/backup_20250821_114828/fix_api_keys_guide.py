#!/usr/bin/env python3
"""
API Key Fix Guide
Comprehensive guide to fix all API authentication issues
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/amlfreak/Desktop/venv/.env')

def print_fix_guide():
    """Print comprehensive fix guide for all API issues"""
    print("🔧 API Key Fix Guide")
    print("=" * 50)
    
    print("\n📋 Current Status Summary:")
    print("-" * 30)
    
    # Check current API keys
    api_status = {
        'BitQuery': {
            'key': os.getenv('BITQUERY_API_KEY'),
            'status': '❌ Invalid format (26 chars, needs 32)',
            'action': 'Get new 32-character key'
        },
        'Zapper': {
            'key': os.getenv('ZAPPER_API_KEY'),
            'status': '❌ Invalid format (UUID-like, needs API key)',
            'action': 'Register and get API key'
        },
        'DeBank': {
            'key': os.getenv('DEBANK_API_KEY'),
            'status': '⚠️ Valid but insufficient units',
            'action': 'Recharge account'
        },
        'Breadcrumbs': {
            'key': os.getenv('BREADCRUMBS_API_KEY'),
            'status': '❌ Invalid (getting Cloudflare protection)',
            'action': 'Get new Bearer token'
        },
        'Twitter': {
            'key': os.getenv('TWITTER_API_KEY'),
            'status': '❌ Invalid Bearer token',
            'action': 'Get new Bearer token'
        }
    }
    
    for api, info in api_status.items():
        print(f"{api}: {info['status']}")
        if info['key']:
            print(f"   Current: {info['key'][:10]}...{info['key'][-4:]}")
        print(f"   Action: {info['action']}")
        print()
    
    print("\n🚀 Step-by-Step Fix Instructions:")
    print("=" * 40)
    
    print("\n1️⃣ BitQuery API Fix:")
    print("   • Go to: https://bitquery.io/")
    print("   • Sign up for free account")
    print("   • Go to API Keys section")
    print("   • Generate new API key (should be 32 characters)")
    print("   • Update .env file: BITQUERY_API_KEY=your_new_32_char_key")
    
    print("\n2️⃣ Zapper API Fix:")
    print("   • Go to: https://zapper.xyz/")
    print("   • Sign up for developer account")
    print("   • Go to API/Developer section")
    print("   • Generate API key")
    print("   • Update .env file: ZAPPER_API_KEY=your_new_api_key")
    
    print("\n3️⃣ DeBank API Fix:")
    print("   • Go to: https://cloud.debank.com/")
    print("   • Login to your account")
    print("   • Recharge your account with credits")
    print("   • Your current API key should work after recharge")
    
    print("\n4️⃣ Breadcrumbs API Fix:")
    print("   • Go to: https://breadcrumbs.app/")
    print("   • Sign up for account")
    print("   • Go to API section")
    print("   • Generate new Bearer token")
    print("   • Update .env file: BREADCRUMBS_API_KEY=your_new_bearer_token")
    
    print("\n5️⃣ Twitter API Fix:")
    print("   • Go to: https://developer.twitter.com/")
    print("   • Sign up for developer account")
    print("   • Create new app")
    print("   • Get Bearer Token from app settings")
    print("   • Update .env file: TWITTER_API_KEY=your_new_bearer_token")
    
    print("\n📝 .env File Update Template:")
    print("-" * 35)
    print("# Replace these with your new API keys:")
    print("BITQUERY_API_KEY=your_32_character_bitquery_key")
    print("ZAPPER_API_KEY=your_zapper_api_key")
    print("DEBANK_API_KEY=your_debank_access_key")
    print("BREADCRUMBS_API_KEY=your_breadcrumbs_bearer_token")
    print("TWITTER_API_KEY=your_twitter_bearer_token")
    
    print("\n✅ After Updates:")
    print("-" * 20)
    print("• Run: python3 scripts/v1.5/test_api_endpoints.py")
    print("• All APIs should return 200 status codes")
    print("• Your DeFi risk assessment will have full API coverage")
    
    print("\n💡 Pro Tips:")
    print("-" * 15)
    print("• Most APIs offer free tiers with limited usage")
    print("• Keep API keys secure and don't share them")
    print("• Monitor usage to avoid hitting rate limits")
    print("• Consider upgrading to paid plans for higher limits")

def check_free_tier_alternatives():
    """Check if there are free alternatives for paid APIs"""
    print("\n🆓 Free Tier Alternatives:")
    print("=" * 30)
    
    alternatives = {
        'BitQuery': [
            "• Use Etherscan API (free tier available)",
            "• Use Ethplorer API (free tier available)",
            "• Use Covalent API (free tier with limits)"
        ],
        'Zapper': [
            "• Use DeBank API (free tier available)",
            "• Use Etherscan for portfolio data",
            "• Use 1inch API (free tier available)"
        ],
        'DeBank': [
            "• Use Etherscan API for balance data",
            "• Use Ethplorer API for token data",
            "• Use Covalent API (free tier)"
        ],
        'Breadcrumbs': [
            "• Use Etherscan for contract verification",
            "• Use CertiK API (if available)",
            "• Manual security checks"
        ],
        'Twitter': [
            "• Use Reddit API (free tier available)",
            "• Use Telegram API (free tier available)",
            "• Use Discord API (free tier available)"
        ]
    }
    
    for api, options in alternatives.items():
        print(f"\n{api} Alternatives:")
        for option in options:
            print(f"  {option}")

if __name__ == "__main__":
    print_fix_guide()
    check_free_tier_alternatives()
