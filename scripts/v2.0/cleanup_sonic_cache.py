#!/usr/bin/env python3
"""
Clean up SONIC tokens from cache, keeping only the correct one
"""

import json
import os

def cleanup_sonic_cache():
    """Remove old SONIC tokens from cache, keep only the correct one"""
    
    # Correct SONIC token address
    correct_sonic = '0x039e2fB66102314Ce7b64Ce5Ce3E5183bc94aD38'
    
    # Old incorrect SONIC token addresses to remove
    old_sonic_tokens = [
        '0x67898d21Cd030fc7bfc62808c0CD675097d370f1',
        '0x7A0C53F7eb34C5BC8B01691723669adA9D6CB384'
    ]
    
    # Load cache data
    cache_file = 'cache_data.json'
    fallback_file = 'fallback_data.json'
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Remove old SONIC tokens from cache
        tokens = cache_data.get('tokens', {})
        removed_count = 0
        
        for old_addr in old_sonic_tokens:
            if old_addr in tokens:
                del tokens[old_addr]
                removed_count += 1
                print(f"✅ Removed old SONIC token: {old_addr}")
        
        # Save updated cache
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"✅ Removed {removed_count} old SONIC tokens from cache")
    
    if os.path.exists(fallback_file):
        with open(fallback_file, 'r') as f:
            fallback_data = json.load(f)
        
        # Remove old SONIC tokens from fallback data
        token_mappings = fallback_data.get('token_mappings', {})
        removed_count = 0
        
        for old_addr in old_sonic_tokens:
            if old_addr in token_mappings:
                del token_mappings[old_addr]
                removed_count += 1
                print(f"✅ Removed old SONIC token from fallback: {old_addr}")
        
        # Save updated fallback data
        with open(fallback_file, 'w') as f:
            json.dump(fallback_data, f, indent=2)
        
        print(f"✅ Removed {removed_count} old SONIC tokens from fallback data")
    
    print(f"✅ Cache cleanup complete. Only correct SONIC token remains: {correct_sonic}")

if __name__ == "__main__":
    cleanup_sonic_cache()
