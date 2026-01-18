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
from typing import List, Dict, Any, Optional, Callable

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
    additional_context: str = '',
    check_cancelled: Optional[Callable[[], bool]] = None
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
                repeat_penalty=config.stage1_repeat_penalty,
                check_cancelled=check_cancelled
            )
        else:
            response = ollama_client.generate_vision_multi(
                image_paths=image_paths,
                prompt=stage1_prompt,
                model_name=model_name,
                stream=True,
                repeat_penalty=config.stage1_repeat_penalty,
                check_cancelled=check_cancelled
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
                if educational and relevant to task or relative benchmarks/research, then it is not distraction. Note that it must be in the same domain. If the user is reading something related to the
                social sciences or history, and their work is coding, then it is a distraction. Similarly, if the user is reading something related to historic events on wikipedia, and their work is coding, then it is a distraction.
                Note that any educational tools must be directly relevant. Not "generally cognitive in nature". Puzzle games are still distracting.
                
                Remember that the user is working on {work_topic}.


                Note that we want to minimize false positives, thus unless you are almost 100% certain it is a distraction, you should
                reason very carefully.

                Note that you don't need to see a console or word file to confirm that they *were* working. They could just be looking things up like relevant studies, models, tools, or resources.
                Your primary objective should be to monitor for game use or social media/communication, or if something is significantly different from their work.

                Provide your detailed reasoning explaining what you see, why it might or might not be a distraction, and your thought process.

                IMPORTANT: At the very end of your response, after all your reasoning, output exactly this format on its own line:
                -Final Conclusion: Working
                or
                -Final Conclusion: Distracted"""
            
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
                top_p=0.9,
                check_cancelled=check_cancelled
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
                # Extract status word ("Working" or "Distracted") from the response
                # Look for the format "-Final Conclusion: {status}" at the end
                cleaned_stage2 = stage2_text.strip()
                
                # Extract reasoning (everything before the status word)
                status_word = None
                reasoning = None
                
                # First, try to find the exact format "-Final Conclusion: {status}"
                conclusion_pattern = re.search(r'-Final\s+Conclusion:\s*(Working|Distracted)', cleaned_stage2, re.IGNORECASE)
                
                if conclusion_pattern:
                    status_word = conclusion_pattern.group(1).capitalize()  # Normalize to "Working" or "Distracted"
                    reasoning = cleaned_stage2[:conclusion_pattern.start()].strip()
                else:
                    # Fallback: Try to find "Working" or "Distracted" at the end of the response
                    # Check last few lines for the status word
                    lines = cleaned_stage2.split('\n')
                    
                    # Search from the end backwards for the status word
                    for i in range(len(lines) - 1, max(-1, len(lines) - 10), -1):
                        line = lines[i].strip()
                        # Check for the format pattern
                        line_match = re.search(r'-Final\s+Conclusion:\s*(Working|Distracted)', line, re.IGNORECASE)
                        if line_match:
                            status_word = line_match.group(1).capitalize()
                            reasoning = '\n'.join(lines[:i]).strip()
                            break
                        elif line.upper() == "WORKING":
                            status_word = "Working"
                            reasoning = '\n'.join(lines[:i]).strip()
                            break
                        elif line.upper() == "DISTRACTED":
                            status_word = "Distracted"
                            reasoning = '\n'.join(lines[:i]).strip()
                            break
                    
                    # If still not found, try regex search for standalone words
                    if not status_word:
                        # Look for "Working" or "Distracted" as standalone words (case-insensitive)
                        working_match = re.search(r'\b(Working|WORKING)\b', cleaned_stage2, re.IGNORECASE)
                        distracted_match = re.search(r'\b(Distracted|DISTRACTED)\b', cleaned_stage2, re.IGNORECASE)
                        
                        # Prefer the one that appears later in the text (closer to the end)
                        if working_match and distracted_match:
                            if working_match.end() > distracted_match.end():
                                status_word = "Working"
                                reasoning = cleaned_stage2[:working_match.start()].strip()
                            else:
                                status_word = "Distracted"
                                reasoning = cleaned_stage2[:distracted_match.start()].strip()
                        elif working_match:
                            status_word = "Working"
                            reasoning = cleaned_stage2[:working_match.start()].strip()
                        elif distracted_match:
                            status_word = "Distracted"
                            reasoning = cleaned_stage2[:distracted_match.start()].strip()
                
                if status_word:
                    # Set distracted based on status word
                    stage2_result['distracted'] = (status_word == "Distracted")
                    
                    # Store reasoning if found
                    if reasoning:
                        stage2_result['reasoning'] = reasoning
                    
                    # Set a default confidence (we can't extract it from the word-only format)
                    # Use a reasonable default or try to extract from reasoning if possible
                    stage2_result['confidence'] = 85  # Default confidence when using word-only format
                    
                    # Try to extract confidence from reasoning if mentioned
                    confidence_match = re.search(r'(\d+)%?\s*(?:confidence|certain)', reasoning or '', re.IGNORECASE)
                    if confidence_match:
                        try:
                            stage2_result['confidence'] = int(confidence_match.group(1))
                        except ValueError:
                            pass
                    
                    # Display results in debug mode
                    if debug_mode:
                        if reasoning:
                            print(f"\n[VLM Stage 2] Reasoning:")
                            print("-" * 70)
                            print(reasoning)
                            print("-" * 70)
                        print(f"\n[VLM Stage 2] Conclusion:")
                        print(f"  - Status: {status_word}")
                        print(f"  - Distracted: {stage2_result['distracted']}")
                        print(f"  - Confidence: {stage2_result['confidence']}%")
                        print(f"{'='*70}\n")
                else:
                    # Status word not found
                    error_msg = "Could not find 'Working' or 'Distracted' status word in Stage 2 response"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    if debug_mode:
                        print(f"[VLM Stage 2] Status Word Not Found")
                        print(f"[VLM Stage 2] Response text: {stage2_text[:500]}...")
                        print(f"[VLM Stage 2] Full response length: {len(stage2_text)} characters")
            else:
                error_msg = "Empty Stage 2 response"
                errors.append(error_msg)
                logger.warning(error_msg)
                if debug_mode:
                    print(f"[VLM Stage 2] Empty response received")
        except Exception as e:
            error_msg = f"Stage 2 error: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
    
    return {
        'stage1': stage1_result,
        'stage2': stage2_result,
        'errors': errors
    }

