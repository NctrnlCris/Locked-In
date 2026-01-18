"""
Setup window for initial profile configuration
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QTextEdit, QStackedWidget,
                             QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from config import SETUP_QUESTIONS, MODEL_INPUT_DIR, MODEL_OUTPUT_DIR
from profile_manager import save_profile
from pathlib import Path
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
        # Placeholder - will be linked later
        QMessageBox.information(self, "Pre-default", 
                               "Pre-default setup will be available soon!")
    
    def on_custom_clicked(self):
        self.parent_window.switch_to_custom_page()


class CustomSetupPage(QWidget):
    """Page for custom profile setup with chat interface"""
    def __init__(self, parent_window):
        super().__init__()
        self.parent_window = parent_window
        self.current_question_index = 0
        self.responses = {}
        self.model_thread = None
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
        from config import SETUP_QUESTIONS
        
        if self.current_question_index >= len(SETUP_QUESTIONS):
            self.finish_setup()
            return
        
        question = SETUP_QUESTIONS[self.current_question_index]
        self.question_label.setText(f"Question {self.current_question_index + 1}/{len(SETUP_QUESTIONS)}:\n{question}")
        
        # Update button text
        if self.current_question_index == len(SETUP_QUESTIONS) - 1:
            self.next_btn.setText("Finish & Process")
        else:
            self.next_btn.setText("Next")
    
    def on_next_clicked(self):
        response = self.input_area.toPlainText().strip()
        
        if not response:
            QMessageBox.warning(self, "Empty Response", 
                               "Please provide a response before continuing.")
            return
        
        # Save response
        from config import SETUP_QUESTIONS
        question = SETUP_QUESTIONS[self.current_question_index]
        self.responses[question] = response
        
        # Add to chat display
        self.chat_display.append(f"<b>Q:</b> {question}")
        self.chat_display.append(f"<b>A:</b> {response}\n")
        
        # Clear input
        self.input_area.clear()
        
        # Move to next question
        self.current_question_index += 1
        self.show_next_question()
    
    def on_back_clicked(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            from config import SETUP_QUESTIONS
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
        """Save responses to file and process with model"""
        # Combine all responses into a text format
        combined_text = "User Profile Setup Responses:\n\n"
        for question, response in self.responses.items():
            combined_text += f"Q: {question}\nA: {response}\n\n"
        
        # Show processing message
        QMessageBox.information(self, "Processing", 
                               "Your responses are being processed. "
                               "This may take a moment...")
        
        # Disable next button during processing
        self.next_btn.setEnabled(False)
        self.next_btn.setText("Processing...")
        
    #TODO: Process with model
    
    def on_model_finished(self, model_response):
        """Handle successful model processing"""
        # Save profile
        profile_data = {
            "setup_type": "custom",
            "responses": self.responses,
            "model_input": self.get_input_text(),
            "model_output": model_response
        }
        save_profile(profile_data)
        
        QMessageBox.information(self, "Setup Complete!", 
                               "Your profile has been created successfully!\n\n"
                               "The application will now start.")
        self.parent_window.setup_complete()
    
    def get_input_text(self):
        """Get the combined input text"""
        combined_text = "User Profile Setup Responses:\n\n"
        for question, response in self.responses.items():
            combined_text += f"Q: {question}\nA: {response}\n\n"
        return combined_text


class SetupWindow(QMainWindow):
    """Main setup window with stacked pages"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locked-In Setup")
        self.setGeometry(200, 200, 700, 600)
        
        # Stacked widget for pages
        self.stacked_widget = QStackedWidget()
        
        # Create pages
        self.selection_page = SetupModeSelectionPage(self)
        self.custom_page = CustomSetupPage(self)
        
        # Add pages to stack
        self.stacked_widget.addWidget(self.selection_page)
        self.stacked_widget.addWidget(self.custom_page)
        
        self.setCentralWidget(self.stacked_widget)
    
    def switch_to_selection_page(self):
        self.stacked_widget.setCurrentWidget(self.selection_page)
    
    def switch_to_custom_page(self):
        self.stacked_widget.setCurrentWidget(self.custom_page)
    
    def setup_complete(self):
        """Signal that setup is complete - will be connected to main app"""
        self.close()
        # The profile is saved, main.py will check and proceed

