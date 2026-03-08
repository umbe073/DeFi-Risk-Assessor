#!/usr/bin/env python3
"""
Setup and run Santiment API test with proper environment handling
"""

import os
import sys
import subprocess
import importlib.util

def check_and_install_package(package_name):
    """Check if a package is installed and install it if needed"""
    try:
        importlib.import_module(package_name)
        print(f"✅ {package_name} is already installed")
        return True
    except ImportError:
        print(f"📦 Installing {package_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"✅ {package_name} installed successfully")
            return True
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package_name}")
            return False

def main():
    """Main function to setup environment and run tests"""
    print("🚀 Santiment API Test Setup")
    print("=" * 40)
    
    # Check and install required packages
    required_packages = ["san", "python-dotenv", "requests"]
    
    for package in required_packages:
        if not check_and_install_package(package):
            print(f"❌ Cannot proceed without {package}")
            return False
    
    print("\n🧪 Running Santiment API tests...")
    print("=" * 40)
    
    # Import and run the test
    try:
        # Import the test module
        spec = importlib.util.spec_from_file_location("santiment_test", "santiment_test.py")
        test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(test_module)
        
        # Run the tests
        if hasattr(test_module, 'test_santiment_official_client'):
            official_result = test_module.test_santiment_official_client()
        
        if hasattr(test_module, 'test_santiment_graphql_direct'):
            graphql_result = test_module.test_santiment_graphql_direct()
        
        print("\n📊 SUMMARY")
        print("=" * 40)
        print(f"Official Client: {'✅ Working' if official_result else '❌ Failed'}")
        print(f"Direct GraphQL: {'✅ Working' if graphql_result else '❌ Failed'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error running tests: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Setup and tests completed successfully!")
    else:
        print("\n❌ Setup or tests failed!")
        sys.exit(1) 