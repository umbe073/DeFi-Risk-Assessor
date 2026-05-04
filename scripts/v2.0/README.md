# DeFi Risk Assessment Suite v2.0

## Overview
A comprehensive DeFi risk assessment tool with secure credential management, unified app icon support, and enhanced macOS compatibility.

## Key Features

### 🔐 Secure Credential Management
- **Vespia Integration**: Secure storage and management of API credentials
- **Encrypted Storage**: All sensitive data is encrypted using industry-standard cryptography
- **Credential Manager GUI**: User-friendly interface for managing API keys and credentials
- **Chain ID Management**: Secure configuration of blockchain chain IDs for multi-chain support

### 🖥️ System Tray Integration
- **Unified App Icon**: All processes run under a single crypto.icns icon
- **Background Operation**: System tray runs in background mode without dock icons
- **Process Management**: Centralized management of all dashboard components
- **Window Management**: Automatic window positioning and focus management

### 🛡️ macOS Compatibility
- **Enhanced Tkinter Support**: Fixed compatibility issues with macOS
- **Environment Variables**: Comprehensive environment setup for stability
- **App Bundle Integration**: Proper integration with macOS app bundles
- **Background Process Support**: Runs as accessory application

### 📊 Risk Assessment Features
- **Multi-Chain Support**: Ethereum, BSC, Polygon, Arbitrum, Optimism, Avalanche, Fantom, Sonic
- **Real-time Data**: Live market data from multiple sources
- **API Integration**: Comprehensive API support with fallback mechanisms
- **Report Generation**: Detailed risk assessment reports in multiple formats

## Installation

### Prerequisites
- Python 3.9+ (recommended for Apple Silicon Macs)
- macOS 10.15+ (Catalina or later)
- Homebrew (for Python installation)

### Setup
1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the system tray launcher:
   ```bash
   ./scripts/v2.0/run_risk_assessment.sh
   ```

## Usage

### Launching the System Tray
```bash
cd /Users/amlfreak/Desktop/venv
./scripts/v2.0/run_risk_assessment.sh
```

### Managing Credentials
```bash
./scripts/v2.0/run_risk_assessment.sh credentials setup
./scripts/v2.0/run_risk_assessment.sh credentials list
./scripts/v2.0/run_risk_assessment.sh credentials test
```

### Chain ID Management
```bash
python3 scripts/v2.0/credential_management/launch_chains.py
```

### Token Management
The system uses dynamic token mappings generated from `data/tokens.csv`. You can manage tokens in two ways:

#### Interactive Token Editor (Recommended)
1. **Open the dashboard** and click "Edit Token List"
2. **Use the interactive editor** to:
   - Add new tokens with a user-friendly form
   - Edit existing tokens by double-clicking
   - Remove tokens with confirmation
   - Import/export CSV files
   - Save changes with automatic token mapping updates

#### Manual CSV Editing
1. **Edit the token list**: Modify `data/tokens.csv` with the following format:
   ```csv
   address,chain,symbol,name
   0x1234...,ethereum,TOKEN,Token Name
   ```

2. **Regenerate mappings**: Run the update script:
   ```bash
   cd scripts/v2.0
   ./update_token_mappings.sh
   ```

3. **Verify changes**: The system will automatically use the updated token mappings.

**Note**: The `token_mappings.py` file is auto-generated and should not be edited manually.

## File Structure

```
scripts/v2.0/
├── dashboard/
│   ├── system_tray.py          # Main system tray application
│   ├── process_manager.py      # Process management and launch
│   ├── tkinter_compatibility.py # macOS tkinter compatibility
│   ├── defi_dashboard.py       # Main dashboard interface
│   ├── api_service_dashboard.py # API service management
│   ├── token_editor.py         # Interactive token editor
│   └── settings_window.py      # Settings and configuration
├── credential_management/
│   ├── gui_chains.py           # Chain ID management GUI
│   ├── gui_credentials.py      # Credential management GUI
│   ├── secure_credentials.py   # Secure credential storage
│   ├── launch_chains.py        # Chain manager launcher
│   └── launch_credentials.py   # Credential manager launcher
├── run_risk_assessment.sh      # Main launcher script
├── defi_complete_risk_assessment_clean.py # Core risk assessment
├── webhook_server.py           # Webhook server for real-time data
├── token_mappings.py           # Token symbol mappings (auto-generated)
├── generate_token_mappings.py  # Token mapping generator
└── update_token_mappings.sh    # Token mapping update script
```

## Environment Variables

The system uses comprehensive environment variables for macOS compatibility:

- `BUNDLE_IDENTIFIER`: Unified app bundle identifier
- `NSApplicationActivationPolicy`: Set to 'accessory' for background operation
- `LSUIElement`: Set to 'true' to hide from dock
- `TK_SILENCE_DEPRECATION`: Suppress tkinter deprecation warnings
- `TK_FORCE_BASIC_MODE`: Force basic tkinter mode for compatibility

## Dependencies

### Core Dependencies
- `tkinter`: GUI framework (built-in)
- `pystray`: System tray functionality
- `PIL/Pillow`: Image processing for icons
- `cryptography`: Secure credential storage
- `requests`: HTTP client for API calls
- `python-dotenv`: Environment variable management

### Optional Dependencies
- `pandas`: Data manipulation and analysis
- `openpyxl`: Excel file generation
- `matplotlib`: Chart generation
- `seaborn`: Statistical data visualization

## Troubleshooting

### Common Issues

1. **Dual Icons in Dock**: Ensure all environment variables are set correctly
2. **Tkinter Crashes**: Verify Python 3.9+ is installed and environment variables are set
3. **Import Errors**: Check that all dependencies are installed
4. **Credential Issues**: Run credential setup wizard

### Debug Mode
```bash
export DEBUG=1
./scripts/v2.0/run_risk_assessment.sh
```

## Version History

### v2.0 (Current)
- ✅ Unified app icon implementation
- ✅ Enhanced macOS compatibility
- ✅ Fixed import errors and crashes
- ✅ Improved credential management
- ✅ Streamlined file structure
- ✅ Comprehensive environment variable setup

### v1.5 (Previous)
- Basic system tray functionality
- Initial credential management
- Basic macOS compatibility

## Contributing

This tree is part of a **private, proprietary** repository. Contributing is limited to **authorized** collaborators under company agreements—see the root `CONTRIBUTING.md` and `LICENSE`.

## License

Proprietary — see the repository root `LICENSE` (Hodler Suite UAB, Lithuania).

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs in `/tmp/defi_dashboard_locks/`
3. Run in debug mode for detailed error information
4. Create an issue with detailed error logs 