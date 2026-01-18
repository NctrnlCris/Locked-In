"""
Main entry point for Locked-In application
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from profile_manager import any_profiles_exist
from setup_window import SetupWindow
from window import MainWindow

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

