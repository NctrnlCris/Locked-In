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

# --- UI Constants ---
DARK_GREEN = "#0E6B4F"
LIGHT_GRAY = "#F2F2F2"
ACCENT_BLUE = "#00A3FF"

class ProfileSelectionPage(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Select your default profile:")
        label.setStyleSheet(f"font-size: 24px; color: {DARK_GREEN}; font-weight: bold;")
        layout.addWidget(label)

        # Use the whitelist keys from the global scope
        profiles = ["Student", "Developer", "Writer", "Gamer"]

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
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def select_profile(self, profile):
        # Access MainWindow via the stacked widget's parent
        main_window = self.stacked_widget.window() 
        main_window.profile = profile
        
        with open(CONFIG_FILE, "w") as f:
            json.dump({"profile": profile}, f)

        main_window.main_page.update_profile(profile)
        self.stacked_widget.setCurrentIndex(1)

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
        
        # Bottom Settings
        self.settings_btn = QLabel("⚙️ Settings")
        self.settings_btn.setStyleSheet("padding: 15px; font-size: 15px;")
        sidebar_layout.addWidget(self.settings_btn)

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

    def update_profile(self, profile):
        self.greet.setText(f"Hey, {profile}!")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locked-In")
        self.resize(900, 650)

        self.profile = None
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.main_page = MainPage()
        self.profile_page = ProfileSelectionPage(self.stacked_widget)

        self.stacked_widget.addWidget(self.profile_page) # Index 0
        self.stacked_widget.addWidget(self.main_page)    # Index 1

        # Load existing config
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                self.profile = data.get("profile")
                self.main_page.update_profile(self.profile)
                self.stacked_widget.setCurrentIndex(1)
        else:
            self.stacked_widget.setCurrentIndex(0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())