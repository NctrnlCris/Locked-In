"""Configuration management for Locked-in application."""

import os
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and PyInstaller.
    
    Args:
        relative_path: Path relative to project root or executable
        
    Returns:
        Absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Running in development mode
        base_path = Path(__file__).parent.parent.parent.absolute()
    
    return os.path.join(base_path, relative_path)


def get_config_path() -> str:
    """Get path to config.yaml, handling both dev and PyInstaller modes."""
    try:
        # PyInstaller bundles config.yaml in the root
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, 'config.yaml')
    except AttributeError:
        pass
    
    # Development mode: config.yaml is in project root
    return os.path.join(Path(__file__).parent.parent.parent, 'config.yaml')


class Config:
    """Application configuration manager."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Optional path to config file. If None, uses default location.
        """
        if config_path is None:
            config_path = get_config_path()
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            # Try to create config.yaml from message.txt
            try:
                from scripts.utils.process_classifier import initialize_config_from_message_txt
                project_root = Path(__file__).parent.parent.parent
                message_txt_path = str(project_root / "message.txt")
                if initialize_config_from_message_txt(message_txt_path, self.config_path):
                    # Config was created, try loading again
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        self._config = yaml.safe_load(f) or {}
                else:
                    # Config already exists but couldn't read it, use empty config
                    self._config = {}
            except Exception as e:
                # If initialization fails, use empty config
                print(f"Warning: Could not initialize config.yaml: {e}")
                self._config = {}
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing config.yaml: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot-notation path.
        
        Args:
            key_path: Dot-separated path (e.g., 'monitoring.screenshot_interval')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_monitoring(self) -> Dict[str, Any]:
        """Get monitoring configuration."""
        return self._config.get('monitoring', {})
    
    def get_detection(self) -> Dict[str, Any]:
        """Get detection configuration."""
        return self._config.get('detection', {})
    
    def get_alert(self) -> Dict[str, Any]:
        """Get alert configuration."""
        return self._config.get('alert', {})
    
    def get_vlm(self) -> Dict[str, Any]:
        """Get VLM configuration."""
        return self._config.get('vlm', {})
    
    def get_storage(self) -> Dict[str, Any]:
        """Get storage configuration."""
        return self._config.get('storage', {})
    
    def get_session(self) -> Dict[str, Any]:
        """Get session configuration."""
        return self._config.get('session', {})
    
    @property
    def screenshot_interval(self) -> int:
        """Screenshot capture interval in seconds."""
        return self.get_monitoring().get('screenshot_interval', 30)
    
    @property
    def analysis_interval(self) -> int:
        """Analysis interval in seconds."""
        return self.get_monitoring().get('analysis_interval', 60)
    
    @property
    def retention_duration(self) -> int:
        """Screenshot retention duration in seconds."""
        return self.get_monitoring().get('retention_duration', 600)
    
    @property
    def confidence_threshold(self) -> int:
        """Minimum confidence percentage to flag procrastination."""
        return self.get_detection().get('confidence_threshold', 60)
    
    @property
    def strict_mode(self) -> bool:
        """Whether to use strict detection mode."""
        return self.get_detection().get('strict_mode', True)
    
    @property
    def dismissal_clicks(self) -> int:
        """Number of clicks required to dismiss alert popup."""
        return self.get_alert().get('dismissal_clicks', 3)
    
    @property
    def popup_position(self) -> str:
        """Popup position on screen."""
        return self.get_alert().get('popup_position', 'right')
    
    @property
    def popup_width(self) -> int:
        """Popup window width."""
        return self.get_alert().get('popup_width', 300)
    
    @property
    def popup_height(self) -> int:
        """Popup window height."""
        return self.get_alert().get('popup_height', 400)
    
    @property
    def vlm_model(self) -> str:
        """VLM model name."""
        return self.get_vlm().get('model', 'qwen-4b-vlm')
    
    @property
    def vlm_api_endpoint(self) -> str:
        """VLM API endpoint URL."""
        return self.get_vlm().get('api_endpoint', '')
    
    @property
    def vlm_api_key_env(self) -> str:
        """Environment variable name for VLM API key."""
        return self.get_vlm().get('api_key_env', 'QWEN_API_KEY')
    
    @property
    def vlm_timeout(self) -> int:
        """VLM API request timeout in seconds."""
        return self.get_vlm().get('timeout', 30)
    
    @property
    def vlm_mock_mode(self) -> bool:
        """Whether to use mock VLM responses."""
        return self.get_vlm().get('mock_mode', False)
    
    @property
    def use_two_stage(self) -> bool:
        """Whether to use two-stage VLM system."""
        return self.get_vlm().get('use_two_stage', False)
    
    @property
    def stage1_model(self) -> str:
        """Stage 1 model name."""
        return self.get_vlm().get('stage1_model', 'Qwen/Qwen3-VL-8B-Instruct')
    
    @property
    def stage1_endpoint(self) -> str:
        """Stage 1 API endpoint."""
        return self.get_vlm().get('stage1_endpoint', '')
    
    @property
    def stage1_timeout(self) -> int:
        """Stage 1 timeout in seconds."""
        return self.get_vlm().get('stage1_timeout', 30)
    
    @property
    def stage2_model(self) -> str:
        """Stage 2 model name."""
        return self.get_vlm().get('stage2_model', 'qwen')
    
    @property
    def stage2_endpoint(self) -> str:
        """Stage 2 API endpoint."""
        return self.get_vlm().get('stage2_endpoint', '')
    
    @property
    def stage2_timeout(self) -> int:
        """Stage 2 timeout in seconds."""
        return self.get_vlm().get('stage2_timeout', 20)
    
    @property
    def context_window(self) -> int:
        """Number of previous descriptions for context."""
        return self.get_vlm().get('context_window', 5)
    
    @property
    def stage1_local_path(self) -> str:
        """Local path to Stage 1 model (optional)."""
        return self.get_vlm().get('stage1_local_path', '')
    
    @property
    def stage2_local_path(self) -> str:
        """Local path to Stage 2 model (optional)."""
        return self.get_vlm().get('stage2_local_path', '')
    
    def get_memory_optimization(self) -> dict:
        """Get memory optimization settings."""
        return self.get_vlm().get('memory_optimization', {})
    
    @property
    def use_quantization(self) -> bool:
        """Whether to use quantization for memory optimization."""
        return self.get_memory_optimization().get('use_quantization', True)
    
    @property
    def quantization_bits(self) -> int:
        """Quantization bits (8 or 4)."""
        return self.get_memory_optimization().get('quantization_bits', 8)
    
    @property
    def use_cpu_offload(self) -> bool:
        """Whether to use CPU offloading."""
        return self.get_memory_optimization().get('use_cpu_offload', True)
    
    @property
    def max_memory_gb(self) -> Optional[int]:
        """Maximum GPU memory to use in GB (None = use all available)."""
        val = self.get_memory_optimization().get('max_memory_gb')
        return int(val) if val is not None else None
    
    @property
    def low_cpu_mem_usage(self) -> bool:
        """Whether to use low CPU memory usage mode."""
        return self.get_memory_optimization().get('low_cpu_mem_usage', True)
    
    def get_ollama(self) -> dict:
        """Get Ollama configuration settings."""
        return self.get_vlm().get('ollama', {})
    
    @property
    def ollama_base_url(self) -> str:
        """Ollama server base URL."""
        return self.get_ollama().get('base_url', 'http://localhost:11434')
    
    @property
    def stage1_ollama_model(self) -> str:
        """Stage 1 Ollama model name."""
        return self.get_ollama().get('stage1_model', 'qwen3-vl:8b')
    
    @property
    def stage1_ollama_gguf_path(self) -> str:
        """Optional direct path to Stage 1 GGUF file."""
        return self.get_ollama().get('stage1_gguf_path', '')
    
    @property
    def stage1_ollama_quantization(self) -> str:
        """Stage 1 quantization level."""
        return self.get_ollama().get('stage1_quantization', 'Q5_K_M')
    
    @property
    def stage2_ollama_model(self) -> str:
        """Stage 2 Ollama model name."""
        return self.get_ollama().get('stage2_model', 'qwen2.5:7b')
    
    @property
    def stage2_ollama_gguf_path(self) -> str:
        """Optional direct path to Stage 2 GGUF file."""
        return self.get_ollama().get('stage2_gguf_path', '')
    
    @property
    def stage2_ollama_quantization(self) -> str:
        """Stage 2 quantization level."""
        return self.get_ollama().get('stage2_quantization', 'Q5_K_M')
    
    @property
    def ollama_timeout(self) -> int:
        """Ollama request timeout in seconds."""
        return self.get_ollama().get('timeout', 120)
    
    @property
    def use_manual_gguf(self) -> bool:
        """Whether to use manual GGUF files instead of Ollama pull."""
        return self.get_ollama().get('use_manual_gguf', False)
    
    @property
    def ollama_auto_pull(self) -> bool:
        """Whether to automatically pull models if not available."""
        return self.get_ollama().get('auto_pull', True)
    
    @property
    def ollama_auto_start(self) -> bool:
        """Whether to automatically start Ollama server if not running."""
        return self.get_ollama().get('auto_start', True)
    
    @property
    def ollama_max_image_size(self) -> tuple:
        """Maximum image size (width, height) for resizing before sending to Ollama."""
        size = self.get_ollama().get('max_image_size', [512, 512])
        if isinstance(size, list) and len(size) >= 2:
            return tuple(size[:2])
        return (512, 512)  # Default
    
    @property
    def stage2_max_tokens(self) -> int:
        """Maximum tokens to generate for Stage 2 (JSON responses)."""
        return self.get_ollama().get('stage2_max_tokens', 300)
    
    @property
    def stage2_temperature(self) -> float:
        """Temperature for Stage 2 generation (lower = faster, more deterministic)."""
        return self.get_ollama().get('stage2_temperature', 0.3)
    
    @property
    def stage2_top_p(self) -> float:
        """Top-p sampling for Stage 2 generation."""
        return self.get_ollama().get('stage2_top_p', 0.9)
    
    @property
    def stage1_repeat_penalty(self) -> float:
        """Repetition penalty for Stage 1 (higher = less repetition)."""
        return self.get_ollama().get('stage1_repeat_penalty', 1.3)
    
    @property
    def temp_folder(self) -> str:
        """Temporary screenshot storage folder."""
        return self.get_storage().get('temp_folder', './temp/screenshots')
    
    @property
    def context_file(self) -> str:
        """Activity log file path."""
        return self.get_storage().get('context_file', './data/context.txt')
    
    @property
    def log_file(self) -> str:
        """Application log file path."""
        return self.get_storage().get('log_file', './logs/app.log')
    
    @property
    def require_work_topic(self) -> bool:
        """Whether to require work topic at session start."""
        return self.get_session().get('require_work_topic', True)
    
    def get_heuristic(self) -> Dict[str, Any]:
        """Get heuristic configuration."""
        return self._config.get('heuristic', {})
    
    @property
    def heuristic_enabled(self) -> bool:
        """Whether process-based heuristic detection is enabled."""
        return self.get_heuristic().get('enabled', False)
    
    @property
    def work_processes(self) -> list:
        """List of work process names to allow."""
        return self.get_heuristic().get('work_processes', [])
    
    @property
    def heuristic_case_sensitive(self) -> bool:
        """Whether process name matching is case-sensitive."""
        return self.get_heuristic().get('case_sensitive', False)
    
    @property
    def heuristic_match_partial(self) -> bool:
        """Whether to allow partial matches in process names."""
        return self.get_heuristic().get('match_partial', True)
    
    @property
    def heuristic_check_interval(self) -> int:
        """Interval in seconds for checking foreground process (heuristic mode)."""
        return self.get_heuristic().get('check_interval', 5)
    
    def get_debug(self) -> Dict[str, Any]:
        """Get debug configuration."""
        return self._config.get('debug', {})
    
    @property
    def debug_mode(self) -> bool:
        """Whether debug mode is enabled."""
        return self.get_debug().get('debug_mode', False)
    
    def get_process_classification(self) -> Dict[str, Any]:
        """Get process classification configuration."""
        # Return profile override if set, otherwise return global config
        if hasattr(self, '_profile_classification_override') and self._profile_classification_override:
            return self._profile_classification_override
        
        return self._config.get('process_classification', {
            'work_processes': [],
            'entertainment_processes': [],
            'mixed_processes': [],
            'monitor_timeout': 2
        })
    
    def set_profile_classification_override(self, classifications: Optional[Dict[str, Any]]) -> None:
        """
        Set profile-specific process classifications that override global config.
        
        Args:
            classifications: Dict with work_processes, mixed_processes, entertainment_processes
                           Pass None to clear the override and use global config.
        """
        if classifications:
            # Ensure monitor_timeout is preserved
            if 'monitor_timeout' not in classifications:
                classifications['monitor_timeout'] = self._config.get('process_classification', {}).get('monitor_timeout', 2)
            self._profile_classification_override = classifications
        else:
            self._profile_classification_override = None
    
    def clear_profile_override(self) -> None:
        """Clear any profile-specific overrides and use global config."""
        self._profile_classification_override = None
    
    @property
    def monitor_timeout(self) -> int:
        """Timeout in seconds before VLM check for Mixed processes."""
        return self.get_process_classification().get('monitor_timeout', 2)

