"""
AI Chat - Simplified Version
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class AiChat(QWidget):
    # Signals
    command_requested = Signal(str)
    
    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555;
                padding: 5px;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 3px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("AI Assistant")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.append("Welcome to LockIn AI Assistant!")
        layout.addWidget(self.chat_display)
        
        # Input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self.send_message)
        layout.addWidget(self.input_field)
        
        # Send button
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        layout.addWidget(send_btn)
    
    def send_message(self):
        """Send a message"""
        message = self.input_field.text().strip()
        if message:
            self.chat_display.append(f"You: {message}")
            self.input_field.clear()
            
            # Simple responses
            if "help" in message.lower():
                response = "I can help you manage applications and layouts!"
            elif "launch" in message.lower():
                response = "Use the App Launcher on the left to launch applications."
            else:
                response = "I understand. Try 'help' for more information."
            
            self.chat_display.append(f"AI: {response}") 