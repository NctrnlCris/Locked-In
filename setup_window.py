"""
Setup window for initial profile configuration
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit, QStackedWidget,
                             QMessageBox, QLineEdit, QFrame, QScrollArea,
                             QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from pathlib import Path
from datetime import datetime
from config import SETUP_QUESTIONS, OUTPUT_DIR, PROFILES_DIR
from profile_manager import save_profile as save_profile_to_manager
from PyQt6.QtWidgets import QLineEdit
import json
import threading


class ProcessClassifierWorker(QThread):
    """Worker thread for LLM-based process classification"""
    progress_updated = pyqtSignal(int, int)  # current_chunk, total_chunks
    classification_complete = pyqtSignal(dict)  # result dict
    
    def __init__(self, responses: dict, debug_mode: bool = False):
        super().__init__()
        self.responses = responses
        self.debug_mode = debug_mode
    
    def run(self):
        try:
            from scripts.vlm.process_classifier_llm import classify_processes_for_profile
            
            def progress_callback(current, total):
                self.progress_updated.emit(current, total)
            
            result = classify_processes_for_profile(
                responses=self.responses,
                model_name="ministral-3:3b",
                chunk_size=30,
                debug_mode=self.debug_mode,
                progress_callback=progress_callback
            )
            
            self.classification_complete.emit(result)
            
        except Exception as e:
            self.classification_complete.emit({
                'success': False,
                'error': str(e),
                'process_classifications': None
            })

class SetupModeSelectionPage(QWidget):
    """Page for selecting between Pre-default and Custom setup"""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Welcome to Locked-In!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        
        subtitle = QLabel("Choose your setup option:")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 16px; margin: 10px;")
        
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        
        # Pre-default button (placeholder for now)
        predefault_btn = QPushButton("Pre-default")
        predefault_btn.setMinimumHeight(50)
        predefault_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        predefault_btn.clicked.connect(self.on_predefault_clicked)
        
        # Custom button
        custom_btn = QPushButton("Custom")
        custom_btn.setMinimumHeight(50)
        custom_btn.setStyleSheet("font-size: 14px; padding: 10px;")
        custom_btn.clicked.connect(self.on_custom_clicked)
        
        button_layout.addWidget(predefault_btn)
        button_layout.addWidget(custom_btn)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def on_predefault_clicked(self):
        # Placeholder - teammate working on this
        QMessageBox.information(self, "Pre-default", 
                               "Pre-default setup will be available soon!")
    
    def on_custom_clicked(self):
        self.parent_window.switch_to_name_page()


class ProfileNamePage(QWidget):
    """Page to enter profile name"""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Create New Profile")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        
        subtitle = QLabel("Give your profile a name (e.g., Computer Science, Writing, Gaming)")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; margin: 10px;")
        subtitle.setWordWrap(True)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter profile name...")
        self.name_input.setMinimumHeight(40)
        self.name_input.setStyleSheet("font-size: 14px; padding: 10px; border-radius: 5px;")
        
        # Add Enter key shortcut to go to next
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self.name_input)
        enter_shortcut.activated.connect(self.on_next_clicked)
        enter_shortcut2 = QShortcut(QKeySequence(Qt.Key.Key_Enter), self.name_input)
        enter_shortcut2.activated.connect(self.on_next_clicked)
        
        button_layout = QHBoxLayout()
        
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.on_back_clicked)
        
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.on_next_clicked)
        
        button_layout.addWidget(back_btn)
        button_layout.addWidget(self.next_btn)
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addWidget(QLabel("Profile Name:"))
        layout.addWidget(self.name_input)
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def on_next_clicked(self):
        profile_name = self.name_input.text().strip()
        
        if not profile_name:
            QMessageBox.warning(self, "Empty Name", "Please enter a profile name.")
            return
        
        # Store profile name and move to questions
        self.parent_window.profile_name = profile_name
        self.parent_window.switch_to_custom_page()
    
    def on_back_clicked(self):
        self.parent_window.switch_to_selection_page()


class SuggestionWorker(QThread):
    """Worker thread for async suggestion generation"""
    suggestions_ready = pyqtSignal(list)
    
    def __init__(self, q1, q2, q3, q4, suggestion_type):
        super().__init__()
        self.q1 = q1
        self.q2 = q2
        self.q3 = q3
        self.q4 = q4
        self.suggestion_type = suggestion_type
    
    def run(self):
        try:
            from scripts.vlm.profile_suggestion_generator import generate_profile_suggestions
            suggestions = generate_profile_suggestions(
                q1_response=self.q1,
                q2_response=self.q2,
                q3_response=self.q3,
                q4_response=self.q4,
                suggestion_type=self.suggestion_type,
                debug_mode=False
            )
            self.suggestions_ready.emit(suggestions)
        except Exception as e:
            # Fail silently - emit empty list
            self.suggestions_ready.emit([])


class TagWidget(QFrame):
    """Clickable tag widget that shows a keyword"""
    def __init__(self, keyword, parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.parent_widget = parent
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        label = QLabel(keyword)
        label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(label)
        
        close_btn = QLabel("×")
        close_btn.setStyleSheet("color: white; font-size: 16px; font-weight: bold; padding-left: 5px;")
        close_btn.mousePressEvent = lambda e: self.remove_tag()
        layout.addWidget(close_btn)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #0E6B4F;
                border-radius: 12px;
                padding: 2px;
            }
            QFrame:hover {
                background-color: #0C5B44;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def remove_tag(self):
        """Remove this tag from the parent"""
        if self.parent_widget:
            self.parent_widget.remove_keyword(self.keyword)
        self.deleteLater()
    
    def mousePressEvent(self, event):
        """Make entire tag clickable to remove"""
        self.remove_tag()


class CustomSetupPage(QWidget):
    """Page for custom profile setup with chat interface"""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.current_question_index = 0
        self.responses = {}
        self.keywords = {}  # Store keywords for whitelist/blacklist questions
        self.suggestion_worker = None  # For async suggestion generation
        self.init_ui()
        self.show_next_question()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Custom Setup - Tell us about yourself")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 20px; font-weight: bold; margin: 10px;")
        
        # Question label
        self.question_label = QLabel()
        self.question_label.setStyleSheet("font-size: 16px; margin: 15px; padding: 10px;")
        self.question_label.setWordWrap(True)
        
        # Chat text area (read-only for questions, editable for answers)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #f5f5f5; padding: 10px;")
        
        # Regular input area for text questions
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("Type your response here...")
        self.input_area.setMaximumHeight(100)
        
        # Keyword input for whitelist/blacklist questions
        self.keyword_input_container = QWidget()
        keyword_input_layout = QVBoxLayout(self.keyword_input_container)
        
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Type a keyword and press Enter to add...")
        self.keyword_input.setStyleSheet("font-size: 14px; padding: 8px; border-radius: 5px;")
        self.keyword_input.returnPressed.connect(self.add_keyword)
        
        # Loading indicator for suggestions (disabled - user input only)
        self.loading_label = QLabel("")
        self.loading_label.setStyleSheet("color: #666; font-style: italic;")
        self.loading_label.hide()
        
        # Tags container (flow layout simulation)
        self.tags_container = QWidget()
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(8)
        self.tags_layout.addStretch()
        
        # Scroll area for tags if many
        tags_scroll = QScrollArea()
        tags_scroll.setWidget(self.tags_container)
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setMaximumHeight(100)
        tags_scroll.setStyleSheet("QScrollArea { border: none; }")
        
        keyword_input_layout.addWidget(QLabel("Add keywords:"))
        keyword_input_layout.addWidget(self.keyword_input)
        # Loading label removed - user input only, no suggestions
        keyword_input_layout.addWidget(tags_scroll)
        
        self.keyword_input_container.hide()  # Hide by default, show for whitelist/blacklist questions
        
        # Add Enter key shortcut (Ctrl+Enter for multi-line, or just Enter)
        enter_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_area)
        enter_shortcut.activated.connect(self.on_next_clicked)
        enter_shortcut2 = QShortcut(QKeySequence("Ctrl+Enter"), self.input_area)
        enter_shortcut2.activated.connect(self.on_next_clicked)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.on_back_clicked)
        
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.on_next_clicked)
        
        button_layout.addWidget(back_btn)
        button_layout.addWidget(self.next_btn)
        
        layout.addWidget(header)
        layout.addWidget(self.question_label)
        layout.addWidget(self.chat_display)
        layout.addWidget(QLabel("Your response:"))
        layout.addWidget(self.input_area)
        layout.addWidget(self.keyword_input_container)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def add_keyword(self):
        """Add a keyword/tag from the input field"""
        keyword = self.keyword_input.text().strip()
        print(f"\n[DEBUG] add_keyword called with: '{keyword}'")
        
        if not keyword:
            print("[DEBUG] Empty keyword, returning")
            return
        
        # Get current question to determine if it's whitelist or blacklist
        current_question = SETUP_QUESTIONS[self.current_question_index]
        print(f"[DEBUG] Current question index: {self.current_question_index}")
        print(f"[DEBUG] Current question: {current_question[:50]}...")
        
        # Initialize keyword list for this question if needed
        if current_question not in self.keywords:
            print(f"[DEBUG] Initializing keywords list for this question")
            self.keywords[current_question] = []
        else:
            print(f"[DEBUG] Existing keywords for this question: {self.keywords[current_question]}")
        
        # Add keyword if not already present
        if keyword not in self.keywords[current_question]:
            print(f"[DEBUG] Adding new keyword: '{keyword}'")
            self.keywords[current_question].append(keyword)
            
            # Create and add tag widget
            tag = TagWidget(keyword, self)
            # Insert before stretch
            self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag)
            print(f"[DEBUG] Tag widget created and added. Total keywords now: {len(self.keywords[current_question])}")
        else:
            print(f"[DEBUG] Keyword '{keyword}' already exists, skipping")
        
        # Clear input
        self.keyword_input.clear()
        print(f"[DEBUG] add_keyword completed\n")
    
    def remove_keyword(self, keyword):
        """Remove a keyword from the current question"""
        current_question = SETUP_QUESTIONS[self.current_question_index]
        if current_question in self.keywords:
            if keyword in self.keywords[current_question]:
                self.keywords[current_question].remove(keyword)
        
        # Update response to match keywords
        if current_question in self.keywords and self.keywords[current_question]:
            self.responses[current_question] = ", ".join(self.keywords[current_question])
        elif current_question in self.responses:
            del self.responses[current_question]
        
        # Update chat display
        self.update_chat_display()
    
    def generate_suggestions_async(self, suggestion_type):
        """Generate suggestions asynchronously for whitelist/blacklist"""
        print(f"\n[DEBUG] ========== generate_suggestions_async called ==========")
        print(f"[DEBUG] suggestion_type: {suggestion_type}")
        try:
            # Get Q1-Q4 responses
            q1 = self.responses.get(SETUP_QUESTIONS[0], "")
            q2 = self.responses.get(SETUP_QUESTIONS[1], "")
            q3 = self.responses.get(SETUP_QUESTIONS[2], "")
            q4 = self.responses.get(SETUP_QUESTIONS[3], "")
            
            print(f"[DEBUG] Q1: {q1[:50] if q1 else 'EMPTY'}...")
            print(f"[DEBUG] Q2: {q2[:50] if q2 else 'EMPTY'}...")
            print(f"[DEBUG] Q3: {q3[:50] if q3 else 'EMPTY'}...")
            print(f"[DEBUG] Q4: {q4[:50] if q4 else 'EMPTY'}...")
            
            # Only generate if we have at least some responses
            if not (q1 or q2 or q3 or q4):
                print(f"[DEBUG] No responses found, returning early")
                return
            
            # Show loading indicator
            print(f"[DEBUG] Showing loading indicator")
            self.loading_label.show()
            
            # Stop any existing worker
            if self.suggestion_worker and self.suggestion_worker.isRunning():
                print(f"[DEBUG] Stopping existing suggestion worker")
                self.suggestion_worker.terminate()
                self.suggestion_worker.wait()
            
            # Create and start new worker
            print(f"[DEBUG] Creating new SuggestionWorker")
            self.suggestion_worker = SuggestionWorker(q1, q2, q3, q4, suggestion_type)
            self.suggestion_worker.suggestions_ready.connect(self._on_suggestions_ready)
            print(f"[DEBUG] Starting suggestion worker thread")
            self.suggestion_worker.start()
            print(f"[DEBUG] Suggestion worker started")
        except Exception as e:
            # Don't crash if suggestion generation fails
            print(f"[DEBUG] ERROR in generate_suggestions_async: {e}")
            import traceback
            traceback.print_exc()
            self.loading_label.hide()
        print(f"[DEBUG] ========== generate_suggestions_async completed ==========\n")
    
    def _on_suggestions_ready(self, suggestions):
        """Handle suggestions when they're ready"""
        print(f"\n[DEBUG] ========== _on_suggestions_ready called ==========")
        print(f"[DEBUG] Received {len(suggestions) if suggestions else 0} suggestions")
        print(f"[DEBUG] Suggestions: {suggestions}")
        
        self.loading_label.hide()
        
        if not suggestions:
            print(f"[DEBUG] No suggestions received, returning")
            return
        
        # Get current question
        current_question = SETUP_QUESTIONS[self.current_question_index]
        print(f"[DEBUG] Current question index: {self.current_question_index}")
        print(f"[DEBUG] Current question: {current_question[:50]}...")
        
        # Initialize keywords list if needed
        if current_question not in self.keywords:
            print(f"[DEBUG] Initializing keywords list for current question")
            self.keywords[current_question] = []
        else:
            print(f"[DEBUG] Existing keywords: {self.keywords[current_question]}")
        
        # Add suggestions as tags (user can remove them)
        added_count = 0
        for suggestion in suggestions:
            if suggestion not in self.keywords[current_question]:
                print(f"[DEBUG] Adding suggestion: '{suggestion}'")
                self.keywords[current_question].append(suggestion)
                tag = TagWidget(suggestion, self)
                self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag)
                added_count += 1
            else:
                print(f"[DEBUG] Suggestion '{suggestion}' already exists, skipping")
        
        print(f"[DEBUG] Added {added_count} new suggestions. Total keywords: {len(self.keywords[current_question])}")
        
        # Update response
        if self.keywords[current_question]:
            response_text = ", ".join(self.keywords[current_question])
            print(f"[DEBUG] Updating response with: '{response_text}'")
            self.responses[current_question] = response_text
        print(f"[DEBUG] ========== _on_suggestions_ready completed ==========\n")
    
    def show_next_question(self):
        try:
            print(f"\n[DEBUG] show_next_question called - current_question_index: {self.current_question_index}")
            print(f"[DEBUG] Total questions: {len(SETUP_QUESTIONS)}")
            print(f"[DEBUG] Condition check: {self.current_question_index} >= {len(SETUP_QUESTIONS)} = {self.current_question_index >= len(SETUP_QUESTIONS)}")
            
            # Safety check: ensure index is valid
            if self.current_question_index < 0:
                print(f"[DEBUG] ⚠️ Invalid question index (negative): {self.current_question_index}, resetting to 0")
                self.current_question_index = 0
            
            if self.current_question_index >= len(SETUP_QUESTIONS):
                print("[DEBUG] ⚠️ All questions answered, calling finish_setup()")
                print(f"[DEBUG] ⚠️ Index {self.current_question_index} >= {len(SETUP_QUESTIONS)} (total questions)")
                print(f"[DEBUG] ⚠️ Questions answered: {list(self.responses.keys())}")
                # Only finish if we've actually answered all questions
                if len(self.responses) >= len(SETUP_QUESTIONS):
                    print("[DEBUG] ✅ All questions have responses, finishing setup")
                    self.finish_setup()
                else:
                    print(f"[DEBUG] ⚠️ ERROR: Not all questions answered! Only {len(self.responses)}/{len(SETUP_QUESTIONS)} answered")
                    print(f"[DEBUG] ⚠️ Resetting to last question index: {len(SETUP_QUESTIONS) - 1}")
                    self.current_question_index = len(SETUP_QUESTIONS) - 1
                    # Recursively call to show the last question
                    return self.show_next_question()
                return
            
            question = SETUP_QUESTIONS[self.current_question_index]
            print(f"[DEBUG] ✅ Showing question {self.current_question_index + 1} of {len(SETUP_QUESTIONS)}: {question[:50]}...")
            print(f"[DEBUG] ✅ Question index {self.current_question_index} is valid (0-{len(SETUP_QUESTIONS)-1})")
            
            # Explicit check for question 6
            if self.current_question_index == 5:
                print(f"[DEBUG] ✅✅✅ THIS IS QUESTION 6 (BLACKLIST) - Index 5 ✅✅✅")
            
            self.question_label.setText(f"Question {self.current_question_index + 1}/{len(SETUP_QUESTIONS)}:\n{question}")
            
            # Check if this is a whitelist/blacklist question (indices 4 and 5)
            # Question 4 = whitelist (keyword input), Question 5 = blacklist (keyword input)
            is_keyword_question = self.current_question_index in [4, 5]
            print(f"[DEBUG] is_keyword_question: {is_keyword_question} (index {self.current_question_index})")
            
            if is_keyword_question:
                print(f"[DEBUG] Setting up keyword question UI for question {self.current_question_index + 1}")
                # Show keyword input, hide text input
                print(f"[DEBUG] Hiding text input, showing keyword input")
                self.input_area.hide()
                self.keyword_input_container.show()
                
                # Load existing keywords for this question
                print(f"[DEBUG] Checking for existing keywords for question: {question[:50]}...")
                print(f"[DEBUG] Current keywords dict keys: {list(self.keywords.keys())}")
                if question in self.keywords:
                    print(f"[DEBUG] Found existing keywords: {self.keywords[question]}")
                    # Clear existing tags
                    while self.tags_layout.count() > 1:  # Keep the stretch
                        child = self.tags_layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    
                    # Recreate tags
                    print(f"[DEBUG] Recreating {len(self.keywords[question])} tags")
                    for keyword in self.keywords[question]:
                        tag = TagWidget(keyword, self)
                        self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag)
                else:
                    # Clear tags if no keywords
                    print(f"[DEBUG] No existing keywords, clearing tags")
                    while self.tags_layout.count() > 1:
                        child = self.tags_layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
                    
                    # No suggestion generation - user input only
                    print(f"[DEBUG] Question {self.current_question_index + 1} - user input only (no suggestions)")
            else:
                # Show text input, hide keyword input
                print(f"[DEBUG] Showing text input for regular question")
                self.input_area.show()
                self.keyword_input_container.hide()
                
                # Restore text response if exists
                if question in self.responses:
                    print(f"[DEBUG] Restoring existing response: {self.responses[question][:50]}...")
                    self.input_area.setPlainText(self.responses[question])
                else:
                    print(f"[DEBUG] No existing response, clearing input")
                    self.input_area.clear()
            
            # Update button text
            if self.current_question_index == len(SETUP_QUESTIONS) - 1:
                print(f"[DEBUG] Last question - setting button to 'Finish & Save'")
                self.next_btn.setText("Finish & Save")
            else:
                print(f"[DEBUG] Not last question - setting button to 'Next'")
                self.next_btn.setText("Next")
            print(f"[DEBUG] show_next_question completed successfully\n")
        except Exception as e:
            # Don't crash if showing question fails
            print(f"[DEBUG] ERROR in show_next_question: {e}")
            import traceback
            traceback.print_exc()
            # Don't close the window - just show error and stay on current question
            QMessageBox.warning(self, "Error", 
                               f"An error occurred while loading the question:\n{str(e)}\n\n"
                               "The setup will continue. Please try again.")
            # Reset to a safe state - don't increment index if there was an error
            if self.current_question_index >= len(SETUP_QUESTIONS):
                self.current_question_index = len(SETUP_QUESTIONS) - 1
            print(f"[DEBUG] Error handled, staying on question index: {self.current_question_index}")
    
    def update_chat_display(self):
        """Rebuild chat display from current responses"""
        chat_text = ""
        for i, question in enumerate(SETUP_QUESTIONS):
            if question in self.responses:
                chat_text += f"<b>Q:</b> {question}<br>"
                chat_text += f"<b>A:</b> {self.responses[question]}<br><br>"
        self.chat_display.setHtml(chat_text)
    
    def on_next_clicked(self):
        print(f"\n[DEBUG] ========== on_next_clicked called ==========")
        print(f"[DEBUG] Current question index: {self.current_question_index}")
        question = SETUP_QUESTIONS[self.current_question_index]
        print(f"[DEBUG] Current question: {question[:50]}...")
        is_keyword_question = self.current_question_index in [4, 5]
        print(f"[DEBUG] is_keyword_question: {is_keyword_question}")
        
        if is_keyword_question:
            # For keyword questions, check if at least one keyword exists
            print(f"[DEBUG] Processing keyword question")
            keywords_list = self.keywords.get(question, [])
            print(f"[DEBUG] Keywords for this question: {keywords_list}")
            print(f"[DEBUG] Keywords dict: {self.keywords}")
            
            if not keywords_list:
                print(f"[DEBUG] No keywords found - showing warning")
                QMessageBox.warning(self, "No Keywords", 
                                   "Please add at least one keyword before continuing.")
                return
            
            # Save keywords as comma-separated string for responses
            response_text = ", ".join(keywords_list)
            print(f"[DEBUG] Saving keywords as response: '{response_text}'")
            self.responses[question] = response_text
            print(f"[DEBUG] Response saved. Current responses keys: {list(self.responses.keys())}")
        else:
            # Regular text response
            print(f"[DEBUG] Processing regular text question")
            response = self.input_area.toPlainText().strip()
            print(f"[DEBUG] Text response: '{response[:50]}...'")
            
            if not response:
                print(f"[DEBUG] Empty response - showing warning")
                QMessageBox.warning(self, "Empty Response", 
                                   "Please provide a response before continuing.")
                return
            
            # Save response (this will overwrite if already exists)
            print(f"[DEBUG] Saving text response")
            self.responses[question] = response
        
        # Rebuild chat display with all current responses (includes updated answer)
        print(f"[DEBUG] Updating chat display")
        self.update_chat_display()
        
        # Clear input
        self.input_area.clear()
        self.keyword_input.clear()
        
        # Move to next question
        print(f"[DEBUG] Moving to next question. Old index: {self.current_question_index}")
        print(f"[DEBUG] Total questions: {len(SETUP_QUESTIONS)}")
        print(f"[DEBUG] Will increment to: {self.current_question_index + 1}")
        
        # Check if this is the last question before incrementing
        if self.current_question_index == len(SETUP_QUESTIONS) - 1:
            print(f"[DEBUG] ⚠️ This was the last question (index {self.current_question_index}), should finish setup")
        elif self.current_question_index + 1 == len(SETUP_QUESTIONS):
            print(f"[DEBUG] ⚠️ Next question will be the last one (index {self.current_question_index + 1})")
        else:
            print(f"[DEBUG] ✅ Next question will be index {self.current_question_index + 1}")
        
        self.current_question_index += 1
        print(f"[DEBUG] New index: {self.current_question_index}")
        
        # Safety check: ensure we don't skip any questions
        if self.current_question_index > len(SETUP_QUESTIONS):
            print(f"[DEBUG] ⚠️ ERROR: Index {self.current_question_index} exceeds total questions {len(SETUP_QUESTIONS)}!")
            print(f"[DEBUG] ⚠️ Resetting to last question index: {len(SETUP_QUESTIONS) - 1}")
            self.current_question_index = len(SETUP_QUESTIONS) - 1
        
        print(f"[DEBUG] ========== Calling show_next_question ==========")
        self.show_next_question()
        print(f"[DEBUG] ========== on_next_clicked completed ==========\n")
    
    def on_back_clicked(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.show_next_question()
        else:
            self.parent_window.switch_to_selection_page()
    
    def finish_setup(self):
        """Save responses to .txt file and start LLM classification"""
        print(f"\n[DEBUG] ========== finish_setup called ==========")
        profile_name = getattr(self.parent_window, 'profile_name', 'Profile')
        print(f"[DEBUG] Profile name: {profile_name}")
        
        # Get whitelist and blacklist from keywords dictionary
        # Question 4 = whitelist (index 4), Question 5 = blacklist (index 5)
        whitelist_question = SETUP_QUESTIONS[4] if len(SETUP_QUESTIONS) > 4 else None
        blacklist_question = SETUP_QUESTIONS[5] if len(SETUP_QUESTIONS) > 5 else None
        
        print(f"[DEBUG] Whitelist question: {whitelist_question[:50] if whitelist_question else 'None'}...")
        print(f"[DEBUG] Blacklist question: {blacklist_question[:50] if blacklist_question else 'None'}...")
        print(f"[DEBUG] All keywords dict keys: {list(self.keywords.keys())}")
        
        self.user_whitelist = self.keywords.get(whitelist_question, []) if whitelist_question else []
        self.user_blacklist = self.keywords.get(blacklist_question, []) if blacklist_question else []
        
        print(f"[DEBUG] User whitelist: {self.user_whitelist}")
        print(f"[DEBUG] User blacklist: {self.user_blacklist}")
        print(f"[DEBUG] All responses: {list(self.responses.keys())}")
        
        # Combine all responses into a text format
        print(f"[DEBUG] Combining responses into text format")
        combined_text = f"Profile: {profile_name}\n\n"
        combined_text += "User Profile Setup Responses:\n\n"
        for question, response in self.responses.items():
            combined_text += f"Q: {question}\nA: {response}\n\n"
        
        print(f"[DEBUG] Combined text length: {len(combined_text)} characters")
        
        # Save to .txt file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = OUTPUT_DIR / f"{profile_name}_profile_responses_{timestamp}.txt"
        print(f"[DEBUG] Output file path: {self.output_file}")
        
        try:
            print(f"[DEBUG] Writing responses to file...")
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(combined_text)
            print(f"[DEBUG] File written successfully")
        except Exception as e:
            print(f"[DEBUG] ERROR writing file: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", 
                               f"Error saving responses:\n{str(e)}\n\n"
                               "Please try again.")
            return
        
        # Show progress dialog and start LLM classification
        print(f"[DEBUG] Creating progress dialog")
        self.progress_dialog = QProgressDialog(
            "Analyzing your work preferences...\nThis may take a minute.",
            None,  # No cancel button
            0, 100,
            self
        )
        self.progress_dialog.setWindowTitle("Setting Up Profile")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(5)  # Show some initial progress
        self.progress_dialog.show()
        print(f"[DEBUG] Progress dialog shown")
        
        # Start classification worker
        print(f"[DEBUG] Creating ProcessClassifierWorker")
        print(f"[DEBUG] Responses being passed: {list(self.responses.keys())}")
        self.classifier_worker = ProcessClassifierWorker(self.responses, debug_mode=True)
        print(f"[DEBUG] Connecting signals")
        self.classifier_worker.progress_updated.connect(self._on_classification_progress)
        self.classifier_worker.classification_complete.connect(self._on_classification_complete)
        print(f"[DEBUG] Starting classifier worker thread")
        self.classifier_worker.start()
        print(f"[DEBUG] Classifier worker started")
        print(f"[DEBUG] ========== finish_setup completed (classification in progress) ==========\n")
    
    def _on_classification_progress(self, current_chunk: int, total_chunks: int):
        """Update progress dialog during classification"""
        print(f"[DEBUG] Classification progress: {current_chunk}/{total_chunks}")
        # Map chunk progress to 5-95% range (leaving room for start/end)
        progress = 5 + int((current_chunk / total_chunks) * 90)
        self.progress_dialog.setValue(progress)
        self.progress_dialog.setLabelText(
            f"Analyzing your work preferences...\n"
            f"Processing batch {current_chunk} of {total_chunks}"
        )
    
    def _on_classification_complete(self, result: dict):
        """Handle classification completion and save profile"""
        print(f"\n[DEBUG] ========== _on_classification_complete called ==========")
        print(f"[DEBUG] Classification result: success={result.get('success')}, error={result.get('error')}")
        
        self.progress_dialog.setValue(100)
        self.progress_dialog.close()
        print(f"[DEBUG] Progress dialog closed")
        
        profile_name = getattr(self.parent_window, 'profile_name', 'Profile')
        print(f"[DEBUG] Profile name: {profile_name}")
        
        # Build profile data
        print(f"[DEBUG] Building profile data dictionary")
        profile_data = {
            "name": profile_name,
            "setup_type": "custom",
            "setup_completed": True,
            "created": datetime.now().isoformat(),
            "output_file": str(self.output_file),
            "responses": self.responses,
            "whitelist": self.user_whitelist,
            "blacklist": self.user_blacklist
        }
        print(f"[DEBUG] Profile data keys: {list(profile_data.keys())}")
        print(f"[DEBUG] Whitelist in profile_data: {profile_data['whitelist']}")
        print(f"[DEBUG] Blacklist in profile_data: {profile_data['blacklist']}")
        
        # Add process classifications if successful
        if result.get('success') and result.get('process_classifications'):
            print(f"[DEBUG] Classification successful, adding process classifications")
            process_classifications = result['process_classifications']
            print(f"[DEBUG] Work processes: {len(process_classifications.get('work_processes', []))}")
            print(f"[DEBUG] Mixed processes: {len(process_classifications.get('mixed_processes', []))}")
            print(f"[DEBUG] Entertainment processes: {len(process_classifications.get('entertainment_processes', []))}")
            
            profile_data['process_classifications'] = process_classifications
            
            # Add entertainment processes to blacklist (they're distracting)
            entertainment = process_classifications.get('entertainment_processes', [])
            print(f"[DEBUG] Adding {len(entertainment)} entertainment processes to blacklist")
            added_to_blacklist = 0
            for proc in entertainment:
                if proc not in profile_data['blacklist']:
                    profile_data['blacklist'].append(proc)
                    added_to_blacklist += 1
            print(f"[DEBUG] Added {added_to_blacklist} new processes to blacklist")
            print(f"[DEBUG] Final blacklist count: {len(profile_data['blacklist'])}")
        else:
            # Use default classifications as fallback
            print(f"[DEBUG] Classification failed or missing, using default classifications")
            try:
                from scripts.vlm.process_classifier_llm import get_default_classifications
                default_classifications = get_default_classifications()
                print(f"[DEBUG] Got default classifications: {len(default_classifications.get('work_processes', []))} work, {len(default_classifications.get('mixed_processes', []))} mixed, {len(default_classifications.get('entertainment_processes', []))} entertainment")
                profile_data['process_classifications'] = default_classifications
            except Exception as e:
                print(f"[DEBUG] ERROR getting default classifications: {e}")
                import traceback
                traceback.print_exc()
                profile_data['process_classifications'] = {
                    'work_processes': [],
                    'mixed_processes': [],
                    'entertainment_processes': []
                }
            
            # Show warning but continue
            error_msg = result.get('error', 'Unknown error')
            print(f"[DEBUG] Classification failed: {error_msg}, using defaults")
        
        try:
            print(f"[DEBUG] Saving profile to manager...")
            print(f"[DEBUG] Profile data structure: name={profile_data.get('name')}, whitelist_count={len(profile_data.get('whitelist', []))}, blacklist_count={len(profile_data.get('blacklist', []))}")
            save_profile_to_manager(profile_name, profile_data)
            print(f"[DEBUG] Profile saved successfully")
            
            QMessageBox.information(self, "Setup Complete!", 
                                   f"Profile '{profile_name}' has been created!\n\n"
                                   f"Responses saved to: {self.output_file}\n\n"
                                   "The application will now start.")
            
            print(f"[DEBUG] Calling parent_window.setup_complete()")
            self.parent_window.setup_complete()
            print(f"[DEBUG] ========== _on_classification_complete completed ==========\n")
            
        except Exception as e:
            print(f"[DEBUG] ERROR saving profile: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", 
                               f"Error saving your profile:\n{str(e)}\n\n"
                               "Please try again.")


class SetupWindow(QMainWindow):
    """Main setup window with stacked pages"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locked-In Setup")
        self.setGeometry(200, 200, 700, 600)
        self.profile_name = None
        
        # Stacked widget for pages
        self.stacked_widget = QStackedWidget()
        
        # Create pages
        self.selection_page = SetupModeSelectionPage(self)
        self.name_page = ProfileNamePage(self)
        self.custom_page = CustomSetupPage(self)
        
        # Add pages to stack
        self.stacked_widget.addWidget(self.selection_page)  # Index 0
        self.stacked_widget.addWidget(self.name_page)       # Index 1
        self.stacked_widget.addWidget(self.custom_page)     # Index 2
        
        self.setCentralWidget(self.stacked_widget)
    
    def switch_to_selection_page(self):
        self.stacked_widget.setCurrentWidget(self.selection_page)
    
    def switch_to_custom_page(self):
        self.stacked_widget.setCurrentWidget(self.custom_page)
    
    def switch_to_name_page(self):
        self.stacked_widget.setCurrentWidget(self.name_page)
    
    def setup_complete(self):
        """Signal that setup is complete"""
        self.close()

