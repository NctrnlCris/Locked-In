"""
Setup window for initial profile configuration
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit, QStackedWidget,
                             QMessageBox)
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


class CustomSetupPage(QWidget):
    """Page for custom profile setup with chat interface"""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.current_question_index = 0
        self.responses = {}
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
        
        # Input area
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("Type your response here...")
        self.input_area.setMaximumHeight(100)
        
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
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def show_next_question(self):
        if self.current_question_index >= len(SETUP_QUESTIONS):
            self.finish_setup()
            return
        
        question = SETUP_QUESTIONS[self.current_question_index]
        self.question_label.setText(f"Question {self.current_question_index + 1}/{len(SETUP_QUESTIONS)}:\n{question}")
        
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
        response = self.input_area.toPlainText().strip()
        
        if not response:
            QMessageBox.warning(self, "Empty Response", 
                               "Please provide a response before continuing.")
            return
        
        # Save response (this will overwrite if already exists)
        question = SETUP_QUESTIONS[self.current_question_index]
        self.responses[question] = response
        
        # Rebuild chat display with all current responses (includes updated answer)
        self.update_chat_display()
        
        # Clear input
        self.input_area.clear()
        
        # Move to next question
        self.current_question_index += 1
        self.show_next_question()
    
    def on_back_clicked(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            question = SETUP_QUESTIONS[self.current_question_index]
            # Restore previous response if available
            if question in self.responses:
                self.input_area.setPlainText(self.responses[question])
            else:
                self.input_area.clear()
            self.show_next_question()
        else:
            self.parent_window.switch_to_selection_page()
    
    def finish_setup(self):
        """Save responses to .txt file and profile"""
        profile_name = getattr(self.parent_window, 'profile_name', 'Profile')
        
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
            
            # Save profile using profile manager
            profile_data = {
                "name": profile_name,
                "setup_type": "custom",
                "setup_completed": True,
                "created": datetime.now().isoformat(),
                "output_file": str(output_file),
                "responses": self.responses
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

