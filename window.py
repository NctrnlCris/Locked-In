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

        # Button container for Start/Stop buttons
        button_container = QHBoxLayout()
        
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
        self.start_btn.clicked.connect(self.start_monitoring_session)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedSize(100, 45)
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #CC0000;
                color: white;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #AA0000;
            }}
        """)
        self.stop_btn.clicked.connect(self.stop_monitoring_session)
        self.stop_btn.setEnabled(False)  # Disabled by default
        
        button_container.addWidget(self.start_btn)
        button_container.addWidget(self.stop_btn)
        button_container.setSpacing(10)

        text_layout.addWidget(self.greet)
        text_layout.addWidget(self.streak)
        text_layout.addWidget(prompt)
        text_layout.addLayout(button_container)
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
    
    def start_monitoring_session(self):
        """Start continuous monitoring of the user's activity"""
        main_window = self.window()
        
        # Check if already monitoring
        if self.is_monitoring:
            return
        
        # Check if profile is loaded
        if not main_window.profile_data:
            QMessageBox.warning(self, "No Profile", "Please select a profile first.")
            return
        
        # Check if process monitoring is available
        if not PROCESS_MONITOR_AVAILABLE:
            QMessageBox.warning(self, "Dependencies Missing", 
                               "Process monitoring requires psutil and pywin32.\n\n"
                               "Please install them with:\n"
                               "pip install psutil pywin32")
            return
        
        # Start the monitoring timer (check every 2 seconds)
        self.monitoring_timer.start(2000)  # 2000ms = 2 seconds
        self.is_monitoring = True
        
        # Update button states
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Do an initial check immediately
        self.check_current_process()
        
        print("[DEBUG] Monitoring started - checking every 2 seconds")
    
    def stop_monitoring_session(self):
        """Stop the continuous monitoring"""
        if not self.is_monitoring:
            return
        
        self.monitoring_timer.stop()
        self.is_monitoring = False
        
        # Reset tracking variables
        self.previous_process_name = None
        self.previous_classification = None
        self.last_analyzed_key = None
        self.last_analysis_result = None
        if self.mixed_process_monitor is not None:
            self.mixed_process_monitor.reset()
        
        # Update button states
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
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
        
        # Get blacklist from profile
        blacklist = main_window.profile_data.get("blacklist", [])
        
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
        
        # Create and show new popup
        self.current_popup = PenguinPopup()
        self.current_popup.show()
        self.current_popup.raise_()  # Bring to front
        self.current_popup.activateWindow()  # Activate the window
        
        print(f"[DEBUG] Penguin popup shown for process: {process_name}")

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