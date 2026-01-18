"""
Profile suggestion generator using VLM for whitelist/blacklist suggestions and autocomplete.

This module provides functions to generate suggestions based on user profile responses
using the ministral-3:3b model.
"""

import logging
import re
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


def generate_profile_suggestions(
    q1_response: str,
    q2_response: str,
    q3_response: str,
    q4_response: str,
    suggestion_type: str,  # "whitelist" or "blacklist"
    model_name: str = "ministral-3:3b",
    debug_mode: bool = False,
    config: Optional[object] = None
) -> List[str]:
    """
    Generate ~5 whitelist/blacklist suggestions based on Q1-Q4 responses.
    
    Args:
        q1_response: Response to "What would you like to use this app for?"
        q2_response: Response to "What is your background?"
        q3_response: Response to "What are your main things you want to focus on?"
        q4_response: Response to "What are things you want to prevent to be distraction-free?"
        suggestion_type: Either "whitelist" or "blacklist"
        model_name: Ollama model name (default: "ministral-3:3b")
        debug_mode: Enable debug output
        config: Optional Config instance
        
    Returns:
        List of suggested keywords (empty list on error)
    """
    try:
        # Initialize config if not provided
        if config is None:
            try:
                from scripts.utils.config import Config
                config = Config()
            except Exception as e:
                logger.warning(f"Could not load Config: {e}")
                config = None
        
        # Initialize Ollama client (use cached instance)
        try:
            from scripts.vlm.ollama_client import get_or_create_client
            
            ollama_client = get_or_create_client(
                base_url=config.ollama_base_url if config else "http://localhost:11434",
                timeout=config.ollama_timeout if config else 120,
                debug_mode=debug_mode,
                auto_start=config.ollama_auto_start if config else True
            )
        except Exception as e:
            logger.error(f"Failed to initialize OllamaClient: {e}")
            return []
        
        # Build prompt based on suggestion type
        if suggestion_type.lower() == "whitelist":
            prompt = f"""Based on the following user information, suggest 5 specific applications, websites, or tools they should whitelist for productivity.

User Information:
- App purpose: {q1_response}
- Background/discipline: {q2_response}
- Focus areas/projects: {q3_response}
- Distractions to avoid: {q4_response}

Return only a comma-separated list of 5 keywords (applications, websites, or tools). Do not include any explanation or additional text. Example format: "application1, website2, tool3, app4, software5"
"""
        else:  # blacklist
            prompt = f"""Based on the following user information, suggest 5 specific applications, websites, or platforms they should blacklist to avoid distractions.

User Information:
- App purpose: {q1_response}
- Background/discipline: {q2_response}
- Focus areas/projects: {q3_response}
- Distractions to avoid: {q4_response}

Return only a comma-separated list of 5 keywords (applications, websites, or platforms). Do not include any explanation or additional text. Example format: "application1, website2, platform3, app4, site5"
"""
        
        if debug_mode:
            print(f"\n[ProfileSuggestionGenerator] Generating {suggestion_type} suggestions...")
            print(f"[ProfileSuggestionGenerator] Prompt: {prompt[:200]}...")
        
        # Generate text response
        response = ollama_client.generate_text(
            prompt=prompt,
            model_name=model_name,
            stream=False,
            max_tokens=100,  # Should be enough for 5 keywords
            temperature=0.7,
            top_p=0.9
        )
        
        response_text = response.get('response', response.get('text', '')).strip()
        
        if debug_mode:
            print(f"[ProfileSuggestionGenerator] Raw response: {response_text}")
        
        # Parse comma-separated list
        suggestions = []
        if response_text:
            # Remove any markdown formatting or extra text
            cleaned = re.sub(r'```[a-z]*\s*', '', response_text)
            cleaned = cleaned.strip('`').strip()
            
            # Split by comma and clean each suggestion
            parts = cleaned.split(',')
            for part in parts:
                keyword = part.strip()
                # Remove quotes if present
                keyword = keyword.strip('"').strip("'").strip()
                if keyword:
                    suggestions.append(keyword)
        
        # Limit to 5 suggestions
        suggestions = suggestions[:5]
        
        if debug_mode:
            print(f"[ProfileSuggestionGenerator] Parsed suggestions: {suggestions}")
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Error generating profile suggestions: {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return []


def generate_autocomplete_suggestions(
    partial_keyword: str,
    q1_response: str,
    q2_response: str,
    q3_response: str,
    q4_response: str,
    model_name: str = "ministral-3:3b",
    debug_mode: bool = False,
    config: Optional[object] = None
) -> List[str]:
    """
    Generate autocomplete suggestions as user types.
    
    Args:
        partial_keyword: Partial keyword input from user
        q1_response: Response to Q1
        q2_response: Response to Q2
        q3_response: Response to Q3
        q4_response: Response to Q4
        model_name: Ollama model name (default: "ministral-3:3b")
        debug_mode: Enable debug output
        config: Optional Config instance
        
    Returns:
        List of completion suggestions (empty list on error)
    """
    try:
        # Don't generate suggestions for very short inputs
        if len(partial_keyword.strip()) < 2:
            return []
        
        # Initialize config if not provided
        if config is None:
            try:
                from scripts.utils.config import Config
                config = Config()
            except Exception as e:
                logger.warning(f"Could not load Config: {e}")
                config = None
        
        # Initialize Ollama client (use cached instance)
        try:
            from scripts.vlm.ollama_client import get_or_create_client
            
            ollama_client = get_or_create_client(
                base_url=config.ollama_base_url if config else "http://localhost:11434",
                timeout=config.ollama_timeout if config else 60,  # Shorter timeout for autocomplete
                debug_mode=debug_mode,
                auto_start=config.ollama_auto_start if config else True
            )
        except Exception as e:
            logger.error(f"Failed to initialize OllamaClient: {e}")
            return []
        
        # Build prompt for autocomplete
        prompt = f"""Complete the following keyword based on the user's context. Return only the completed keyword, nothing else.

User Information:
- App purpose: {q1_response}
- Background/discipline: {q2_response}
- Focus areas/projects: {q3_response}
- Distractions to avoid: {q4_response}

Partial keyword: "{partial_keyword}"

Return only the completed keyword (e.g., if input is "spot", return "spotify" or "spotlight" based on context). Do not include any explanation.
"""
        
        if debug_mode:
            print(f"\n[ProfileSuggestionGenerator] Generating autocomplete for: '{partial_keyword}'")
        
        # Generate text response (optimized for speed)
        response = ollama_client.generate_text(
            prompt=prompt,
            model_name=model_name,
            stream=False,
            max_tokens=20,  # Very short response for autocomplete
            temperature=0.5,  # Lower temperature for more deterministic completions
            top_p=0.8
        )
        
        response_text = response.get('response', response.get('text', '')).strip()
        
        if debug_mode:
            print(f"[ProfileSuggestionGenerator] Autocomplete response: {response_text}")
        
        # Parse response - should be a single keyword
        if response_text:
            # Remove any quotes or extra formatting
            cleaned = response_text.strip('"').strip("'").strip()
            # Remove any explanation text (take first word/phrase)
            cleaned = cleaned.split('\n')[0].split('.')[0].strip()
            
            if cleaned and len(cleaned) > len(partial_keyword):
                return [cleaned]
        
        return []
        
    except Exception as e:
        logger.error(f"Error generating autocomplete suggestions: {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return []

