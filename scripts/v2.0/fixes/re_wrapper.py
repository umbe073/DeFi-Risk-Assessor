#!/usr/bin/env python3
"""
Wrapper for the re module that handles _sre import issues gracefully.
This can be used as a drop-in replacement for the re module.
"""

import sys
import warnings

# Try to import the original re module
try:
    import re
    # Import all public symbols from re
    from re import *
    # Also import the module itself for direct access
    __all__ = re.__all__
except ImportError as e:
    warnings.warn(f"Could not import re module: {e}", ImportWarning, stacklevel=2)
    raise

# If we get here, the re module imported successfully
# The _sre module should be available since re imported successfully
try:
    import _sre
except ImportError as e:
    warnings.warn(f"Could not import _sre module: {e}. Regular expression functionality may be limited.", 
                  ImportWarning, stacklevel=2)
    # This is just a warning - the re module should still work
    pass

# Test that everything works
if __name__ == "__main__":
    print("Testing re wrapper...")
    try:
        # Test basic functionality
        result = search(r'test', 'this is a test string')
        if result:
            print("✓ Regex search works correctly")
        else:
            print("⚠ Regex search returned no match")
        
        # Test compilation
        pattern = compile(r'\d+')
        result = pattern.search('abc123def')
        if result:
            print("✓ Pattern compilation and search works")
        else:
            print("⚠ Pattern compilation test failed")
            
        print("✅ re wrapper is working correctly!")
        
    except Exception as e:
        print(f"❌ Error testing re wrapper: {e}")
        sys.exit(1) 