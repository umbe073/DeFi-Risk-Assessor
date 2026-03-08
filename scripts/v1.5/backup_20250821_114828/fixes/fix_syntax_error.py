#!/usr/bin/env python3

def fix_syntax_errors():
    """Fix syntax errors in defi_complete_risk_assessment.py"""
    
    # Read the file
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'r') as f:
        lines = f.readlines()
    
    # Fix the empty except block and remove misplaced return statement
    for i, line in enumerate(lines):
        # Fix empty except block around line 1964
        if 'except:' in line and i >= 1960 and i <= 1970:
            if lines[i+1].strip().startswith('return {'):
                # Remove the misplaced return statement
                lines[i+1] = '                pass\n'
                lines[i+2] = '                \n'
                lines[i+3] = '                \n'
                lines[i+4] = '                \n'
                lines[i+5] = '                \n'
                lines[i+6] = '                \n'
                lines[i+7] = '                \n'
                break
    
    # Write the fixed file
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'w') as f:
        f.writelines(lines)
    
    print("Syntax errors fixed!")

if __name__ == "__main__":
    fix_syntax_errors()