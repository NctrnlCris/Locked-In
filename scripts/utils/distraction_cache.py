"""
Distraction cache for storing process+window combinations that were deemed distracting.
This prevents unnecessary LLM calls for known distracting pages.
"""

import json
import os
from pathlib import Path
from typing import Set, Tuple
import logging

logger = logging.getLogger(__name__)

# Default cache directory
CACHE_DIR = Path("data/distraction_cache")


class DistractionCache:
    """Cache for storing distracting process+window combinations."""
    
    def __init__(self, profile_name: str = None, cache_file: Path = None):
        """
        Initialize the distraction cache.
        
        Args:
            profile_name: Profile name to create profile-specific cache. If None, uses "default"
            cache_file: Optional path to cache file. If None, uses data/distraction_cache/{profile_name}.json
        """
        if cache_file is None:
            if profile_name is None:
                profile_name = "default"
            # Sanitize profile name for filename (remove invalid characters)
            safe_profile_name = "".join(c for c in profile_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_profile_name = safe_profile_name.replace(' ', '_')
            self.cache_file = CACHE_DIR / f"{safe_profile_name}.json"
        else:
            self.cache_file = cache_file
        
        self.profile_name = profile_name or "default"
        self._cache: Set[Tuple[str, str]] = set()
        self.load()
    
    def _normalize_key(self, process_name: str, window_title: str) -> Tuple[str, str]:
        """
        Normalize process name and window title for consistent matching.
        
        Args:
            process_name: Process name (e.g., "chrome.exe")
            window_title: Window title (e.g., "YouTube - Watch Videos")
            
        Returns:
            Normalized tuple (process_name_lower, window_title_lower)
        """
        process_normalized = (process_name or "").lower().strip()
        window_normalized = (window_title or "").lower().strip()
        return (process_normalized, window_normalized)
    
    def is_distracting(self, process_name: str, window_title: str = "") -> bool:
        """
        Check if a process+window combination is in the distraction cache.
        
        Args:
            process_name: Process name (e.g., "chrome.exe")
            window_title: Window title (e.g., "YouTube - Watch Videos")
            
        Returns:
            True if the combination is cached as distracting
        """
        key = self._normalize_key(process_name, window_title)
        return key in self._cache
    
    def add_distracting(self, process_name: str, window_title: str = ""):
        """
        Add a process+window combination to the distraction cache.
        
        Args:
            process_name: Process name (e.g., "chrome.exe")
            window_title: Window title (e.g., "YouTube - Watch Videos")
        """
        key = self._normalize_key(process_name, window_title)
        self._cache.add(key)
        self.save()
        logger.info(f"Added to distraction cache: {process_name} | {window_title}")
    
    def remove(self, process_name: str, window_title: str = ""):
        """
        Remove a process+window combination from the cache.
        
        Args:
            process_name: Process name
            window_title: Window title
        """
        key = self._normalize_key(process_name, window_title)
        self._cache.discard(key)
        self.save()
    
    def clear(self):
        """Clear all cached distractions."""
        self._cache.clear()
        self.save()
    
    def load(self):
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert list of lists back to set of tuples
                    self._cache = {tuple(item) for item in data.get('distractions', [])}
                    logger.info(f"Loaded {len(self._cache)} distractions from cache")
            else:
                # Create directory if it doesn't exist
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self._cache = set()
        except Exception as e:
            logger.warning(f"Failed to load distraction cache: {e}")
            self._cache = set()
    
    def save(self):
        """Save cache to file."""
        try:
            # Create directory if it doesn't exist
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert set of tuples to list of lists for JSON serialization
            data = {
                'distractions': [list(item) for item in self._cache]
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved {len(self._cache)} distractions to cache")
        except Exception as e:
            logger.warning(f"Failed to save distraction cache: {e}")
    
    def get_count(self) -> int:
        """Get the number of cached distractions."""
        return len(self._cache)


# Cache instances per profile
_cache_instances: dict[str, DistractionCache] = {}


def get_cache(profile_name: str = None) -> DistractionCache:
    """
    Get the distraction cache instance for a specific profile.
    
    Args:
        profile_name: Profile name. If None, uses "default"
        
    Returns:
        DistractionCache instance for the specified profile
    """
    if profile_name is None:
        profile_name = "default"
    
    if profile_name not in _cache_instances:
        _cache_instances[profile_name] = DistractionCache(profile_name=profile_name)
    
    return _cache_instances[profile_name]


def clear_cache(profile_name: str = None):
    """
    Clear the cache instance for a specific profile.
    
    Args:
        profile_name: Profile name. If None, clears "default" cache
    """
    if profile_name is None:
        profile_name = "default"
    
    if profile_name in _cache_instances:
        del _cache_instances[profile_name]

