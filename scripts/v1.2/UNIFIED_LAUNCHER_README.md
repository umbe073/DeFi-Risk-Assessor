# Unified Risk Assessment Launcher

## Overview

The `run_risk_assessment.sh` script has been enhanced to include all functionality from the previous `run_with_venv.py` script, creating a single unified launcher that handles:

- ✅ Secure credential management
- ✅ Dependency checking
- ✅ Risk assessment execution
- ✅ Excel report updates

## Usage

### Full Risk Assessment Workflow (Default)
```bash
./run_risk_assessment.sh
```
This runs the complete workflow:
1. Checks dependencies
2. Verifies Vespia credentials
3. Prompts for credential setup if needed
4. Runs the risk assessment
5. Updates Excel reports

### Individual Commands

#### Credential Management
```bash
# Test Vespia credentials
./run_risk_assessment.sh credentials test

# Setup Vespia credentials
./run_risk_assessment.sh credentials setup

# Setup Vespia credentials with wizard
./run_risk_assessment.sh credentials setup_vespia

# List stored services
./run_risk_assessment.sh credentials list

# Remove Vespia credentials
./run_risk_assessment.sh credentials remove
```

#### Other Commands
```bash
# Check dependencies only
./run_risk_assessment.sh check_deps

# Run risk assessment only (skip credential checks)
./run_risk_assessment.sh risk_assessment

# Run credential management tool
./run_risk_assessment.sh manage_creds
```

## Benefits of Unified System

1. **Single Entry Point**: No need to manage two separate scripts
2. **Automatic Credential Management**: Secure credential system is always checked and available
3. **Simplified Workflow**: The .app can now directly call this single script
4. **Better Error Handling**: Unified error handling across all functionality
5. **Consistent Interface**: All commands use the same script with different arguments

## Migration from Previous System

- ✅ `run_with_venv.py` functionality has been merged into `run_risk_assessment.sh`
- ✅ Old `run_with_venv.py` has been backed up as `run_with_venv.py.backup`
- ✅ All existing functionality is preserved
- ✅ New unified interface provides better user experience

## File Structure

```
scripts/v1.2/
├── run_risk_assessment.sh          # Unified launcher (NEW)
├── run_with_venv.py.backup        # Backup of old runner
├── defi_complete_risk_assessment.py
├── update_risk_assessment_xlsx.py
├── credential_management/
│   ├── secure_credentials.py
│   ├── setup_vespia.py
│   └── manage_credentials.py
└── UNIFIED_LAUNCHER_README.md     # This file
```

## Security Features

- ✅ Automatic dependency checking and installation
- ✅ Secure credential storage and management
- ✅ Vespia integration with proper authentication
- ✅ Graceful fallback when credentials are not configured

## Troubleshooting

If you encounter issues:

1. **Dependencies**: Run `./run_risk_assessment.sh check_deps`
2. **Credentials**: Run `./run_risk_assessment.sh credentials test`
3. **Setup**: Run `./run_risk_assessment.sh credentials setup_vespia`
4. **Management**: Run `./run_risk_assessment.sh manage_creds`

The unified system ensures that the secure credential management is always available and properly integrated into the workflow. 