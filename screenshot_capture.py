import mss
from pathlib import Path
import time

output_dir = Path("screenshot_data")
output_dir.mkdir(exist_ok=True)

with mss.mss() as sct:
    time.sleep(15)
    for _ in range(15):
        sct.shot(output=str(output_dir / f"screenshot_{time.time()}.png"))
        time.sleep(0.01)