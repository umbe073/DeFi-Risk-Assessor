#!/usr/bin/env python3
"""
PDF Guide Generator for Credential Management
Creates a professional PDF guide similar to the DeFi Risk Assessment Guide
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import os
from pathlib import Path

def create_pdf_guide():
    """Create a comprehensive PDF guide for credential management"""
    
    # Create the PDF file
    output_file = "Credential_Management_Guide_v1.0.pdf"
    doc = SimpleDocTemplate(output_file, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=8,
        spaceBefore=12,
        textColor=colors.darkblue
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )
    
    code_style = ParagraphStyle(
        'CustomCode',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Courier',
        leftIndent=20,
        spaceAfter=6
    )
    
    # Build the story
    story = []
    
    # Title page
    story.append(Paragraph("🔐 Secure Credential Management System", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("DeFi Risk Assessment Tool - Vespia Integration", heading1_style))
    story.append(Spacer(1, 30))
    story.append(Paragraph("Version 1.0", body_style))
    story.append(Paragraph("July 2024", body_style))
    story.append(PageBreak())
    
    # Table of Contents
    story.append(Paragraph("Table of Contents", heading1_style))
    story.append(Spacer(1, 20))
    
    toc_data = [
        ["1. Overview", "3"],
        ["2. Quick Start Guide", "4"],
        ["3. Credential Management", "6"],
        ["4. Security Features", "8"],
        ["5. Troubleshooting", "10"],
        ["6. Best Practices", "12"],
        ["7. Technical Details", "14"]
    ]
    
    toc_table = Table(toc_data, colWidths=[4*inch, 1*inch])
    toc_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(toc_table)
    story.append(PageBreak())
    
    # 1. Overview
    story.append(Paragraph("1. Overview", heading1_style))
    story.append(Paragraph("""
    The Secure Credential Management System provides encrypted storage for sensitive API credentials, 
    specifically designed for the Vespia AML/KYC/KYB integration in the DeFi Risk Assessment tool. 
    This system ensures that your Vespia login credentials are never stored in plain text and are 
    protected by a master password using industry-standard encryption.
    """, body_style))
    
    story.append(Paragraph("Key Features:", heading2_style))
    features = [
        "🔐 AES-256 encryption for all credentials",
        "🛡️ Master password protection with PBKDF2",
        "🧹 Automatic memory cleanup after use",
        "📁 Git-safe file management",
        "🔄 Easy credential updates and management",
        "⚡ Automated integration with risk assessment"
    ]
    
    for feature in features:
        story.append(Paragraph(f"• {feature}", body_style))
    
    story.append(PageBreak())
    
    # 2. Quick Start Guide
    story.append(Paragraph("2. Quick Start Guide", heading1_style))
    
    story.append(Paragraph("Automated Launch (Recommended)", heading2_style))
    story.append(Paragraph("""
    The easiest way to use the system is through the automated risk assessment script:
    """, body_style))
    story.append(Paragraph("""
    cd scripts/v1.2
    ./run_risk_assessment.sh
    """, code_style))
    
    story.append(Paragraph("""
    This script automatically checks dependencies, verifies credentials, and runs the risk assessment 
    with Vespia integration. If credentials are not configured, it will prompt you to set them up.
    """, body_style))
    
    story.append(Paragraph("Manual Credential Management", heading2_style))
    story.append(Paragraph("""
    For direct credential management, use the interactive tool:
    """, body_style))
    story.append(Paragraph("""
    python3 run_with_venv.py manage_creds
    """, code_style))
    
    story.append(PageBreak())
    
    # 3. Credential Management
    story.append(Paragraph("3. Credential Management", heading1_style))
    
    story.append(Paragraph("How to Modify Email and Password", heading2_style))
    story.append(Paragraph("""
    The system provides multiple ways to manage your Vespia credentials:
    """, body_style))
    
    story.append(Paragraph("Option 1: Interactive Management Tool (Easiest)", heading2_style))
    story.append(Paragraph("""
    Run the interactive tool and choose from the menu:
    """, body_style))
    story.append(Paragraph("""
    python3 run_with_venv.py manage_creds
    """, code_style))
    
    story.append(Paragraph("Available Options:", body_style))
    options = [
        "1. View current credentials - See your email (password hidden)",
        "2. Update email - Change only the email address",
        "3. Update password - Change only the password",
        "4. Update both email and password - Change both at once",
        "5. Remove credentials - Delete all credentials",
        "6. Test credentials - Verify credentials are working",
        "7. Exit - Close the tool"
    ]
    
    for option in options:
        story.append(Paragraph(f"• {option}", body_style))
    
    story.append(Paragraph("Option 2: Command Line Setup", heading2_style))
    story.append(Paragraph("""
    Use direct commands for specific operations:
    """, body_style))
    story.append(Paragraph("""
    # Setup new credentials
    python3 run_with_venv.py credentials setup_vespia
    
    # Test credentials
    python3 run_with_venv.py credentials test
    
    # Remove credentials
    python3 run_with_venv.py credentials remove
    """, code_style))
    
    story.append(PageBreak())
    
    # 4. Security Features
    story.append(Paragraph("4. Security Features", heading1_style))
    
    story.append(Paragraph("Encryption", heading2_style))
    story.append(Paragraph("""
    • Algorithm: AES-256 encryption
    • Key Derivation: PBKDF2 with 100,000 iterations
    • Salt: Random 16-byte salt for each master key
    • Storage: Encrypted binary files
    """, body_style))
    
    story.append(Paragraph("Protection", heading2_style))
    story.append(Paragraph("""
    • Master Password: Single password protects all credentials
    • No Plain Text: Credentials never stored in plain text
    • Memory Cleanup: Credentials cleared from memory after use
    • Git Ignored: All credential files automatically ignored
    """, body_style))
    
    story.append(Paragraph("Files Created", heading2_style))
    story.append(Paragraph("""
    • .secure_credentials - Encrypted credential storage
    • .master_key - Encrypted master key (salt + key)
    • Both files are automatically added to .gitignore
    """, body_style))
    
    story.append(PageBreak())
    
    # 5. Troubleshooting
    story.append(Paragraph("5. Troubleshooting", heading1_style))
    
    story.append(Paragraph("Common Issues", heading2_style))
    
    story.append(Paragraph("Invalid master password", heading2_style))
    story.append(Paragraph("""
    • Make sure you're using the correct master password
    • Passwords are case-sensitive
    • Try the setup process again if needed
    """, body_style))
    
    story.append(Paragraph("Credentials not found", heading2_style))
    story.append(Paragraph("""
    • Run 'python3 run_with_venv.py manage_creds' to set up credentials
    • Check that you have a Vespia account
    """, body_style))
    
    story.append(Paragraph("Permission denied", heading2_style))
    story.append(Paragraph("""
    • Check file permissions on credential files
    • Make sure you have write access to the directory
    """, body_style))
    
    story.append(Paragraph("Import error", heading2_style))
    story.append(Paragraph("""
    • Make sure 'cryptography' package is installed
    • Ensure you're in the correct directory
    """, body_style))
    
    story.append(PageBreak())
    
    # 6. Best Practices
    story.append(Paragraph("6. Best Practices", heading1_style))
    
    story.append(Paragraph("Master Password", heading2_style))
    story.append(Paragraph("""
    • Use a strong, unique password
    • Minimum 8 characters
    • Include numbers, symbols, mixed case
    • Don't reuse passwords from other services
    """, body_style))
    
    story.append(Paragraph("Credential Updates", heading2_style))
    story.append(Paragraph("""
    • Update credentials when you change your Vespia password
    • Test credentials after any changes
    • Keep your master password secure
    """, body_style))
    
    story.append(Paragraph("Environment", heading2_style))
    story.append(Paragraph("""
    • Use on trusted machines only
    • Lock your computer when away
    • Consider full disk encryption
    """, body_style))
    
    story.append(PageBreak())
    
    # 7. Technical Details
    story.append(Paragraph("7. Technical Details", heading1_style))
    
    story.append(Paragraph("File Structure", heading2_style))
    story.append(Paragraph("""
    All credential management files are organized in the 'credential_management' folder:
    """, body_style))
    story.append(Paragraph("""
    credential_management/
    ├── secure_credentials.py      # Core encryption system
    ├── manage_credentials.py      # Interactive management tool
    ├── setup_vespia.py           # Easy setup wizard
    ├── CREDENTIAL_MANAGEMENT_GUIDE.md
    ├── SECURE_CREDENTIALS_README.md
    ├── VESPIA_INTEGRATION.md
    └── SETUP_COMPLETE.md
    """, code_style))
    
    story.append(Paragraph("Integration Points", heading2_style))
    story.append(Paragraph("""
    The credential system integrates with:
    """, body_style))
    story.append(Paragraph("""
    • run_risk_assessment.sh - Automated script with credential checks
    • run_with_venv.py - Environment-aware runner
    • defi_complete_risk_assessment.py - Main risk assessment tool
    • Vespia API - AML/KYC/KYB verification services
    """, body_style))
    
    story.append(Paragraph("Commands Available", heading2_style))
    story.append(Paragraph("""
    • python3 run_with_venv.py check_deps - Check dependencies
    • python3 run_with_venv.py manage_creds - Interactive credential management
    • python3 run_with_venv.py credentials [command] - Direct credential operations
    • python3 run_with_venv.py risk_assessment - Run risk assessment
    • ./run_risk_assessment.sh - Automated launch with credential checks
    """, body_style))
    
    # Build the PDF
    doc.build(story)
    print(f"✅ PDF guide created successfully: {output_file}")

if __name__ == "__main__":
    create_pdf_guide() 