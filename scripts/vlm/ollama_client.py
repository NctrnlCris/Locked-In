"""Ollama client for GGUF model inference."""

import base64
import io
import json
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Any, Callable
from PIL import Image
import requests

logger = logging.getLogger(__name__)

# Module-level cache for OllamaClient instances (singleton pattern)
_client_cache: Dict[str, 'OllamaClient'] = {}


def get_or_create_client(base_url: str = "http://localhost:11434", timeout: int = 120,
                        debug_mode: bool = False, auto_start: bool = True,
                        max_image_size: Optional[tuple] = None,
                        temp_folder: Optional[str] = None) -> 'OllamaClient':
    """
    Get or create a cached OllamaClient instance.
    
    Args:
        base_url: Ollama server base URL
        timeout: Request timeout in seconds
        debug_mode: Enable debug output
        auto_start: Automatically start Ollama server if not running
        max_image_size: Optional (width, height) tuple to resize images
        temp_folder: Optional path to temp folder
        
    Returns:
        Cached OllamaClient instance
    """
    # Create cache key based on parameters
    cache_key = f"{base_url}:{timeout}:{debug_mode}:{auto_start}:{max_image_size}:{temp_folder}"
    
    # Return cached client if available
    if cache_key in _client_cache:
        return _client_cache[cache_key]
    
    # Create new client
    client = OllamaClient(
        base_url=base_url,
        timeout=timeout,
        debug_mode=debug_mode,
        auto_start=auto_start,
        max_image_size=max_image_size,
        temp_folder=temp_folder
    )
    
    # Cache it
    _client_cache[cache_key] = client
    return client


