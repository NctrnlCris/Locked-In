import json
import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QStackedWidget, QMessageBox, 
                             QHBoxLayout, QListWidget, QListWidgetItem, QFrame,
                             QSlider, QScrollArea, QAbstractButton)
from PyQt6.QtCore import QTimer, QSize, Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPixmap, QIcon, QMouseEvent, QPainter, QBrush, QColor, QPen

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

# Import profile management and sessions
try:
    from profile_manager import get_all_profiles, load_profile, get_profiles_index
    from setup_window import SetupWindow
    from sessions_manager import save_session, get_all_sessions
except ImportError:
    def get_all_profiles(): return []
    def load_profile(name): return None
    def get_profiles_index(): return {"profiles": []}
    def get_all_sessions(): return []
    SetupWindow = None

# Import process monitoring and popup
try:
    from process_monitor import get_foreground_process_name, get_foreground_window_title, is_browser, is_in_blacklist, classify_process
    from penguin_popup import PenguinPopup
    from screenshot_capture import capture_multiple_screenshots, capture_single_screenshot
    PROCESS_MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Process monitoring modules not available: {e}")
    def get_foreground_process_name(): 
        print("Warning: get_foreground_process_name() fallback used - modules not installed")
        return None
    def get_foreground_window_title():
        return None
    def is_browser(name): return False
    def is_in_blacklist(name, blacklist): return False
    def classify_process(name, config=None): return 'unknown'
    def is_in_whitelist(name, whitelist): return False
    def capture_multiple_screenshots(count=3, duration=5): return []
    def capture_single_screenshot(): return None
    PenguinPopup = None
    PROCESS_MONITOR_AVAILABLE = False

# Import classification and VLM modules
try:
    from scripts.utils.mixed_process_monitor import MixedProcessMonitor
    from scripts.utils.config import Config
    from scripts.vlm.ministral_analyzer import analyze_screenshots
    CLASSIFICATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Classification/VLM modules not available: {e}")
    MixedProcessMonitor = None
    Config = None
    analyze_screenshots = None
    CLASSIFICATION_AVAILABLE = False

# --- UI Constants ---
DARK_GREEN = "#0E6B4F"
LIGHT_GRAY = "#F2F2F2"
ACCENT_BLUE = "#00A3FF"

