"""
Ministral-based two-stage distraction detection pipeline.

This module provides a reusable function for analyzing screenshots using
the ministral vision model in a two-stage process:
1. Stage 1: Describe what's visible in each screenshot
2. Stage 2: Determine if the user is distracted based on screenshot history

Usage:
    from scripts.vlm.ministral_analyzer import analyze_screenshots
    
    result = analyze_screenshots(
        image_paths=["image1.png", "image2.png"],
        work_topic="Python development",
        additional_context="Process: python.exe"
    )
    
    print(f"Distracted: {result['stage2']['distracted']}")
    print(f"Confidence: {result['stage2']['confidence']}%")

The function can be used from any directory as long as the scripts/ directory
is in the Python path or the script is run from the project root.
"""

import json
import re
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Handle imports - make it work from different directories
try:
    # Try relative imports first (when used as module)
    from .ollama_client import OllamaClient
    from ..utils.config import Config
except ImportError:
    try:
        # Try absolute imports with scripts prefix
        from scripts.vlm.ollama_client import OllamaClient
        from scripts.utils.config import Config
    except ImportError:
        # Fallback: add project root to path and try again
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from scripts.vlm.ollama_client import OllamaClient
        from scripts.utils.config import Config

logger = logging.getLogger(__name__)


def _get_or_create_ollama_client(config: Optional[Config] = None, debug_mode: bool = False) -> Any:
    """
    Get or create a cached OllamaClient instance.
    
    Args:
        config: Optional Config instance
        debug_mode: Enable debug output
        
    Returns:
        OllamaClient instance
    """
    # Initialize config if not provided
    if config is None:
        config = Config()
    
    # Use shared cache function from ollama_client module
    try:
        from scripts.vlm.ollama_client import get_or_create_client
        return get_or_create_client(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
            debug_mode=debug_mode,
            auto_start=config.ollama_auto_start,
            max_image_size=(768, 768),
            temp_folder=config.temp_folder
        )
    except ImportError:
        # Fallback: create new client if import fails
        return OllamaClient(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
            debug_mode=debug_mode,
            auto_start=config.ollama_auto_start,
            max_image_size=(768, 768),
            temp_folder=config.temp_folder
        )


