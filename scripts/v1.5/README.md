# Performance Validation Script

This script validates the performance of the DeFi Risk Assessment System with large datasets.

## Prerequisites

- Python 3.7+
- Virtual environment with required dependencies
- `psutil` module installed

## Running the Script

### Option 1: Using the Shell Script (Recommended)

```bash
# From the project root directory
./scripts/v1.4/run_performance_validation.sh
```

This script will:
- Automatically activate the virtual environment
- Check for required dependencies
- Run the performance validation

### Option 2: Manual Execution

```bash
# Activate virtual environment first
source bin/activate

# Run the performance validation
python3 scripts/v1.4/performance_validation.py
```

### Option 3: Direct Execution (if virtual environment is already activated)

```bash
python3 scripts/v1.4/performance_validation.py
```

## Troubleshooting

### psutil Import Error

If you see an error like "Import 'psutil' could not be resolved from source":

1. **Ensure virtual environment is activated:**
   ```bash
   source bin/activate
   ```

2. **Check if psutil is installed:**
   ```bash
   pip list | grep psutil
   ```

3. **Install psutil if missing:**
   ```bash
   pip install psutil
   ```

4. **Verify installation:**
   ```bash
   python3 -c "import psutil; print('psutil available')"
   ```

## What the Script Tests

1. **Scoring Performance**: Tests how fast the scoring algorithms process large datasets
2. **Concurrent Processing**: Tests multi-threaded processing capabilities
3. **Memory Efficiency**: Tests memory usage with large datasets
4. **Cache Performance**: Tests the caching system performance

## Output

The script generates:
- Console output with performance metrics
- `performance_validation_report.json` with detailed results
- System resource monitoring data

## Expected Performance Metrics

- **Scoring**: 1000+ scores per second
- **Concurrent Processing**: 500+ tokens per second
- **Memory Efficiency**: < 1MB per 1000 tokens
- **Cache Performance**: 100% hit rate for cached data 