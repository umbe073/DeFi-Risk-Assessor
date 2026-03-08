#!/usr/bin/env python3
"""
Unit tests for core module
"""

import unittest
import json
import tempfile
import os
from unittest.mock import Mock, patch

from modules.core import DeFiRiskAssessor, RiskReport

class TestRiskReport(unittest.TestCase):
    """Test RiskReport dataclass"""
    
    def test_risk_report_creation(self):
        """Test creating a RiskReport"""
        report = RiskReport(
            token_address="0x1234567890123456789012345678901234567890",
            symbol="TEST",
            token_name="Test Token",
            timestamp="2024-01-01T00:00:00"
        )
        
        self.assertEqual(report.token_address, "0x1234567890123456789012345678901234567890")
        self.assertEqual(report.symbol, "TEST")
        self.assertEqual(report.token_name, "Test Token")
        self.assertEqual(report.timestamp, "2024-01-01T00:00:00")
        self.assertEqual(report.risk_scores, {})
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

class TestDeFiRiskAssessor(unittest.TestCase):
    """Test DeFiRiskAssessor class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False)
        self.temp_config.write(json.dumps({
            'api_keys': {},
            'rate_limits': {},
            'cache_settings': {'enabled': True, 'ttl': 3600},
            'logging': {'level': 'INFO', 'file': 'logs/test.log'},
            'output': {'json': True, 'excel': True, 'csv': False}
        }))
        self.temp_config.close()
        
        with patch('modules.core.MarketDataCollector'), \
             patch('modules.core.SocialDataCollector'), \
             patch('modules.core.SecurityDataCollector'), \
             patch('modules.core.ComplianceDataCollector'), \
             patch('modules.core.LiquidityDataCollector'), \
             patch('modules.core.TransferDataCollector'), \
             patch('modules.core.MarketDataScorer'), \
             patch('modules.core.SocialDataScorer'), \
             patch('modules.core.SecurityDataScorer'), \
             patch('modules.core.ComplianceDataScorer'), \
             patch('modules.core.LiquidityDataScorer'), \
             patch('modules.core.TransferDataScorer'), \
             patch('modules.core.TokenValidator'), \
             patch('modules.core.ConfigValidator'), \
             patch('modules.core.Logger'), \
             patch('modules.core.CacheManager'), \
             patch('modules.core.RateLimiter'):
            
            self.assessor = DeFiRiskAssessor(self.temp_config.name)
    
    def tearDown(self):
        """Clean up test fixtures"""
        os.unlink(self.temp_config.name)
    
    def test_init_with_config(self):
        """Test initialization with config file"""
        self.assertIsNotNone(self.assessor.config)
        self.assertIn('api_keys', self.assessor.config)
        self.assertIn('rate_limits', self.assessor.config)
    
    def test_init_without_config(self):
        """Test initialization without config file"""
        # Test with a non-existent config file
        assessor = DeFiRiskAssessor("nonexistent.json")
        self.assertIsNotNone(assessor.config)
        self.assertIn('api_keys', assessor.config)
        self.assertIn('rate_limits', assessor.config)
    
    def test_calculate_overall_score(self):
        """Test overall score calculation"""
        scores = {
            'market_data': 7.5,
            'social_data': 6.0,
            'security_data': 8.0,
            'compliance_data': 9.0,
            'liquidity_data': 5.5,
            'transfer_data': 4.0
        }
        
        overall_score = self.assessor._calculate_overall_score(scores)
        
        # Expected: (7.5*0.25 + 6.0*0.20 + 8.0*0.25 + 9.0*0.15 + 5.5*0.10 + 4.0*0.05)
        expected = 7.175
        self.assertAlmostEqual(overall_score, expected, places=2)
    
    def test_track_api_usage(self):
        """Test API usage tracking"""
        api_usage = self.assessor._track_api_usage()
        
        self.assertIn('market_data', api_usage)
        self.assertIn('social_data', api_usage)
        self.assertIn('security_data', api_usage)
        self.assertIn('compliance_data', api_usage)
        self.assertIn('liquidity_data', api_usage)
        self.assertIn('transfer_data', api_usage)
    
    def test_combine_enhanced_data(self):
        """Test enhanced data combination"""
        report = RiskReport(
            token_address="0x1234567890123456789012345678901234567890",
            symbol="TEST",
            token_name="Test Token",
            timestamp="2024-01-01T00:00:00"
        )
        report.market_data = {'price': 100}
        report.social_data = {'tweets': 1000}
        report.security_data = {'audit': 'passed'}
        report.compliance_data = {'risk': 'low'}
        report.liquidity_data = {'tvl': 1000000}
        report.transfer_data = {'transfers': 500}
        
        enhanced_data = self.assessor._combine_enhanced_data(report)
        
        self.assertIn('market', enhanced_data)
        self.assertIn('social', enhanced_data)
        self.assertIn('security', enhanced_data)
        self.assertIn('compliance', enhanced_data)
        self.assertIn('liquidity', enhanced_data)
        self.assertIn('transfer', enhanced_data)
    
    def test_get_statistics(self):
        """Test statistics generation"""
        self.assessor.stats['total_tokens'] = 10
        self.assessor.stats['successful_assessments'] = 8
        self.assessor.stats['failed_assessments'] = 2
        self.assessor.stats['cache_hits'] = 3
        self.assessor.stats['cache_misses'] = 7
        self.assessor.stats['start_time'] = None
        self.assessor.stats['end_time'] = None
        
        stats = self.assessor.get_statistics()
        
        self.assertEqual(stats['total_tokens'], 10)
        self.assertEqual(stats['successful_assessments'], 8)
        self.assertEqual(stats['failed_assessments'], 2)
        self.assertEqual(stats['success_rate'], 80.0)
        self.assertEqual(stats['cache_hit_rate'], 30.0)

if __name__ == '__main__':
    unittest.main() 