"""
Main entry point for Locked-In application
"""
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from profile_manager import any_profiles_exist
from setup_window import SetupWindow
from window import MainWindow

logger = logging.getLogger(__name__)


def preload_ministral_model():
    """
    Preload the Ministral model by doing a dummy inference.
    This keeps the model loaded in memory so subsequent calls are faster.
    """
    try:
        from scripts.utils.config import Config
        from scripts.vlm.ollama_client import get_or_create_client
        
        print("Loading Ministral model...")
        config = Config()
        
        # Get or create Ollama client (this will start Ollama if needed)
        ollama_client = get_or_create_client(
            base_url=config.ollama_base_url,
            timeout=config.ollama_timeout,
            debug_mode=config.debug_mode,
            auto_start=config.ollama_auto_start
        )
        
        # Use the model name from the codebase (ministral-3:8b)
        model_name = "ministral-3:8b"
        
        # Do a dummy inference with a minimal prompt to load the model
        # This keeps it in memory for faster subsequent calls
        print(f"Preloading model '{model_name}' with dummy inference...")
        result = ollama_client.generate_text(
            prompt="a",
            model_name=model_name,
            stream=False,
            max_tokens=1  # Just generate 1 token to minimize time
        )
        
        if result and result.get('text'):
            print(f"Model '{model_name}' loaded successfully!")
        else:
            print(f"Warning: Model '{model_name}' preload completed but got empty response")
            
    except Exception as e:
        # Don't crash if model loading fails - just log and continue
        print(f"Warning: Could not preload Ministral model: {e}")
        logger.warning(f"Could not preload Ministral model: {e}", exc_info=True)


def main():
    # Initialize config.yaml from message.txt if it doesn't exist
    try:
        from scripts.utils.process_classifier import initialize_config_from_message_txt
        project_root = Path(__file__).parent
        config_path = project_root / "config.yaml"
        message_txt_path = project_root / "message.txt"
        
        if not config_path.exists() and message_txt_path.exists():
            print("Initializing config.yaml from message.txt...")
            initialize_config_from_message_txt(str(message_txt_path), str(config_path))
    except Exception as e:
        print(f"Warning: Could not initialize config.yaml: {e}")
        # Continue anyway - Config class will handle missing config.yaml
    
    # Preload Ministral model to keep it ready for faster inference
    preload_ministral_model()
    
    app = QApplication(sys.argv)
    
    # Check if any profiles exist
    if not any_profiles_exist():
        # Show setup window
        setup_window = SetupWindow()
        setup_window.show()
        
        # Run event loop until setup window is closed
        app.exec()
        
        # Check if setup was completed (profiles exist now)
        if not any_profiles_exist():
            print("Setup was not completed. Exiting...")
            sys.exit(0)
    
    # Profile exists, show main window
    main_window = MainWindow()
    main_window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

