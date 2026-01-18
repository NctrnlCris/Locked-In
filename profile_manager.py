"""
Profile management utilities - Supports multiple profiles
"""
import json
from pathlib import Path
from config import PROFILES_DIR

PROFILES_INDEX_FILE = PROFILES_DIR / "profiles_index.json"

def get_profiles_index():
    """Get the profiles index (list of all profiles)"""
    if PROFILES_INDEX_FILE.exists():
        with open(PROFILES_INDEX_FILE, 'r') as f:
            return json.load(f)
    return {"profiles": []}

def save_profiles_index(data):
    """Save the profiles index"""
    with open(PROFILES_INDEX_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def any_profiles_exist():
    """Check if any profiles exist"""
    index = get_profiles_index()
    return len(index.get("profiles", [])) > 0

def get_all_profiles():
    """Get list of all profile names"""
    index = get_profiles_index()
    return [p["name"] for p in index.get("profiles", [])]

def get_profile_path(profile_name):
    """Get the path to a specific profile"""
    return PROFILES_DIR / f"{profile_name}.json"

def profile_exists(profile_name):
    """Check if a specific profile exists"""
    return get_profile_path(profile_name).exists()

def load_profile(profile_name):
    """Load a specific profile"""
    profile_path = get_profile_path(profile_name)
    if profile_path.exists():
        with open(profile_path, 'r') as f:
            return json.load(f)
    return None

def save_profile(profile_name, profile_data):
    """Save a profile and update the index"""
    # Save profile file
    profile_path = get_profile_path(profile_name)
    with open(profile_path, 'w') as f:
        json.dump(profile_data, f, indent=2)
    
    # Update profiles index
    index = get_profiles_index()
    profiles = index.get("profiles", [])
    
    # Check if profile already exists in index
    existing = next((p for p in profiles if p["name"] == profile_name), None)
    if existing:
        # Update existing
        existing.update({
            "updated": profile_data.get("created", ""),
            "setup_type": profile_data.get("setup_type", "custom")
        })
    else:
        # Add new profile
        profiles.append({
            "name": profile_name,
            "created": profile_data.get("created", ""),
            "setup_type": profile_data.get("setup_type", "custom")
        })
    
    index["profiles"] = profiles
    save_profiles_index(index)

def delete_profile(profile_name):
    """Delete a profile"""
    profile_path = get_profile_path(profile_name)
    if profile_path.exists():
        profile_path.unlink()
    
    # Remove from index
    index = get_profiles_index()
    profiles = index.get("profiles", [])
    index["profiles"] = [p for p in profiles if p["name"] != profile_name]
    save_profiles_index(index)

