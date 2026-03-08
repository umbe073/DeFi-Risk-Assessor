# macOS Compatibility Setup

This directory contains several files to handle macOS compatibility issues with tkinter applications.

## Files Overview

### 1. `macos_patch.c` and `macos_patch.cpython-39-darwin.so`
- **Purpose**: C extension that patches NSApplication to handle missing methods
- **Function**: Provides a low-level fix for macOS tkinter crashes
- **Usage**: Automatically imported if available

### 2. `macos_patch.py` (Python fallback)
- **Purpose**: Pure Python implementation of the same functionality
- **Function**: Provides the same interface as the C extension
- **Usage**: Used when C extension is not available

### 3. `macos_fix.py`
- **Purpose**: Environment-based macOS compatibility fixes
- **Function**: Sets environment variables and initializes AppKit
- **Usage**: Final fallback when other methods fail

### 4. `setup_macos_patch.py`
- **Purpose**: Build script for the C extension
- **Function**: Compiles the C extension from source
- **Usage**: Run to build the C extension if needed

## Import Hierarchy

The code uses a three-tier fallback system:

1. **C Extension** (`macos_patch.cpython-*.so`)
   - Fastest and most reliable
   - Requires compilation

2. **Python Module** (`macos_patch.py`)
   - Pure Python implementation
   - Same interface as C extension
   - Good performance

3. **Environment Fix** (`macos_fix.py`)
   - Sets environment variables
   - Initializes AppKit manually
   - Most compatible but least performant

## Usage

The import logic automatically tries each method in order:

```python
try:
    import macos_patch  # type: ignore
    macos_patch.patch_nsapplication()
    print("✅ C extension patch applied")
except ImportError:
    try:
        from macos_patch import patch_nsapplication
        patch_nsapplication()
        print("✅ Python patch module applied")
    except ImportError:
        from macos_fix import apply_macos_fix, setup_macos_environment
        setup_macos_environment()
        apply_macos_fix()
        print("✅ Environment fix applied")
```

## Building the C Extension

If you need to build the C extension:

```bash
cd scripts/v1.5/dashboard
python3 setup_macos_patch.py build_ext --inplace
```

## Troubleshooting

- **Import warnings**: The `# type: ignore` comment suppresses linter warnings for the optional import
- **Missing C extension**: The Python fallback will be used automatically
- **AppKit issues**: The environment fix provides the most compatible solution

## Notes

- All files are designed to work together seamlessly
- The system automatically chooses the best available method
- No manual configuration is required
- The `# type: ignore` comment is used to suppress linter warnings for optional imports
