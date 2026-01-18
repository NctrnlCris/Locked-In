"""
Process classification utilities for parsing message.txt and classifying processes.
"""
import csv
import yaml
from pathlib import Path
from typing import Dict, List, Optional


def parse_message_txt(file_path: str) -> Dict[str, List[str]]:
    """
    Parse message.txt CSV file and extract process classifications.
    
    Args:
        file_path: Path to message.txt CSV file
        
    Returns:
        Dictionary with keys: 'work_processes', 'entertainment_processes', 'mixed_processes'
        Each value is a list of exe names (lowercase)
    """
    classifications = {
        'work_processes': [],
        'entertainment_processes': [],
        'mixed_processes': []
    }
    
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"message.txt not found at: {file_path}")
    
    with open(file_path_obj, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            exe_name = row.get('exe', '').strip().lower()
            use_hint = row.get('use_hint', '').strip()
            
            if not exe_name:
                continue
            
            # Classify based on use_hint column
            if use_hint == 'Work':
                classifications['work_processes'].append(exe_name)
            elif use_hint == 'Entertainment':
                classifications['entertainment_processes'].append(exe_name)
            elif use_hint == 'Mixed':
                classifications['mixed_processes'].append(exe_name)
            # Note: "System/Work" entries are treated as Work
            elif 'Work' in use_hint:
                classifications['work_processes'].append(exe_name)
    
    return classifications


def initialize_config_from_message_txt(message_txt_path: Optional[str] = None, 
                                       config_yaml_path: Optional[str] = None) -> bool:
    """
    Create config.yaml from message.txt if config.yaml doesn't exist.
    
    Args:
        message_txt_path: Path to message.txt (default: project root/message.txt)
        config_yaml_path: Path to config.yaml (default: project root/config.yaml)
        
    Returns:
        True if config.yaml was created, False if it already existed
    """
    if message_txt_path is None:
        # Default to project root
        project_root = Path(__file__).parent.parent.parent
        message_txt_path = str(project_root / "message.txt")
    
    if config_yaml_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_yaml_path = str(project_root / "config.yaml")
    
    config_path = Path(config_yaml_path)
    
    # If config.yaml already exists, don't overwrite
    if config_path.exists():
        return False
    
    # Parse message.txt
    try:
        classifications = parse_message_txt(message_txt_path)
    except FileNotFoundError:
        # If message.txt doesn't exist, create empty config
        print(f"Warning: message.txt not found at {message_txt_path}, creating empty config.yaml")
        classifications = {
            'work_processes': [],
            'entertainment_processes': [],
            'mixed_processes': []
        }
    
    # Create config.yaml structure
    config_data = {
        'process_classification': {
            'work_processes': classifications['work_processes'],
            'entertainment_processes': classifications['entertainment_processes'],
            'mixed_processes': classifications['mixed_processes'],
            'monitor_timeout': 2
        }
    }
    
    # Write config.yaml
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created config.yaml from message.txt at {config_yaml_path}")
    return True


def classify_process(process_name: str, config) -> str:
    """
    Classify a process name as 'work', 'entertainment', 'mixed', or 'unknown'.
    
    Args:
        process_name: Process name (e.g., 'chrome.exe')
        config: Config instance with get_process_classification() method
        
    Returns:
        Classification string: 'work', 'entertainment', 'mixed', or 'unknown'
    """
    if not process_name:
        return 'unknown'
    
    process_lower = process_name.lower()
    
    try:
        classification = config.get_process_classification()
        
        work_processes = [p.lower() for p in classification.get('work_processes', [])]
        entertainment_processes = [p.lower() for p in classification.get('entertainment_processes', [])]
        mixed_processes = [p.lower() for p in classification.get('mixed_processes', [])]
        
        # Check in order: work, entertainment, mixed
        if process_lower in work_processes:
            return 'work'
        elif process_lower in entertainment_processes:
            return 'entertainment'
        elif process_lower in mixed_processes:
            return 'mixed'
        else:
            return 'unknown'
    except Exception as e:
        print(f"Error classifying process {process_name}: {e}")
        return 'unknown'