def reparse_json_response(
    raw_response: str,
    model_name: str = "ministral-3:8b",
    debug_mode: bool = False,
    config: Optional[Config] = None,
    ollama_client: Optional[Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Reparse a failed JSON response by asking the model to reformat it.
    
    Args:
        raw_response: The raw response that failed to parse as JSON
        model_name: Ollama model name
        debug_mode: Enable debug output
        config: Optional Config instance
        ollama_client: Optional OllamaClient instance (will create one if not provided)
        
    Returns:
        Parsed JSON dictionary if successful, None otherwise
    """
    if debug_mode:
        print(f"\n[Reparse] Attempting to reparse failed JSON response...")
        print(f"[Reparse] Raw response length: {len(raw_response)} characters")
    
    # Initialize Ollama client if not provided (use cached instance)
    if ollama_client is None:
        if config is None:
            try:
                from scripts.utils.config import Config
                config = Config()
            except Exception as e:
                logger.warning(f"Could not load Config for reparse: {e}")
                return None
        
        try:
            ollama_client = _get_or_create_ollama_client(config=config, debug_mode=debug_mode)
        except Exception as e:
            logger.error(f"Failed to initialize OllamaClient for reparse: {e}")
            return None
    
    # Build reparse prompt
    reparse_prompt = f"""The following text was supposed to be a JSON response but failed to parse. Please reformat it into valid JSON.

Previous response:
{raw_response}

Please extract and reformat this into a valid JSON object with the following structure:
{{
    "Reasoning": "Your reasoning/thoughts here",
    "Distracted": true/false,
    "Confidence": 0-100
}}

Return ONLY the JSON object, no other text. Make sure it's valid JSON."""
    
    if debug_mode:
        print(f"[Reparse] Sending reparse request to model...")
        print(f"[Reparse] Prompt preview: {reparse_prompt[:200]}...")
    
    try:
        # Generate reformatted response
        response = ollama_client.generate_text(
            prompt=reparse_prompt,
            model_name=model_name,
            stream=False,
            max_tokens=200,  # Should be enough for reformatted JSON
            temperature=0.1,  # Lower temperature for more deterministic reformatting
            top_p=0.9
        )
        
        response_text = response.get('response', response.get('text', '')).strip()
        
        if debug_mode:
            print(f"[Reparse] Received reformatted response:")
            print(f"[Reparse] {response_text[:300]}...")
        
        # Try to parse the reformatted JSON
        import re
        cleaned_response = response_text.strip()
        cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
        cleaned_response = re.sub(r'```\s*', '', cleaned_response)
        
        # Find JSON object
        json_match = re.search(r'\{.*?"Reasoning".*?\}', cleaned_response, re.DOTALL | re.IGNORECASE)
        if not json_match:
            json_match = re.search(r'\{[^{}]*"Distracted"[^{}]*\}', cleaned_response, re.DOTALL | re.IGNORECASE)
        if not json_match:
            json_match = re.search(r'\{.*"Distracted".*\}', cleaned_response, re.DOTALL | re.IGNORECASE)
        
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed_json = json.loads(json_str)
                if debug_mode:
                    print(f"[Reparse] Successfully parsed reformatted JSON!")
                return parsed_json
            except json.JSONDecodeError as e:
                if debug_mode:
                    print(f"[Reparse] Still failed to parse reformatted JSON: {e}")
                return None
        else:
            if debug_mode:
                print(f"[Reparse] No JSON object found in reformatted response")
            return None
            
    except Exception as e:
        logger.error(f"Error during JSON reparse: {e}")
        if debug_mode:
            print(f"[Reparse] Error: {e}")
        return None


def analyze_screenshots(
    image_paths: List[str],
    work_topic: str,
    model_name: str = "ministral-3:8b",
    debug_mode: bool = False,
    config: Optional[Config] = None,
    additional_context: str = ''
) -> Dict[str, Any]:
    """
    Analyze multiple screenshots using two-stage ministral pipeline.
    
    Args:
        image_paths: List of paths to screenshot images
        work_topic: User's current work topic
        model_name: Ollama model name (default: "ministral-3:8b")
        debug_mode: Enable debug output
        config: Optional Config instance (will create one if not provided)
        additional_context: Additional context to inject into Stage 2 reasoning
                           (e.g., process type, work history, system preferences)
                           Default: empty string
        
    Returns:
        Dictionary with analysis results:
        {
            'stage1': {
                'descriptions': List[str],  # List of image descriptions
                'raw_response': str,
                'model': str,
                'eval_count': int,
                'prompt_eval_count': int,
                'duration_ms': float
            },
            'stage2': {
                'distracted': bool,
                'confidence': int (0-100),
                'reasoning': str,  # Detailed reasoning/thoughts from the model
                'raw_response': str,
                'model': str,
                'eval_count': int,
                'duration_ms': float
            },
            'errors': List[str]  # Any errors encountered
        }
    """
    errors = []
    
    # Display analysis start info in debug mode
    if debug_mode:
        print(f"\n{'='*70}")
        print(f"[VLM Analysis] Starting analysis")
        print(f"{'='*70}")
        print(f"[VLM Analysis] Input Parameters:")
        print(f"  - Image paths: {len(image_paths)} image(s)")
        for i, img_path in enumerate(image_paths, 1):
            print(f"    {i}. {img_path}")
        print(f"  - Work topic: {work_topic}")
        if additional_context:
            print(f"  - Additional context: {additional_context}")
        print(f"  - Model: {model_name}")
        print(f"  - Debug mode: {debug_mode}")
    
    # Initialize config if not provided
    if config is None:
        config = Config()
    
    # Initialize Ollama client (use cached instance)
    ollama_client = _get_or_create_ollama_client(config=config, debug_mode=debug_mode)
    
    num_images = len(image_paths)
    
    # Stage 1: Describe screenshots
    stage1_result = {
        'descriptions': [],
        'raw_response': '',
        'model': '',
        'eval_count': 0,
        'prompt_eval_count': 0,
        'duration_ms': 0.0
    }
    
    try:
        # Build Stage 1 prompt (ministral format)
        if num_images == 1:
            stage1_prompt = f"""Look at this screenshot and describe what you see in one simple sentence.

            The user should be working on: {work_topic}

            Respond with ONLY a simple JSON object. Use this exact format:

            {{"desc_image1": "brief one-sentence description of what is visible"}}

            IMPORTANT: The value must be a simple string, NOT a nested object. Just describe what you see in plain text. If you see a conversation in a chat app, summarize it to obtain context."""
        else:
            stage1_prompt = f"""You are analyzing {num_images} screenshots. Describe what you see in each one.

            The user should be working on: {work_topic}

            Respond with ONLY a simple JSON object. Use this exact format for the {num_images} images:

            {{"desc_image1": "one sentence description", "desc_image2": "one sentence description", "desc_image3": "one sentence description", ...}}

            IMPORTANT: Each value must be a simple string, NOT a nested object. Just describe what you see in plain text. Make sure to describe all {num_images} images."""
        
        # Display prompt in debug mode
        if debug_mode:
            print(f"\n{'='*70}")
            print(f"[VLM Stage 1] Prompt:")
            print("-" * 70)
            print(stage1_prompt)
            print("-" * 70)
            print(f"[VLM Stage 1] Analyzing {num_images} image(s)...")
        
        # Run Stage 1
        if num_images == 1:
            response = ollama_client.generate_vision(
                image_path=image_paths[0],
                prompt=stage1_prompt,
                model_name=model_name,
                stream=True,
                repeat_penalty=config.stage1_repeat_penalty
            )
        else:
            response = ollama_client.generate_vision_multi(
                image_paths=image_paths,
                prompt=stage1_prompt,
                model_name=model_name,
                stream=True,
                repeat_penalty=config.stage1_repeat_penalty
            )
        
        # Extract and parse Stage 1 response
        response_text = response.get('response', response.get('text', ''))
        stage1_result['raw_response'] = response_text
        
        # Display raw response in debug mode
        if debug_mode:
            print(f"\n[VLM Stage 1] Raw Response:")
            print("-" * 70)
            print(response_text[:500] + ("..." if len(response_text) > 500 else ""))
            print("-" * 70)
        stage1_result['model'] = response.get('model', 'N/A')
        stage1_result['eval_count'] = response.get('eval_count', 0)
        stage1_result['prompt_eval_count'] = response.get('prompt_eval_count', 0)
        
        if response.get('total_duration'):
            stage1_result['duration_ms'] = response.get('total_duration', 0) / 1_000_000
        
        if response_text:
            # Parse Stage 1 descriptions
            cleaned_text = response_text.strip()
            cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
            cleaned_text = re.sub(r'```\s*', '', cleaned_text)
            cleaned_text = cleaned_text.replace('\\_', '_').replace('\\*', '*')
            
            # Find JSON object
            json_match = re.search(r'\{[^{}]*"desc_image\d+"[^{}]*\}', cleaned_text, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*"desc_image.*\}', cleaned_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_json = json.loads(json_str)
                    
                    # Extract descriptions
                    descriptions = []
                    for i in range(1, num_images + 1):
                        key = f"desc_image{i}"
                        alt_keys = [f"image_{i}", f"image{i}", f"Image {i}", f"Image_{i}"]
                        desc = None
                        
                        if key in parsed_json:
                            desc = parsed_json[key]
                        else:
                            for alt_key in alt_keys:
                                if alt_key in parsed_json:
                                    desc = parsed_json[alt_key]
                                    break
                        
                        if desc is not None:
                            # Recursively extract string from nested structures
                            def extract_string(obj):
                                if isinstance(obj, str):
                                    return obj
                                elif isinstance(obj, dict):
                                    for field in ["description", "text", "desc", "content", "summary"]:
                                        if field in obj and isinstance(obj[field], str):
                                            return obj[field]
                                    strings = [v for v in obj.values() if isinstance(v, str)]
                                    if strings:
                                        return max(strings, key=len)
                                    for v in obj.values():
                                        result = extract_string(v)
                                        if result:
                                            return result
                                    return None
                                elif isinstance(obj, list):
                                    for item in obj:
                                        result = extract_string(item)
                                        if result:
                                            return result
                                    return None
                                return None
                            
                            extracted = extract_string(desc)
                            if extracted:
                                descriptions.append(extracted)
                            else:
                                descriptions.append(str(desc)[:200])
                    
                    stage1_result['descriptions'] = descriptions
                    
                except json.JSONDecodeError as e:
                    error_msg = f"Failed to parse Stage 1 JSON: {e}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    # Try to extract manually
                    desc_matches = re.findall(r'"desc_image(\d+)"\s*:\s*"([^"]+)"', json_str)
                    if desc_matches:
                        stage1_result['descriptions'] = [desc for _, desc in desc_matches]
            else:
                error_msg = "No JSON object found in Stage 1 response"
                errors.append(error_msg)
                logger.warning(error_msg)
    except Exception as e:
        error_msg = f"Stage 1 error: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg, exc_info=True)
    
    # Stage 2: Distraction detection (only if we have descriptions)
    stage2_result = {
        'distracted': None,
        'confidence': None,
        'raw_response': '',
        'model': '',
        'eval_count': 0,
        'duration_ms': 0.0
    }
    
    if stage1_result['descriptions']:
        try:
            # Build Stage 2 prompt
            desc_text = "\n".join([f"  {i+1}. {desc}" for i, desc in enumerate(stage1_result['descriptions'])])
            
            # Build additional context section if provided
            context_section = ""
            if additional_context:
                context_section = f"""
                
                Additional Context:
                {additional_context}
                """
            
            stage2_prompt = f"""You are analyzing a sequence of screenshot descriptions to determine if the user is distracted.

                The user should be working on: {work_topic} and related tasks

                Screenshot History:
                {desc_text}{context_section}
                Based on this screenshot history, determine if the user is distracted from their work. Make sure to consider context of any videos they are watching if applicable. 
                if educational and relevant to task or relative benchmarks/research, then it is not distraction.
                Note that we want to minimize false positives, thus unless you are almost 100% certain it is a distraction, you should
                reason very carefully.

                Note that you don't need to see a console or word file to confirm that they *were* working. They could just be looking things up like relevant studies, models, tools, or resources.
                Your primary objective should be to monitor for game use or social media/communication, or if something is significantly different from their work.

                Respond with ONLY a JSON object. Use this exact format:

                {{
                    "Reasoning": "Your detailed reasoning here - explain what you see, why it might or might not be a distraction, and your thought process",
                    "Distracted": true/false,
                    "Confidence": 0-100
                }}

                IMPORTANT: 
                - "Reasoning" must be a string explaining your thought process and analysis
                - "Distracted" must be a boolean (true or false)
                - "Confidence" must be a number between 0 and 100
                - Return ONLY the JSON object, no other text
                - Put your reasoning FIRST, then the conclusion"""
            
            # Display prompt in debug mode
            if debug_mode:
                print(f"\n{'='*70}")
                print(f"[VLM Stage 2] Prompt:")
                print("-" * 70)
                print(stage2_prompt)
                print("-" * 70)
            
            # Run Stage 2
            stage2_response = ollama_client.generate_text(
                prompt=stage2_prompt,
                model_name=model_name,
                stream=True,
                max_tokens=400,  # Increased to allow for complete JSON with reasoning
                temperature=0.3,
                top_p=0.9
            )
            
            # Parse Stage 2 response
            stage2_text = stage2_response.get('response', stage2_response.get('text', ''))
            stage2_result['raw_response'] = stage2_text
            stage2_result['model'] = stage2_response.get('model', 'N/A')
            stage2_result['eval_count'] = stage2_response.get('eval_count', 0)
            
            if stage2_response.get('total_duration'):
                stage2_result['duration_ms'] = stage2_response.get('total_duration', 0) / 1_000_000
            
            # Display raw response in debug mode
            if debug_mode:
                print(f"\n[VLM Stage 2] Raw Response:")
                print("-" * 70)
                print(stage2_text)
                print("-" * 70)
            
            if stage2_text:
                # Clean and parse Stage 2 JSON
                cleaned_stage2 = stage2_text.strip()
                cleaned_stage2 = re.sub(r'```json\s*', '', cleaned_stage2)
                cleaned_stage2 = re.sub(r'```\s*', '', cleaned_stage2)
                
                # Try to parse the entire cleaned text first (most robust)
                stage2_parsed = None
                stage2_json_str = None
                
                try:
                    stage2_parsed = json.loads(cleaned_stage2)
                    stage2_json_str = cleaned_stage2
                except json.JSONDecodeError:
                    # If direct parse fails, try to extract JSON object using balanced braces
                    def find_json_object(text):
                        """Find the first complete JSON object by matching balanced braces."""
                        start_idx = text.find('{')
                        if start_idx == -1:
                            return None
                        
                        brace_count = 0
                        in_string = False
                        escape_next = False
                        
                        for i in range(start_idx, len(text)):
                            char = text[i]
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        return text[start_idx:i+1]
                        
                        return None
                    
                    # Try to find JSON object with balanced braces
                    stage2_json_str = find_json_object(cleaned_stage2)
                    
                    if stage2_json_str:
                        try:
                            stage2_parsed = json.loads(stage2_json_str)
                        except json.JSONDecodeError:
                            stage2_json_str = None
                    
                    # Fallback to regex if balanced brace matching failed
                    if not stage2_json_str:
                        stage2_json_match = re.search(r'\{.*?"Reasoning".*?\}', cleaned_stage2, re.DOTALL | re.IGNORECASE)
                        if not stage2_json_match:
                            stage2_json_match = re.search(r'\{[^{}]*"Distracted"[^{}]*\}', cleaned_stage2, re.DOTALL | re.IGNORECASE)
                        if not stage2_json_match:
                            stage2_json_match = re.search(r'\{.*"Distracted".*\}', cleaned_stage2, re.DOTALL | re.IGNORECASE)
                        
                        if stage2_json_match:
                            stage2_json_str = stage2_json_match.group(0)
                            try:
                                stage2_parsed = json.loads(stage2_json_str)
                            except json.JSONDecodeError:
                                stage2_parsed = None
                
                if stage2_parsed:
                    # Extract reasoning if present
                    reasoning = None
                    for key, value in stage2_parsed.items():
                        key_lower = key.lower()
                        if 'reason' in key_lower:
                            reasoning = str(value)
                            stage2_result['reasoning'] = reasoning
                            break
                    
                    # Display reasoning in debug mode
                    if debug_mode and reasoning:
                        print(f"\n[VLM Stage 2] Reasoning:")
                        print("-" * 70)
                        print(reasoning)
                        print("-" * 70)
                    
                    # Extract values (case-insensitive)
                    for key, value in stage2_parsed.items():
                        key_lower = key.lower()
                        if 'distract' in key_lower:
                            stage2_result['distracted'] = bool(value)
                        elif 'confid' in key_lower:
                            stage2_result['confidence'] = int(value) if isinstance(value, (int, float)) else None
                    
                    # Display conclusion in debug mode
                    if debug_mode:
                        print(f"\n[VLM Stage 2] Conclusion:")
                        print(f"  - Distracted: {stage2_result['distracted']}")
                        print(f"  - Confidence: {stage2_result['confidence']}%")
                        print(f"{'='*70}\n")
                else:
                    # JSON parsing failed, try to reparse
                    error_msg = "Failed to parse Stage 2 JSON"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    if debug_mode:
                        print(f"[VLM Stage 2] JSON Parse Error: Could not extract valid JSON")
                        if stage2_json_str:
                            print(f"[VLM Stage 2] Attempted to parse: {stage2_json_str[:200]}...")
                        print(f"[VLM Stage 2] Attempting to reparse...")
                    
                    # Try to reparse the response
                    try:
                        reparsed_json = reparse_json_response(
                            raw_response=stage2_text,
                            model_name=model_name,
                            debug_mode=debug_mode,
                            config=config,
                            ollama_client=ollama_client
                        )
                        
                        if reparsed_json:
                            # Successfully reparsed - extract values
                            reasoning = None
                            for key, value in reparsed_json.items():
                                key_lower = key.lower()
                                if 'reason' in key_lower:
                                    reasoning = str(value)
                                    stage2_result['reasoning'] = reasoning
                                    break
                            
                            # Display reasoning in debug mode
                            if debug_mode and reasoning:
                                print(f"\n[VLM Stage 2] Reasoning (from reparsed):")
                                print("-" * 70)
                                print(reasoning)
                                print("-" * 70)
                            
                            # Extract values
                            for key, value in reparsed_json.items():
                                key_lower = key.lower()
                                if 'distract' in key_lower:
                                    stage2_result['distracted'] = bool(value)
                                elif 'confid' in key_lower:
                                    stage2_result['confidence'] = int(value) if isinstance(value, (int, float)) else None
                            
                            if debug_mode:
                                print(f"[VLM Stage 2] Successfully reparsed JSON!")
                                print(f"\n[VLM Stage 2] Conclusion:")
                                print(f"  - Distracted: {stage2_result['distracted']}")
                                print(f"  - Confidence: {stage2_result['confidence']}%")
                                print(f"{'='*70}\n")
                        else:
                            if debug_mode:
                                print(f"[VLM Stage 2] Reparse also failed")
                    except Exception as e:
                        if debug_mode:
                            print(f"[VLM Stage 2] Error during reparse: {e}")
            else:
                error_msg = "No JSON object found in Stage 2 response"
                errors.append(error_msg)
                logger.warning(error_msg)
                if debug_mode:
                    print(f"[VLM Stage 2] No JSON found in response")
                    print(f"[VLM Stage 2] Response text: {stage2_text[:200]}...")
                    print(f"[VLM Stage 2] Attempting to reparse...")
                
                # Try to reparse the entire response
                try:
                    reparsed_json = reparse_json_response(
                        raw_response=stage2_text,
                        model_name=model_name,
                        debug_mode=debug_mode,
                        config=config,
                        ollama_client=ollama_client
                    )
                    
                    if reparsed_json:
                        # Successfully reparsed - extract values
                        reasoning = None
                        for key, value in reparsed_json.items():
                            key_lower = key.lower()
                            if 'reason' in key_lower:
                                reasoning = str(value)
                                stage2_result['reasoning'] = reasoning
                                break
                        
                        # Display reasoning in debug mode
                        if debug_mode and reasoning:
                            print(f"\n[VLM Stage 2] Reasoning (from reparsed):")
                            print("-" * 70)
                            print(reasoning)
                            print("-" * 70)
                        
                        # Extract values
                        for key, value in reparsed_json.items():
                            key_lower = key.lower()
                            if 'distract' in key_lower:
                                stage2_result['distracted'] = bool(value)
                            elif 'confid' in key_lower:
                                stage2_result['confidence'] = int(value) if isinstance(value, (int, float)) else None
                        
                        if debug_mode:
                            print(f"[VLM Stage 2] Successfully reparsed JSON!")
                            print(f"\n[VLM Stage 2] Conclusion:")
                            print(f"  - Distracted: {stage2_result['distracted']}")
                            print(f"  - Confidence: {stage2_result['confidence']}%")
                            print(f"{'='*70}\n")
                except Exception as e:
                    if debug_mode:
                        print(f"[VLM Stage 2] Error during reparse: {e}")
                        error_msg = f"Failed to parse Stage 2 JSON: {e}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        if debug_mode:
                            print(f"[VLM Stage 2] JSON Parse Error: {e}")
                            print(f"[VLM Stage 2] Attempted to parse: {stage2_json_str[:200]}...")
                            print(f"[VLM Stage 2] Attempting to reparse...")
                        
                        # Try to reparse the response
                        reparsed_json = reparse_json_response(
                            raw_response=stage2_text,
                            model_name=model_name,
                            debug_mode=debug_mode,
                            config=config,
                            ollama_client=ollama_client
                        )
                        
                        if reparsed_json:
                            # Successfully reparsed - extract values
                            reasoning = None
                            for key, value in reparsed_json.items():
                                key_lower = key.lower()
                                if 'reason' in key_lower:
                                    reasoning = str(value)
                                    stage2_result['reasoning'] = reasoning
                                    break
                            
                            # Display reasoning in debug mode
                            if debug_mode and reasoning:
                                print(f"\n[VLM Stage 2] Reasoning (from reparsed):")
                                print("-" * 70)
                                print(reasoning)
                                print("-" * 70)
                            
                            # Extract values
                            for key, value in reparsed_json.items():
                                key_lower = key.lower()
                                if 'distract' in key_lower:
                                    stage2_result['distracted'] = bool(value)
                                elif 'confid' in key_lower:
                                    stage2_result['confidence'] = int(value) if isinstance(value, (int, float)) else None
                            
                            if debug_mode:
                                print(f"[VLM Stage 2] Successfully reparsed JSON!")
                                print(f"\n[VLM Stage 2] Conclusion:")
                                print(f"  - Distracted: {stage2_result['distracted']}")
                                print(f"  - Confidence: {stage2_result['confidence']}%")
                                print(f"{'='*70}\n")
                        else:
                            if debug_mode:
                                print(f"[VLM Stage 2] Reparse also failed")
                else:
                    error_msg = "No JSON object found in Stage 2 response"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    if debug_mode:
                        print(f"[VLM Stage 2] No JSON found in response")
                        print(f"[VLM Stage 2] Response text: {stage2_text[:200]}...")
                        print(f"[VLM Stage 2] Attempting to reparse...")
                    
                    # Try to reparse the entire response
                    reparsed_json = reparse_json_response(
                        raw_response=stage2_text,
                        model_name=model_name,
                        debug_mode=debug_mode,
                        config=config,
                        ollama_client=ollama_client
                    )
                    
                    if reparsed_json:
                        # Successfully reparsed - extract values
                        reasoning = None
                        for key, value in reparsed_json.items():
                            key_lower = key.lower()
                            if 'reason' in key_lower:
                                reasoning = str(value)
                                stage2_result['reasoning'] = reasoning
                                break
                        
                        # Display reasoning in debug mode
                        if debug_mode and reasoning:
                            print(f"\n[VLM Stage 2] Reasoning (from reparsed):")
                            print("-" * 70)
                            print(reasoning)
                            print("-" * 70)
                        
                        # Extract values
                        for key, value in reparsed_json.items():
                            key_lower = key.lower()
                            if 'distract' in key_lower:
                                stage2_result['distracted'] = bool(value)
                            elif 'confid' in key_lower:
                                stage2_result['confidence'] = int(value) if isinstance(value, (int, float)) else None
                        
                        if debug_mode:
                            print(f"[VLM Stage 2] Successfully reparsed JSON!")
                            print(f"\n[VLM Stage 2] Conclusion:")
                            print(f"  - Distracted: {stage2_result['distracted']}")
                            print(f"  - Confidence: {stage2_result['confidence']}%")
                            print(f"{'='*70}\n")
        except Exception as e:
            error_msg = f"Stage 2 error: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
    
    return {
        'stage1': stage1_result,
        'stage2': stage2_result,
        'errors': errors
    }

