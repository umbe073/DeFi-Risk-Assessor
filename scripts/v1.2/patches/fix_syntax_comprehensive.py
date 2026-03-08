#!/usr/bin/env python3

def fix_syntax_error():
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'r') as f:
        content = f.read()
    
    # Find the problematic pattern and replace it
    # Look for the incomplete return statement followed by the comment
    pattern = r'return \{\s*\n\s*# Scoring methods'
    replacement = '''return {
                'token': token_address,
                'chain': chain,
                'risk_score': 150,
                'risk_category': 'Extreme Risk',
                'details': {'error': str(e)},
                'component_scores': {}
            }

    # Scoring methods'''
    
    # Replace the pattern
    new_content = content.replace(pattern, replacement)
    
    # Write the fixed content back
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'w') as f:
        f.write(new_content)

if __name__ == "__main__":
    fix_syntax_error()
    print("Comprehensive syntax error fix applied!")