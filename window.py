from PyQt6.QtWidgets import QMainWindow, QPushButton
from screenshot_capture import capture_screenshot


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locked-In")
        self.setGeometry(100, 100, 800, 600)
        button = QPushButton("Capture Screenshot", self)
        button.clicked.connect(capture_screenshot)
        self.setCentralWidget(button)