class ToggleSwitch(QWidget):
    """Custom toggle switch widget"""
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_on = False
        self.setFixedSize(70, 35)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Animation for circle position
        self._circle_x = 3.0 + 2.0  # Starting position (left)
        self.animation = QPropertyAnimation(self, b"circleX")
        self.animation.setDuration(200)  # 200ms animation
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    @pyqtProperty(float)
    def circleX(self):
        return self._circle_x
    
    @circleX.setter
    def circleX(self, value):
        self._circle_x = value
        self.update()
    
    def paintEvent(self, event):
        """Draw the toggle switch with circle"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background track
        track_height = 30
        track_y = (self.height() - track_height) // 2
        
        if self.is_on:
            painter.setBrush(QBrush(QColor(DARK_GREEN)))
        else:
            painter.setBrush(QBrush(QColor("#D0D0D0")))
        painter.drawRoundedRect(2, track_y, self.width() - 4, track_height, 15, 15)
        
        # Draw circle with shadow effect (use animated position)
        circle_size = 26
        circle_y = (self.height() - circle_size) // 2
        x_pos = int(self._circle_x)
        
        # Draw shadow
        painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
        painter.drawEllipse(x_pos + 1, circle_y + 1, circle_size, circle_size)
        
        # Draw circle
        painter.setBrush(QBrush(QColor("white")))
        painter.setPen(QPen(QColor(220, 220, 220)))  # Light gray border
        painter.drawEllipse(x_pos, circle_y, circle_size, circle_size)
        
        super().paintEvent(event)
    
    def mousePressEvent(self, event):
        self.toggle()
        super().mousePressEvent(event)
    
    def toggle(self):
        self.is_on = not self.is_on
        
        # Animate circle position
        circle_size = 26
        margin = 3
        if self.is_on:
            target_x = self.width() - circle_size - margin - 2
        else:
            target_x = margin + 2
        
        self.animation.setStartValue(self._circle_x)
        self.animation.setEndValue(float(target_x))
        self.animation.start()
        
        self.toggled.emit(self.is_on)
    
    def setChecked(self, checked):
        if self.is_on != checked:
            self.toggle()

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
        self.setStyleSheet(f"background-color: white;")
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self.check_current_process)
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self.update_session_timer)
        self.is_monitoring = False
        self.current_popup = None  # Track current popup to prevent duplicates
        self.previous_process_name = None  # Track previous process to detect changes
        self.previous_classification = None  # Track previous classification to detect tabbing away
        self.last_analyzed_key = None  # Track last analyzed process+window combination
        self.last_analysis_result = None  # Track if last analysis was "not distracted"
        
        # Initialize classification and monitoring
        if CLASSIFICATION_AVAILABLE and Config is not None and MixedProcessMonitor is not None:
            try:
                self.config = Config()
                timeout = self.config.monitor_timeout
                self.mixed_process_monitor = MixedProcessMonitor(timeout_seconds=timeout)
            except Exception as e:
                print(f"Warning: Could not initialize classification system: {e}")
                self.config = None
                self.mixed_process_monitor = None
        else:
            self.config = None
            self.mixed_process_monitor = None
        
        # Session tracking
        self.session_start_time = None
        self.session_elapsed_seconds = 0
        self.session_popup_count = 0  # Count how many times popup was shown
        self.session_distraction_count = 0  # Count distractions detected
        
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
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) 
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        items = [
            ("Home", "assets/house.png"),
            ("Sessions", "assets/sessions.png")
        ]
        for text, icon_path in items:
            item = QListWidgetItem(QIcon(icon_path), text)
            self.nav.addItem(item)
        
        # Make Sessions clickable to navigate to sessions page
        self.nav.itemClicked.connect(self.on_nav_item_clicked)
        
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch()
        
        # Bottom Settings and Profile Management
        settings_container = QWidget()
        settings_container.setStyleSheet(f"background-color: {LIGHT_GRAY}; border-radius: 10px; padding: 5px;")
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
        content_container.setSpacing(0)
        
        # Header Row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 20)
        header = QLabel("Home")
        header.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {DARK_GREEN}; background: transparent;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # Icon with transparent background
        mini_p = QLabel()
        logo_pixmap = QPixmap("assets/logo.png")
        # Create a transparent version of the pixmap
        transparent_pixmap = QPixmap(logo_pixmap.size())
        transparent_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(transparent_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawPixmap(0, 0, logo_pixmap)
        painter.end()
        mini_p.setPixmap(transparent_pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        mini_p.setStyleSheet("background-color: transparent; border: none;")
        mini_p.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(mini_p)
        content_container.addLayout(header_layout)

        # The Center Card
        self.card = QFrame()
        self.card.setStyleSheet(f"background-color: {LIGHT_GRAY}; border-radius: 25px; padding: 0px;")
        card_layout = QHBoxLayout(self.card)
        card_layout.setContentsMargins(30, 35, 30, 35)
        card_layout.setSpacing(25)

        # Penguin Image
        self.penguin_img = QLabel()
        self.penguin_img.setPixmap(QPixmap("assets/sideways_penguin.png").scaledToWidth(200, Qt.TransformationMode.SmoothTransformation))
        self.penguin_img.setStyleSheet("background-color: transparent;")
        card_layout.addWidget(self.penguin_img)

        # Text Section
        text_layout = QVBoxLayout()
        text_layout.setSpacing(10)
        self.greet = QLabel("Hey, Profile!")
        self.greet.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {DARK_GREEN}; background: transparent; margin-bottom: 5px;")
        
        # Session timer (replaces streak count)
        self.streak = QLabel("00:00:00")
        self.streak.setStyleSheet(f"font-size: 18px; color: {DARK_GREEN}; background: transparent; margin-bottom: 10px;")
        self.streak.hide()  # Hidden until session starts

        prompt = QLabel("Start session?")
        prompt.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {DARK_GREEN}; background: transparent;")
        
        self.toggle_switch = ToggleSwitch()
        self.toggle_switch.toggled.connect(self.on_toggle_switched)
        
        text_layout.addWidget(self.greet)
        text_layout.addWidget(self.streak)  # Timer label (replaces streak)
        
        # Prompt and toggle in same row - aligned with "Hey, Profile!"
        prompt_toggle_layout = QHBoxLayout()
        prompt_toggle_layout.setContentsMargins(0, 0, 0, 0)
        prompt_toggle_layout.setSpacing(10)
        prompt_toggle_layout.addWidget(prompt)
        prompt_toggle_layout.addWidget(self.toggle_switch)
        prompt_toggle_layout.addStretch()
        text_layout.addLayout(prompt_toggle_layout)
        card_layout.addLayout(text_layout)
        
        content_container.addSpacing(15)
        content_container.addWidget(self.card)
        
        self.view_more_link = QLabel("view more sessions >>")
        self.view_more_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.view_more_link.setStyleSheet(f"color: {DARK_GREEN}; font-weight: bold; background-color: transparent; font-size: 14px; margin-top: 10px; padding: 5px;")
        self.view_more_link.mousePressEvent = lambda e: self.show_sessions_history()
        self.view_more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        content_container.addWidget(self.view_more_link)
        
        # Recent Sessions Section
        content_container.addSpacing(28)
        recent_sessions_label = QLabel("Recent Sessions")
        recent_sessions_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {DARK_GREEN}; background: transparent; margin-bottom: 15px; padding: 0px;")
        content_container.addWidget(recent_sessions_label)
        
        # Container for recent sessions - aligned with "Recent Sessions" text
        self.recent_sessions_container = QWidget()
        self.recent_sessions_layout = QVBoxLayout(self.recent_sessions_container)
        self.recent_sessions_layout.setSpacing(0)
        self.recent_sessions_layout.setContentsMargins(0, 0, 0, 0)
        content_container.addWidget(self.recent_sessions_container)
        
        # Load recent sessions
        self.refresh_recent_sessions()
        
        content_container.addStretch()
        self.root.addLayout(content_container, 1)

    def update_profile(self, profile_name):
        self.greet.setText(f"Hey, {profile_name}!")
    
    def refresh_recent_sessions(self):
        """Refresh the recent 3 sessions display on home page"""
        # Clear existing sessions
        while self.recent_sessions_layout.count():
            child = self.recent_sessions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Load sessions
        try:
            all_sessions = get_all_sessions()
            # Get only the first 3 (most recent)
            recent_sessions = all_sessions[:3]
            
            if not recent_sessions:
                no_sessions = QLabel("No sessions yet. Start a monitoring session to see history here!")
                no_sessions.setStyleSheet("font-size: 14px; color: gray; padding: 20px;")
                no_sessions.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.recent_sessions_layout.addWidget(no_sessions)
            else:
                for session in recent_sessions:
                    self.add_recent_session_card(session)
        except Exception as e:
            print(f"[ERROR] Failed to load recent sessions: {e}")
            error_label = QLabel("Unable to load session history.")
            error_label.setStyleSheet("font-size: 14px; color: gray; padding: 20px;")
            self.recent_sessions_layout.addWidget(error_label)
    
    def add_recent_session_card(self, session):
        """Add a session card to the recent sessions layout"""
        # Add divider line before card (except for first one) with light gray spacing
        if self.recent_sessions_layout.count() > 0:
            # Add light gray spacing before divider
            spacer = QWidget()
            spacer.setFixedHeight(8)
            spacer.setStyleSheet(f"background-color: {LIGHT_GRAY};")
            self.recent_sessions_layout.addWidget(spacer)
            
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Sunken)
            divider.setStyleSheet("color: black; background-color: black; max-height: 1px;")
            self.recent_sessions_layout.addWidget(divider)
            
            # Add light gray spacing after divider
            spacer2 = QWidget()
            spacer2.setFixedHeight(8)
            spacer2.setStyleSheet(f"background-color: {LIGHT_GRAY};")
            self.recent_sessions_layout.addWidget(spacer2)
        
        # Card content - match home screen background (light gray)
        card = QWidget()
        card.setStyleSheet(f"background-color: {LIGHT_GRAY};")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(8)
        
        # Duration - first item
        duration = session.get("duration", "0:00")
        duration_label = QLabel(duration)
        duration_label.setStyleSheet(f"font-size: 14px; color: {DARK_GREEN}; font-weight: bold; background-color: transparent; min-width: 60px;")
        card_layout.addWidget(duration_label)
        
        # Date and time
        start_time = session.get("start_time", "")
        date_label = QLabel(start_time)
        date_label.setStyleSheet(f"font-size: 13px; color: black; background-color: transparent;")
        card_layout.addWidget(date_label)
        
        card_layout.addStretch()
        
        # Popup clicks icon and count on the right
        popup_clicks = session.get("popup_click_count", 0)
        if popup_clicks > 0:
            clicks_container = QHBoxLayout()
            clicks_container.setSpacing(5)
            clicks_container.setContentsMargins(0, 0, 0, 0)
            
            # Click icon (using text emoji or could use image)
            click_icon = QLabel("👆")
            click_icon.setStyleSheet(f"font-size: 14px; background-color: transparent;")
            clicks_container.addWidget(click_icon)
            
            clicks_label = QLabel(str(popup_clicks))
            clicks_label.setStyleSheet(f"font-size: 13px; color: {DARK_GREEN}; font-weight: bold; background-color: transparent;")
            clicks_container.addWidget(clicks_label)
            
            clicks_widget = QWidget()
            clicks_widget.setLayout(clicks_container)
            card_layout.addWidget(clicks_widget)
        
        self.recent_sessions_layout.addWidget(card)
    
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
    
    def on_nav_item_clicked(self, item):
        """Handle navigation item clicks"""
        text = item.text()
        main_window = self.window()
        
        if text == "Sessions":
            if hasattr(main_window, 'sessions_page'):
                main_window.stacked_widget.setCurrentWidget(main_window.sessions_page)
                main_window.sessions_page.refresh_sessions()
        # Home and Insights can be handled later if needed
    
    def on_toggle_switched(self, is_on):
        """Handle toggle switch change"""
        if is_on:
            self.start_monitoring_session()
        else:
            self.stop_monitoring_session()
    
    def update_session_timer(self):
        """Update the session timer display"""
        self.session_elapsed_seconds += 1
        hours = self.session_elapsed_seconds // 3600
        minutes = (self.session_elapsed_seconds % 3600) // 60
        seconds = self.session_elapsed_seconds % 60
        self.streak.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def start_monitoring_session(self):
        """Start continuous monitoring of the user's activity"""
        main_window = self.window()
        
        # Check if already monitoring
        if self.is_monitoring:
            return
        
        # Check if profile is loaded
        if not main_window.profile_data:
            QMessageBox.warning(self, "No Profile", "Please select a profile first.")
            self.toggle_switch.setChecked(False)
            return
        
        # Check if process monitoring is available
        if not PROCESS_MONITOR_AVAILABLE:
            QMessageBox.warning(self, "Dependencies Missing", 
                               "Process monitoring requires psutil and pywin32.\n\n"
                               "Please install them with:\n"
                               "pip install psutil pywin32")
            self.toggle_switch.setChecked(False)
            return
        
        # Initialize session tracking
        self.session_start_time = datetime.now()
        self.session_elapsed_seconds = 0
        self.session_popup_count = 0
        self.session_distraction_count = 0
        
        # Start timers
        self.monitoring_timer.start(2000)  # Check every 2 seconds
        self.session_timer.start(1000)  # Update timer every 1 second
        self.is_monitoring = True
        
        # Show timer
        self.streak.show()
        self.streak.setText("00:00:00")
        
        # Do an initial check immediately
        self.check_current_process()
        
        print("[DEBUG] Monitoring started - checking every 2 seconds")
    
    def stop_monitoring_session(self):
        """Stop the continuous monitoring and save session"""
        if not self.is_monitoring:
            return
        
        self.monitoring_timer.stop()
        self.session_timer.stop()
        self.is_monitoring = False
        
        # Reset tracking variables
        self.previous_process_name = None
        self.previous_classification = None
        self.last_analyzed_key = None
        self.last_analysis_result = None
        if self.mixed_process_monitor is not None:
            self.mixed_process_monitor.reset()
        
        # Update toggle switch state
        self.toggle_switch.setChecked(False)
        # Hide timer
        self.streak.hide()
        self.streak.setText("00:00:00")
        
        # Save session data
        if self.session_start_time:
            duration_seconds = self.session_elapsed_seconds
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}"
            
            main_window = self.window()
            session_data = {
                "profile": main_window.current_profile or "Unknown",
                "start_time": self.session_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "duration": duration_str,
                "duration_seconds": duration_seconds,
                "distraction_count": self.session_distraction_count,
                "popup_click_count": self.session_popup_count  # Track clicks from popups
            }
            
            try:
                save_session(session_data)
                print(f"[DEBUG] Session saved: {duration_str}, {self.session_distraction_count} distractions")
                # Refresh recent sessions display to show the new session
                self.refresh_recent_sessions()
            except Exception as e:
                print(f"[ERROR] Failed to save session: {e}")
        
        print("[DEBUG] Monitoring stopped - all timers reset")
    
    def get_work_topic_from_profile(self) -> str:
        """
        Extract work topic from profile data.
        
        Returns:
            Work topic string, or default if not found
        """
        main_window = self.window()
        if not main_window.profile_data:
            return "General work"
        
        # Try to get from responses
        responses = main_window.profile_data.get("responses", {})
        work_topic = responses.get("What are your main things you want to focus on?", "")
        
        if work_topic:
            return work_topic
        
        # Fallback to profile name or default
        return main_window.profile_data.get("name", "General work")
    
    def check_current_process(self):
        """Check the current foreground process - called by timer"""
        main_window = self.window()
        
        if not main_window.profile_data:
            self.stop_monitoring_session()
            return
        
        # Get blacklist and whitelist from profile
        blacklist = main_window.profile_data.get("blacklist", [])
        whitelist = main_window.profile_data.get("whitelist", [])
        
        # Check current foreground process
        process_name = get_foreground_process_name()
        
        if not process_name:
            # Silently skip if we can't detect process (don't spam error messages)
            return
        
        # Detect process change
        process_changed = (process_name != self.previous_process_name)
        self.previous_process_name = process_name
        
        # Priority 1: Check if process is in profile blacklist (takes precedence)
        if is_in_blacklist(process_name, blacklist):
            print(f"[DEBUG] Process '{process_name}' matched profile blacklist!")
            # Only show popup if one isn't already showing
            if self.current_popup is None or not self.current_popup.isVisible():
                self.show_penguin_popup(process_name, blacklist)
            return
        
        # Priority 2: Classify process using config system
        if CLASSIFICATION_AVAILABLE and self.config is not None:
            classification = classify_process(process_name, self.config)
            
            # Get window title for debug output
            try:
                window_title = get_foreground_window_title()
                if window_title:
                    print(f"[DEBUG] Process '{process_name}' (Window: '{window_title}') classified as: {classification}")
                else:
                    print(f"[DEBUG] Process '{process_name}' classified as: {classification}")
            except Exception:
                print(f"[DEBUG] Process '{process_name}' classified as: {classification}")
            
            # Check if user tabbed away from Mixed/Unknown process
            if self.previous_classification in ['mixed', 'unknown'] and classification not in ['mixed', 'unknown']:
                print(f"[DEBUG] User tabbed away from {self.previous_classification} process, resetting timer")
                if self.mixed_process_monitor is not None:
                    self.mixed_process_monitor.reset()
                    print(f"[DEBUG] Timer reset - no longer tracking {self.previous_classification} process")
            
            # Update previous classification
            self.previous_classification = classification
            
            # Handle based on classification
            if classification == 'entertainment':
                # Entertainment process - show popup immediately
                try:
                    window_title = get_foreground_window_title()
                    if window_title:
                        print(f"[DEBUG] Entertainment process detected: {process_name} (Window: '{window_title}')")
                    else:
                        print(f"[DEBUG] Entertainment process detected: {process_name}")
                except Exception:
                    print(f"[DEBUG] Entertainment process detected: {process_name}")
                if self.current_popup is None or not self.current_popup.isVisible():
                    self.show_penguin_popup(process_name, [])
                return
            
            elif classification == 'work':
                # Work process - allow (no action)
                try:
                    window_title = get_foreground_window_title()
                    if window_title:
                        print(f"[DEBUG] Work process allowed: {process_name} (Window: '{window_title}')")
                    else:
                        print(f"[DEBUG] Work process allowed: {process_name}")
                except Exception:
                    print(f"[DEBUG] Work process allowed: {process_name}")
                return
            
            elif classification == 'mixed':
                # Mixed process - monitor with timer
                if self.mixed_process_monitor is not None:
                    # Get window title to create unique key
                    try:
                        window_title = get_foreground_window_title() or ""
                    except Exception:
                        window_title = ""
                    
                    # Create unique key for this process+window combination
                    current_key = f"{process_name}|{window_title}"
                    
                    # Check if this is a new Mixed process or window (first time detected or changed)
                    if process_changed or (self.last_analyzed_key is None) or (current_key != self.last_analyzed_key):
                        # Reset analysis tracking when process or window changes
                        if self.last_analyzed_key is not None and current_key != self.last_analyzed_key:
                            print(f"[DEBUG] Process or window changed, resetting analysis tracking")
                            self.last_analyzed_key = None
                            self.last_analysis_result = None
                        
                        # Take screenshot when Mixed process is first identified or window changes
                        try:
                            print(f"[SCREENSHOT] Capturing screenshot for newly detected Mixed process: {process_name}")
                            screenshot_path = capture_single_screenshot()
                            if screenshot_path:
                                print(f"[SCREENSHOT] Screenshot saved to: {screenshot_path}")
                            else:
                                print(f"[SCREENSHOT] Warning: Screenshot capture returned None")
                        except Exception as e:
                            print(f"[SCREENSHOT] Error capturing screenshot: {e}")
                        
                        # Set the key to prevent continuous resets (but don't set analysis result yet)
                        if self.last_analyzed_key is None:
                            self.last_analyzed_key = current_key
                    
                    self.mixed_process_monitor.update_process(process_name, classification)
                    
                    # Check if timer exceeded and we should run VLM analysis
                    # Only analyze if we haven't already determined this process+window is not distracted
                    if self.mixed_process_monitor.should_check():
                        # Skip if we've already analyzed this exact process+window and it wasn't distracted
                        if self.last_analyzed_key == current_key and self.last_analysis_result == False:
                            print(f"[DEBUG] Skipping VLM analysis - already determined '{process_name}' with window '{window_title}' is not distracted")
                            print(f"[DEBUG] Timer will restart only when process or window changes")
                            # Reset timer but keep the analysis result
                            self.mixed_process_monitor.reset()
                            return
                        
                        print(f"[DEBUG] Mixed process timer exceeded for: {process_name}")
                        # Capture screenshot and analyze with VLM
                        try:
                            print(f"[SCREENSHOT] Capturing screenshot for VLM analysis (timer exceeded): {process_name}")
                            screenshot_path = capture_single_screenshot()
                            if screenshot_path:
                                print(f"[SCREENSHOT] Screenshot saved to: {screenshot_path}")
                            else:
                                print(f"[SCREENSHOT] Warning: Screenshot capture returned None")
                            
                            if screenshot_path and analyze_screenshots is not None:
                                work_topic = self.get_work_topic_from_profile()
                                
                                # Build context info with window title
                                if window_title:
                                    context_info = f"Process: {process_name}, Window Title: {window_title}"
                                    print(f"[VLM] Running VLM analysis for {process_name} (Title: {window_title})...")
                                else:
                                    context_info = f"Process: {process_name}"
                                    print(f"[VLM] Running VLM analysis for {process_name}...")
                                
                                result = analyze_screenshots(
                                    image_paths=[str(screenshot_path)],
                                    work_topic=work_topic,
                                    additional_context=context_info,
                                    debug_mode=True  # Enable debug mode to see reasoning
                                )
                                
                                # Check if distracted
                                if result.get('stage2', {}).get('distracted', False):
                                    confidence = result.get('stage2', {}).get('confidence', 0)
                                    print(f"[VLM] Detected distraction (confidence: {confidence}%)")
                                    
                                    # Verify we're still on the same distracting page before showing popup
                                    try:
                                        current_process_check = get_foreground_process_name()
                                        current_window_check = get_foreground_window_title() or ""
                                        current_key_check = f"{current_process_check}|{current_window_check}"
                                        
                                        if current_key_check == current_key:
                                            # Still on the same page, show popup
                                            self.last_analyzed_key = current_key
                                            self.last_analysis_result = True  # Mark as distracted
                                            if self.current_popup is None or not self.current_popup.isVisible():
                                                self.show_penguin_popup(process_name, [])
                                        else:
                                            # User has navigated away, skip popup
                                            print(f"[VLM] User navigated away from distracting page (was: {current_key}, now: {current_key_check}), skipping popup")
                                            self.last_analyzed_key = current_key
                                            self.last_analysis_result = True  # Still mark as distracted for tracking
                                    except Exception as e:
                                        print(f"[VLM] Error checking current process/window before popup: {e}")
                                        # Fallback: show popup anyway if check fails
                                        self.last_analyzed_key = current_key
                                        self.last_analysis_result = True
                                        if self.current_popup is None or not self.current_popup.isVisible():
                                            self.show_penguin_popup(process_name, [])
                                else:
                                    print(f"[VLM] Determined not distracted - will not re-analyze until process or window changes")
                                    self.last_analyzed_key = current_key
                                    self.last_analysis_result = False  # Mark as not distracted
                                
                                # Reset timer after check
                                self.mixed_process_monitor.reset()
                        except Exception as e:
                            print(f"[ERROR] VLM analysis failed: {e}")
                            import traceback
                            traceback.print_exc()
                            # Reset timer even on error to prevent infinite retries
                            if self.mixed_process_monitor is not None:
                                self.mixed_process_monitor.reset()
                return
            
            elif classification == 'unknown':
                # Unknown process - monitor with timer (same as Mixed)
                if self.mixed_process_monitor is not None:
                    # Get window title to create unique key
                    try:
                        window_title = get_foreground_window_title() or ""
                    except Exception:
                        window_title = ""
                    
                    # Create unique key for this process+window combination
                    current_key = f"{process_name}|{window_title}"
                    
                    # Check if this is a new Unknown process or window (first time detected or changed)
                    if process_changed or (self.last_analyzed_key is None) or (current_key != self.last_analyzed_key):
                        # Reset analysis tracking when process or window changes
                        if self.last_analyzed_key is not None and current_key != self.last_analyzed_key:
                            print(f"[DEBUG] Process or window changed for Unknown process, resetting analysis tracking")
                            self.last_analyzed_key = None
                            self.last_analysis_result = None
                        
                        # Take screenshot when Unknown process is first identified or window changes
                        try:
                            print(f"[SCREENSHOT] Capturing screenshot for newly detected Unknown process: {process_name}")
                            screenshot_path = capture_single_screenshot()
                            if screenshot_path:
                                print(f"[SCREENSHOT] Screenshot saved to: {screenshot_path}")
                            else:
                                print(f"[SCREENSHOT] Warning: Screenshot capture returned None")
                        except Exception as e:
                            print(f"[SCREENSHOT] Error capturing screenshot: {e}")
                        
                        # Set the key to prevent continuous resets (but don't set analysis result yet)
                        if self.last_analyzed_key is None:
                            self.last_analyzed_key = current_key
                    
                    self.mixed_process_monitor.update_process(process_name, classification)
                    
                    # Check if timer exceeded and we should run VLM analysis
                    # Only analyze if we haven't already determined this process+window is not distracted
                    if self.mixed_process_monitor.should_check():
                        # Skip if we've already analyzed this exact process+window and it wasn't distracted
                        if self.last_analyzed_key == current_key and self.last_analysis_result == False:
                            print(f"[DEBUG] Skipping VLM analysis - already determined '{process_name}' with window '{window_title}' is not distracted")
                            print(f"[DEBUG] Timer will restart only when process or window changes")
                            # Reset timer but keep the analysis result
                            self.mixed_process_monitor.reset()
                            return
                        
                        print(f"[DEBUG] Unknown process timer exceeded for: {process_name}")
                        # Capture screenshot and analyze with VLM
                        try:
                            print(f"[SCREENSHOT] Capturing screenshot for VLM analysis (timer exceeded): {process_name}")
                            screenshot_path = capture_single_screenshot()
                            if screenshot_path:
                                print(f"[SCREENSHOT] Screenshot saved to: {screenshot_path}")
                            else:
                                print(f"[SCREENSHOT] Warning: Screenshot capture returned None")
                            
                            if screenshot_path and analyze_screenshots is not None:
                                work_topic = self.get_work_topic_from_profile()
                                
                                # Build context info with window title
                                if window_title:
                                    context_info = f"Process: {process_name}, Window Title: {window_title}"
                                    print(f"[VLM] Running VLM analysis for {process_name} (Title: {window_title})...")
                                else:
                                    context_info = f"Process: {process_name}"
                                    print(f"[VLM] Running VLM analysis for {process_name}...")
                                
                                result = analyze_screenshots(
                                    image_paths=[str(screenshot_path)],
                                    work_topic=work_topic,
                                    additional_context=context_info,
                                    debug_mode=True  # Enable debug mode to see reasoning
                                )
                                
                                # Check if distracted
                                if result.get('stage2', {}).get('distracted', False):
                                    confidence = result.get('stage2', {}).get('confidence', 0)
                                    print(f"[VLM] Detected distraction (confidence: {confidence}%)")
                                    
                                    # Verify we're still on the same distracting page before showing popup
                                    try:
                                        current_process_check = get_foreground_process_name()
                                        current_window_check = get_foreground_window_title() or ""
                                        current_key_check = f"{current_process_check}|{current_window_check}"
                                        
                                        if current_key_check == current_key:
                                            # Still on the same page, show popup
                                            self.last_analyzed_key = current_key
                                            self.last_analysis_result = True  # Mark as distracted
                                            if self.current_popup is None or not self.current_popup.isVisible():
                                                self.show_penguin_popup(process_name, [])
                                        else:
                                            # User has navigated away, skip popup
                                            print(f"[VLM] User navigated away from distracting page (was: {current_key}, now: {current_key_check}), skipping popup")
                                            self.last_analyzed_key = current_key
                                            self.last_analysis_result = True  # Still mark as distracted for tracking
                                    except Exception as e:
                                        print(f"[VLM] Error checking current process/window before popup: {e}")
                                        # Fallback: show popup anyway if check fails
                                        self.last_analyzed_key = current_key
                                        self.last_analysis_result = True
                                        if self.current_popup is None or not self.current_popup.isVisible():
                                            self.show_penguin_popup(process_name, [])
                                else:
                                    print(f"[VLM] Determined not distracted - will not re-analyze until process or window changes")
                                    self.last_analyzed_key = current_key
                                    self.last_analysis_result = False  # Mark as not distracted
                                
                                # Reset timer after check
                                self.mixed_process_monitor.reset()
                        except Exception as e:
                            print(f"[ERROR] VLM analysis failed: {e}")
                            import traceback
                            traceback.print_exc()
                            # Reset timer even on error to prevent infinite retries
                            if self.mixed_process_monitor is not None:
                                self.mixed_process_monitor.reset()
                return
        
        # Legacy: Check if it's a browser - if so, we need to check for unproductive sites
        if is_browser(process_name):
            # Capture 3 screenshots over 5 seconds for browser analysis
            # Note: This runs in background, we don't block here
            print(f"[SCREENSHOT] Capturing multiple screenshots for browser analysis: {process_name}")
            screenshots = capture_multiple_screenshots(count=3, duration_seconds=5)
            print(f"[SCREENSHOT] Captured {len(screenshots)} screenshots for browser analysis")
            
            # #TODO: Call model with screenshots to check if user is being unproductive
            # #TODO: from model_handler import check_unproductive_activity
            # #TODO: Pass the screenshots to the model for analysis
            # #TODO: is_unproductive = check_unproductive_activity(screenshots)
            # 
            # #TODO: The model should analyze the screenshots to detect:
            # #TODO: - YouTube, social media sites, distracting content
            # #TODO: - Compare against blacklist URLs/domains
            # #TODO: - Return True if unproductive activity detected
            # 
            # #TODO: If model determines unproductive, show penguin popup
            # #TODO: if is_unproductive:
            # #TODO:     self.show_penguin_popup(process_name, blacklist)
            
            print(f"[DEBUG] Browser detected: {process_name} - Screenshots captured for analysis")
    
    def show_penguin_popup(self, process_name, blacklist):
        """Show the penguin popup when user is being unproductive"""
        if PenguinPopup is None:
            QMessageBox.warning(self, "Error", "Penguin popup not available.")
            return
        
        # Close existing popup if any
        if self.current_popup is not None:
            try:
                self.current_popup.close()
            except:
                pass
        
        # Track distraction
        self.session_distraction_count += 1
        
        # Create and show new popup
        self.current_popup = PenguinPopup()
        self.current_popup.show()
        self.current_popup.raise_()  # Bring to front
        self.current_popup.activateWindow()  # Activate the window
        
        # Track popup shown count (for click counting later)
        self.session_popup_count += 1
        
        print(f"[DEBUG] Penguin popup shown for process: {process_name}")
    
    def show_sessions_history(self):
        """Navigate to sessions history page"""
        main_window = self.window()
        if hasattr(main_window, 'sessions_page'):
            main_window.stacked_widget.setCurrentWidget(main_window.sessions_page)
            main_window.sessions_page.refresh_sessions()

