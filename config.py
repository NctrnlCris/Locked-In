"""
Configuration file for Locked-In application
"""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
OUTPUT_DIR = BASE_DIR / "profile_output"

# Create directories if they don't exist
PROFILES_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Profile file name
DEFAULT_PROFILE_NAME = "user_profile.json"

# Setup questions for custom profile
SETUP_QUESTIONS = [
    "What would you like to use this app for?",
    "What is your background? (e.g., student, developer, writer)",
    "What are your main things you want to focus on?",
    "What are things you want to prevent to be distraction-free?"
]

