"""
Configuration file for Locked-In application
"""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
OUTPUT_DIR = BASE_DIR / "profile_output"
SESSIONS_DIR = BASE_DIR / "sessions"

# Create directories if they don't exist
PROFILES_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

# Profile file name
DEFAULT_PROFILE_NAME = "user_profile.json"

# Setup questions for custom profile
SETUP_QUESTIONS = [
    "What would you like to use this app for?",
    "What is your background? (e.g., student, developer, writer) - Please specify your specific discipline of study",
    "What are your main things you want to focus on? (What are you planning on working on, describe your project or task)",
    "What are things you want to prevent to be distraction-free?",
    "Is there anything particular that you want to whitelist that will be used when you focus?",
    "Is there anything that you want to be distraction-free from?"
]

