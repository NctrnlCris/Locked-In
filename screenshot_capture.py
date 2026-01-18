import mss
from pathlib import Path
import time

output_dir = Path("screenshot_data")
output_dir.mkdir(exist_ok=True)

def capture_screenshot():
    with mss.mss() as sct:
        time.sleep(1)
        for _ in range(1):
            sct.shot(output=str(output_dir / f"screenshot_{time.time()}.png"))
            # time.sleep(0.01)

