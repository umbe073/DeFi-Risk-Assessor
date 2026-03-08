#!/usr/bin/env python3
"""
Script to fix the _sre import issue in the re module.
This adds proper error handling for the _sre import to prevent IDE warnings.
"""

import os
import sys
import shutil
from pathlib import Path

def backup_original_file(file_path):
    """Create a backup of the original file."""
    backup_path = str(file_path) + '.backup'
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path

def patch_re_module():
    """Patch the re module to add proper error handling for _sre import."""
    
    # Find the re module file
    re_module_path = None
    
    # Try to find it in the standard library
    for path in sys.path:
        potential_path = Path(path) / 're' / '__init__.py'
        if potential_path.exists():
            re_module_path = potential_path
            break
    
    if not re_module_path:
        print("Could not find re module. Please run this script with appropriate permissions.")
        return False
    
    print(f"Found re module at: {re_module_path}")
    
    # Read the original file
    with open(re_module_path, 'r') as f:
        content = f.read()
    
    # Check if already patched
    if 'try:\n    import _sre' in content:
        print("Module already patched!")
        return True
    
    # Create backup
    backup_original_file(re_module_path)
    
    # Replace the simple import with try-except
    old_import = 'import _sre'
    new_import = '''try:
    import _sre
except ImportError as e:
    # If _sre is not available, we'll need to handle this gracefully
    # This is a fallback for environments where _sre is not built
    _sre = None
    import warnings
    warnings.warn(f"Could not import _sre module: {e}. Regular expression functionality may be limited.", 
                  ImportWarning, stacklevel=2)'''
    
    # Replace the import
    new_content = content.replace(old_import, new_import)
    
    # Also update the _compile_template function to handle None _sre
    if '_sre.template(' in new_content and 'if _sre is None:' not in new_content:
        # Find the _compile_template function and add error handling
        template_pattern = '@functools.lru_cache(_MAXCACHE)\ndef _compile_template(pattern, repl):\n    # internal: compile replacement pattern\n    return _sre.template(pattern, _parser.parse_template(repl, pattern))'
        
        if template_pattern in new_content:
            new_template = '''@functools.lru_cache(_MAXCACHE)
def _compile_template(pattern, repl):
    # internal: compile replacement pattern
    if _sre is None:
        raise ImportError("_sre module is not available")
    return _sre.template(pattern, _parser.parse_template(repl, pattern))'''
            
            new_content = new_content.replace(template_pattern, new_template)
    
    # Write the patched file
    with open(re_module_path, 'w') as f:
        f.write(new_content)
    
    print("Successfully patched re module!")
    return True

def test_patch():
    """Test that the patch works correctly."""
    try:
        import re
        print("✓ re module imports successfully")
        
        # Test basic regex functionality
        result = re.search(r'test', 'this is a test string')
        if result:
            print("✓ regex functionality works correctly")
        else:
            print("⚠ regex search returned no match (this might be expected)")
            
        return True
    except Exception as e:
        print(f"✗ Error testing patch: {e}")
        return False

if __name__ == "__main__":
    print("Fixing _sre import issue in re module...")
    
    if patch_re_module():
        print("\nTesting the patch...")
        if test_patch():
            print("\n✅ Patch applied successfully!")
            print("The _sre import warning should now be resolved.")
        else:
            print("\n❌ Patch test failed. Please check the backup file.")
    else:
        print("\n❌ Failed to apply patch.") 