class OllamaClient:
    """Client for communicating with Ollama server for GGUF model inference."""
    
    # Class-level cache for model availability and name resolution
    _model_cache: Dict[str, tuple] = {}  # {model_name: (is_available, resolved_name, timestamp)}
    _tags_cache: Optional[tuple] = None  # (models_data, timestamp)
    _cache_ttl: float = 30.0  # Cache TTL in seconds
    
    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120, 
                 debug_mode: bool = False, auto_start: bool = True, max_image_size: Optional[tuple] = None,
                 temp_folder: Optional[str] = None):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server base URL
            timeout: Request timeout in seconds
            debug_mode: Enable debug output
            auto_start: Automatically start Ollama server if not running
            max_image_size: Optional (width, height) tuple to resize images before encoding (default: (1080, 1080))
            temp_folder: Optional path to temp folder for saving rescaled images
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.debug_mode = debug_mode
        self.auto_start = auto_start
        self.max_image_size = max_image_size if max_image_size is not None else (1080, 1080)
        self.temp_folder = temp_folder or './temp/screenshots'  # Kept for backward compatibility but not used
        self._server_process: Optional[subprocess.Popen] = None
        
        # Test connection on init, start server if needed
        if not self._check_server_connection():
            if auto_start:
                self._start_server()
            else:
                raise ConnectionError(f"Cannot connect to Ollama server at {self.base_url}. Is Ollama running?")
    
    def _check_server_connection(self) -> bool:
        """
        Check if Ollama server is running.
        
        Returns:
            True if server is running, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                if self.debug_mode:
                    print(f"[Ollama] Connected to server at {self.base_url}")
                return True
            else:
                logger.warning(f"Ollama server returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException:
            return False
    
    def _start_server(self) -> None:
        """Start Ollama server programmatically."""
        if self.debug_mode:
            print(f"[Ollama] Starting Ollama server...")
        
        try:
            # Check if ollama command exists
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                raise FileNotFoundError("ollama command not found")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            error_msg = (
                "Ollama is not installed or not in PATH. "
                "Please install Ollama from https://ollama.ai/download"
            )
            logger.error(error_msg)
            if self.debug_mode:
                print(f"[Ollama] ERROR: {error_msg}")
            raise RuntimeError(error_msg)
        
        # Start ollama serve in background
        try:
            if self.debug_mode:
                print(f"[Ollama] Launching 'ollama serve'...")
            
            # Start server process
            self._server_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Wait for server to be ready (poll with retries)
            max_retries = 30
            retry_delay = 1
            
            for attempt in range(max_retries):
                time.sleep(retry_delay)
                if self._check_server_connection():
                    if self.debug_mode:
                        print(f"[Ollama] Server started successfully!")
                    return
                if self.debug_mode and attempt % 5 == 0:
                    print(f"[Ollama] Waiting for server to start... ({attempt + 1}/{max_retries})")
            
            # If we get here, server didn't start
            error_msg = "Ollama server failed to start within timeout"
            logger.error(error_msg)
            if self._server_process:
                self._server_process.terminate()
                self._server_process = None
            raise RuntimeError(error_msg)
            
        except Exception as e:
            logger.error(f"Error starting Ollama server: {e}")
            if self._server_process:
                self._server_process.terminate()
                self._server_process = None
            raise
    
    def __del__(self):
        """Cleanup: stop server process if we started it."""
        if self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
    
    def _get_models_list(self) -> List[str]:
        """
        Get list of available models, using cache if available.
        
        Returns:
            List of model names
        """
        current_time = time.time()
        
        # Check cache
        if OllamaClient._tags_cache is not None:
            models_data, cache_time = OllamaClient._tags_cache
            if current_time - cache_time < OllamaClient._cache_ttl:
                return models_data
        
        # Fetch fresh data
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                # Update cache
                OllamaClient._tags_cache = (model_names, current_time)
                return model_names
        except Exception as e:
            logger.error(f"Error fetching models list: {e}")
        
        return []
    
    def check_model_available(self, model_name: str) -> bool:
        """
        Check if model is available in Ollama (cached).
        
        Args:
            model_name: Model name to check
            
        Returns:
            True if model is available
        """
        # Check cache first
        current_time = time.time()
        cache_key = f"{self.base_url}:{model_name}"
        
        if cache_key in OllamaClient._model_cache:
            is_available, _, cache_time = OllamaClient._model_cache[cache_key]
            if current_time - cache_time < OllamaClient._cache_ttl:
                if self.debug_mode:
                    print(f"[Ollama] Model '{model_name}' available (cached): {is_available}")
                return is_available
        
        # Fetch fresh data
        try:
            model_names = self._get_models_list()
            # Check exact match first
            if model_name in model_names:
                is_available = True
                if self.debug_mode:
                    print(f"[Ollama] Model '{model_name}' available: True (exact match)")
            else:
                # Check if any model name starts with the requested name
                is_available = any(name.startswith(model_name) for name in model_names)
                if self.debug_mode:
                    print(f"[Ollama] Model '{model_name}' available: {is_available}")
            
            # Update cache
            OllamaClient._model_cache[cache_key] = (is_available, model_name, current_time)
            return is_available
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            return False
    
    def _resolve_model_name(self, model_name: str) -> str:
        """
        Resolve model name to exact name in Ollama (cached).
        
        Args:
            model_name: Model name to resolve
            
        Returns:
            Exact model name as stored in Ollama
        """
        # Check cache first
        current_time = time.time()
        cache_key = f"{self.base_url}:{model_name}"
        
        if cache_key in OllamaClient._model_cache:
            _, resolved_name, cache_time = OllamaClient._model_cache[cache_key]
            if current_time - cache_time < OllamaClient._cache_ttl and resolved_name:
                if self.debug_mode and resolved_name != model_name:
                    print(f"[Ollama] Resolved '{model_name}' to '{resolved_name}' (cached)")
                return resolved_name
        
        # Fetch fresh data
        try:
            model_names = self._get_models_list()
            
            # Exact match
            if model_name in model_names:
                resolved = model_name
            else:
                # Find model that starts with the requested name
                resolved = model_name  # Default to original
                for name in model_names:
                    if name.startswith(model_name):
                        resolved = name
                        if self.debug_mode:
                            print(f"[Ollama] Resolved '{model_name}' to '{name}'")
                        break
                
                if resolved == model_name and self.debug_mode:
                    print(f"[Ollama] Could not resolve '{model_name}', using as-is")
            
            # Update cache (reuse availability check if available)
            if cache_key in OllamaClient._model_cache:
                is_available, _, _ = OllamaClient._model_cache[cache_key]
                OllamaClient._model_cache[cache_key] = (is_available, resolved, current_time)
            else:
                is_available = resolved in model_names or any(name.startswith(model_name) for name in model_names)
                OllamaClient._model_cache[cache_key] = (is_available, resolved, current_time)
            
            return resolved
        except Exception as e:
            logger.error(f"Error resolving model name: {e}")
            return model_name
    
    def pull_model(self, model_name: str) -> bool:
        """
        Pull model from Ollama registry.
        
        Args:
            model_name: Model name to pull
            
        Returns:
            True if successful
        """
        if self.debug_mode:
            print(f"[Ollama] Pulling model: {model_name}...")
        
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                # Stream progress updates
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get('status', '')
                            if self.debug_mode and status:
                                print(f"[Ollama] {status}")
                            if data.get('completed', False):
                                if self.debug_mode:
                                    print(f"[Ollama] Model '{model_name}' pulled successfully!")
                                return True
                        except json.JSONDecodeError:
                            continue
                return True
            else:
                logger.error(f"Failed to pull model: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            return False
    
    def _encode_image_base64(self, image_path: str) -> str:
        """
        Encode image to base64 for Ollama API.
        Image should already be resized at capture time, but we'll verify size here.
        
        Args:
            image_path: Path to image file (should already be resized)
            
        Returns:
            Base64-encoded image string
            
        Raises:
            OSError: If image file is corrupted, truncated, or cannot be opened
        """
        try:
            # Load image - handle truncated/corrupted images
            try:
                img = Image.open(image_path)
                # Verify image is not truncated by loading it fully
                img.load()
                img = img.convert('RGB')
            except (OSError, IOError) as e:
                error_msg = f"Image file is corrupted or truncated: {image_path}"
                if self.debug_mode:
                    print(f"[Ollama] Error: {error_msg} - {str(e)}")
                logger.warning(error_msg)
                raise OSError(error_msg) from e
            
            # Verify size - images should already be resized at capture time
            # This is just a safety check in case an old/unresized image is passed
            if img.size[0] > self.max_image_size[0] or img.size[1] > self.max_image_size[1]:
                original_size = img.size
                img.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
                if self.debug_mode:
                    print(f"[Ollama] WARNING: Image was not resized at capture! Resized from {original_size} to {img.size}")
            elif self.debug_mode:
                print(f"[Ollama] Image already resized: {img.size} (max: {self.max_image_size})")
            
            # Convert to JPEG bytes (smaller than PNG)
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='JPEG', quality=85, optimize=True)
            image_data = img_bytes.getvalue()
            
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            raise
    
    def generate_vision(self, image_path: str, prompt: str, model_name: str, 
                       stream: bool = False, repeat_penalty: Optional[float] = None,
                       check_cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        Generate response using vision-language model (single image).
        Uses /api/generate endpoint for single images (simpler format).
        
        Args:
            image_path: Path to image file
            prompt: Text prompt
            model_name: Ollama model name
            stream: Whether to stream the response
            
        Returns:
            Dictionary with 'text' field containing response
        """
        if self.debug_mode:
            print(f"[Ollama] Generating vision response with model: {model_name}")
            print(f"[Ollama] Image: {image_path}")
            print(f"[Ollama] Prompt: {prompt[:100]}...")
        
        # Resolve to exact model name
        resolved_model_name = self._resolve_model_name(model_name)
        
        # Check if model is available
        if not self.check_model_available(resolved_model_name):
            if self.debug_mode:
                print(f"[Ollama] Model '{resolved_model_name}' not found, attempting to pull...")
            if not self.pull_model(resolved_model_name):
                raise ValueError(f"Model '{resolved_model_name}' not available and could not be pulled")
        
        # Encode image
        try:
            image_base64 = self._encode_image_base64(image_path)
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            raise
        
        # Use /api/generate endpoint for single image (simpler)
        options = {
            "num_predict": 512,
            "temperature": 0.7
        }
        
        # Add repetition penalty if provided
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty
        
        payload = {
            "model": resolved_model_name,
            "prompt": prompt,
            "images": [image_base64],  # Single image in array
            "stream": stream,
            "think": False,  # Disable thinking mode
            "options": options
        }
        
        # Make request
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Ollama API error: {response.status_code} - {error_text}")
                raise RuntimeError(f"Ollama API error: {response.status_code} - {error_text}")
            
            # Parse response (generate endpoint uses 'response' field)
            if stream:
                full_response = ""
                last_data = {}
                done_received = False
                chunk_count = 0
                
                for line in response.iter_lines():
                    # Check if cancelled before processing each chunk
                    if check_cancelled and check_cancelled():
                        if self.debug_mode:
                            print(f"\n[Ollama] Request cancelled by user")
                        response.close()  # Close the connection
                        raise InterruptedError("LLM request was cancelled (user changed page)")
                    
                    if line:
                        chunk_count += 1
                        try:
                            data = json.loads(line)
                            
                            if self.debug_mode and chunk_count <= 3:
                                print(f"\n[Ollama] Chunk {chunk_count} keys: {list(data.keys())}")
                                print(f"[Ollama] Chunk {chunk_count} data: {data}")
                            
                            # Collect response tokens - check multiple possible fields
                            # Some models use 'thinking' field instead of 'response'
                            token = data.get('response', '') or data.get('thinking', '') or data.get('content', '') or data.get('text', '')
                            if token:
                                full_response += token
                                if self.debug_mode:
                                    print(token, end='', flush=True)
                            
                            # Track metadata from each chunk
                            if 'done' in data:
                                last_data.update(data)  # Update with all fields from done chunk
                                if data.get('done', False):
                                    done_received = True
                                    if self.debug_mode:
                                        print()  # New line after streaming
                            
                            # Always update metadata fields as we see them
                            if 'eval_count' in data:
                                last_data['eval_count'] = data.get('eval_count', 0)
                            if 'prompt_eval_count' in data:
                                last_data['prompt_eval_count'] = data.get('prompt_eval_count', 0)
                            if 'model' in data:
                                last_data['model'] = data.get('model', model_name)
                            if 'total_duration' in data:
                                last_data['total_duration'] = data.get('total_duration', 0)
                            if 'load_duration' in data:
                                last_data['load_duration'] = data.get('load_duration', 0)
                                
                        except json.JSONDecodeError as e:
                            if self.debug_mode:
                                print(f"\n[Ollama] JSON decode error: {e}, line: {line[:100]}")
                            continue
                
                response_text = full_response
                final_data = last_data if last_data else {}
                
                if self.debug_mode:
                    print(f"\n[Ollama] Streaming complete. Chunks processed: {chunk_count}")
                    print(f"[Ollama] Response length: {len(response_text)}")
                    print(f"[Ollama] Done received: {done_received}")
                    print(f"[Ollama] Eval count: {final_data.get('eval_count', 0)}")
                    if not response_text:
                        print(f"[Ollama] WARNING: Empty streaming response despite eval_count={final_data.get('eval_count', 0)}!")
                        print(f"[Ollama] Last data keys: {list(final_data.keys())}")
                        print(f"[Ollama] Last data: {final_data}")
            else:
                data = response.json()
                response_text = data.get('response', '')
                final_data = data
                
                if self.debug_mode:
                    print(f"[Ollama] Response text length: {len(response_text)}")
                    if not response_text:
                        print(f"[Ollama] WARNING: Empty response but eval_count={data.get('eval_count', 0)}")
            
            # If response is empty but eval_count > 0, try streaming mode as fallback
            if not response_text and final_data.get('eval_count', 0) > 0 and not stream:
                if self.debug_mode:
                    print(f"[Ollama] Empty response detected, retrying with streaming mode...")
                # Retry with streaming
                payload['stream'] = True
                stream_response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                    stream=True
                )
                if stream_response.status_code == 200:
                    full_response = ""
                    last_stream_data = {}
                    for line in stream_response.iter_lines():
                        if line:
                            try:
                                stream_data = json.loads(line)
                                token = stream_data.get('response', '')
                                if token:
                                    full_response += token
                                if stream_data.get('done', False):
                                    last_stream_data = stream_data
                                    break
                            except json.JSONDecodeError:
                                continue
                    if full_response:
                        response_text = full_response
                        final_data = last_stream_data
                        if self.debug_mode:
                            print(f"[Ollama] Streaming retry successful, got {len(response_text)} chars")
            
            elapsed_time = time.time() - start_time
            
            if self.debug_mode:
                print(f"[Ollama] Generation complete in {elapsed_time:.2f}s")
                if response_text:
                    print(f"[Ollama] Response preview: {response_text[:200]}")
                else:
                    print(f"[Ollama] ERROR: Still empty response after retry!")
            
            return {
                'text': response_text,
                'response': response_text,
                'model': final_data.get('model', model_name),
                'total_duration': final_data.get('total_duration', elapsed_time * 1e9),  # nanoseconds
                'load_duration': final_data.get('load_duration', 0),
                'prompt_eval_count': final_data.get('prompt_eval_count', 0),
                'eval_count': final_data.get('eval_count', 0)
            }
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request error: {e}")
            raise
    
    def generate_vision_multi(self, image_paths: List[str], prompt: str, model_name: str, 
                             stream: bool = False, repeat_penalty: Optional[float] = None,
                             check_cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        Generate response using vision-language model (multiple images).
        Uses /api/generate endpoint with images array.
        
        Args:
            image_paths: List of paths to image files
            prompt: Text prompt
            model_name: Ollama model name
            stream: Whether to stream the response
            repeat_penalty: Repetition penalty (higher = less repetition, default 1.1, recommended 1.2-1.5)
            
        Returns:
            Dictionary with 'text' field containing response
        """
        if self.debug_mode:
            print(f"[Ollama] Generating vision response with model: {model_name}")
            print(f"[Ollama] Images: {len(image_paths)}")
            for i, img_path in enumerate(image_paths, 1):
                print(f"[Ollama]   Image {i}: {img_path}")
            print(f"[Ollama] Prompt: {prompt[:100]}...")
        
        # Resolve to exact model name
        resolved_model_name = self._resolve_model_name(model_name)
        
        # Check if model is available
        if not self.check_model_available(resolved_model_name):
            if self.debug_mode:
                print(f"[Ollama] Model '{resolved_model_name}' not found, attempting to pull...")
            if not self.pull_model(resolved_model_name):
                raise ValueError(f"Model '{resolved_model_name}' not available and could not be pulled")
        
        # Encode all images to base64, skipping corrupted/truncated images
        image_base64_list = []
        skipped_images = []
        
        for img_path in image_paths:
            try:
                encoded = self._encode_image_base64(img_path)
                image_base64_list.append(encoded)
            except (OSError, IOError) as e:
                skipped_images.append(img_path)
                if self.debug_mode:
                    print(f"[Ollama] Skipping corrupted image: {os.path.basename(img_path)}")
                logger.warning(f"Skipping corrupted image: {img_path} - {str(e)}")
        
        if not image_base64_list:
            raise ValueError("All images failed to encode. Check if image files are valid.")
        
        if skipped_images:
            if self.debug_mode:
                print(f"[Ollama] Warning: {len(skipped_images)} image(s) skipped due to corruption")
            logger.warning(f"Skipped {len(skipped_images)} corrupted image(s): {skipped_images}")
        
        # Use /api/generate endpoint with images array
        # Ollama's /api/generate accepts multiple images in the images array
        options = {
            "num_predict": 512,  # Ensure enough tokens are generated
            "temperature": 0.7
        }
        
        # Add repetition penalty if provided
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty
        
        payload = {
            "model": resolved_model_name,
            "prompt": prompt,
            "images": image_base64_list,  # Multiple images as array of base64 strings
            "stream": stream,
            "think": False,  # Disable thinking mode
            "options": options
        }
        
        if self.debug_mode:
            print(f"[Ollama] Sending {len(image_paths)} image(s) using /api/generate endpoint")
            print(f"[Ollama] Images array length: {len(image_base64_list)}")
        
        # Make request to /api/generate endpoint
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code != 200:
                # For streamed responses, get error text before consuming stream
                try:
                    if stream:
                        error_text = response.content.decode('utf-8', errors='ignore')[:500]
                    else:
                        error_text = response.text
                except:
                    error_text = f"HTTP {response.status_code}"
                logger.error(f"Ollama API error: {response.status_code} - {error_text}")
                raise RuntimeError(f"Ollama API error: {response.status_code} - {error_text}")
            
            # Parse response (/api/generate endpoint uses 'response' field)
            if stream:
                full_response = ""
                last_data = {}
                done_received = False
                
                for line in response.iter_lines():
                    # Check if cancelled before processing each chunk
                    if check_cancelled and check_cancelled():
                        if self.debug_mode:
                            print(f"\n[Ollama] Request cancelled by user")
                        response.close()  # Close the connection
                        raise InterruptedError("LLM request was cancelled (user changed page)")
                    
                    if line:
                        try:
                            data = json.loads(line)
                            
                            # Collect response tokens - check multiple possible fields
                            # Some models use 'thinking' field instead of 'response'
                            token = data.get('response', '') or data.get('thinking', '') or data.get('content', '') or data.get('text', '')
                            if token:
                                full_response += token
                                if self.debug_mode:
                                    print(token, end='', flush=True)
                            
                            # Track metadata from each chunk
                            if 'done' in data:
                                last_data = data
                                if data.get('done', False):
                                    done_received = True
                                    if self.debug_mode:
                                        print()  # New line after streaming
                                    # Don't break - continue to get final metadata
                            
                            # Also collect other metadata fields
                            if 'eval_count' in data:
                                last_data['eval_count'] = data.get('eval_count', 0)
                            if 'prompt_eval_count' in data:
                                last_data['prompt_eval_count'] = data.get('prompt_eval_count', 0)
                            if 'model' in data:
                                last_data['model'] = data.get('model', model_name)
                            if 'total_duration' in data:
                                last_data['total_duration'] = data.get('total_duration', 0)
                            if 'load_duration' in data:
                                last_data['load_duration'] = data.get('load_duration', 0)
                                
                        except json.JSONDecodeError as e:
                            if self.debug_mode:
                                print(f"\n[Ollama] JSON decode error: {e}, line: {line[:100]}")
                            continue
                
                response_text = full_response
                final_data = last_data if last_data else {}
                
                if self.debug_mode:
                    print(f"\n[Ollama] Streaming complete. Response length: {len(response_text)}")
                    print(f"[Ollama] Done received: {done_received}")
                    print(f"[Ollama] Eval count: {final_data.get('eval_count', 0)}")
                    if not response_text:
                        print(f"[Ollama] WARNING: Empty streaming response despite eval_count={final_data.get('eval_count', 0)}!")
                        print(f"[Ollama] Last data received: {last_data}")
            else:
                data = response.json()
                response_text = data.get('response', '')
                final_data = data
                
                if self.debug_mode:
                    print(f"[Ollama] Response keys: {list(data.keys())}")
                    print(f"[Ollama] Response text length: {len(response_text)}")
                    print(f"[Ollama] Eval count: {data.get('eval_count', 0)}")
                    if not response_text:
                        print(f"[Ollama] WARNING: Empty response but eval_count={data.get('eval_count', 0)}")
                        print(f"[Ollama] Full response data: {data}")
            
            # If response is empty but eval_count > 0, try streaming mode as fallback
            if not response_text and final_data.get('eval_count', 0) > 0 and not stream:
                if self.debug_mode:
                    print(f"[Ollama] Empty response detected, retrying with streaming mode...")
                # Retry with streaming
                payload['stream'] = True
                stream_response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                    stream=True
                )
                if stream_response.status_code == 200:
                    full_response = ""
                    last_stream_data = {}
                    for line in stream_response.iter_lines():
                        if line:
                            try:
                                stream_data = json.loads(line)
                                token = stream_data.get('response', '')
                                if token:
                                    full_response += token
                                if stream_data.get('done', False):
                                    last_stream_data = stream_data
                                    break
                            except json.JSONDecodeError:
                                continue
                    if full_response:
                        response_text = full_response
                        final_data = last_stream_data
                        if self.debug_mode:
                            print(f"[Ollama] Streaming retry successful, got {len(response_text)} chars")
            
            elapsed_time = time.time() - start_time
            
            if self.debug_mode:
                print(f"[Ollama] Generation complete in {elapsed_time:.2f}s")
                if response_text:
                    print(f"[Ollama] Response preview: {response_text[:200]}")
                else:
                    print(f"[Ollama] ERROR: Still empty response after retry!")
            
            return {
                'text': response_text,
                'response': response_text,
                'model': final_data.get('model', model_name),
                'total_duration': final_data.get('total_duration', elapsed_time * 1e9),  # nanoseconds
                'load_duration': final_data.get('load_duration', 0),
                'prompt_eval_count': final_data.get('prompt_eval_count', 0),
                'eval_count': final_data.get('eval_count', 0)
            }
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request error: {e}")
            raise
    
    def generate_text(self, prompt: str, model_name: str, stream: bool = False, 
                      max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                      top_p: Optional[float] = None, check_cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """
        Generate response using text-only model.
        
        Args:
            prompt: Text prompt
            model_name: Ollama model name
            stream: Whether to stream the response
            max_tokens: Maximum tokens to generate (None = use default)
            temperature: Sampling temperature (None = use default)
            top_p: Top-p sampling (None = use default)
            
        Returns:
            Dictionary with 'text' field containing response
        """
        if self.debug_mode:
            print(f"[Ollama] Generating text response with model: {model_name}")
            print(f"[Ollama] Prompt: {prompt[:100]}...")
        
        # Resolve to exact model name
        resolved_model_name = self._resolve_model_name(model_name)
        
        # Check if model is available
        if not self.check_model_available(resolved_model_name):
            if self.debug_mode:
                print(f"[Ollama] Model '{resolved_model_name}' not found, attempting to pull...")
            if not self.pull_model(resolved_model_name):
                raise ValueError(f"Model '{resolved_model_name}' not available and could not be pulled")
        
        # Prepare request with optimized parameters for speed
        payload = {
            "model": resolved_model_name,  # Use resolved name
            "prompt": prompt,
            "stream": stream
        }
        
        # Add generation parameters for faster inference
        if max_tokens is not None:
            payload["num_predict"] = max_tokens  # Ollama uses num_predict instead of max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        
        # Add stop sequences to stop early when JSON is complete
        payload["stop"] = ["\n\n", "}\n", "\n}\n"]
        
        # Make request
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=stream
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Ollama API error: {response.status_code} - {error_text}")
                raise RuntimeError(f"Ollama API error: {response.status_code} - {error_text}")
            
            # Parse response
            if stream:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get('response', '')
                            if token:
                                full_response += token
                                if self.debug_mode:
                                    print(token, end='', flush=True)
                            if data.get('done', False):
                                if self.debug_mode:
                                    print()  # New line after streaming
                                break
                        except json.JSONDecodeError:
                            continue
                response_text = full_response
            else:
                data = response.json()
                response_text = data.get('response', '')
            
            elapsed_time = time.time() - start_time
            
            if self.debug_mode:
                print(f"[Ollama] Generation complete in {elapsed_time:.2f}s")
            
            return {
                'text': response_text,
                'response': response_text,
                'model': data.get('model', model_name),
                'total_duration': data.get('total_duration', elapsed_time * 1e9),  # nanoseconds
                'load_duration': data.get('load_duration', 0),
                'prompt_eval_count': data.get('prompt_eval_count', 0),
                'eval_count': data.get('eval_count', 0)
            }
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request error: {e}")
            raise

