"""
Main Window - Simplified Version
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QSplitter, QLabel, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from .app_launcher import AppLauncher
from .ai_chat import AiChat
from .app_area import AppArea
from core.window_manager import WindowManager


class MainWindow(QMainWindow):
    def __init__(self, config_manager, virtual_desktop_manager, process_manager):
        super().__init__()
        
        # Store manager references
        self.config = config_manager
        self.virtual_desktop = virtual_desktop_manager
        self.process_manager = process_manager
        self.window_manager = None
        
        # Setup UI
        self.init_ui()
        self.setup_managers()
        self.setup_connections()
        
        # Start periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_managed_apps)
        self.update_timer.start(2000)  # Update every 2 seconds
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("LockIn - Focus Manager")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Make window fullscreen
        self.showMaximized()
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QSplitter::handle {
                background-color: #555;
                width: 2px;
            }
        """)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Add title bar
        self.create_title_bar(main_layout)
        
        # Create three-column layout using splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left sidebar - App Launcher
        self.app_launcher = AppLauncher(self.config, self.process_manager)
        self.app_launcher.setMinimumWidth(300)
        self.app_launcher.setMaximumWidth(400)
        splitter.addWidget(self.app_launcher)
        
        # Center area - Application Area
        self.app_area = AppArea()
        self.app_area.setMinimumWidth(400)
        splitter.addWidget(self.app_area)
        
        # Right sidebar - AI Chat
        self.ai_chat = AiChat(self.config)
        self.ai_chat.setMinimumWidth(300)
        self.ai_chat.setMaximumWidth(400)
        splitter.addWidget(self.ai_chat)
        
        # Set splitter proportions
        splitter.setSizes([300, 800, 300])
        splitter.setChildrenCollapsible(False)
        
        main_layout.addWidget(splitter)
    
    def create_title_bar(self, parent_layout):
        """Create a custom title bar"""
        title_frame = QFrame()
        title_frame.setFixedHeight(30)
        title_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-bottom: 1px solid #555;
            }
        """)
        
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        # Title label
        title_label = QLabel("LockIn - Focus Manager")
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # Close button
        close_button = QLabel("✕")
        close_button.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                padding: 5px 10px;
            }
            QLabel:hover {
                background-color: #ff4444;
            }
        """)
        close_button.mousePressEvent = lambda e: self.close()
        title_layout.addWidget(close_button)
        
        parent_layout.addWidget(title_frame)
    
    def setup_managers(self):
        """Setup and configure managers"""
        # Create window manager
        self.window_manager = WindowManager(self.geometry())
        
        # Setup app area with window manager
        self.app_area.set_window_manager(self.window_manager)
    
    def setup_connections(self):
        """Setup signal-slot connections"""
        # Connect app launcher signals
        if self.app_launcher:
            self.app_launcher.app_launch_requested.connect(self.launch_application)
    
    def launch_application(self, app_path: str, app_name: str = None):
        """Launch an application"""
        if self.process_manager.launch_application(app_path, app_name):
            print(f"Successfully launched: {app_name or app_path}")
            # Update UI after a delay
            QTimer.singleShot(3000, self.update_managed_apps)
        else:
            print(f"Failed to launch: {app_name or app_path}")
    
    def update_managed_apps(self):
        """Update the list of managed applications"""
        managed_apps = self.process_manager.get_managed_apps()
        
        # Update app launcher
        if self.app_launcher:
            self.app_launcher.update_running_apps(managed_apps)
        
        # Update window manager with new windows
        if self.window_manager:
            for app_id, app in managed_apps.items():
                for window_hwnd in app.windows:
                    if window_hwnd not in self.window_manager.managed_windows:
                        self.window_manager.add_window(window_hwnd, app_id, app.name)
        
        # Update app area
        if self.app_area:
            window_list = self.window_manager.get_window_list() if self.window_manager else []
            self.app_area.update_window_list(window_list)
    
    def closeEvent(self, event):
        """Handle window close event"""
        print("Closing LockIn...")
        event.accept() 