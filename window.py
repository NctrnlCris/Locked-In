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
    SetupWindow = None

# Import process monitoring and popup
try:
    from process_monitor import get_foreground_process_name, is_browser, is_in_blacklist, is_in_whitelist
    from penguin_popup import PenguinPopup
    from screenshot_capture import capture_multiple_screenshots
    PROCESS_MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Process monitoring modules not available: {e}")
    def get_foreground_process_name(): 
        print("Warning: get_foreground_process_name() fallback used - modules not installed")
        return None
    def is_browser(name): return False
    def is_in_blacklist(name, blacklist): return False
    def is_in_whitelist(name, whitelist): return False
    def capture_multiple_screenshots(count=3, duration=5): return []
    PenguinPopup = None
    PROCESS_MONITOR_AVAILABLE = False

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
        self.setStyleSheet("background-color: white;")
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self.check_current_process)
        self.session_timer = QTimer()
        self.session_timer.timeout.connect(self.update_session_timer)
        self.is_monitoring = False
        self.current_popup = None  # Track current popup to prevent duplicates
        
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
            ("Sessions", "assets/sessions.png"),
            ("Insights", "assets/insights.png")
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
        
        # Header Row
        header_layout = QHBoxLayout()
        header = QLabel("Home")
        header.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {DARK_GREEN}; background: transparent;")
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
        
        # Session timer (replaces streak count)
        self.streak = QLabel("00:00:00")
        self.streak.setStyleSheet(f"font-size: 18px; color: {DARK_GREEN};")
        self.streak.hide()  # Hidden until session starts

        prompt = QLabel("Start session?")
        prompt.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {DARK_GREEN}; margin-top: 20px;")

        # Toggle switch container
        toggle_container = QHBoxLayout()
        toggle_container.addStretch()
        
        self.toggle_switch = ToggleSwitch()
        self.toggle_switch.toggled.connect(self.on_toggle_switched)
        toggle_container.addWidget(self.toggle_switch)
        toggle_container.addStretch()
        
        text_layout.addWidget(self.greet)
        text_layout.addWidget(self.streak)  # Timer label (replaces streak)
        text_layout.addWidget(prompt)
        text_layout.addLayout(toggle_container)
        card_layout.addLayout(text_layout)
        
        content_container.addSpacing(20)
        content_container.addWidget(self.card)
        
        self.view_more_link = QLabel("view more sessions >>")
        self.view_more_link.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.view_more_link.setStyleSheet(f"color: {DARK_GREEN}; font-weight: bold; background-color: transparent;")
        self.view_more_link.mousePressEvent = lambda e: self.show_sessions_history()
        self.view_more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        content_container.addWidget(self.view_more_link)
        
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
            except Exception as e:
                print(f"[ERROR] Failed to save session: {e}")
        
        print("[DEBUG] Monitoring stopped")
    
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
        
        # If popup is showing, check if we should close it (switched to whitelist or browser)
        if self.current_popup is not None and self.current_popup.isVisible():
            # Close popup if switched to whitelisted process
            if is_in_whitelist(process_name, whitelist):
                print(f"[DEBUG] Process '{process_name}' is whitelisted - closing popup")
                self.current_popup.close()
                self.current_popup = None
                return
            
            # Close popup if switched to browser (browsers are handled separately)
            if is_browser(process_name):
                print(f"[DEBUG] Process '{process_name}' is a browser - closing popup")
                self.current_popup.close()
                self.current_popup = None
                # Continue to browser handling below
        
        # Check if process is in blacklist
        if is_in_blacklist(process_name, blacklist):
            print(f"[DEBUG] Process '{process_name}' matched blacklist!")
            # Only show popup if one isn't already showing
            if self.current_popup is None or not self.current_popup.isVisible():
                self.show_penguin_popup(process_name, blacklist)
            return
        
        # Check if it's a browser - if so, we need to check for unproductive sites
        if is_browser(process_name):
            # Capture 3 screenshots over 5 seconds for browser analysis
            # Note: This runs in background, we don't block here
            screenshots = capture_multiple_screenshots(count=3, duration_seconds=5)
            
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())