class SessionsHistoryPage(QWidget):
    """Page displaying session history"""
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        self.setStyleSheet(f"background-color: {LIGHT_GRAY};")
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Sessions History")
        title.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {DARK_GREEN}; background-color: transparent;")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Back button
        back_btn = QPushButton("← Back to Home")
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_GREEN};
                color: white;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: #0C5B44; }}
        """)
        back_btn.clicked.connect(self.go_back_home)
        header_layout.addWidget(back_btn)
        
        layout.addLayout(header_layout)
        layout.addSpacing(20)
        
        # Scroll area for sessions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.sessions_container = QWidget()
        self.sessions_layout = QVBoxLayout(self.sessions_container)
        self.sessions_layout.setSpacing(15)
        
        scroll.setWidget(self.sessions_container)
        layout.addWidget(scroll)
    
    def refresh_sessions(self):
        """Refresh the sessions list"""
        # Clear existing sessions
        while self.sessions_layout.count():
            child = self.sessions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Load sessions
        try:
            sessions = get_all_sessions()
            if not sessions:
                no_sessions = QLabel("No sessions yet. Start a monitoring session to see history here!")
                no_sessions.setStyleSheet("font-size: 16px; color: gray; padding: 40px;")
                no_sessions.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.sessions_layout.addWidget(no_sessions)
            else:
                for session in sessions:
                    self.add_session_card(session)
        except Exception as e:
            print(f"[ERROR] Failed to load sessions: {e}")
    
    def add_session_card(self, session):
        """Add a session card to the layout"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 15px 0px;
            }
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon (penguin for now - can be varied based on session type)
        icon_label = QLabel()
        icon_pix = QPixmap("assets/penguin.png").scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        icon_label.setPixmap(icon_pix)
        icon_label.setStyleSheet("background-color: transparent;")
        card_layout.addWidget(icon_label)
        
        # Session info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        # Date and time
        start_time = session.get("start_time", "")
        date_label = QLabel(start_time)
        date_label.setStyleSheet(f"font-size: 14px; color: {DARK_GREEN}; font-weight: bold; background-color: transparent;")
        info_layout.addWidget(date_label)
        
        # Duration and metrics
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(15)
        
        duration = session.get("duration", "0:00")
        duration_label = QLabel(f"⏱ {duration}")
        duration_label.setStyleSheet(f"font-size: 12px; color: #7B2CBF; background-color: transparent;")
        metrics_layout.addWidget(duration_label)
        
        distractions = session.get("distraction_count", 0)
        if distractions > 0:
            dist_label = QLabel(f"❄️ {distractions}")
            dist_label.setStyleSheet(f"font-size: 12px; color: #0066CC; background-color: transparent;")
            metrics_layout.addWidget(dist_label)
        
        popup_clicks = session.get("popup_click_count", 0)
        # Always show popup clicks if there were any popups shown
        if popup_clicks > 0:
            clicks_label = QLabel(f"👆 {popup_clicks}")
            clicks_label.setStyleSheet(f"font-size: 12px; color: #FF6B35; background-color: transparent;")
            metrics_layout.addWidget(clicks_label)
        
        metrics_layout.addStretch()
        info_layout.addLayout(metrics_layout)
        
        card_layout.addLayout(info_layout, 1)
        
        self.sessions_layout.addWidget(card)
    
    def go_back_home(self):
        """Navigate back to home page"""
        main_window = self.window()
        if hasattr(main_window, 'main_page'):
            main_window.stacked_widget.setCurrentWidget(main_window.main_page)

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
        self.sessions_page = SessionsHistoryPage()

        self.stacked_widget.addWidget(self.profile_page) # Index 0 - Profile selection
        self.stacked_widget.addWidget(self.main_page)    # Index 1 - Main page
        self.stacked_widget.addWidget(self.sessions_page) # Index 2 - Sessions history

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
    
    def closeEvent(self, event):
        """Handle window close event - cleanup screenshots and stop monitoring"""
        import shutil
        
        # Stop monitoring if active
        if hasattr(self.main_page, 'monitoring_timer') and self.main_page.monitoring_timer.isActive():
            self.main_page.monitoring_timer.stop()
            print("[CLEANUP] Stopped monitoring timer")
        
        # Clear screenshot folder
        screenshot_dir = Path("screenshot_data")
        if screenshot_dir.exists() and screenshot_dir.is_dir():
            try:
                # Remove all files in the screenshot directory
                for file_path in screenshot_dir.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        print(f"[CLEANUP] Deleted screenshot: {file_path.name}")
                print(f"[CLEANUP] Cleared screenshot folder: {screenshot_dir}")
            except Exception as e:
                print(f"[CLEANUP] Error clearing screenshot folder: {e}")
        
        # Close any open popups
        if hasattr(self.main_page, 'current_popup') and self.main_page.current_popup is not None:
            try:
                self.main_page.current_popup.close()
            except Exception as e:
                print(f"[CLEANUP] Error closing popup: {e}")
        
        # Call parent closeEvent
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())