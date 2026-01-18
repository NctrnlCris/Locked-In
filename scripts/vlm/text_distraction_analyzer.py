"""
Text-based distraction detection using VLM model (no image input).

This module provides a simple text-only inference function that analyzes
window titles to determine if the user is distracted based on their objectives.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_text_distraction(
    window_title: str,
    objectives: str,
    context: str = "",
    model_name: str = "ministral-3:8b",
    debug_mode: bool = False,
    config: Optional[object] = None
) -> str:
    """
    Analyze if a window title indicates distraction based on user objectives.
    
    Args:
        window_title: Title of the foreground window
        objectives: User's work objectives/goals
        context: Additional context (default: empty string)
        model_name: Ollama model name (default: "ministral-3:8b")
        debug_mode: Enable debug output
        config: Optional Config instance (will create one if not provided)
        
    Returns:
        "Distracted" if likely a distraction, "Normal" otherwise
    """
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
        return "Normal"  # Default to Normal on error
    
    # Build prompt according to specification with exception for Google searches
    base_prompt = """The following process was detected with the title {window_title}.

Based on the user's objective of {objectives},

IMPORTANT: If the user is googling something, it is probably relevant to their work. Make sure that they are not on social media such as Instagram, TikTok, Reddit, Facebook, Messenger, or a game.

Is this likely a distraction? If yes, return one word "Distracted". If not return one word "Normal"
"""
    
    if context:
        prompt = f"""{context}

{base_prompt.format(window_title=window_title, objectives=objectives)}"""
    else:
        prompt = base_prompt.format(window_title=window_title, objectives=objectives)
    
    # Verbose console output
    print(f"\n{'='*70}")
    print(f"[TextDistractionAnalyzer] Starting text-based distraction analysis")
    print(f"{'='*70}")
    print(f"[TextDistractionAnalyzer] Input Parameters:")
    print(f"  - Window title: {window_title}")
    print(f"  - Objectives: {objectives}")
    if context:
        print(f"  - Context: {context}")
    else:
        print(f"  - Context: (empty)")
    print(f"  - Model: {model_name}")
    print(f"  - Debug mode: {debug_mode}")
    
    print(f"\n[TextDistractionAnalyzer] Building prompt...")
    if debug_mode:
        print(f"[TextDistractionAnalyzer] Full prompt:")
        print("-" * 70)
        print(prompt)
        print("-" * 70)
    else:
        print(f"[TextDistractionAnalyzer] Prompt preview:")
        print(f"  {prompt[:200]}...")
        print(f"  (Full prompt length: {len(prompt)} characters)")
    
    try:
        print(f"\n[TextDistractionAnalyzer] Initializing Ollama client...")
        print(f"[TextDistractionAnalyzer] Calling Ollama API with model '{model_name}'...")
        print(f"[TextDistractionAnalyzer] Request parameters:")
        print(f"  - max_tokens: 10")
        print(f"  - temperature: 0.3")
        print(f"  - top_p: 0.9")
        print(f"  - stream: False")
        
        # Generate text response
        response = ollama_client.generate_text(
            prompt=prompt,
            model_name=model_name,
            stream=False,
            max_tokens=10,  # Very short response expected
            temperature=0.3,
            top_p=0.9
        )
        
        print(f"[TextDistractionAnalyzer] API call completed successfully")
        
        response_text = response.get('response', response.get('text', '')).strip()
        eval_count = response.get('eval_count', 0)
        prompt_eval_count = response.get('prompt_eval_count', 0)
        duration_ms = response.get('total_duration', 0) / 1_000_000 if response.get('total_duration') else 0
        
        print(f"\n[TextDistractionAnalyzer] Response received:")
        print(f"  - Raw response: '{response_text}'")
        print(f"  - Response length: {len(response_text)} characters")
        print(f"  - Eval count: {eval_count}")
        print(f"  - Prompt eval count: {prompt_eval_count}")
        if duration_ms > 0:
            print(f"  - Duration: {duration_ms:.2f}ms")
        
        # Parse response - look for "Distracted" or "Normal"
        print(f"\n[TextDistractionAnalyzer] Parsing response...")
        response_lower = response_text.lower()
        
        if "distracted" in response_lower:
            result = "Distracted"
            print(f"[TextDistractionAnalyzer] ✓ Parsed as: {result}")
            print(f"[TextDistractionAnalyzer] → Interpretation: Distraction detected")
            print(f"{'='*70}\n")
            return result
        elif "normal" in response_lower:
            result = "Normal"
            print(f"[TextDistractionAnalyzer] ✓ Parsed as: {result}")
            print(f"[TextDistractionAnalyzer] → Interpretation: Not distracted")
            print(f"{'='*70}\n")
            return result
        else:
            # If response doesn't match expected format, default to Normal
            logger.warning(f"Unexpected response format: {response_text}")
            print(f"[TextDistractionAnalyzer] ⚠ Warning: Unexpected response format")
            print(f"[TextDistractionAnalyzer]   Expected: 'Distracted' or 'Normal'")
            print(f"[TextDistractionAnalyzer]   Received: '{response_text}'")
            print(f"[TextDistractionAnalyzer] → Defaulting to: Normal")
            print(f"{'='*70}\n")
            return "Normal"
            
    except Exception as e:
        logger.error(f"Error during text distraction analysis: {e}")
        print(f"\n[TextDistractionAnalyzer] ✗ Error occurred:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        if debug_mode:
            import traceback
            print(f"  Traceback:")
            traceback.print_exc()
        print(f"[TextDistractionAnalyzer] → Defaulting to: Normal (due to error)")
        print(f"{'='*70}\n")
        return "Normal"  # Default to Normal on error

