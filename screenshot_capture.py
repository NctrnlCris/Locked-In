"""
Screenshot capture utilities
"""
import mss
from pathlib import Path
import time
from datetime import datetime
from PIL import Image
import io

def capture_single_screenshot(max_size=None, temp_folder=None):
    """
    Capture a single screenshot, resize it immediately, and save to temp folder.
    
    Args:
        max_size: Maximum (width, height) tuple for resizing. If None, uses (512, 512) default
        temp_folder: Path to temp folder for saving screenshots. If None, uses './temp/screenshots'
    
    Returns:
        Path to saved screenshot file
    """
    # Set defaults
    if max_size is None:
        max_size = (512, 512)  # Default to config default
    if temp_folder is None:
        temp_folder = './temp/screenshots'
    
    # Create temp directory if it doesn't exist
    output_dir = Path(temp_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with mss.mss() as sct:
        timestamp = time.time()
        filename = output_dir / f"screenshot_{timestamp}.jpg"
        
        # Capture screenshot to memory first
        screenshot = sct.grab(sct.monitors[1])  # Capture primary monitor
        
        # Convert to PIL Image
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        original_size = img.size
        
        # Resize immediately maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save resized image as JPEG (smaller than PNG)
        try:
            img.save(filename, format='JPEG', quality=85, optimize=True)
            if img.size != original_size:
                print(f"[SCREENSHOT] Resized from {original_size} to {img.size} and saved to {filename}")
            else:
                print(f"[SCREENSHOT] Saved screenshot to {filename} (no resize needed)")
        except Exception as e:
            print(f"[SCREENSHOT] Error saving screenshot: {e}")
            # Fallback: try saving as PNG
            try:
                filename = output_dir / f"screenshot_{timestamp}.png"
                img.save(filename, format='PNG', optimize=True)
            except Exception as e2:
                print(f"[SCREENSHOT] Error saving as PNG: {e2}")
                return None
        
        return filename

def capture_multiple_screenshots(count=3, duration_seconds=5, max_size=None, temp_folder=None):
    """
    Capture multiple screenshots over a duration
    
    Args:
        count: Number of screenshots to take (default: 3)
        duration_seconds: Total duration in seconds (default: 5)
        max_size: Maximum (width, height) tuple for resizing. If None, uses (512, 512) default
        temp_folder: Path to temp folder for saving screenshots. If None, uses './temp/screenshots'
    
    Returns:
        List of screenshot file paths
    """
    screenshots = []
    interval = duration_seconds / count if count > 1 else 0
    
    for i in range(count):
        screenshot_path = capture_single_screenshot(max_size=max_size, temp_folder=temp_folder)
        if screenshot_path:
            screenshots.append(str(screenshot_path))
        
        # Wait between screenshots (except for the last one)
        if i < count - 1:
            time.sleep(interval)
    
    return screenshots

