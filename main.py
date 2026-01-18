"""
Main entry point for Locked-In application
"""
import sys
from PyQt6.QtWidgets import QApplication
from profile_manager import any_profiles_exist
from setup_window import SetupWindow
from window import MainWindow

def main():
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

