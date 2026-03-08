#!/usr/bin/env python3
"""
Refresh Token Data Viewer with Enhanced Data
Uses the enhanced API endpoints to fetch comprehensive data and update the Token Data Viewer CSV files
"""

import os
import sys
import json
import time
import pandas as pd
from datetime import datetime

# Add project root to path
PROJECT_ROOT = '/Users/amlfreak/Desktop/venv'
sys.path.append(PROJECT_ROOT)

def refresh_token_data_viewer():
    """Refresh Token Data Viewer with enhanced data from improved API endpoints"""
    print("🔄 Refreshing Token Data Viewer with Enhanced Data")
    print("=" * 60)
    
    # Import the webhook server
    try:
        from webhook_server import WebhookServer
        server = WebhookServer()
        print("✅ Enhanced webhook server loaded")
    except Exception as e:
        print(f"❌ Failed to load webhook server: {e}")
        return False
    
    # Load tokens from CSV
    tokens_file = '/Users/amlfreak/Desktop/venv/data/tokens.csv'
    try:
        df = pd.read_csv(tokens_file)
        print(f"✅ Loaded {len(df)} tokens from {tokens_file}")
    except Exception as e:
        print(f"❌ Failed to load tokens CSV: {e}")
        return False
    
    # Process each token with enhanced data fetching
    enhanced_data = []
    
    for index, row in df.iterrows():
        token_name = row.get('Token Name', 'Unknown')
        symbol = row.get('Symbol', 'Unknown')
        chain = row.get('Chain', 'ethereum')
        address = row.get('Contract Address', '')
        
        if not address:
            print(f"⚠️  Skipping {token_name} - no contract address")
            continue
        
        print(f"\n🔍 Processing {token_name} ({symbol})")
        print("-" * 40)
        
        try:
            # Fetch comprehensive data using enhanced API endpoints
            start_time = time.time()
            data = server.fetch_real_time_data(address)
            end_time = time.time()
            
            fetch_time = end_time - start_time
            print(f"⏱️  Fetch time: {fetch_time:.2f} seconds")
            
            # Extract data from aggregates
            aggregates = data.get('aggregates', {})
            market_data = aggregates.get('market', {})
            onchain_data = aggregates.get('onchain', {})
            liquidity_data = aggregates.get('liquidity', {})
            
            # Extract values with fallbacks
            market_cap = market_data.get('market_cap', 0)
            volume_24h = market_data.get('volume_24h', 0)
            price = market_data.get('price', 0)
            change_24h = market_data.get('change_24h', 0)
            
            holders = onchain_data.get('holders', 0)
            total_supply = onchain_data.get('total_supply', 0)
            
            liquidity = liquidity_data.get('liquidity', 0)
            liquidity_volume = liquidity_data.get('volume_24h', 0)
            trade_count = liquidity_data.get('trade_count', 0)
            
            # Format values for display
            market_cap_str = f"${market_cap:,.2f}" if market_cap > 0 else "N/A"
            volume_24h_str = f"${volume_24h:,.2f}" if volume_24h > 0 else "N/A"
            price_str = f"${price:.6f}" if price > 0 else "N/A"
            change_24h_str = f"{change_24h:.2f}%" if change_24h != 0 else "N/A"
            
            holders_str = f"{holders:,.0f}" if holders > 0 else "N/A"
            liquidity_str = f"${liquidity:,.2f}" if liquidity > 0 else "N/A"
            
            # Determine data source
            data_sources = []
            if data.get('market_data'): data_sources.append('market')
            if data.get('onchain_data'): data_sources.append('onchain')
            if data.get('liquidity_data'): data_sources.append('liquidity')
            if data.get('social_data'): data_sources.append('social')
            
            data_source = ', '.join(data_sources) if data_sources else 'fallback'
            
            # Create enhanced row
            enhanced_row = {
                'Token': token_name,
                'Symbol': symbol,
                'Chain': chain,
                'Market Cap': market_cap_str,
                'Volume 24h': volume_24h_str,
                'Holders': holders_str,
                'Liquidity': liquidity_str,
                'Price': price_str,
                'Change 24h': change_24h_str,
                'Risk Score': 'N/A',
                'Data Source': data_source,
                'Last Updated': datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            enhanced_data.append(enhanced_row)
            
            print(f"✅ {symbol}: MC={market_cap_str}, Vol={volume_24h_str}, Holders={holders_str}, Liq={liquidity_str}")
            
        except Exception as e:
            print(f"❌ Error processing {token_name}: {e}")
            # Add fallback row with basic data
            enhanced_row = {
                'Token': token_name,
                'Symbol': symbol,
                'Chain': chain,
                'Market Cap': 'N/A',
                'Volume 24h': 'N/A',
                'Holders': 'N/A',
                'Liquidity': 'N/A',
                'Price': 'N/A',
                'Change 24h': 'N/A',
                'Risk Score': 'N/A',
                'Data Source': 'error',
                'Last Updated': datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            enhanced_data.append(enhanced_row)
    
    # Create enhanced DataFrame
    enhanced_df = pd.DataFrame(enhanced_data)
    
    # Save to multiple CSV files for Token Data Viewer
    output_files = [
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer.csv',
        '/Users/amlfreak/Desktop/venv/data/token_data_viewer_export.csv',
        '/Users/amlfreak/Desktop/venv/data/tokens_enhanced.csv'
    ]
    
    for output_file in output_files:
        try:
            enhanced_df.to_csv(output_file, index=False)
            print(f"✅ Saved enhanced data to {output_file}")
        except Exception as e:
            print(f"❌ Failed to save {output_file}: {e}")
    
    # Generate summary report
    print(f"\n📊 Summary Report")
    print("=" * 60)
    
    total_tokens = len(enhanced_data)
    successful_tokens = len([row for row in enhanced_data if row['Data Source'] != 'error'])
    
    print(f"Total Tokens: {total_tokens}")
    print(f"Successful: {successful_tokens}")
    print(f"Success Rate: {(successful_tokens/total_tokens)*100:.1f}%")
    
    # Show data completeness
    market_cap_count = len([row for row in enhanced_data if row['Market Cap'] != 'N/A'])
    volume_count = len([row for row in enhanced_data if row['Volume 24h'] != 'N/A'])
    holders_count = len([row for row in enhanced_data if row['Holders'] != 'N/A'])
    liquidity_count = len([row for row in enhanced_data if row['Liquidity'] != 'N/A'])
    
    print(f"\n📈 Data Completeness:")
    print(f"  Market Cap: {market_cap_count}/{total_tokens} ({(market_cap_count/total_tokens)*100:.1f}%)")
    print(f"  Volume 24h: {volume_count}/{total_tokens} ({(volume_count/total_tokens)*100:.1f}%)")
    print(f"  Holders: {holders_count}/{total_tokens} ({(holders_count/total_tokens)*100:.1f}%)")
    print(f"  Liquidity: {liquidity_count}/{total_tokens} ({(liquidity_count/total_tokens)*100:.1f}%)")
    
    return True

if __name__ == "__main__":
    success = refresh_token_data_viewer()
    if success:
        print("\n✅ Token Data Viewer refresh completed successfully!")
        print("🔄 The Token Data Viewer should now display enhanced data with more comprehensive information.")
    else:
        print("\n❌ Token Data Viewer refresh completed with errors!")









