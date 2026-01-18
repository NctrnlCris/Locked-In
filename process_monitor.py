"""
Process monitoring utilities for Windows
"""
import psutil
import win32gui
import win32process

# List of browsers to check
BROWSERS = [
    'chrome.exe',
    'firefox.exe',
    'msedge.exe',
    'opera.exe',
    'brave.exe',
    'safari.exe',
    'vivaldi.exe',
    'waterfox.exe'
]

def get_foreground_process_name():
    """Get the name of the currently active foreground window's process"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        return process.name().lower()
    except Exception as e:
        print(f"Error getting foreground process: {e}")
        return None

def get_foreground_window_title():
    """Get the title of the currently active foreground window"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        window_title = win32gui.GetWindowText(hwnd)
        return window_title
    except Exception as e:
        print(f"Error getting foreground window title: {e}")
        return None

def is_browser(process_name):
    """Check if the process is a browser"""
    if not process_name:
        return False
    return process_name.lower() in [b.lower() for b in BROWSERS]

def is_in_blacklist(process_name, blacklist):
    """Check if process name is in the blacklist"""
    if not process_name or not blacklist:
        return False
    process_lower = process_name.lower()
    
    # Check if any blacklist item matches the process name
    for blacklist_item in blacklist:
        blacklist_lower = blacklist_item.lower()
        # Remove .exe extension from process name for comparison
        process_base = process_lower.replace('.exe', '')
        blacklist_base = blacklist_lower.replace('.exe', '')
        
        # Match if the base names are equal or if one contains the other
        if process_base == blacklist_base or blacklist_base in process_base or process_base in blacklist_base:
            print(f"[DEBUG] Matched: process='{process_name}' (base: '{process_base}') with blacklist item='{blacklist_item}' (base: '{blacklist_base}')")
            return True
    
    return False

def classify_process(process_name, config=None):
    """
    Classify a process using the Config system.
    
    Args:
        process_name: Name of the process (e.g., 'chrome.exe')
        config: Optional Config instance. If None, creates a new one.
        
    Returns:
        Classification string: 'work', 'entertainment', 'mixed', or 'unknown'
    """
    if config is None:
        try:
            from scripts.utils.config import Config
            config = Config()
        except Exception as e:
            print(f"Warning: Could not load Config for classification: {e}")
            return 'unknown'
    
    try:
        from scripts.utils.process_classifier import classify_process as _classify_process
        return _classify_process(process_name, config)
    except Exception as e:
        print(f"Error classifying process {process_name}: {e}")
        return 'unknown'
def is_in_whitelist(process_name, whitelist):
    """Check if process name is in the whitelist"""
    if not process_name or not whitelist:
        return False
    process_lower = process_name.lower()
    
    # Check if any whitelist item matches the process name
    for whitelist_item in whitelist:
        whitelist_lower = whitelist_item.lower()
        # Remove .exe extension from process name for comparison
        process_base = process_lower.replace('.exe', '')
        whitelist_base = whitelist_lower.replace('.exe', '')
        
        # Match if the base names are equal or if one contains the other
        if process_base == whitelist_base or whitelist_base in process_base or process_base in whitelist_base:
            print(f"[DEBUG] Matched: process='{process_name}' (base: '{process_base}') with whitelist item='{whitelist_item}' (base: '{whitelist_base}')")
            return True
    
    return False

