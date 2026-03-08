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
        
        # Create the progress bar window
        self._create_progress_window()
    
    def _get_logo_data_urls(self):
        # Read base64 logo files and return data URLs
        logo_files = [
            ("1inch-exchange-logo.png", "/tmp/1inch-exchange-logo.b64", "image/png"),
            ("bitquery-logo.jpg", "/tmp/bitquery-logo.b64", "image/jpeg"),
            ("coingecko logo.png", "/tmp/coingecko logo.b64", "image/png"),
            ("defillama-logo.jpg", "/tmp/defillama-logo.b64", "image/jpeg"),
            ("450px-EtherScan-Logo.png", "/tmp/450px-EtherScan-Logo.b64", "image/png"),
        ]
        data_urls = []
        for name, b64_path, mime in logo_files:
            try:
                with open(b64_path, "r") as f:
                    b64 = f.read().replace("\n", "")
                data_urls.append(f"data:{mime};base64,{b64}")
            except Exception:
                data_urls.append("")
        return data_urls

    def _create_progress_window(self):
        """Create a working progress bar using a simple GUI"""
        try:
            # Copy logo files to /tmp/ so they can be referenced from the HTML
            logo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../docs/Logos'))
            logo_files = [
                '1inch-exchange-logo.png',
                'bitquery-logo.jpg',
                'coingecko logo.png',
                'defillama-logo.jpg',
                '450px-EtherScan-Logo.png',
            ]
            for logo in logo_files:
                src = os.path.join(logo_dir, logo)
                dst = os.path.join('/tmp', logo)
                if os.path.exists(src):
                    shutil.copyfile(src, dst)

            # Only add meta refresh if not finished
            meta_refresh = '<meta http-equiv="refresh" content="1">' if self.completed_phases < self.total_phases else ''

            logo_data_urls = self._get_logo_data_urls()

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{self.title}</title>
                {meta_refresh}
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #2c3e50;
                        color: white;
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
                    .logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 32px;
                        margin-bottom: 24px;
                        margin-top: 8px;
                    }}
                    .logo-row img {{
                        height: 80px;
                        width: auto;
                        border-radius: 12px;
                        background: #fff;
                        padding: 4px 10px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                        opacity: 0.5;
                        transition: opacity 0.2s;
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
                        color: #ecf0f1;
                    }}
                    .progress-container {{
                        width: 100%;
                        background-color: #34495e;
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
                        color: #bdc3c7;
                    }}
                    .details {{
                        font-size: 14px;
                        color: #95a5a6;
                    }}
                </style>
            </head>
            <body>
                <div class="logo-row">
                    <img src="{logo_data_urls[0]}" alt="1inch" />
                    <img src="{logo_data_urls[1]}" alt="BitQuery" />
                    <img src="{logo_data_urls[2]}" alt="CoinGecko" />
                    <img src="{logo_data_urls[3]}" alt="DefiLlama" />
                    <img src="{logo_data_urls[4]}" alt="Etherscan" />
                </div>
                <div class="container">
                    <div class="title">{self.title}</div>
                    <div class="status" id="status">Initializing...</div>
                    <div class="progress-container">
                        <div class="progress-bar" id="progress"></div>
                    </div>
                    <div class="details" id="details">Token 0/{self.total_tokens} - Phase 0/3</div>
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
    
    def update_phase(self, phase_index: int, message: str = None):
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
    
    def next_token(self, token_name: str = None):
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
    
    def complete_phase(self, message: str = None):
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
                <div class="countdown" id="countdown">This page will be closed in 10 seconds...</div>
                <script>
                    var countdown = 10;
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
                            }, 1000);
                        }
                    }, 1000);
                </script>
                '''
            logo_data_urls = self._get_logo_data_urls()
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{self.title}</title>
                {meta_refresh}
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #2c3e50;
                        color: white;
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
                    .logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 32px;
                        margin-bottom: 24px;
                        margin-top: 8px;
                    }}
                    .logo-row img {{
                        height: 80px;
                        width: auto;
                        border-radius: 12px;
                        background: #fff;
                        padding: 4px 10px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                        opacity: 0.5;
                        transition: opacity 0.2s;
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
                        color: #ecf0f1;
                    }}
                    .progress-container {{
                        width: 100%;
                        background-color: #34495e;
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
                        color: #bdc3c7;
                    }}
                    .details {{
                        font-size: 14px;
                        color: #95a5a6;
                    }}
                </style>
            </head>
            <body>
                <div class="logo-row">
                    <img src="{logo_data_urls[0]}" alt="1inch" />
                    <img src="{logo_data_urls[1]}" alt="BitQuery" />
                    <img src="{logo_data_urls[2]}" alt="CoinGecko" />
                    <img src="{logo_data_urls[3]}" alt="DefiLlama" />
                    <img src="{logo_data_urls[4]}" alt="Etherscan" />
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
                logo_data_urls = self._get_logo_data_urls()
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{self.title}</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            background-color: #2c3e50;
                            color: white;
                            margin: 0;
                            padding: 20px;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            position: relative;
                        }}
                        .logo-row {{
                            display: flex;
                            flex-direction: row;
                            justify-content: center;
                            align-items: center;
                            gap: 32px;
                            margin-bottom: 24px;
                            margin-top: 8px;
                        }}
                        .logo-row img {{
                            height: 60px;
                            width: auto;
                            border-radius: 12px;
                            background: #fff;
                            padding: 2px 6px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                            opacity: 0.5;
                            transition: opacity 0.2s;
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
                            color: #ecf0f1;
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
                    <div class="logo-row">
                        <img src="{logo_data_urls[0]}" alt="1inch" />
                        <img src="{logo_data_urls[1]}" alt="BitQuery" />
                        <img src="{logo_data_urls[2]}" alt="CoinGecko" />
                        <img src="{logo_data_urls[3]}" alt="DefiLlama" />
                        <img src="{logo_data_urls[4]}" alt="Etherscan" />
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
                    <script>
                        // Force a final reload if not already in ?final=1
                        if (!window.location.search.includes('final=1')) {{
                            window.location.search = '?final=1';
                        }} else {{
                            var countdown = 10;
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
                                    }}, 1000);
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
            except Exception as e:
                with open("/tmp/progress_bar_error.log", "a") as logf:
                    logf.write(f"[FINISH] {time.ctime()}: {e}\n")
                pass
            self.is_running = False
    
    def close(self):
        """Close the progress bar"""
        if self.is_running:
            try:
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
    
    def update_phase(self, phase_index: int, message: str = None):
        self.current_phase = phase_index
        if message:
            self._print_progress(message)
        else:
            self._print_progress(self.token_phases[phase_index])
    
    def next_token(self, token_name: str = None):
        self.current_token += 1
        self.current_phase = 0
        self.completed_phases = (self.current_token - 1) * self.phases_per_token
        
        token_display = f"Token {self.current_token}/{self.total_tokens}"
        if token_name:
            token_display += f" ({token_name})"
        
        self._print_progress(f"{token_display} - {self.token_phases[0]}")
    
    def complete_phase(self, message: str = None):
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

def update_progress_phase(phase_index: int, message: str = None):
    """Update progress bar phase"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.update_phase(phase_index, message)
        # Small delay to ensure browser sees the update
        time.sleep(0.1)
    elif console_progress_bar:
        console_progress_bar.update_phase(phase_index, message)

def next_token_progress(token_name: str = None):
    """Move to next token in progress bar"""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.next_token(token_name)
    elif console_progress_bar:
        console_progress_bar.next_token(token_name)

def complete_phase_progress(message: str = None):
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
        print("[DEBUG] finish() called on working_progress_bar")
        import time
        time.sleep(3)  # Allow browser to process final HTML and close
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