# DeFi Risk Assessment Suite - Test Files

This directory contains all test files for the DeFi Risk Assessment Suite, organized by category.

## Directory Structure

### `/api/` - API Testing

- `test_api_calls.py` - Tests for general API calls and responses
- `test_api_endpoints.py` - Tests for specific API endpoint functionality
- `test_dune_api.py` - Tests for Dune Analytics API integration

### `/dashboard/` - Dashboard Testing

- `test_api_dashboard_minimal.py` - Minimal tests for API dashboard functionality
- `test_minimal_tkinter.py` - Tests for tkinter GUI components
- `test_system_tray.py` - Tests for system tray functionality

### `/integration/` - Integration Testing

- `test_cache_integration.py` - Tests for cache system integration
- `test_dashboard_data_fetching.py` - Tests for dashboard data fetching
- `test_priority_cache_system.py` - Tests for priority cache system

### `/system/` - System Testing

- `test_icon_hiding.py` - Tests for icon hiding functionality
- `test_subprocess_icons.py` - Tests for subprocess icon management

### Root Level Tests

- `test_core.py` - Core functionality tests
- `test_scorers.py` - Risk scoring algorithm tests

## Running Tests

To run all tests:

```bash
cd /Users/amlfreak/Desktop/venv/scripts/v2.0
python -m pytest tests/
```

To run specific test categories:

```bash
# API tests only
python -m pytest tests/api/

# Dashboard tests only
python -m pytest tests/dashboard/

# Integration tests only
python -m pytest tests/integration/

# System tests only
python -m pytest tests/system/
```

## Test Organization

Tests are organized by functionality to make it easier to:

- Run specific test suites
- Maintain and update tests
- Identify test coverage gaps
- Debug specific components

Each test file should be self-contained and not depend on other test files for execution.
