#!/usr/bin/env python3
"""
Working Progress Bar for DeFi Risk Assessment
This version actually updates during script execution using a simple GUI
"""

import os
import sys
import time
import threading
import subprocess
from typing import Optional
import shutil
import glob
import base64

class WorkingProgressBar:
    """
    Working progress bar that actually updates during script execution
    Uses a simple GUI window that updates in real-time
    """
    
    def __init__(self, total_tokens: int, title: str = "DeFi Risk Assessment"):
        self.total_tokens = total_tokens
        self.title = title
        self.current_token = 0
        self.current_phase = 0
        self.phases_per_token = 3  # Data fetching, Analysis, Finalizing
        self.total_phases = total_tokens * self.phases_per_token
        self.completed_phases = 0
        self.is_running = False
        self.lock = threading.Lock()
        self.finished = False
        
        # Progress bar phases for each token
        self.token_phases = [
            "Fetching token data",
            "Analyzing security & market data",
            "Generating final reports..."
        ]
        
        # Store logo HTML for reuse
        self.logo_html = ""
        
        # Create the progress bar window
        self._create_progress_window()
    


    def _create_progress_window(self):
        """Create a working progress bar using a simple GUI"""
        try:
            # Only add meta refresh if not finished
            meta_refresh = '<meta http-equiv="refresh" content="1">' if self.completed_phases < self.total_phases else ''

            # Copy logo files to /tmp/ so they can be referenced from the HTML
            logo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'Logos'))
            # Logo directory found
            if not os.path.exists(logo_dir):
                print(f"[WARNING] Logo directory not found: {logo_dir}")
                # Try alternative paths
                alternative_paths = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs', 'Logos')),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'docs', 'Logos')),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'docs', 'Logos')),
                    '/Users/amlfreak/Desktop/venv/docs/Logos'  # Absolute path as fallback
                ]
                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        logo_dir = alt_path
                        print(f"[DEBUG] Found logo directory: {logo_dir}")
                        break
                else:
                    print(f"[ERROR] No logo directory found in any of the attempted paths")
                    logo_dir = None
            # Updated logo files list with all available logos (excluding Compliance Logo)
            logo_files = [
                '1inch-exchange-logo.png',
                'bitquery-logo.jpg',
                'coingecko logo.png',
                'defillama-logo.jpg',
                '450px-EtherScan-Logo.png',
                '254-2541523_welcome-cointelegraph-logo.png',
                '360_F_968950664_bwRliEbRitVbRMOO7zfRg3P4K9RYK0E9.jpg',
                'Alchemy-Logo-Vector-300x300.jpg',
                'nqyB2SI.jpeg',
                'x-new-twitter-icon-twitter-rebrand-little-bird-to-x-letter-symbol-twitter-x-new-logo-vcetor-elon-musk-change-social-media-logo-novation-set-of-twitter-new-and-old-round-and-square-logo-free-vector.jpg',
                'telegram-logo-bundle-icon-set-telegram-app-editable-svg-transparent-background-premium-social-media-design-for-digital-download-free-vector.jpg'
            ]
            if logo_dir:
                for logo in logo_files:
                    src = os.path.join(logo_dir, logo)
                    dst = os.path.join('/tmp', logo)
                    if os.path.exists(src):
                        try:
                            shutil.copyfile(src, dst)
                            # Logo copied successfully
                        except Exception as e:
                            print(f"Warning: Could not copy logo {logo}: {e}")
                    else:
                        print(f"[WARNING] Logo file not found: {src}")
            else:
                print("[WARNING] No logo directory available - logos will not be displayed")
            
            # Create logo HTML with embedded base64 images for proper display
            logo_html = ""
            if logo_dir:
                for logo in logo_files:
                    src = os.path.join(logo_dir, logo)
                    if os.path.exists(src):
                        try:
                            # Read and encode logo as base64
                            with open(src, 'rb') as f:
                                logo_data = f.read()
                                logo_b64 = base64.b64encode(logo_data).decode('utf-8')
                                
                                # Determine MIME type based on file extension
                                if logo.lower().endswith('.png'):
                                    mime_type = 'image/png'
                                elif logo.lower().endswith('.jpg') or logo.lower().endswith('.jpeg'):
                                    mime_type = 'image/jpeg'
                                else:
                                    mime_type = 'image/png'
                                
                                logo_html += f'<img src="data:{mime_type};base64,{logo_b64}" style="height: 60px; width: auto; border-radius: 12px; background: #fff; padding: 2px 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); opacity: 0.8; transition: opacity 0.2s; object-fit: contain;" alt="{logo}" onerror="this.style.display=\'none\'">'
                                # Logo encoded successfully
                        except Exception as e:
                            print(f"[WARNING] Could not encode logo {logo}: {e}")
                            # Fallback to colored box
                            service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                            logo_html += f'<div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">{service_name}</div>'
                    else:
                        # Fallback to colored box if logo not found
                        service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                        logo_html += f'<div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">{service_name}</div>'
            
            # Split logos into two rows: first 5 on top, last 6 on bottom (including Telegram)
            logo_files_split = logo_files[:5], logo_files[5:]
            top_logo_html = ""
            bottom_logo_html = ""
            
            if logo_dir:
                # Generate top row (first 5 logos)
                for logo in logo_files_split[0]:
                    src = os.path.join(logo_dir, logo)
                    if os.path.exists(src):
                        try:
                            with open(src, 'rb') as f:
                                logo_data = f.read()
                                logo_b64 = base64.b64encode(logo_data).decode('utf-8')
                                
                                if logo.lower().endswith('.png'):
                                    mime_type = 'image/png'
                                elif logo.lower().endswith('.jpg') or logo.lower().endswith('.jpeg'):
                                    mime_type = 'image/jpeg'
                                else:
                                    mime_type = 'image/png'
                                
                                top_logo_html += f'<img src="data:{mime_type};base64,{logo_b64}" style="height: 95px; width: auto; border-radius: 14px; background: #fff; padding: 3px 10px; box-shadow: 0 3px 12px rgba(0,0,0,0.1); opacity: 0.9; transition: opacity 0.2s; object-fit: contain;" alt="{logo}" onerror="this.style.display=\'none\'">'
                        except Exception as e:
                            service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                            top_logo_html += f'<div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">{service_name}</div>'
                    else:
                        service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                        top_logo_html += f'<div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">{service_name}</div>'
                
                # Generate bottom row (last 5 logos)
                for logo in logo_files_split[1]:
                    src = os.path.join(logo_dir, logo)
                    if os.path.exists(src):
                        try:
                            with open(src, 'rb') as f:
                                logo_data = f.read()
                                logo_b64 = base64.b64encode(logo_data).decode('utf-8')
                                
                                if logo.lower().endswith('.png'):
                                    mime_type = 'image/png'
                                elif logo.lower().endswith('.jpg') or logo.lower().endswith('.jpeg'):
                                    mime_type = 'image/jpeg'
                                else:
                                    mime_type = 'image/png'
                                
                                bottom_logo_html += f'<img src="data:{mime_type};base64,{logo_b64}" style="height: 100px; width: auto; border-radius: 12px; background: #fff; padding: 3px 8px; box-shadow: 0 3px 12px rgba(0,0,0,0.1); opacity: 0.9; transition: opacity 0.2s; object-fit: contain;" alt="{logo}" onerror="this.style.display=\'none\'">'
                        except Exception as e:
                            service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                            bottom_logo_html += f'<div style="height: 50px; width: 50px; background: linear-gradient(45deg, #667eea, #764ba2); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">{service_name}</div>'
                    else:
                        service_name = logo.split('-')[0].upper() if '-' in logo else logo.split('.')[0].upper()
                        bottom_logo_html += f'<div style="height: 50px; width: 50px; background: linear-gradient(45deg, #667eea, #764ba2); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">{service_name}</div>'
            
            # Store both logo HTMLs for reuse in updates
            self.top_logo_html = top_logo_html
            self.bottom_logo_html = bottom_logo_html
            
            # If no logos found, use colored boxes
            if not logo_html:
                logo_html = f"""
                    <div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff6b6b, #ee5a24); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">1INCH</div>
                    <div style="height: 60px; width: 60px; background: linear-gradient(45deg, #4834d4, #686de0); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">BITQ</div>
                    <div style="height: 60px; width: 60px; background: linear-gradient(45deg, #00d2d3, #54a0ff); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">CG</div>
                    <div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff9ff3, #f368e0); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">DEFI</div>
                    <div style="height: 60px; width: 60px; background: linear-gradient(45deg, #ff9f43, #feca57); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">ETH</div>
                """
            
            # All logos are now included in the main logo_files list above

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{self.title}</title>
                {meta_refresh}
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: white;
                        color: #333;
                        margin: 0;
                        padding: 20px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        position: relative;
                        overflow: hidden;
                    }}
                    .top-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 32px;
                        margin-bottom: 24px;
                        margin-top: 8px;
                        flex-wrap: wrap;
                    }}
                    .bottom-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 20px;
                        margin-top: 24px;
                        margin-bottom: 8px;
                        flex-wrap: wrap;
                    }}
                    .container {{
                        text-align: center;
                        max-width: 500px;
                        z-index: 1;
                        position: relative;
                    }}
                    .title {{
                        font-size: 24px;
                        margin-bottom: 30px;
                        color: #333;
                    }}
                    .progress-container {{
                        width: 100%;
                        background-color: #f0f0f0;
                        border-radius: 10px;
                        padding: 3px;
                        margin-bottom: 20px;
                    }}
                    .progress-bar {{
                        width: 0%;
                        height: 30px;
                        background: linear-gradient(90deg, #27ae60, #2ecc71);
                        border-radius: 8px;
                        transition: width 0.3s ease;
                    }}
                    .status {{
                        font-size: 16px;
                        margin-bottom: 10px;
                        color: #666;
                    }}
                    .details {{
                        font-size: 14px;
                        color: #999;
                    }}
                </style>
            </head>
            <body>
                <div class="top-logo-row">
                    {self.top_logo_html if hasattr(self, 'top_logo_html') else ""}
                </div>
                <div class="container">
                    <div class="title">{self.title}</div>
                    <div class="status" id="status">Initializing...</div>
                    <div class="progress-container">
                        <div class="progress-bar" id="progress"></div>
                    </div>
                    <div class="details" id="details">Token 0/{self.total_tokens} - Phase 0/3</div>
                </div>
                <div class="bottom-logo-row">
                    {self.bottom_logo_html if hasattr(self, 'bottom_logo_html') else ""}
                </div>
            </body>
            </html>
            """
            
            # Write HTML to a temporary file
            self.html_file = "/tmp/progress_bar.html"
            self.html_temp = "/tmp/progress_bar.html.tmp"
            with open(self.html_temp, 'w') as f:
                f.write(html_content)
            shutil.move(self.html_temp, self.html_file)
            
            # Open the HTML file in a browser
            subprocess.Popen(['open', self.html_file], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            self.is_running = True
            # Removed the initialization message
                
        except Exception as e:
            self.is_running = False
            with open("/tmp/progress_bar_error.log", "a") as logf:
                logf.write(f"[CREATE] {time.ctime()}: {e}\n")
    
    def update_phase(self, phase_index: int, message: Optional[str] = None):
        """Update to a specific phase for the current token"""
        with self.lock:
            if not self.is_running or self.finished:
                return
                
            self.current_phase = phase_index
            if message:
                self.current_message = message
            else:
                self.current_message = self.token_phases[phase_index]
            
            self._update_progress_bar()
    
    def update_title(self, new_title: str):
        """Update the progress bar title"""
        with self.lock:
            if not self.is_running or self.finished:
                return
                
            self.title = new_title
            self._update_progress_bar()
    
    def next_token(self, token_name: Optional[str] = None):
        """Move to the next token and reset phases"""
        with self.lock:
            if not self.is_running or self.finished:
                return
                
            self.current_token += 1
            self.current_phase = 0
            self.completed_phases = (self.current_token - 1) * self.phases_per_token
            
            token_display = f"Token {self.current_token}/{self.total_tokens}"
            if token_name:
                token_display += f" ({token_name})"
            
            self.current_message = f"{token_display} - {self.token_phases[0]}"
            self._update_progress_bar()
    
    def complete_phase(self, message: Optional[str] = None):
        """Complete the current phase and move to the next"""
        with self.lock:
            if not self.is_running or self.finished:
                return
                
            # Only increment if we haven't completed all phases for this token
            if self.completed_phases < self.total_phases:
                self.completed_phases += 1
                self.current_phase += 1
                
                # Ensure we don't exceed the total phases
                if self.completed_phases >= self.total_phases:
                    self.completed_phases = self.total_phases
                    self.current_phase = self.phases_per_token - 1
                    # Mark as completed to prevent further updates
                    self.is_running = False
            
            if message:
                self.current_message = message
            elif self.current_phase < len(self.token_phases):
                self.current_message = self.token_phases[self.current_phase]
            
            self._update_progress_bar()
    
    def _update_progress_bar(self):
        """Update the progress bar display"""
        if not self.is_running or self.finished:
            return
            
        try:
            # Calculate percentage (ensure it never exceeds 100%)
            percentage = min((self.completed_phases / self.total_phases) * 100 if self.total_phases > 0 else 0, 100.0)
            
            # Add a unique timestamp to force browser refresh
            timestamp = int(time.time() * 1000)
            
            # Only add meta refresh if not finished
            meta_refresh = '<meta http-equiv="refresh" content="1">' if self.completed_phases < self.total_phases else ''
            # If finished, add the countdown/auto-close JS
            countdown_html = ""
            if self.completed_phases >= self.total_phases:
                countdown_html = '''
                <div class="completion-message">
                    <div class="completion-title">Risk Assessment Completed!</div>
                    Please check the notification on the Apple Dialog window and see the results on the report.
                </div>
                <div class="countdown" id="countdown">This page will be closed in 5 seconds...</div>
                <script>
                    var countdown = 5;
                    var countdownElement = document.getElementById('countdown');
                    var timer = setInterval(function() {
                        countdown--;
                        if (countdown > 0) {
                            countdownElement.textContent = `This page will be closed in ${{countdown}} seconds...`;
                        } else {
                            countdownElement.textContent = 'Closing Now...';
                            clearInterval(timer);
                            setTimeout(function() {
                                window.close();
                            }, 500);
                        }
                    }, 1000);
                </script>
                '''
            # Use stored logo HTMLs instead of regenerating
            top_logo_html = self.top_logo_html if hasattr(self, 'top_logo_html') and self.top_logo_html else ""
            bottom_logo_html = self.bottom_logo_html if hasattr(self, 'bottom_logo_html') and self.bottom_logo_html else ""
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{self.title}</title>
                {meta_refresh}
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: white;
                        color: #333;
                        margin: 0;
                        padding: 20px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        position: relative;
                        overflow: hidden;
                    }}
                    .top-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 32px;
                        margin-bottom: 24px;
                        margin-top: 8px;
                        flex-wrap: wrap;
                    }}
                    .bottom-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 20px;
                        margin-top: 24px;
                        margin-bottom: 8px;
                        flex-wrap: wrap;
                    }}
                    .container {{
                        text-align: center;
                        max-width: 500px;
                        z-index: 1;
                        position: relative;
                    }}
                    .title {{
                        font-size: 24px;
                        margin-bottom: 30px;
                        color: #333;
                    }}
                    .progress-container {{
                        width: 100%;
                        background-color: #f0f0f0;
                        border-radius: 10px;
                        padding: 3px;
                        margin-bottom: 20px;
                    }}
                    .progress-bar {{
                        width: {percentage}%;
                        height: 30px;
                        background: linear-gradient(90deg, #27ae60, #2ecc71);
                        border-radius: 8px;
                        transition: width 0.3s ease;
                    }}
                    .status {{
                        font-size: 16px;
                        margin-bottom: 10px;
                        color: #666;
                    }}
                    .details {{
                        font-size: 14px;
                        color: #999;
                    }}
                </style>
            </head>
            <body>
                <div class="top-logo-row">
                    {top_logo_html}
                </div>
                <div class="container">
                    <div class="title">{self.title}</div>
                    <div class="status" id="status">{getattr(self, 'current_message', 'Initializing...')}</div>
                    <div class="progress-container">
                        <div class="progress-bar" id="progress"></div>
                    </div>
                    <div class="details">Token {self.current_token}/{self.total_tokens} - Phase {min(self.current_phase + 1, 3)}/3</div>
                    {countdown_html}
                </div>
                <div class="bottom-logo-row">
                    {bottom_logo_html}
                </div>
                <script>
                    // Force immediate refresh with timestamp
                    if (window.location.search !== '?t={timestamp}') {{
                        window.location.search = '?t={timestamp}';
                    }}
                </script>
            </body>
            </html>
            """
            
            self.html_temp = "/tmp/progress_bar.html.tmp"
            with open(self.html_temp, 'w') as f:
                f.write(html_content)
            shutil.move(self.html_temp, self.html_file)
            
            # Small delay to ensure browser processes the update
            time.sleep(0.3)  # Throttle updates to 0.3s
                
        except Exception as e:
            with open("/tmp/progress_bar_error.log", "a") as logf:
                logf.write(f"[UPDATE] {time.ctime()}: {e}\n")
            self.is_running = False
    
    def finish(self, message: str = "Risk assessment complete!"):
        """Complete the progress bar"""
        with self.lock:
            self.finished = True
            try:
                # Use stored logo HTMLs
                top_logo_html = self.top_logo_html if hasattr(self, 'top_logo_html') and self.top_logo_html else ""
                bottom_logo_html = self.bottom_logo_html if hasattr(self, 'bottom_logo_html') and self.bottom_logo_html else ""
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{self.title}</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            background-color: white;
                            color: #333;
                            margin: 0;
                            padding: 20px;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            position: relative;
                        }}
                        .top-logo-row {{
                            display: flex;
                            flex-direction: row;
                            justify-content: center;
                            align-items: center;
                            gap: 32px;
                            margin-bottom: 24px;
                            margin-top: 8px;
                            flex-wrap: wrap;
                        }}
                        .bottom-logo-row {{
                            display: flex;
                            flex-direction: row;
                            justify-content: center;
                            align-items: center;
                            gap: 20px;
                            margin-top: 24px;
                            margin-bottom: 8px;
                            flex-wrap: wrap;
                        }}
                        .container {{
                            text-align: center;
                            max-width: 500px;
                            z-index: 1;
                            position: relative;
                        }}
                        .title {{
                            font-size: 24px;
                            margin-bottom: 30px;
                            color: #333;
                        }}
                        .progress-container {{
                            width: 100%;
                            background-color: #34495e;
                            border-radius: 10px;
                            padding: 3px;
                            margin-bottom: 20px;
                        }}
                        .progress-bar {{
                            width: 100%;
                            height: 30px;
                            background: linear-gradient(90deg, #27ae60, #2ecc71);
                            border-radius: 8px;
                            transition: width 0.3s ease;
                        }}
                        .status {{
                            font-size: 16px;
                            margin-bottom: 10px;
                            color: #bdc3c7;
                        }}
                        .details {{
                            font-size: 14px;
                            color: #95a5a6;
                        }}
                        .completion-message {{
                            margin: 32px 0 0 0;
                        }}
                        .completion-title {{
                            font-size: 32px;
                            font-weight: bold;
                            color: #27ae60;
                            margin-bottom: 18px;
                        }}
                        .countdown {{
                            font-size: 22px;
                            color: #e74c3c;
                            margin-top: 32px;
                            font-weight: bold;
                        }}
                    </style>
                </head>
                <body>
                    <div class="top-logo-row">
                        {top_logo_html}
                    </div>
                    <div class="container">
                        <div class="title">{self.title}</div>
                        <div class="progress-container">
                            <div class="progress-bar"></div>
                        </div>
                        <div class="details">Complete!</div>
                        <div class="completion-message">
                            <div class="completion-title">Risk Assessment Completed!</div>
                            Please check the notification on the Apple Dialog window and see the results on the report.
                        </div>
                        <div class="countdown" id="countdown">This page will be closed in 10 seconds...</div>
                    </div>
                    <div class="bottom-logo-row">
                        {bottom_logo_html}
                    </div>
                    <script>
                        // Force a final reload if not already in ?final=1
                        if (!window.location.search.includes('final=1')) {{
                            window.location.search = '?final=1';
                        }} else {{
                            var countdown = 5;
                            var countdownElement = document.getElementById('countdown');
                            var timer = setInterval(function() {{
                                countdown--;
                                if (countdown > 0) {{
                                    countdownElement.textContent = `This page will be closed in ${{countdown}} seconds...`;
                                }} else {{
                                    countdownElement.textContent = 'Closing Now...';
                                    clearInterval(timer);
                                    setTimeout(function() {{
                                        window.close();
                                    }}, 500);
                                }}
                            }}, 1000);
                        }}
                    </script>
                </body>
                </html>
                """
                self.html_temp = "/tmp/progress_bar.html.tmp"
                with open(self.html_temp, 'w') as f:
                    f.write(html_content)
                shutil.move(self.html_temp, self.html_file)
                print("[DEBUG] finish() called on working_progress_bar")
                # Give browser time to process the final state
                time.sleep(1)
            except Exception as e:
                with open("/tmp/progress_bar_error.log", "a") as logf:
                    logf.write(f"[FINISH] {time.ctime()}: {e}\n")
                pass
            self.is_running = False
    
    def close(self):
        """Close the progress bar"""
        if self.is_running:
            try:
                # Wait a bit for browser to finish processing before deleting file
                time.sleep(2)
                # Remove the HTML file
                if os.path.exists(self.html_file):
                    os.remove(self.html_file)
            except Exception as e:
                with open("/tmp/progress_bar_error.log", "a") as logf:
                    logf.write(f"[CLOSE] {time.ctime()}: {e}\n")
            self.is_running = False

# Console progress bar as fallback
class ConsoleProgressBar:
    """Console progress bar that always works"""
    
    def __init__(self, total_tokens: int, title: str = "DeFi Risk Assessment"):
        self.total_tokens = total_tokens
        self.title = title
        self.current_token = 0
        self.current_phase = 0
        self.phases_per_token = 2  # Data fetching + Analysis (report generation is separate)
        self.total_phases = (total_tokens * self.phases_per_token) + 1  # +1 for final report generation
        self.completed_phases = 0
        self.start_time = time.time()
        
        self.token_phases = [
            "Fetching token data",
            "Analyzing security & market data"
        ]
    
    def update_phase(self, phase_index: int, message: Optional[str] = None):
        self.current_phase = phase_index
        if message:
            self._print_progress(message)
        else:
            self._print_progress(self.token_phases[phase_index])
    
    def next_token(self, token_name: Optional[str] = None):
        self.current_token += 1
        self.current_phase = 0
        self.completed_phases = (self.current_token - 1) * self.phases_per_token
        
        token_display = f"Token {self.current_token}/{self.total_tokens}"
        if token_name:
            token_display += f" ({token_name})"
        
        self._print_progress(f"{token_display} - {self.token_phases[0]}")
    
    def complete_phase(self, message: Optional[str] = None):
        self.completed_phases += 1
        self.current_phase += 1
        
        if message:
            self._print_progress(message)
        elif self.current_phase < len(self.token_phases):
            self._print_progress(self.token_phases[self.current_phase])
    
    def _print_progress(self, message: str):
        percent = int((self.completed_phases / self.total_phases) * 100)
        elapsed = time.time() - self.start_time
        
        if self.completed_phases > 0:
            eta = (elapsed / self.completed_phases) * (self.total_phases - self.completed_phases)
            eta_str = f"ETA: {eta:.1f}s"
        else:
            eta_str = "ETA: --"
        
        bar_length = 30
        filled_length = int(bar_length * self.completed_phases // self.total_phases)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        sys.stdout.write(f'\r{self.title}: [{bar}] {percent}% ({self.completed_phases}/{self.total_phases}) {eta_str} {message}')
        sys.stdout.flush()
    
    def finish(self, message: str = "Risk assessment complete!"):
        self.completed_phases = self.total_phases
        self._print_progress(message)
        print()
    
    def close(self):
        pass

# Global progress bar instances
working_progress_bar: Optional[WorkingProgressBar] = None
console_progress_bar: Optional[ConsoleProgressBar] = None

def initialize_working_progress_bar(total_tokens: int, title: str = "DeFi Risk Assessment"):
    """Initialize the working progress bar"""
    global working_progress_bar
    try:
        working_progress_bar = WorkingProgressBar(total_tokens, title)
        return working_progress_bar.is_running
    except Exception as e:
        return False

def initialize_console_progress_bar(total_tokens: int, title: str = "DeFi Risk Assessment"):
    """Initialize console progress bar"""
    global console_progress_bar
    console_progress_bar = ConsoleProgressBar(total_tokens, title)

def update_progress_phase(phase_index: int, message: Optional[str] = None):
    """Update progress bar phase"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.update_phase(phase_index, message)
        # Small delay to ensure browser sees the update
        time.sleep(0.1)
    elif console_progress_bar:
        console_progress_bar.update_phase(phase_index, message)

def update_progress_title(new_title: str):
    """Update progress bar title"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.update_title(new_title)
        # Small delay to ensure browser sees the update
        time.sleep(0.1)
    elif console_progress_bar:
        # Console progress bar doesn't have title updates
        pass

def next_token_progress(token_name: Optional[str] = None):
    """Move to next token in progress bar"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.next_token(token_name)
    elif console_progress_bar:
        console_progress_bar.next_token(token_name)

def complete_phase_progress(message: Optional[str] = None):
    """Complete current phase in progress bar"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.complete_phase(message)
    elif console_progress_bar:
        console_progress_bar.complete_phase(message)

def finish_progress_bar(message: str = "Risk assessment complete!"):
    """Finish the progress bar"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.finish(message)
        import time
        time.sleep(5)  # Allow browser to process final HTML and close
        working_progress_bar = None
    elif console_progress_bar:
        console_progress_bar.finish(message)
        console_progress_bar = None

def close_progress_bar():
    """Close the progress bar"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.close()
        working_progress_bar = None
    elif console_progress_bar:
        console_progress_bar.close()
        console_progress_bar = None

# Unified progress bar interface
def initialize_progress_bar(total_tokens: int, title: str = "DeFi Risk Assessment"):
    """Initialize the best available progress bar"""
    # Try working progress bar first
    if initialize_working_progress_bar(total_tokens, title):
        return "working"
    else:
        # Fallback to console progress bar
        initialize_console_progress_bar(total_tokens, title)
        return "console"

if __name__ == "__main__":
    # Test the progress bar
    import time
    
    print("Testing Working Progress Bar...")
    progress_type = initialize_progress_bar(3, "Test Progress")
    print(f"Using progress bar type: {progress_type}")
    
    for token_idx in range(3):
        next_token_progress(f"Token_{token_idx}")
        
        for phase_idx in range(3):
            update_progress_phase(phase_idx)
            time.sleep(1)
            complete_phase_progress()
    
    # Ensure bar is at 100% before finishing
    if working_progress_bar:
        working_progress_bar.completed_phases = working_progress_bar.total_phases
    finish_progress_bar("Test complete!")
    time.sleep(2)
    close_progress_bar() 
