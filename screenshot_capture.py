"""
Screenshot capture utilities
"""
import mss
from pathlib import Path
import time
from datetime import datetime

output_dir = Path("screenshot_data")
output_dir.mkdir(exist_ok=True)

def capture_single_screenshot():
    """Capture a single screenshot"""
    with mss.mss() as sct:
        timestamp = time.time()
        filename = output_dir / f"screenshot_{timestamp}.png"
        sct.shot(output=str(filename))
        return filename

def capture_multiple_screenshots(count=3, duration_seconds=5):
    """
    Capture multiple screenshots over a duration
    
    Args:
        count: Number of screenshots to take (default: 3)
        duration_seconds: Total duration in seconds (default: 5)
    
    Returns:
        List of screenshot file paths
    """
    screenshots = []
    interval = duration_seconds / count if count > 1 else 0
    
    for i in range(count):
        screenshot_path = capture_single_screenshot()
        screenshots.append(str(screenshot_path))
        
        # Wait between screenshots (except for the last one)
        if i < count - 1:
            time.sleep(interval)
    
    return screenshots

