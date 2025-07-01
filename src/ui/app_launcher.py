"""
Application Launcher - Simplified Version
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from typing import Dict


class AppLauncher(QWidget):
    # Signals
    app_launch_requested = Signal(str, str)    # app_path, app_name
    app_close_requested = Signal(str)         # app_id
    app_focus_requested = Signal(str)         # app_id
    layout_change_requested = Signal(str)     # layout_name
    
    def __init__(self, config_manager, process_manager):
        super().__init__()
        
        self.config = config_manager
        self.process_manager = process_manager
        self.running_apps = {}
        
        self.init_ui()
        self.load_applications()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #555;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("App Launcher")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Quick launch
        quick_group = QGroupBox("Quick Launch")
        quick_layout = QVBoxLayout(quick_group)
        
        for name, path in [("Notepad", "notepad.exe"), ("Calculator", "calc.exe")]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, p=path, n=name: 
                              self.app_launch_requested.emit(p, n))
            quick_layout.addWidget(btn)
        
        layout.addWidget(quick_group)
        
        # Running apps
        running_group = QGroupBox("Running Apps")
        running_layout = QVBoxLayout(running_group)
        
        self.running_list = QListWidget()
        running_layout.addWidget(self.running_list)
        
        layout.addWidget(running_group)
        layout.addStretch()
    
    def load_applications(self):
        """Load applications from config"""
        pass
    
    def update_running_apps(self, apps: Dict):
        """Update running apps list"""
        self.running_apps = apps
        self.running_list.clear()
        
        for app_id, app in apps.items():
            item = QListWidgetItem(f"{app.name} (PID: {app.process.pid})")
            self.running_list.addItem(item) 