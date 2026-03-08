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
import base64
import webbrowser

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
        self.current_message = "Initializing assessment..."
        self._last_render_ts = 0.0
        self._min_render_interval = 0.35
        self._browser_opened = False
        self._last_browser_launch_attempt = 0.0
        
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
    

    def _log_progress_error(self, context: str, err: str):
        """Append progress window errors to local runtime log."""
        try:
            with open("/tmp/progress_bar_error.log", "a") as logf:
                logf.write(f"[{context}] {time.ctime()}: {err}\n")
        except Exception:
            pass

    def _open_progress_window(self):
        """Open/restore the progress window in the default browser."""
        target = getattr(self, "html_file", "/tmp/progress_bar.html")
        if not target:
            return False
        self._last_browser_launch_attempt = time.time()
        open_cmds = [
            ['open', target],
            ['open', '-a', 'Safari', target],
            ['open', '-a', 'Google Chrome', target],
        ]
        for cmd in open_cmds:
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=8
                )
                if proc.returncode == 0:
                    self._browser_opened = True
                    return True
                self._log_progress_error("OPEN", f"{' '.join(cmd)} -> rc={proc.returncode}, err={proc.stderr.strip()}")
            except Exception as e:
                self._log_progress_error("OPEN", f"{' '.join(cmd)} -> {e}")
        try:
            opened = bool(webbrowser.open(f"file://{target}", new=1))
            if opened:
                self._browser_opened = True
                return True
        except Exception as e:
            self._log_progress_error("OPEN", f"webbrowser fallback failed: {e}")
        self._browser_opened = False
        return False


    def _create_progress_window(self):
        """Create a working progress bar using a simple GUI"""
        try:
            # Only add meta refresh if not finished
            meta_refresh = '<meta http-equiv="refresh" content="1">' if self.completed_phases < self.total_phases else ''

            # Resolve logos directory.
            logo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'Logos'))
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
            # Collect all logos in docs/Logos (including newly added source attributions).
            logo_files = []
            allowed_exts = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
            excluded_files = {
                'logo_watermark_2.svg',
                'crypto.icns',
                'crypto.png',
                'crypto_small.png',
            }
            if logo_dir:
                try:
                    discovered = []
                    for entry in os.listdir(logo_dir):
                        if entry.startswith('.'):
                            continue
                        if entry.lower() in excluded_files:
                            continue
                        src = os.path.join(logo_dir, entry)
                        if not os.path.isfile(src):
                            continue
                        _, ext = os.path.splitext(entry.lower())
                        if ext in allowed_exts:
                            discovered.append(entry)
                    logo_files = sorted(discovered, key=lambda name: name.lower())
                except Exception as e:
                    print(f"[WARNING] Could not enumerate logos in {logo_dir}: {e}")
                    logo_files = []

            if not logo_files:
                print("[WARNING] No logo files found to render in progress page attribution")

            def _mime_type_for_logo(filename: str) -> str:
                _, ext = os.path.splitext(filename.lower())
                if ext == '.png':
                    return 'image/png'
                if ext in {'.jpg', '.jpeg'}:
                    return 'image/jpeg'
                if ext == '.webp':
                    return 'image/webp'
                if ext == '.svg':
                    return 'image/svg+xml'
                return 'application/octet-stream'

            logo_count = len(logo_files)
            if logo_count > 18:
                logo_height_px = 52
                top_gap_px = 18
                bottom_gap_px = 14
            elif logo_count > 10:
                logo_height_px = 60
                top_gap_px = 22
                bottom_gap_px = 18
            else:
                logo_height_px = 70
                top_gap_px = 26
                bottom_gap_px = 22

            def _logo_tile_html(logo_name: str, height_px: int) -> str:
                src = os.path.join(logo_dir, logo_name) if logo_dir else ''
                try:
                    with open(src, 'rb') as f:
                        logo_data = f.read()
                    logo_b64 = base64.b64encode(logo_data).decode('utf-8')
                    mime_type = _mime_type_for_logo(logo_name)
                    return (
                        f'<img src="data:{mime_type};base64,{logo_b64}" '
                        f'style="height: {height_px}px; width: auto; border-radius: 10px; '
                        'background: #fff; padding: 4px 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.10); '
                        'opacity: 0.95; object-fit: contain;" '
                        f'alt="{logo_name}" onerror="this.style.display=\'none\'">'
                    )
                except Exception as e:
                    print(f"[WARNING] Could not encode logo {logo_name}: {e}")
                    service_name = os.path.splitext(logo_name)[0][:10].upper()
                    return (
                        f'<div style="height: {height_px}px; min-width: 60px; padding: 0 8px; '
                        'background: linear-gradient(45deg, #4b6cb7, #182848); border-radius: 10px; '
                        'display: flex; align-items: center; justify-content: center; color: white; '
                        'font-weight: bold; font-size: 9px; box-shadow: 0 2px 8px rgba(0,0,0,0.10);">'
                        f'{service_name}</div>'
                    )

            split_at = (len(logo_files) + 1) // 2
            top_logos = logo_files[:split_at]
            bottom_logos = logo_files[split_at:]

            top_logo_html = ""
            bottom_logo_html = ""
            for logo_name in top_logos:
                top_logo_html += _logo_tile_html(logo_name, logo_height_px)
            for logo_name in bottom_logos:
                bottom_logo_html += _logo_tile_html(logo_name, logo_height_px)

            # If we only have one row of logos, reuse it on bottom for balanced layout.
            if top_logo_html and not bottom_logo_html:
                bottom_logo_html = top_logo_html

            # Store both logo HTMLs for reuse in updates
            self.top_logo_html = top_logo_html
            self.bottom_logo_html = bottom_logo_html
            # All detected logo files are now included in top/bottom rows.

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
                        gap: 18px;
                        margin-bottom: {top_gap_px}px;
                        margin-top: 8px;
                        flex-wrap: wrap;
                        max-width: min(96vw, 1400px);
                    }}
                    .bottom-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 14px;
                        margin-top: {bottom_gap_px}px;
                        margin-bottom: 8px;
                        flex-wrap: wrap;
                        max-width: min(96vw, 1400px);
                    }}
                    .container {{
                        text-align: center;
                        max-width: 640px;
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
                    <div class="details" id="details">0%</div>
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
            if not self._open_progress_window():
                print("[WARNING] Could not auto-open progress window in browser")
            
            self.is_running = True
            # Removed the initialization message
                
        except Exception as e:
            self.is_running = False
            self._log_progress_error("CREATE", str(e))
    
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

    def set_total_steps(self, total_steps: int):
        """Configure custom total steps for smoother progress updates."""
        with self.lock:
            if not self.is_running or self.finished:
                return
            try:
                total_steps = max(1, int(total_steps))
            except Exception:
                total_steps = self.total_phases if self.total_phases > 0 else 1
            self.total_phases = total_steps
            self.completed_phases = 0
            self.current_token = 0
            self.current_phase = 0
            self._update_progress_bar()

    def set_token_context(self, token_index: int, total_tokens: Optional[int] = None, token_name: Optional[str] = None):
        """Compatibility no-op: token counters are intentionally hidden."""
        return

    def advance_steps(self, steps: int = 1, message: Optional[str] = None):
        """Advance progress by logical steps (independent from token phase labels)."""
        with self.lock:
            if not self.is_running or self.finished:
                return
            try:
                increment = max(1, int(steps))
            except Exception:
                increment = 1
            self.completed_phases = min(self.total_phases, self.completed_phases + increment)
            if message:
                self.current_message = message
            self._update_progress_bar()
    
    def next_token(self, token_name: Optional[str] = None):
        """Move to the next token and reset phases"""
        with self.lock:
            if not self.is_running or self.finished:
                return
                
            self.current_token += 1
            self.current_phase = 0
            self.completed_phases = (self.current_token - 1) * self.phases_per_token
            
            self.current_message = "Processing token data..."
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
        now_ts = time.time()
        if (now_ts - self._last_render_ts) < self._min_render_interval and self.completed_phases < self.total_phases:
            return
        self._last_render_ts = now_ts
            
        try:
            # Calculate percentage (ensure it never exceeds 100%)
            percentage = min((self.completed_phases / self.total_phases) * 100 if self.total_phases > 0 else 0, 100.0)
            percent_display = int(round(percentage))
            
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
                        gap: 18px;
                        margin-bottom: 24px;
                        margin-top: 8px;
                        flex-wrap: wrap;
                        max-width: min(96vw, 1400px);
                    }}
                    .bottom-logo-row {{
                        display: flex;
                        flex-direction: row;
                        justify-content: center;
                        align-items: center;
                        gap: 14px;
                        margin-top: 24px;
                        margin-bottom: 8px;
                        flex-wrap: wrap;
                        max-width: min(96vw, 1400px);
                    }}
                    .container {{
                        text-align: center;
                        max-width: 640px;
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
                    <div class="details">{percent_display}%</div>
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

            # If launch failed earlier, retry opening periodically.
            now_ts = time.time()
            if (not self._browser_opened) and ((now_ts - self._last_browser_launch_attempt) >= 5.0):
                self._open_progress_window()
            
            # Small delay to ensure browser processes the update
            # Avoid blocking worker threads; HTML refresh cadence handles visual throttling.
                
        except Exception as e:
            self._log_progress_error("UPDATE", str(e))
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
                            gap: 18px;
                            margin-bottom: 24px;
                            margin-top: 8px;
                            flex-wrap: wrap;
                            max-width: min(96vw, 1400px);
                        }}
                        .bottom-logo-row {{
                            display: flex;
                            flex-direction: row;
                            justify-content: center;
                            align-items: center;
                            gap: 14px;
                            margin-top: 24px;
                            margin-bottom: 8px;
                            flex-wrap: wrap;
                            max-width: min(96vw, 1400px);
                        }}
                        .container {{
                            text-align: center;
                            max-width: 640px;
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
                self._log_progress_error("FINISH", str(e))
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
                self._log_progress_error("CLOSE", str(e))
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

    def set_total_steps(self, total_steps: int):
        try:
            self.total_phases = max(1, int(total_steps))
            self.completed_phases = 0
            self.current_token = 0
            self.current_phase = 0
        except Exception:
            pass

    def set_token_context(self, token_index: int, total_tokens: Optional[int] = None, token_name: Optional[str] = None):
        # Compatibility no-op: token counters are intentionally hidden.
        return

    def advance_steps(self, steps: int = 1, message: Optional[str] = None):
        try:
            increment = max(1, int(steps))
        except Exception:
            increment = 1
        self.completed_phases = min(self.total_phases, self.completed_phases + increment)
        self._print_progress(message or "Processing...")
    
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
        self._print_progress(self.token_phases[0])
    
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

        sys.stdout.write(f'\r{self.title}: [{bar}] {percent}% {eta_str} {message}')
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

def set_progress_total_steps(total_steps: int):
    """Set total logical steps for progress completion."""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.set_total_steps(total_steps)
    elif console_progress_bar:
        console_progress_bar.set_total_steps(total_steps)

def set_progress_token(token_index: int, total_tokens: int, token_name: Optional[str] = None):
    """Compatibility no-op: token counters are intentionally hidden."""
    return

def advance_progress_steps(steps: int = 1, message: Optional[str] = None):
    """Advance progress by N logical steps."""
    global working_progress_bar, console_progress_bar
    if working_progress_bar:
        working_progress_bar.advance_steps(steps, message)
    elif console_progress_bar:
        console_progress_bar.advance_steps(steps, message)

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
