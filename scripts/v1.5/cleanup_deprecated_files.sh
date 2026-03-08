#!/bin/bash

# Cleanup script for v1.5 - Remove deprecated files while preserving essential ones
# This script removes files that are no longer needed after v2.0 migration

echo "🧹 Cleaning up deprecated files from v1.5..."

# Files to KEEP (essential files)
ESSENTIAL_FILES=(
    "run_risk_assessment.sh"
    "dashboard/"
    "credential_management/"
    "README.md"
    "defi_complete_risk_assessment_clean.py"
    "webhook_server.py"
    "token_mappings.py"
)

# Files to REMOVE (deprecated/duplicate files)
DEPRECATED_FILES=(
    # API test and debug files
    "test_api_endpoints.py"
    "test_bitquery_working.py"
    "test_new_bitquery_key.py"
    "test_bitquery_api_key.py"
    "test_bitquery_fix.py"
    "check_bitquery_free_tier.py"
    "debug_bitquery_alternatives.py"
    "debug_api_auth.py"
    "debug_api_issues.py"
    "diagnose_api_issues.py"
    
    # API fix files
    "fix_api_authentication.py"
    "fix_api_errors.py"
    "fix_api_keys_guide.py"
    "fix_final_requirements.py"
    "fix_final_two_tokens.py"
    "fix_incoherent_values.py"
    "fix_xlsx_comprehensive.py"
    "placeholder_api_fixes.py"
    
    # API implementation files
    "api_implementations.py"
    "api_integration.py"
    "final_api_fixes.py"
    "enhanced_comprehensive_parallel_apis.py"
    "enhanced_parallel_apis.py"
    "parallel_api_endpoints.py"
    "comprehensive_api_implementation.py"
    "enhanced_api_integrations.py"
    "comprehensive_api_test.py"
    
    # Data processing files
    "complete_fallback_data.py"
    "cleanup_fallback_data.py"
    "update_symbol_cache.py"
    "webhook_data_updater.py"
    "enhanced_market_data_fetcher.py"
    "real_time_data_fetcher.py"
    "working_progress_bar.py"
    
    # Quality enhancement files
    "apply_quality_enhancements.py"
    "enhance_report_quality.py"
    "achieve_full_market_coverage.py"
    
    # Documentation files
    "COMPREHENSIVE_ERROR_ANALYSIS_AND_FIXES.md"
    "FINAL_ERROR_FIX_SUMMARY.md"
    "COMPREHENSIVE_PARALLEL_API_SUMMARY.md"
    "PARALLEL_API_IMPLEMENTATION_SUMMARY.md"
    "error_fix_implementation.md"
    "FINAL_ERROR_FIXES_SUMMARY.md"
    "REMAINING_ERROR_FIXES.md"
    "API_ERROR_FIXES.md"
    "FIXES_APPLIED_SUMMARY.md"
    "FINAL_FIXES_SUMMARY.md"
    "API_FIXES_SUMMARY.md"
    "TWITTER_RATE_LIMIT_FIX_SUMMARY.md"
    "FINAL_CLEANUP_AND_IMPROVEMENTS_SUMMARY.md"
    
    # JSON and data files
    "api_fixes_summary.json"
    "comprehensive_error_fixes.json"
    "comprehensive_api_endpoints.json"
    
    # Backup files
    "defi_complete_risk_assessment_clean.py.backup"
    "defi_complete_risk_assessment_fixed.py"
    
    # Test files
    "santiment_test.py"
    "master_automation.py"
    "social_media_checker.py"
    "automated_api_verification.py"
    
    # Index and changelog files
    "PROFESSIONAL_SCRIPTS_INDEX.md"
    "CHANGELOG_v1.4_to_v1.5.txt"
    "SCRIPTS_INDEX.txt"
)

# Function to check if a file is essential
is_essential() {
    local file="$1"
    for essential in "${ESSENTIAL_FILES[@]}"; do
        if [[ "$file" == "$essential" || "$file" == *"$essential"* ]]; then
            return 0
        fi
    done
    return 1
}

# Function to check if a file should be removed
should_remove() {
    local file="$1"
    for deprecated in "${DEPRECATED_FILES[@]}"; do
        if [[ "$file" == "$deprecated" ]]; then
            return 0
        fi
    done
    return 1
}

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo ""

# Create backup directory
BACKUP_DIR="$SCRIPT_DIR/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "📦 Creating backup in: $BACKUP_DIR"

# Process all files in the directory
for file in *; do
    if [[ -f "$file" ]]; then
        if should_remove "$file"; then
            echo "🗑️  Removing deprecated file: $file"
            mv "$file" "$BACKUP_DIR/"
        elif is_essential "$file"; then
            echo "✅ Keeping essential file: $file"
        else
            echo "⚠️  Unknown file (keeping): $file"
        fi
    elif [[ -d "$file" && "$file" != "backup_"* ]]; then
        if is_essential "$file"; then
            echo "✅ Keeping essential directory: $file/"
        else
            echo "🗑️  Removing deprecated directory: $file/"
            mv "$file" "$BACKUP_DIR/"
        fi
    fi
done

echo ""
echo "🧹 Cleanup completed!"
echo "📦 Deprecated files backed up to: $BACKUP_DIR"
echo "✅ Essential files preserved"
echo ""
echo "📋 Summary:"
echo "   - Essential files: ${#ESSENTIAL_FILES[@]}"
echo "   - Deprecated files: ${#DEPRECATED_FILES[@]}"
echo "   - Backup location: $BACKUP_DIR"
echo ""
echo "💡 To restore files if needed:"
echo "   cp -r $BACKUP_DIR/* ."
