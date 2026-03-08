#!/usr/bin/env python3

def fix_syntax_error():
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'r') as f:
        lines = f.readlines()
    
    # Find the problematic line and fix it
    for i, line in enumerate(lines):
        if 'return {' in line and i == 1967:  # 0-indexed, so line 1968
            # Replace the incomplete return statement
            lines[i] = '''            return {
                'token': token_address,
                'chain': chain,
                'risk_score': 150,
                'risk_category': 'Extreme Risk',
                'details': {'error': str(e)},
                'component_scores': {}
            }
'''
            break
    
    # Write the fixed content back
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'w') as f:
        f.writelines(lines)

if __name__ == "__main__":
    fix_syntax_error()
    print("Syntax error fixed!")