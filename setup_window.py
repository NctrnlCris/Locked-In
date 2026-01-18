"""
Setup window for initial profile configuration
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit, QStackedWidget,
                             QMessageBox, QLineEdit, QFrame, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence
from pathlib import Path
from datetime import datetime
from config import SETUP_QUESTIONS, OUTPUT_DIR, PROFILES_DIR
from profile_manager import save_profile as save_profile_to_manager
from PyQt6.QtWidgets import QLineEdit
import json

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
        if not keyword:
            return
        
        # Get current question to determine if it's whitelist or blacklist
        current_question = SETUP_QUESTIONS[self.current_question_index]
        
        # Initialize keyword list for this question if needed
        if current_question not in self.keywords:
            self.keywords[current_question] = []
        
        # Add keyword if not already present
        if keyword not in self.keywords[current_question]:
            self.keywords[current_question].append(keyword)
            
            # Create and add tag widget
            tag = TagWidget(keyword, self)
            # Insert before stretch
            self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag)
        
        # Clear input
        self.keyword_input.clear()
    
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
    
    def show_next_question(self):
        if self.current_question_index >= len(SETUP_QUESTIONS):
            self.finish_setup()
            return
        
        question = SETUP_QUESTIONS[self.current_question_index]
        self.question_label.setText(f"Question {self.current_question_index + 1}/{len(SETUP_QUESTIONS)}:\n{question}")
        
        # Check if this is a whitelist/blacklist question (indices 4 and 5)
        # Question 4 = whitelist (keyword input), Question 5 = blacklist (keyword input)
        is_keyword_question = self.current_question_index in [4, 5]
        
        if is_keyword_question:
            # Show keyword input, hide text input
            self.input_area.hide()
            self.keyword_input_container.show()
            
            # Load existing keywords for this question
            if question in self.keywords:
                # Clear existing tags
                while self.tags_layout.count() > 1:  # Keep the stretch
                    child = self.tags_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                
                # Recreate tags
                for keyword in self.keywords[question]:
                    tag = TagWidget(keyword, self)
                    self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag)
            else:
                # Clear tags if no keywords
                while self.tags_layout.count() > 1:
                    child = self.tags_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        else:
            # Show text input, hide keyword input
            self.input_area.show()
            self.keyword_input_container.hide()
            
            # Restore text response if exists
            if question in self.responses:
                self.input_area.setPlainText(self.responses[question])
            else:
                self.input_area.clear()
        
        # Update button text
        if self.current_question_index == len(SETUP_QUESTIONS) - 1:
            self.next_btn.setText("Finish & Save")
        else:
            self.next_btn.setText("Next")
    
    def update_chat_display(self):
        """Rebuild chat display from current responses"""
        chat_text = ""
        for i, question in enumerate(SETUP_QUESTIONS):
            if question in self.responses:
                chat_text += f"<b>Q:</b> {question}<br>"
                chat_text += f"<b>A:</b> {self.responses[question]}<br><br>"
        self.chat_display.setHtml(chat_text)
    
    def on_next_clicked(self):
        question = SETUP_QUESTIONS[self.current_question_index]
        is_keyword_question = self.current_question_index in [4, 5]
        
        if is_keyword_question:
            # For keyword questions, check if at least one keyword exists
            keywords_list = self.keywords.get(question, [])
            if not keywords_list:
                QMessageBox.warning(self, "No Keywords", 
                                   "Please add at least one keyword before continuing.")
                return
            # Save keywords as comma-separated string for responses
            self.responses[question] = ", ".join(keywords_list)
        else:
            # Regular text response
            response = self.input_area.toPlainText().strip()
            
            if not response:
                QMessageBox.warning(self, "Empty Response", 
                                   "Please provide a response before continuing.")
                return
            
            # Save response (this will overwrite if already exists)
            self.responses[question] = response
        
        # Rebuild chat display with all current responses (includes updated answer)
        self.update_chat_display()
        
        # Clear input
        self.input_area.clear()
        self.keyword_input.clear()
        
        # Move to next question
        self.current_question_index += 1
        self.show_next_question()
    
    def on_back_clicked(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.show_next_question()
        else:
            self.parent_window.switch_to_selection_page()
    
    def finish_setup(self):
        """Save responses to .txt file and profile"""
        profile_name = getattr(self.parent_window, 'profile_name', 'Profile')
        
        # Get whitelist and blacklist from keywords dictionary
        # Question 4 = whitelist (index 4), Question 5 = blacklist (index 5)
        whitelist_question = SETUP_QUESTIONS[4] if len(SETUP_QUESTIONS) > 4 else None
        blacklist_question = SETUP_QUESTIONS[5] if len(SETUP_QUESTIONS) > 5 else None
        
        whitelist = self.keywords.get(whitelist_question, []) if whitelist_question else []
        blacklist = self.keywords.get(blacklist_question, []) if blacklist_question else []
        
        # Combine all responses into a text format
        combined_text = f"Profile: {profile_name}\n\n"
        combined_text += "User Profile Setup Responses:\n\n"
        for question, response in self.responses.items():
            combined_text += f"Q: {question}\nA: {response}\n\n"
        
        # Save to .txt file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = OUTPUT_DIR / f"{profile_name}_profile_responses_{timestamp}.txt"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(combined_text)
            
            # Save profile using profile manager with extracted whitelist/blacklist
            profile_data = {
                "name": profile_name,
                "setup_type": "custom",
                "setup_completed": True,
                "created": datetime.now().isoformat(),
                "output_file": str(output_file),
                "responses": self.responses,
                "whitelist": whitelist,
                "blacklist": blacklist
            }
            save_profile_to_manager(profile_name, profile_data)
            
            QMessageBox.information(self, "Setup Complete!", 
                                   f"Profile '{profile_name}' has been created!\n\n"
                                   f"Responses saved to: {output_file}\n\n"
                                   "The application will now start.")
            
            # #TO-DO: Model processing would go here
            # #TO-DO: from model_handler import process_profile_with_model
            # #TO-DO: model_response = process_profile_with_model(combined_text)
            # #TO-DO: Save model response to file
            
            self.parent_window.setup_complete()
            
        except Exception as e:
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

