"""
Profile management utilities
"""
import json
from pathlib import Path
from config import PROFILES_DIR, DEFAULT_PROFILE_NAME

def profile_exists():
    """Check if a user profile exists"""
    profile_path = PROFILES_DIR / DEFAULT_PROFILE_NAME
    return profile_path.exists()

def get_profile_path():
    """Get the path to the user profile"""
    return PROFILES_DIR / DEFAULT_PROFILE_NAME

def load_profile():
    """Load the user profile if it exists"""
    if profile_exists():
        with open(get_profile_path(), 'r') as f:
            return json.load(f)
    return None

def save_profile(data):
    """Save the user profile"""
    with open(get_profile_path(), 'w') as f:
        json.dump(data, f, indent=2)

