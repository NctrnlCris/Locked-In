"""
Penguin popup window that appears when user is being unproductive
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, pyqtProperty
from PyQt6.QtGui import QPixmap

class PenguinPopup(QWidget):
    """Overlay popup window with penguin mascot requiring 3 clicks to dismiss"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.click_count = 0
        self.clicks_required = 3
        self.init_ui()
    
    def init_ui(self):
        # Make window always on top, frameless, and semi-transparent
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set size and position (center of screen)
        self.setFixedSize(400, 300)
        self.center_on_screen()
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # Penguin image
        penguin_label = QLabel()
        try:
            penguin_pix = QPixmap("assets/penguin.png")
            if penguin_pix.isNull():
                # Fallback if penguin.png doesn't exist
                penguin_label.setText("🐧")
                penguin_label.setStyleSheet("font-size: 80px;")
            else:
                penguin_pix = penguin_pix.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                penguin_label.setPixmap(penguin_pix)
        except:
            penguin_label.setText("🐧")
            penguin_label.setStyleSheet("font-size: 80px;")
        
        penguin_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Message
        message_label = QLabel("Stop procrastinating!\nFocus on your work!")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0E6B4F; padding: 10px;")
        message_label.setWordWrap(True)
        
        # Click counter
        self.counter_label = QLabel(f"Click me {self.clicks_required} times to dismiss")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("font-size: 14px; color: #666; padding: 5px;")
        
        layout.addWidget(penguin_label)
        layout.addWidget(message_label)
        layout.addWidget(self.counter_label)
        
        # Make the entire window clickable
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                border: 3px solid #0E6B4F;
            }
        """)
        
        self.setLayout(layout)
    
    def center_on_screen(self):
        """Center the window on the screen"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen.center())
        self.move(window_geometry.topLeft())
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on the popup"""
        self.click_count += 1
        remaining = self.clicks_required - self.click_count
        
        if self.click_count >= self.clicks_required:
            self.hide()
            self.close()
        else:
            self.counter_label.setText(f"Click me {remaining} more time{'s' if remaining > 1 else ''} to dismiss")
            # Optional: Add a visual feedback animation here
    
    def showEvent(self, event):
        """Reset click counter when shown"""
        super().showEvent(event)
        self.click_count = 0
        self.counter_label.setText(f"Click me {self.clicks_required} times to dismiss")

