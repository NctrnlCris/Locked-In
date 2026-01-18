import json
from pathlib import Path

def check_distraction(json_file_path):
    if not Path(json_file_path).exists():
        print(f"JSON file not found: {json_file_path}")
        return False

    with open(json_file_path, "r") as f:
        try:
            data = json.load(f)
            distracted = data.get("distracted", False)
            reason = data.get("reason", "")
            if distracted:
                print(f"User is distracted: {reason}")
            return distracted
        except json.JSONDecodeError:
            print(f"Error decoding JSON: {json_file_path}")
            return False
