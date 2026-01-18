"""
Session management utilities - Save and load session history
"""
import json
from pathlib import Path
from datetime import datetime
from config import SESSIONS_DIR

SESSIONS_INDEX_FILE = SESSIONS_DIR / "sessions_index.json"
SESSIONS_DIR.mkdir(exist_ok=True)

def save_session(session_data):
    """Save a session to the sessions directory"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = SESSIONS_DIR / f"session_{timestamp}.json"
    
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2)
    
    # Update sessions index
    index = get_sessions_index()
    index["sessions"].append({
        "file": session_file.name,
        "timestamp": timestamp,
        "date": session_data.get("start_time", ""),
        "duration": session_data.get("duration", ""),
        "distractions": session_data.get("distraction_count", 0),
        "popup_clicks": session_data.get("popup_click_count", 0)
    })
    # Sort by timestamp descending (newest first)
    index["sessions"].sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    save_sessions_index(index)
    
    return session_file

def get_sessions_index():
    """Get the sessions index"""
    if SESSIONS_INDEX_FILE.exists():
        with open(SESSIONS_INDEX_FILE, 'r') as f:
            return json.load(f)
    return {"sessions": []}

def save_sessions_index(data):
    """Save the sessions index"""
    with open(SESSIONS_INDEX_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_all_sessions():
    """Get list of all sessions"""
    index = get_sessions_index()
    sessions = []
    for session_info in index.get("sessions", []):
        session_file = SESSIONS_DIR / session_info["file"]
        if session_file.exists():
            with open(session_file, 'r') as f:
                session_data = json.load(f)
                session_data["_file"] = session_info["file"]  # Add filename for reference
                sessions.append(session_data)
    return sessions

def load_session(session_filename):
    """Load a specific session by filename"""
    session_file = SESSIONS_DIR / session_filename
    if session_file.exists():
        with open(session_file, 'r') as f:
            return json.load(f)
    return None

