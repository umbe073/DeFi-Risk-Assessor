#!/usr/bin/env python3
"""
Master Automation Script
========================
This script automates the entire process:
1. API verification
2. Social media checking
3. Enhanced API testing
4. Main risk assessment execution
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MasterAutomation:
    def __init__(self):
        self.scripts_dir = os.path.dirname(os.path.abspath(__file__))
        self.logs_dir = os.path.join(self.scripts_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.verification_passed = False
        self.social_check_passed = False
        self.enhanced_api_passed = False
        
    def run_script(self, script_name, description):
        """Run a Python script and return success status"""
        print(f"\n{'='*60}")
        print(f"🔍 {description}")
        print(f"{'='*60}")
        
        script_path = os.path.join(self.scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            return False
        
        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                cwd=self.scripts_dir
            )
            
            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"⚠️  Warnings/Errors: {result.stderr}")
            
            # Check exit code
            if result.returncode == 0:
                print(f"✅ {description} completed successfully!")
                return True
            else:
                print(f"❌ {description} failed with exit code {result.returncode}")
                return False
                
        except Exception as e:
            print(f"❌ Error running {script_name}: {e}")
            return False
    
    def check_api_keys(self):
        """Check which API keys are available"""
        print(f"\n{'='*60}")
        print("🔑 API KEY STATUS CHECK")
        print(f"{'='*60}")
        
        required_keys = {
            'INFURA_API_KEY': 'Infura',
            'ETHERSCAN_API_KEY': 'Etherscan',
            'COINGECKO_API_KEY': 'CoinGecko',
            'COINMARKETCAP_API_KEY': 'CoinMarketCap',
            'INCH_API_KEY': '1inch',
            'ALCHEMY_API_KEY': 'Alchemy',
            'MORALIS_API_KEY': 'Moralis',
            'BITQUERY_ACCESS_TOKEN': 'BitQuery',
            'SANTIMENT_API_KEY': 'Santiment',
            'DUNE_ANALYTICS_API_KEY': 'Dune Analytics',
            'ETHPLORER_API_KEY': 'Ethplorer',
            'ZAPPER_API_KEY': 'Zapper',
            'DEBANK_API_KEY': 'DeBank'
        }
        
        optional_keys = {
            'TWITTER_API_KEY': 'Twitter',
            'TELEGRAM_BOT_TOKEN': 'Telegram',
            'DISCORD_BOT_TOKEN': 'Discord',
            'REDDIT_CLIENT_ID': 'Reddit',
            'LIFI_API_KEY': 'Li-Fi',
            'THE_GRAPH_API_KEY': 'The Graph',
            'SCORECHAIN_API_KEY': 'Scorechain',
            'TRM_LABS_API_KEY': 'TRM Labs',
            'OPENSANCTIONS_API_KEY': 'OpenSanctions',
            'LUKKA_API_KEY': 'Lukka',
            'DEFISAFETY_API_KEY': 'DeFiSafety',
            'MEDIUM_INTEGRATION_TOKEN': 'Medium',
            'CERTIK_API_KEY': 'CertiK'
        }
        
        print("\n📋 Required API Keys:")
        print("-" * 30)
        required_missing = 0
        for key, name in required_keys.items():
            if os.getenv(key):
                print(f"  ✅ {name}: Available")
            else:
                print(f"  ❌ {name}: Missing")
                required_missing += 1
        
        print(f"\n📋 Optional API Keys:")
        print("-" * 30)
        optional_missing = 0
        for key, name in optional_keys.items():
            if os.getenv(key):
                print(f"  ✅ {name}: Available")
            else:
                print(f"  ⚠️  {name}: Missing (Optional)")
                optional_missing += 1
        
        print(f"\n📊 Summary:")
        print(f"  Required: {len(required_keys) - required_missing}/{len(required_keys)} available")
        print(f"  Optional: {len(optional_keys) - optional_missing}/{len(optional_keys)} available")
        
        if required_missing > 0:
            print(f"\n⚠️  Warning: {required_missing} required API keys are missing!")
            print("   Some functionality may be limited.")
        
        return required_missing == 0
    
    def step1_api_verification(self):
        """Step 1: Run automated API verification"""
        print(f"\n{'='*60}")
        print("🚀 STEP 1: AUTOMATED API VERIFICATION")
        print(f"{'='*60}")
        
        success = self.run_script(
            "automated_api_verification.py",
            "Automated API Verification"
        )
        
        self.verification_passed = success
        
        if success:
            print("✅ API verification passed! All required APIs are working.")
        else:
            print("❌ API verification failed! Some APIs are not working properly.")
            print("⚠️  The main script may have limited functionality.")
        
        return success
    
    def step2_social_media_check(self):
        """Step 2: Run social media checker"""
        print(f"\n{'='*60}")
        print("🚀 STEP 2: SOCIAL MEDIA PLATFORM CHECK")
        print(f"{'='*60}")
        
        success = self.run_script(
            "social_media_checker.py",
            "Social Media Platform Check"
        )
        
        self.social_check_passed = success
        
        if success:
            print("✅ Social media check passed! All platforms are accessible.")
        else:
            print("❌ Social media check failed! Some platforms are not accessible.")
            print("⚠️  Social data collection may be limited.")
        
        return success
    
    def step3_enhanced_api_test(self):
        """Step 3: Run enhanced API integrations test"""
        print(f"\n{'='*60}")
        print("🚀 STEP 3: ENHANCED API INTEGRATIONS TEST")
        print(f"{'='*60}")
        
        success = self.run_script(
            "enhanced_api_integrations.py",
            "Enhanced API Integrations Test"
        )
        
        self.enhanced_api_passed = success
        
        if success:
            print("✅ Enhanced API test passed! Li-Fi, Zapper, and The Graph are working.")
        else:
            print("❌ Enhanced API test failed! Some enhanced APIs are not working.")
            print("⚠️  Enhanced scoring features may be limited.")
        
        return success
    
    def step4_comprehensive_api_test(self):
        """Step 4: Run comprehensive API test"""
        print(f"\n{'='*60}")
        print("🚀 STEP 4: COMPREHENSIVE API TEST")
        print(f"{'='*60}")
        
        success = self.run_script(
            "comprehensive_api_test.py",
            "Comprehensive API Test"
        )
        
        if success:
            print("✅ Comprehensive API test passed! All APIs are functioning.")
        else:
            print("❌ Comprehensive API test failed! Some APIs have issues.")
        
        return success
    
    def step5_main_script_execution(self):
        """Step 5: Execute main risk assessment script"""
        print(f"\n{'='*60}")
        print("🚀 STEP 5: MAIN RISK ASSESSMENT EXECUTION")
        print(f"{'='*60}")
        
        # Check if we should proceed based on previous steps
        if not self.verification_passed:
            print("⚠️  API verification failed. Do you want to proceed anyway? (y/n)")
            response = input().lower().strip()
            if response != 'y':
                print("❌ Execution cancelled due to API verification failure.")
                return False
        
        print("🎯 Starting main risk assessment script...")
        print("📊 This will analyze all tokens and generate comprehensive risk reports.")
        
        success = self.run_script(
            "defi_complete_risk_assessment_clean.py",
            "Main Risk Assessment Script"
        )
        
        if success:
            print("✅ Main risk assessment completed successfully!")
            print("📄 Check the logs/ directory for detailed reports.")
        else:
            print("❌ Main risk assessment failed!")
            print("📄 Check the logs/ directory for error details.")
        
        return success
    
    def generate_summary_report(self):
        """Generate a summary report of all steps"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.logs_dir, f"automation_summary_{timestamp}.txt")
        
        with open(report_file, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("MASTER AUTOMATION SUMMARY REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Script Directory: {self.scripts_dir}\n\n")
            
            f.write("STEP RESULTS:\n")
            f.write("-" * 20 + "\n")
            f.write(f"1. API Verification: {'✅ PASSED' if self.verification_passed else '❌ FAILED'}\n")
            f.write(f"2. Social Media Check: {'✅ PASSED' if self.social_check_passed else '❌ FAILED'}\n")
            f.write(f"3. Enhanced API Test: {'✅ PASSED' if self.enhanced_api_passed else '❌ FAILED'}\n")
            f.write(f"4. Comprehensive API Test: {'✅ PASSED' if self.enhanced_api_passed else '❌ FAILED'}\n")
            
            f.write("\nOVERALL STATUS:\n")
            f.write("-" * 20 + "\n")
            if self.verification_passed and self.social_check_passed:
                f.write("🎉 ALL SYSTEMS OPERATIONAL\n")
                f.write("✅ Ready for production use\n")
            elif self.verification_passed:
                f.write("⚠️  PARTIAL FUNCTIONALITY\n")
                f.write("✅ Core APIs working, some social features limited\n")
            else:
                f.write("❌ LIMITED FUNCTIONALITY\n")
                f.write("⚠️  Some core APIs not working\n")
        
        print(f"\n📄 Summary report saved to: {report_file}")
    
    def run_full_automation(self):
        """Run the complete automation process"""
        print("🎯 MASTER AUTOMATION SYSTEM")
        print("=" * 60)
        print("This script will run all verifications and tests in order.")
        print("Only proceed to the main script if all checks pass.")
        print("=" * 60)
        
        # Check API keys first
        api_keys_ok = self.check_api_keys()
        
        # Step 1: API Verification
        step1_ok = self.step1_api_verification()
        
        # Step 2: Social Media Check
        step2_ok = self.step2_social_media_check()
        
        # Step 3: Enhanced API Test
        step3_ok = self.step3_enhanced_api_test()
        
        # Step 4: Comprehensive API Test
        step4_ok = self.step4_comprehensive_api_test()
        
        # Step 5: Main Script Execution
        step5_ok = self.step5_main_script_execution()
        
        # Generate summary
        self.generate_summary_report()
        
        # Final summary
        print(f"\n{'='*60}")
        print("🎯 AUTOMATION COMPLETE")
        print(f"{'='*60}")
        print(f"API Keys Check: {'✅' if api_keys_ok else '❌'}")
        print(f"API Verification: {'✅' if step1_ok else '❌'}")
        print(f"Social Media Check: {'✅' if step2_ok else '❌'}")
        print(f"Enhanced API Test: {'✅' if step3_ok else '❌'}")
        print(f"Comprehensive API Test: {'✅' if step4_ok else '❌'}")
        print(f"Main Script Execution: {'✅' if step5_ok else '❌'}")
        
        if step1_ok and step2_ok and step3_ok and step4_ok and step5_ok:
            print("\n🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
            print("✅ System is fully operational and ready for production use.")
        else:
            print("\n⚠️  SOME STEPS FAILED!")
            print("❌ Check the logs for details and fix any issues.")
        
        return step1_ok and step2_ok and step3_ok and step4_ok and step5_ok

def main():
    """Main automation function"""
    automation = MasterAutomation()
    
    try:
        success = automation.run_full_automation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Automation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Automation failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 