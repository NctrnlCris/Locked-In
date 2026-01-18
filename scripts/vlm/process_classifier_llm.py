"""
LLM-based process classifier for profile-specific process classifications.

This module uses the Ministral LLM to classify processes from message.txt
into Work/Mixed/Entertainment categories based on user's profile responses.
"""

import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


def read_processes_from_message_txt(file_path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Read all processes from message.txt.
    
    Args:
        file_path: Path to message.txt. If None, uses default location.
        
    Returns:
        List of dicts with keys: exe, category, product, use_hint
    """
    if file_path is None:
        project_root = Path(__file__).parent.parent.parent
        file_path = str(project_root / "message.txt")
    
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        logger.error(f"message.txt not found at: {file_path}")
        return []
    
    processes = []
    with open(file_path_obj, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            exe = row.get('exe', '').strip()
            if exe:
                processes.append({
                    'exe': exe,
                    'category': row.get('category', '').strip(),
                    'product': row.get('product', '').strip(),
                    'use_hint': row.get('use_hint', '').strip()
                })
    
    return processes


def chunk_processes(processes: List[Dict[str, str]], chunk_size: int = 30) -> List[List[Dict[str, str]]]:
    """Split processes into chunks of specified size."""
    return [processes[i:i + chunk_size] for i in range(0, len(processes), chunk_size)]


def build_classification_prompt(
    processes_chunk: List[Dict[str, str]],
    responses: Dict[str, str]
) -> str:
    """
    Build the LLM prompt for classifying a chunk of processes.
    
    Args:
        processes_chunk: List of process dicts to classify
        responses: User's responses to the 6 setup questions
        
    Returns:
        Formatted prompt string
    """
    # Extract responses (handle both full question text and shortened keys)
    q1 = responses.get("What would you like to use this app for?", "")
    q2 = responses.get("What is your background? (e.g., student, developer, writer) - Please specify your specific discipline of study", 
                       responses.get("What is your background? (e.g., student, developer, writer)", ""))
    q3 = responses.get("What are your main things you want to focus on? (What are you planning on working on, describe your project or task)",
                       responses.get("What are your main things you want to focus on?", ""))
    q4 = responses.get("What are things you want to prevent to be distraction-free?", "")
    q5 = responses.get("Is there anything particular that you want to whitelist that will be used when you focus?", "")
    q6 = responses.get("Is there anything that you want to be distraction-free from?", "")
    
    # Build process list
    process_list = ""
    for p in processes_chunk:
        process_list += f"- {p['exe']} ({p['product']}, {p['category']})\n"
    
    prompt = f"""Based on this user's profile, classify each application as Work, Mixed, or Entertainment.

USER PROFILE:
- Purpose for using focus app: {q1}
- Background/discipline: {q2}
- Focus areas/projects: {q3}
- Distractions to avoid: {q4}
- Things to whitelist for work: {q5}
- Things to blacklist as distractions: {q6}

CLASSIFICATION RULES:
- Work: Applications essential for the user's work/study based on their background
- Mixed: Applications that could be used for work OR entertainment (e.g., browsers, chat apps)
- Entertainment: Applications primarily for entertainment, gaming, or leisure

APPLICATIONS TO CLASSIFY:
{process_list}
For each application, output EXACTLY in this format (one per line):
exe_name: Classification

Example output:
chrome.exe: Mixed
spotify.exe: Entertainment
code.exe: Work

IMPORTANT: Output ONLY the classification lines, nothing else. Classify ALL {len(processes_chunk)} applications."""

    return prompt


def parse_classification_response(response_text: str, processes_chunk: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Parse the LLM response to extract classifications.
    
    Args:
        response_text: Raw LLM response
        processes_chunk: Original process list for fallback
        
    Returns:
        Dict mapping exe name to classification
    """
    classifications = {}
    
    # Create a set of valid exe names for validation
    valid_exes = {p['exe'].lower() for p in processes_chunk}
    
    # Parse each line
    for line in response_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Try to match "exe_name: Classification" pattern
        match = re.match(r'^([^:]+\.exe)\s*:\s*(Work|Mixed|Entertainment)\s*$', line, re.IGNORECASE)
        if match:
            exe = match.group(1).strip().lower()
            classification = match.group(2).strip().capitalize()
            
            # Normalize classification
            if classification.lower() in ['work', 'system/work']:
                classification = 'Work'
            elif classification.lower() == 'mixed':
                classification = 'Mixed'
            elif classification.lower() == 'entertainment':
                classification = 'Entertainment'
            else:
                continue
            
            if exe in valid_exes:
                classifications[exe] = classification
    
    return classifications


def classify_processes_for_profile(
    responses: Dict[str, str],
    model_name: str = "ministral-3:3b",
    chunk_size: int = 30,
    debug_mode: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, any]:
    """
    Classify all processes from message.txt based on user profile responses.
    
    Args:
        responses: User's responses to the 6 setup questions
        model_name: Ollama model to use for classification
        chunk_size: Number of processes per LLM call
        debug_mode: Enable debug output
        progress_callback: Optional callback(current_chunk, total_chunks) for progress updates
        
    Returns:
        Dict with keys:
        - process_classifications: {work_processes: [], mixed_processes: [], entertainment_processes: []}
        - success: bool
        - error: str (if failed)
    """
    result = {
        'process_classifications': {
            'work_processes': [],
            'mixed_processes': [],
            'entertainment_processes': []
        },
        'success': False,
        'error': None
    }
    
    try:
        # Read all processes
        processes = read_processes_from_message_txt()
        if not processes:
            result['error'] = "No processes found in message.txt"
            return result
        
        if debug_mode:
            print(f"[ProcessClassifier] Found {len(processes)} processes to classify")
        
        # Initialize Ollama client
        try:
            from scripts.vlm.ollama_client import get_or_create_client
            from scripts.utils.config import Config
            
            config = Config()
            ollama_client = get_or_create_client(
                base_url=config.ollama_base_url,
                timeout=config.ollama_timeout,
                debug_mode=debug_mode,
                auto_start=config.ollama_auto_start
            )
        except Exception as e:
            result['error'] = f"Failed to initialize Ollama client: {e}"
            logger.error(result['error'])
            return result
        
        # Chunk processes
        chunks = chunk_processes(processes, chunk_size)
        total_chunks = len(chunks)
        
        if debug_mode:
            print(f"[ProcessClassifier] Split into {total_chunks} chunks of {chunk_size}")
        
        # Notify progress callback that we're starting (chunk 0 of total)
        if progress_callback:
            try:
                progress_callback(0, total_chunks)
            except Exception as e:
                logger.warning(f"Error calling progress callback: {e}")
        
        # Track all classifications
        all_classifications = {}
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            if progress_callback:
                try:
                    progress_callback(i + 1, total_chunks)
                except Exception as e:
                    logger.warning(f"Error calling progress callback: {e}")
            
            if debug_mode:
                print(f"[ProcessClassifier] Processing chunk {i + 1}/{total_chunks}...")
            
            # Build prompt
            prompt = build_classification_prompt(chunk, responses)
            
            # Call LLM
            try:
                response = ollama_client.generate_text(
                    prompt=prompt,
                    model_name=model_name,
                    stream=False,
                    max_tokens=1500,  # Enough for ~30 classifications
                    temperature=0.3,  # Lower temperature for consistency
                    top_p=0.9
                )
                
                response_text = response.get('response', response.get('text', ''))
                
                if debug_mode:
                    print(f"[ProcessClassifier] Chunk {i + 1} response:\n{response_text[:500]}...")
                
                # Parse response
                chunk_classifications = parse_classification_response(response_text, chunk)
                all_classifications.update(chunk_classifications)
                
                if debug_mode:
                    print(f"[ProcessClassifier] Classified {len(chunk_classifications)} processes in chunk {i + 1}")
                
            except Exception as e:
                logger.warning(f"Error processing chunk {i + 1}: {e}")
                # Use default hints for failed chunks
                for p in chunk:
                    exe = p['exe'].lower()
                    if exe not in all_classifications:
                        hint = p['use_hint']
                        if hint == 'Work' or 'Work' in hint:
                            all_classifications[exe] = 'Work'
                        elif hint == 'Entertainment':
                            all_classifications[exe] = 'Entertainment'
                        else:
                            all_classifications[exe] = 'Mixed'
        
        # For any processes not classified by LLM, use default hints
        for p in processes:
            exe = p['exe'].lower()
            if exe not in all_classifications:
                hint = p['use_hint']
                if hint == 'Work' or 'Work' in hint:
                    all_classifications[exe] = 'Work'
                elif hint == 'Entertainment':
                    all_classifications[exe] = 'Entertainment'
                else:
                    all_classifications[exe] = 'Mixed'
        
        # Organize into categories
        for exe, classification in all_classifications.items():
            if classification == 'Work':
                result['process_classifications']['work_processes'].append(exe)
            elif classification == 'Entertainment':
                result['process_classifications']['entertainment_processes'].append(exe)
            else:
                result['process_classifications']['mixed_processes'].append(exe)
        
        result['success'] = True
        
        if debug_mode:
            work_count = len(result['process_classifications']['work_processes'])
            mixed_count = len(result['process_classifications']['mixed_processes'])
            ent_count = len(result['process_classifications']['entertainment_processes'])
            print(f"[ProcessClassifier] Classification complete: {work_count} Work, {mixed_count} Mixed, {ent_count} Entertainment")
        
        return result
        
    except Exception as e:
        result['error'] = f"Classification failed: {e}"
        logger.error(result['error'], exc_info=True)
        return result


def get_default_classifications() -> Dict[str, List[str]]:
    """
    Get default classifications from message.txt without using LLM.
    Fallback when LLM classification fails.
    
    Returns:
        Dict with work_processes, mixed_processes, entertainment_processes
    """
    classifications = {
        'work_processes': [],
        'mixed_processes': [],
        'entertainment_processes': []
    }
    
    processes = read_processes_from_message_txt()
    for p in processes:
        exe = p['exe'].lower()
        hint = p['use_hint']
        
        if hint == 'Work' or 'Work' in hint:
            classifications['work_processes'].append(exe)
        elif hint == 'Entertainment':
            classifications['entertainment_processes'].append(exe)
        else:
            classifications['mixed_processes'].append(exe)
    
    return classifications

