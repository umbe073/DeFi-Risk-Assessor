#!/usr/bin/env python3
"""
Unit tests for scorers module
"""

import unittest

from modules.scorers import (
    MarketDataScorer,
    SocialDataScorer,
    SecurityDataScorer,
    ComplianceDataScorer,
    LiquidityDataScorer,
    TransferDataScorer
)

class TestMarketDataScorer(unittest.TestCase):
    """Test MarketDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = MarketDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid market data"""
        data = {
            'coingecko_price': 100.0,
            'coingecko_market_cap': 1000000000,  # $1B
            'coingecko_volume_24h': 50000000,    # $50M
            'coingecko_change_24h': 5.0
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_price(self):
        """Test price scoring"""
        self.assertEqual(self.scorer._score_price(0), 5.0)
        self.assertEqual(self.scorer._score_price(50), 6.0)
        self.assertEqual(self.scorer._score_price(1000), 7.0)
    
    def test_score_market_cap(self):
        """Test market cap scoring"""
        self.assertEqual(self.scorer._score_market_cap(0), 5.0)
        self.assertEqual(self.scorer._score_market_cap(1000000), 4.0)
        self.assertEqual(self.scorer._score_market_cap(100000000), 6.0)
        self.assertEqual(self.scorer._score_market_cap(10000000000), 8.0)
    
    def test_score_volume(self):
        """Test volume scoring"""
        self.assertEqual(self.scorer._score_volume(0, 1000000), 5.0)
        self.assertEqual(self.scorer._score_volume(100000, 1000000), 5.0)
        self.assertEqual(self.scorer._score_volume(500000, 1000000), 7.0)
    
    def test_score_volatility(self):
        """Test volatility scoring"""
        self.assertEqual(self.scorer._score_volatility(0), 7.0)
        self.assertEqual(self.scorer._score_volatility(10), 6.0)
        self.assertEqual(self.scorer._score_volatility(50), 4.0)

class TestSocialDataScorer(unittest.TestCase):
    """Test SocialDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = SocialDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid social data"""
        data = {
            'twitter_tweet_count': 5000,
            'telegram_members': 25000,
            'discord_members': 15000,
            'reddit_subscribers': 5000,
            'bitcointalk_posts': 500,
            'cointelegraph_articles': 20
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_twitter(self):
        """Test Twitter scoring"""
        self.assertEqual(self.scorer._score_twitter(0), 3.0)
        self.assertEqual(self.scorer._score_twitter(100), 4.0)
        self.assertEqual(self.scorer._score_twitter(5000), 7.0)
    
    def test_score_telegram(self):
        """Test Telegram scoring"""
        self.assertEqual(self.scorer._score_telegram(0), 3.0)
        self.assertEqual(self.scorer._score_telegram(1000), 4.0)
        self.assertEqual(self.scorer._score_telegram(50000), 7.0)
    
    def test_score_discord(self):
        """Test Discord scoring"""
        self.assertEqual(self.scorer._score_discord(0), 3.0)
        self.assertEqual(self.scorer._score_discord(1000), 4.0)
        self.assertEqual(self.scorer._score_discord(25000), 7.0)

class TestSecurityDataScorer(unittest.TestCase):
    """Test SecurityDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = SecurityDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid security data"""
        data = {
            'certik_score': 85,
            'defisafety_score': 75,
            'alchemy_contract_verified': True
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_certik(self):
        """Test CertiK scoring"""
        self.assertEqual(self.scorer._score_certik(0), 4.0)
        self.assertEqual(self.scorer._score_certik(70), 7.0)
        self.assertEqual(self.scorer._score_certik(90), 9.0)
    
    def test_score_defisafety(self):
        """Test DeFiSafety scoring"""
        self.assertEqual(self.scorer._score_defisafety(0), 4.0)
        self.assertEqual(self.scorer._score_defisafety(60), 7.0)
        self.assertEqual(self.scorer._score_defisafety(80), 9.0)
    
    def test_score_alchemy(self):
        """Test Alchemy scoring"""
        self.assertEqual(self.scorer._score_alchemy(False), 5.0)
        self.assertEqual(self.scorer._score_alchemy(True), 8.0)

class TestComplianceDataScorer(unittest.TestCase):
    """Test ComplianceDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = ComplianceDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid compliance data"""
        data = {
            'scorechain_risk_score': 30,
            'trm_risk_score': 40,
            'sanctions_risk': 'Low'
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_scorechain(self):
        """Test Scorechain scoring"""
        self.assertEqual(self.scorer._score_scorechain(0), 9.0)
        self.assertEqual(self.scorer._score_scorechain(60), 7.0)
        self.assertEqual(self.scorer._score_scorechain(100), 5.0)
    
    def test_score_trm(self):
        """Test TRM Labs scoring"""
        self.assertEqual(self.scorer._score_trm(0), 9.0)
        self.assertEqual(self.scorer._score_trm(50), 8.0)
        self.assertEqual(self.scorer._score_trm(100), 5.0)
    
    def test_score_sanctions(self):
        """Test sanctions scoring"""
        self.assertEqual(self.scorer._score_sanctions('Low'), 9.0)
        self.assertEqual(self.scorer._score_sanctions('Medium'), 7.0)
        self.assertEqual(self.scorer._score_sanctions('High'), 5.0)
        self.assertEqual(self.scorer._score_sanctions('Critical'), 3.0)

class TestLiquidityDataScorer(unittest.TestCase):
    """Test LiquidityDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = LiquidityDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid liquidity data"""
        data = {
            'etherscan_transactions': 50000,
            'defillama_tvl': 100000000,  # $100M
            'oneinch_liquidity': 5000000  # $5M
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_transactions(self):
        """Test transaction scoring"""
        self.assertEqual(self.scorer._score_transactions(0), 3.0)
        self.assertEqual(self.scorer._score_transactions(1000), 4.0)
        self.assertEqual(self.scorer._score_transactions(50000), 7.0)
    
    def test_score_tvl(self):
        """Test TVL scoring"""
        self.assertEqual(self.scorer._score_tvl(0), 4.0)
        self.assertEqual(self.scorer._score_tvl(100000), 4.0)
        self.assertEqual(self.scorer._score_tvl(10000000), 6.0)
        self.assertEqual(self.scorer._score_tvl(1000000000), 8.0)
    
    def test_score_liquidity(self):
        """Test liquidity scoring"""
        self.assertEqual(self.scorer._score_liquidity(0), 4.0)
        self.assertEqual(self.scorer._score_liquidity(10000), 5.0)
        self.assertEqual(self.scorer._score_liquidity(1000000), 7.0)

class TestTransferDataScorer(unittest.TestCase):
    """Test TransferDataScorer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scorer = TransferDataScorer()
    
    def test_score_with_valid_data(self):
        """Test scoring with valid transfer data"""
        data = {
            'moralis_transfers': 5000,
            'etherscan_transfers': 3000,
            'bitquery_transfers': 2000
        }
        
        score = self.scorer.score(data)
        
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)
    
    def test_score_with_empty_data(self):
        """Test scoring with empty data"""
        score = self.scorer.score({})
        self.assertEqual(score, 5.0)
    
    def test_score_transfers(self):
        """Test transfer scoring"""
        self.assertEqual(self.scorer._score_transfers(0), 3.0)
        self.assertEqual(self.scorer._score_transfers(100), 4.0)
        self.assertEqual(self.scorer._score_transfers(5000), 7.0)

if __name__ == '__main__':
    unittest.main() 