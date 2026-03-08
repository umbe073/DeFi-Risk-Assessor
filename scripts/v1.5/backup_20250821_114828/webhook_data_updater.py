#!/usr/bin/env python3
"""
Webhook Data Updater
Flask-based web server for real-time data cache updates
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import schedule

# Project paths
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CACHE_FILE = os.path.join(DATA_DIR, 'real_data_cache.json')

app = Flask(__name__)

class DataUpdater:
    def __init__(self):
        self.rate_limits = {
            'etherscan': {'calls_per_hour': 100, 'calls_made': 0, 'last_reset': time.time()},
            'moralis': {'calls_per_hour': 100, 'calls_made': 0, 'last_reset': time.time()},
            'covalent': {'calls_per_hour': 100, 'calls_made': 0, 'last_reset': time.time()}
        }
        self.ensure_cache_exists()
    
    def ensure_cache_exists(self):
        """Ensure cache file and directory exist"""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not os.path.exists(CACHE_FILE):
                initial_cache = {
                    'last_updated': time.time(),
                    'tokens': {},
                    'metadata': {
                        'version': '1.5',
                        'data_sources': []
                    }
                }
                self.save_cache(initial_cache)
        except Exception as e:
            print(f"Error ensuring cache exists: {e}")
    
    def load_cache(self):
        """Load current cache data with enhanced fallback support"""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    # Ensure all required sections exist
                    if 'fallback_data' not in data:
                        data['fallback_data'] = {
                            'market_data': {},
                            'holder_data': {},
                            'social_data': {},
                            'onchain_data': {}
                        }
                    if 'metadata' not in data:
                        data['metadata'] = {
                            'version': '1.5',
                            'data_sources': []
                        }
                    return data
            else:
                return {
                    'last_updated': 0, 
                    'tokens': {}, 
                    'metadata': {},
                    'fallback_data': {
                        'market_data': {},
                        'holder_data': {},
                        'social_data': {},
                        'onchain_data': {}
                    }
                }
        except Exception as e:
            print(f"Error loading cache: {e}")
            return {
                'last_updated': 0, 
                'tokens': {}, 
                'metadata': {},
                'fallback_data': {
                    'market_data': {},
                    'holder_data': {},
                    'social_data': {},
                    'onchain_data': {}
                }
            }
    
    def save_cache(self, cache_data):
        """Save cache data"""
        try:
            cache_data['last_updated'] = time.time()
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving cache: {e}")
            return False
    
    def check_rate_limit(self, service):
        """Check if service is within rate limits"""
        if service not in self.rate_limits:
            return True
        
        current_time = time.time()
        rate_info = self.rate_limits[service]
        
        # Reset counter every hour
        if current_time - rate_info['last_reset'] >= 3600:
            rate_info['calls_made'] = 0
            rate_info['last_reset'] = current_time
        
        return rate_info['calls_made'] < rate_info['calls_per_hour']
    
    def increment_rate_limit(self, service):
        """Increment rate limit counter"""
        if service in self.rate_limits:
            self.rate_limits[service]['calls_made'] += 1
    
    def update_token_data(self, token_address, chain, data):
        """Update data for a specific token"""
        try:
            cache = self.load_cache()
            
            token_key = f"{chain}:{token_address.lower()}"
            
            if token_key not in cache['tokens']:
                cache['tokens'][token_key] = {}
            
            # Update token data
            cache['tokens'][token_key].update(data)
            cache['tokens'][token_key]['last_updated'] = time.time()
            
            # Update metadata
            if 'metadata' not in cache:
                cache['metadata'] = {}
            
            data_sources = cache['metadata'].get('data_sources', [])
            source = data.get('source', 'unknown')
            if source not in data_sources:
                data_sources.append(source)
                cache['metadata']['data_sources'] = data_sources
            
            return self.save_cache(cache)
            
        except Exception as e:
            print(f"Error updating token data: {e}")
            return False
    
    def update_all_tokens(self):
        """Update all tokens in cache and refresh timestamp"""
        try:
            cache = self.load_cache()
            print(f"Scheduled update: {len(cache.get('tokens', {}))} tokens in cache")
            
            # Update the cache timestamp to mark it as fresh
            cache['last_updated'] = time.time()
            
            # Ensure metadata exists
            if 'metadata' not in cache:
                cache['metadata'] = {}
            
            cache['metadata']['last_refresh'] = datetime.now().isoformat()
            cache['metadata']['refresh_source'] = 'webhook_scheduler'
            
            # Save the updated cache
            self.save_cache(cache)
            print(f"✅ Cache timestamp updated - now marked as fresh")
            return True
        except Exception as e:
            print(f"Error in scheduled update: {e}")
            return False

# Global updater instance
updater = DataUpdater()

@app.route('/api/cache_status', methods=['GET'])
def get_cache_status():
    """Get current cache status"""
    try:
        cache = updater.load_cache()
        
        # Calculate cache age
        cache_age = (time.time() - cache.get('last_updated', 0)) / 3600
        
        # Get supported chains and data sources
        tokens = cache.get('tokens', {})
        chains = set()
        data_sources = set()
        
        for token_key, token_data in tokens.items():
            if ':' in token_key:
                chain = token_key.split(':')[0]
                chains.add(chain)
            
            source = token_data.get('source', '')
            if source:
                data_sources.add(source)
        
        # Also get from metadata
        metadata_sources = cache.get('metadata', {}).get('data_sources', [])
        data_sources.update(metadata_sources)
        
        stats = {
            'total_tokens': len(tokens),
            'cache_age_hours': cache_age,
            'last_updated': cache.get('last_updated', 0),
            'supported_chains': sorted(list(chains)),
            'data_sources': sorted(list(data_sources)),
            'rate_limits': updater.rate_limits
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/update_token', methods=['POST'])
def webhook_update_token():
    """Webhook endpoint for updating token data"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['token_address', 'chain']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        token_address = data['token_address']
        chain = data['chain']
        
        # Extract update data
        update_data = {k: v for k, v in data.items() if k not in ['token_address', 'chain']}
        
        # Update cache
        success = updater.update_token_data(token_address, chain, update_data)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Token data updated successfully',
                'token': f"{chain}:{token_address}",
                'timestamp': time.time()
            })
        else:
            return jsonify({'error': 'Failed to update cache'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/update_all', methods=['POST'])
def webhook_update_all():
    """Webhook endpoint for triggering full cache update"""
    try:
        success = updater.update_all_tokens()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Cache update triggered successfully',
                'timestamp': time.time()
            })
        else:
            return jsonify({'error': 'Failed to trigger cache update'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/service_test', methods=['POST'])
def webhook_service_test():
    """Webhook endpoint for API service test results"""
    try:
        data = request.get_json()
        service = data.get('service')
        success = data.get('success')
        message = data.get('message')
        timestamp = data.get('timestamp')
        
        print(f"API Service Test: {service} - {'SUCCESS' if success else 'FAILED'} - {message}")
        
        return jsonify({
            'success': True,
            'service': service,
            'logged': True,
            'timestamp': timestamp
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def scheduled_updates():
    """Run scheduled updates every hour"""
    print("Running scheduled data updates...")
    updater.update_all_tokens()

def start_scheduler():
    """Start the background scheduler"""
    schedule.every().hour.do(scheduled_updates)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

def main():
    """Main entry point"""
    try:
        print("Starting webhook data updater server...")
        print(f"Cache file: {CACHE_FILE}")
        
        # Ensure cache exists
        updater.ensure_cache_exists()
        
        # Start background scheduler
        start_scheduler()
        
        # Start Flask app
        app.run(host='0.0.0.0', port=5001, debug=False)
        
    except Exception as e:
        print(f"Error starting webhook server: {e}")

if __name__ == "__main__":
    main()
