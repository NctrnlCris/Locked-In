import json
import sys
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QStackedWidget, QMessageBox, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QFrame)
from PyQt6.QtCore import QTimer, QSize, Qt
from PyQt6.QtGui import QPixmap, QIcon

# --- Keep your original file paths and logic ---
CONFIG_FILE = Path("config.json")
WHITELIST_FILE = Path("archetype_whitelist.json")
VLM_JSON = "vlm_output.json"

# Mock/Import check for your custom logic
try:
    from dataparsing import check_distraction
    from screenshot_capture import capture_screenshot
except ImportError:
    def check_distraction(x): return False
    def capture_screenshot(): pass

# Import profile management
try:
    from profile_manager import get_all_profiles, load_profile, get_profiles_index
    from setup_window import SetupWindow
except ImportError:
    def get_all_profiles(): return []
    def load_profile(name): return None
    def get_profiles_index(): return {"profiles": []}
    SetupWindow = None

# --- UI Constants ---
DARK_GREEN = "#0E6B4F"
LIGHT_GRAY = "#F2F2F2"
ACCENT_BLUE = "#00A3FF"

class ProfileSelectionPage(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.init_ui()
        self.refresh_profiles()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Select a Profile:")
        label.setStyleSheet(f"font-size: 24px; color: {DARK_GREEN}; font-weight: bold;")
        layout.addWidget(label)

        # Create button container
        self.profiles_container = QWidget()
        self.profiles_layout = QVBoxLayout(self.profiles_container)
        self.profiles_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.profiles_container)

        # Add new profile button
        add_btn = QPushButton("+ Create New Profile")
        add_btn.setFixedSize(200, 50)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_BLUE};
                color: white;
                border-radius: 10px;
                font-size: 18px;
            }}
            QPushButton:hover {{ background-color: #0088CC; }}
        """)
        add_btn.clicked.connect(self.create_new_profile)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def refresh_profiles(self):
        # Clear existing profile buttons
        while self.profiles_layout.count():
            child = self.profiles_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Get all profiles
        profiles = get_all_profiles()

        if not profiles:
            no_profiles_label = QLabel("No profiles found. Create one to get started!")
            no_profiles_label.setStyleSheet("font-size: 14px; color: gray; margin: 20px;")
            self.profiles_layout.addWidget(no_profiles_label)
        else:
            for profile in profiles:
                btn = QPushButton(profile)
                btn.setFixedSize(200, 50)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {DARK_GREEN};
                        color: white;
                        border-radius: 10px;
                        font-size: 18px;
                    }}
                    QPushButton:hover {{ background-color: #0C5B44; }}
                """)
                btn.clicked.connect(lambda checked, p=profile: self.select_profile(p))
                self.profiles_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def select_profile(self, profile_name):
        # Access MainWindow via the stacked widget's parent
        main_window = self.stacked_widget.window() 
        main_window.current_profile = profile_name
        main_window.profile_data = load_profile(profile_name)
        
        # Save current profile to config
        with open(CONFIG_FILE, "w") as f:
            json.dump({"current_profile": profile_name}, f)

        main_window.main_page.update_profile(profile_name)
        self.stacked_widget.setCurrentIndex(1)

    def create_new_profile(self):
        """Open setup window to create a new profile"""
        setup_window = SetupWindow()
        setup_window.show()
        
        # Connect to refresh when setup completes
        def on_setup_complete():
            self.refresh_profiles()
        
        # Note: This is a simple approach - in practice you might want to use signals
        # For now, user will need to manually refresh or we'll refresh on next show
        setup_window.setup_complete = lambda: (setup_window.close(), self.refresh_profiles())

class MainPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: white;")
        
        # Main Layout: Sidebar + Content
        self.root = QHBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        # ---------- Sidebar ----------
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {LIGHT_GRAY};
                border-right: 2px solid {ACCENT_BLUE};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 12px;
                font-size: 15px;
                color: black;
            }}
            QListWidget::item:selected {{
                background-color: #E0E0E0;
                color: {DARK_GREEN};
                font-weight: bold;
            }}
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        # Logo
        logo_container = QHBoxLayout()
        logo_img = QLabel()
        # Scale smoothly to avoid pixelation
        logo_pix = QPixmap("assets/logo.png").scaled(35, 35, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logo_img.setPixmap(logo_pix)
        
        logo_text = QLabel("Locked-in")
        logo_text.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {DARK_GREEN};")
        logo_container.addWidget(logo_img)
        logo_container.addWidget(logo_text)
        sidebar_layout.addLayout(logo_container)
        sidebar_layout.addSpacing(20)

        self.nav = QListWidget()
        items = [
            ("Home", "assets/house.png"),
            ("Sessions", "assets/sessions.png"),
            ("Insights", "assets/insights.png"),
            ("The Glacier", "assets/glacier.png")
        ]
        for text, icon_path in items:
            item = QListWidgetItem(QIcon(icon_path), text)
            self.nav.addItem(item)
        
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch()
        
        # Bottom Settings and Profile Management
        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        
        # Current profile display
        self.current_profile_label = QLabel("Profile: None")
        self.current_profile_label.setStyleSheet("padding: 10px; font-size: 12px; color: gray;")
        settings_layout.addWidget(self.current_profile_label)
        
        # Create new profile button
        self.new_profile_btn = QPushButton("+ New Profile")
        self.new_profile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_BLUE};
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #0088CC; }}
        """)
        self.new_profile_btn.clicked.connect(self.show_setup_window)
        settings_layout.addWidget(self.new_profile_btn)
        
        # Switch profile button
        self.switch_profile_btn = QPushButton("Switch Profile")
        self.switch_profile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_GREEN};
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #0C5B44; }}
        """)
        self.switch_profile_btn.clicked.connect(self.switch_to_profile_selection)
        settings_layout.addWidget(self.switch_profile_btn)
        
        sidebar_layout.addWidget(settings_container)

        self.root.addWidget(self.sidebar)

        # ---------- Main Content Area ----------
        content_container = QVBoxLayout()
        content_container.setContentsMargins(40, 30, 40, 30)
        
        # Header Row
        header_layout = QHBoxLayout()
        header = QLabel("Home")
        header.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {DARK_GREEN};")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        mini_p = QLabel()
        mini_p.setPixmap(QPixmap("assets/logo.png").scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(mini_p)
        content_container.addLayout(header_layout)

        # The Center Card
        self.card = QFrame()
        self.card.setStyleSheet(f"background-color: {LIGHT_GRAY}; border-radius: 30px;")
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(20, 40, 20, 40)

        # Penguin Image
        self.penguin_img = QLabel()
        self.penguin_img.setPixmap(QPixmap("assets/sideways_penguin.png").scaledToWidth(220, Qt.TransformationMode.SmoothTransformation))
        card_layout.addWidget(self.penguin_img)

        # Text Section
        text_layout = QVBoxLayout()
        self.greet = QLabel("Hey, user!")
        self.greet.setStyleSheet(f"font-size: 36px; font-weight: bold; color: {DARK_GREEN};")
        
        self.streak = QLabel("❄️ 134 Streak Count")
        self.streak.setStyleSheet(f"font-size: 18px; color: {DARK_GREEN};")

        prompt = QLabel("Start session?")
        prompt.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {DARK_GREEN}; margin-top: 20px;")

        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedSize(100, 45)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_GREEN};
                color: white;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
        """)

        text_layout.addWidget(self.greet)
        text_layout.addWidget(self.streak)
        text_layout.addWidget(prompt)
        text_layout.addWidget(self.start_btn)
        card_layout.addLayout(text_layout)
        
        content_container.addSpacing(20)
        content_container.addWidget(self.card)
        
        view_more = QLabel("view more sessions >>")
        view_more.setAlignment(Qt.AlignmentFlag.AlignRight)
        view_more.setStyleSheet(f"color: {DARK_GREEN}; font-weight: bold;")
        content_container.addWidget(view_more)
        
        content_container.addStretch()
        self.root.addLayout(content_container, 1)

    def update_profile(self, profile_name):
        self.greet.setText(f"Hey, {profile_name}!")
    
    def show_setup_window(self):
        """Open setup window to create a new profile"""
        setup_window = SetupWindow()
        setup_window.show()
        
        def on_close():
            # Refresh profile list when setup completes
            main_window = self.window()
            if hasattr(main_window, 'profile_page'):
                main_window.profile_page.refresh_profiles()
        
        # Use a timer to check if setup completed (simple approach)
        # In practice, you might want to use signals
        setup_window.destroyed.connect(on_close)
    
    def switch_to_profile_selection(self):
        """Switch to profile selection page"""
        main_window = self.window()
        if hasattr(main_window, 'profile_page'):
            main_window.profile_page.refresh_profiles()
            main_window.stacked_widget.setCurrentIndex(0)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locked-In")
        self.resize(900, 650)

        self.current_profile = None
        self.profile_data = None
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.main_page = MainPage()
        self.profile_page = ProfileSelectionPage(self.stacked_widget)

        self.stacked_widget.addWidget(self.profile_page) # Index 0 - Profile selection
        self.stacked_widget.addWidget(self.main_page)    # Index 1 - Main page

        # Load existing config or show profile selection
        profiles = get_all_profiles()
        if CONFIG_FILE.exists() and profiles:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                current_profile = data.get("current_profile")
                if current_profile and current_profile in profiles:
                    self.current_profile = current_profile
                    self.profile_data = load_profile(current_profile)
                    self.main_page.update_profile(current_profile)
                    self.main_page.current_profile_label.setText(f"Profile: {current_profile}")
                    self.stacked_widget.setCurrentIndex(1)
                else:
                    # Invalid profile, show selector
                    self.stacked_widget.setCurrentIndex(0)
        else:
            # No profiles or no config, show selector
            self.stacked_widget.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())