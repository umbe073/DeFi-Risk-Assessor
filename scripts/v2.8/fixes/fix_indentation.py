#!/usr/bin/env python3

def fix_indentation():
    """Fix indentation in the except block"""
    
    # Read the file
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'r') as f:
        lines = f.readlines()
    
    # Fix the indentation around line 1964
    for i, line in enumerate(lines):
        if 'except:' in line and i >= 1960 and i <= 1970:
            # Fix the indentation of the pass statement
            if lines[i+1].strip() == 'pass':
                lines[i+1] = '                    pass\n'
                # Remove the extra empty lines
                for j in range(i+2, i+9):
                    if j < len(lines):
                        lines[j] = ''
                break
    
    # Write the fixed file
    with open('scripts/v1.0/defi_complete_risk_assessment.py', 'w') as f:
        f.writelines(lines)
    
    print("Indentation fixed!")

if __name__ == "__main__":
    fix_indentation()