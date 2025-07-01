"""
Header Window for LockIn
Spans the top of the screen and provides main controls
"""

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, 
                               QLabel, QMessageBox, QFrame)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPalette, QColor
import time


class HeaderWindow(QWidget):
    # Signal emitted when user confirms closing the application
    close_requested = Signal()
    
    def __init__(self, config, virtual_desktop, process_manager):
        super().__init__()
        self.config = config
        self.virtual_desktop = virtual_desktop
        self.process_manager = process_manager
        self.showing_confirmation = False  # Flag to prevent multiple dialogs
        self.allow_close = False  # Flag to allow closing during shutdown
        
        self.setup_window()
        self.setup_ui()
        self.setup_timer()
        
    def setup_window(self):
        """Configure window properties"""
        self.setWindowTitle("LockIn - Control Header")
        
        # Make window span the top of the screen
        screen_geometry = self.screen().geometry()
        header_height = 50
        self.setGeometry(0, 0, screen_geometry.width(), header_height)
        
        # Window flags to make it stay behind other windows but visible
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |  # Behind other windows
            Qt.WindowType.Tool  # Don't show in taskbar
        )
        
        # Make it semi-transparent and dark
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 200);
                color: white;
                border: none;
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 180);
                border: 1px solid rgba(100, 100, 100, 100);
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 200);
                border: 1px solid rgba(120, 120, 120, 150);
            }
            QPushButton:pressed {
                background-color: rgba(50, 50, 50, 220);
            }
            QPushButton#closeButton {
                background-color: rgba(180, 60, 60, 180);
            }
            QPushButton#closeButton:hover {
                background-color: rgba(200, 80, 80, 200);
            }
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QFrame#separator {
                background-color: rgba(100, 100, 100, 100);
                max-width: 1px;
                min-width: 1px;
            }
        """)
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)
        
        # LockIn title/logo
        title_label = QLabel("🔒 LockIn")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Status information
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.status_label)
        
        # Add separator
        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(separator)
        
        # Virtual desktop info
        self.desktop_info_label = QLabel("Desktop: --")
        self.desktop_info_label.setFont(QFont("Arial", 10))
        layout.addWidget(self.desktop_info_label)
        
        # Add stretch to push buttons to the right
        layout.addStretch()
        
        # Minimize all button
        minimize_all_btn = QPushButton("📉 Minimize All")
        minimize_all_btn.setToolTip("Minimize all managed applications")
        minimize_all_btn.clicked.connect(self.minimize_all_apps)
        layout.addWidget(minimize_all_btn)
        
        # Restore all button
        restore_all_btn = QPushButton("📈 Restore All")
        restore_all_btn.setToolTip("Restore all managed applications")
        restore_all_btn.clicked.connect(self.restore_all_apps)
        layout.addWidget(restore_all_btn)
        
        # Add separator
        separator2 = QFrame()
        separator2.setObjectName("separator")
        separator2.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(separator2)
        
        # Time display
        self.time_label = QLabel("")
        self.time_label.setFont(QFont("Arial", 11))
        layout.addWidget(self.time_label)
        
        # Close button
        close_btn = QPushButton("✖ Close LockIn")
        close_btn.setObjectName("closeButton")
        close_btn.setToolTip("Close LockIn and return to original desktop")
        close_btn.clicked.connect(self.show_close_confirmation)
        layout.addWidget(close_btn)
        
    def setup_timer(self):
        """Setup timer for updating status information"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
    def update_status(self):
        """Update status information"""
        try:
            # Update time
            current_time = time.strftime("%H:%M:%S")
            self.time_label.setText(f"⏰ {current_time}")
            
            # Update status
            managed_apps = self.process_manager.get_managed_apps()
            app_count = len(managed_apps)
            self.status_label.setText(f"📱 {app_count} apps running")
            
            # Update desktop info
            if self.virtual_desktop.is_virtual_desktop_active():
                desktop_info = self.virtual_desktop.get_desktop_info()
                if desktop_info.get("is_real_virtual_desktop"):
                    current_desk = desktop_info.get("current_desktop_number", "?")
                    total_desks = desktop_info.get("total_desktop_count", "?")
                    self.desktop_info_label.setText(f"🖥️ Desktop {current_desk} of {total_desks}")
                else:
                    self.desktop_info_label.setText("🖥️ Kiosk Mode")
            else:
                self.desktop_info_label.setText("🖥️ Standard Desktop")
                
        except Exception as e:
            print(f"Error updating header status: {e}")
    
    def minimize_all_apps(self):
        """Minimize all managed applications"""
        try:
            managed_apps = self.process_manager.get_managed_apps()
            for app_id in managed_apps:
                self.process_manager.minimize_application(app_id)
        except Exception as e:
            print(f"Error minimizing applications: {e}")
    
    def restore_all_apps(self):
        """Restore all managed applications"""
        try:
            managed_apps = self.process_manager.get_managed_apps()
            for app_id in managed_apps:
                self.process_manager.restore_application(app_id)
        except Exception as e:
            print(f"Error restoring applications: {e}")
    
    def show_close_confirmation(self):
        """Show confirmation dialog before closing LockIn"""
        # Prevent multiple confirmation dialogs
        if self.showing_confirmation:
            return
            
        self.showing_confirmation = True
        
        try:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Close LockIn?")
            msg_box.setText("Are you sure you want to close LockIn?")
            msg_box.setInformativeText(
                "This will:\n"
                "• Close all running applications\n"
                "• Remove the virtual desktop\n"
                "• Return to your original desktop"
            )
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            # Style the message box
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #2d2d2d;
                    color: white;
                }
                QMessageBox QPushButton {
                    background-color: #4d4d4d;
                    border: 1px solid #666;
                    border-radius: 3px;
                    padding: 5px 15px;
                    color: white;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #5d5d5d;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #3d3d3d;
                }
            """)
            
            result = msg_box.exec()
            
            if result == QMessageBox.StandardButton.Yes:
                self.close_requested.emit()
            else:
                print("User cancelled shutdown")
                
        finally:
            self.showing_confirmation = False
    
    def allow_closing(self):
        """Allow the window to be closed (called during shutdown)"""
        self.allow_close = True
    
    def closeEvent(self, event):
        """Override close event to prevent accidental closing"""
        # Allow closing during shutdown
        if self.allow_close:
            event.accept()
            return
            
        # Only show confirmation if not already showing
        if not self.showing_confirmation:
            self.show_close_confirmation()
        
        # Always ignore the event since we handle closing through the signal
        event.ignore()