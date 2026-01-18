"""
Penguin popup window that appears when user is being unproductive
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, pyqtProperty, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from pathlib import Path

class PenguinPopup(QWidget):
    """Overlay popup window with penguin mascot requiring 3 clicks to dismiss"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.click_count = 0
        self.clicks_required = 3
        self.media_player = None
        self.video_widget = None
        self.init_ui()
    
    def init_ui(self):
        # Make window always on top, frameless, and semi-transparent
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set size and position (center of screen) - adjusted for all elements
        self.setFixedSize(450, 550)
        self.center_on_screen()
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        # Speech bubble with message at the top
        message_label = QLabel("Focus on your work!")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setMinimumWidth(250)
        message_label.setMaximumWidth(350)
        message_label.setMinimumHeight(50)
        message_label.setStyleSheet("""
            QLabel {
                background-color: white;
                color: #0E6B4F;
                font-size: 18px;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 20px;
                border: 2px solid #0E6B4F;
            }
        """)
        layout.addWidget(message_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Video widget for character animation
        video_path = Path("assets/I_want_you_to_create_an_animation_or_gif_of_this_character_getting_angry_and_and_waving_his_hand_in__seed1382098396.mp4")
        
        if video_path.exists():
            # Create video widget (smaller size to fit all elements)
            self.video_widget = QVideoWidget()
            self.video_widget.setFixedSize(300, 300)
            self.video_widget.setStyleSheet("background-color: transparent; border-radius: 10px;")
            
            # Create media player
            self.media_player = QMediaPlayer()
            self.media_player.setVideoOutput(self.video_widget)
            self.media_player.setSource(QUrl.fromLocalFile(str(video_path.absolute())))
            # Set to loop the video
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
            
            layout.addWidget(self.video_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            # Fallback if video doesn't exist
            fallback_label = QLabel("🐧")
            fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback_label.setStyleSheet("font-size: 80px;")
            layout.addWidget(fallback_label)
        
        # Click counter (at the bottom)
        self.counter_label = QLabel(f"Click me {self.clicks_required} times to dismiss")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("""
            QLabel {
                background-color: #0E6B4F;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 15px;
            }
        """)
        
        # Add counter below video
        layout.addWidget(self.counter_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
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
        """Reset click counter when shown and start video"""
        super().showEvent(event)
        self.click_count = 0
        self.counter_label.setText(f"Click me {self.clicks_required} times to dismiss")
        
        # Start playing the video when popup is shown
        if self.media_player:
            self.media_player.play()
    
    def closeEvent(self, event):
        """Stop video when closing"""
        if self.media_player:
            self.media_player.stop()
        super().closeEvent(event)

