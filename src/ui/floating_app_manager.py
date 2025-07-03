"""
Floating App Manager Window for LockIn
Manages applications in a floating, always-on-top window
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QScrollArea, QFrame, QListWidget, 
                               QListWidgetItem, QComboBox, QMessageBox, QInputDialog,
                               QTextEdit, QDialog, QDialogButtonBox, QFormLayout,
                               QGridLayout)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QCursor
import os
import time
import win32gui
from typing import List
from utils.system_app_scanner import SystemAppScanner
from .app_search_widget import AppSearchWidget


class AppButton(QPushButton):
    """Custom uniform button for app display in grid"""
    def __init__(self, app_name, status_text, app_data, manager, parent=None):
        super().__init__(parent)
        self.app_data = app_data
        self.app_name = app_name
        self.status_text = status_text
        self.manager = manager  # Store reference to FloatingAppManager
        
        # Set uniform size for all buttons
        self.setFixedSize(140, 70)  # Fixed size for consistency
        
        # Set button content
        self.setText(f"📱 {app_name}\n{status_text}")
        
        # Apply styling
        self.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: 10px;
                text-align: center;
                white-space: normal;
                word-wrap: break-word;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
                border: 1px solid #444;
            }
        """)
        
        # Connect click event
        self.clicked.connect(self.on_clicked)
        
    def on_clicked(self):
        """Handle button click - focus the app"""
        self.manager.focus_app_by_data(self.app_data)


class PresetSaveDialog(QDialog):
    def __init__(self, parent=None, existing_presets=None):
        super().__init__(parent)
        self.existing_presets = existing_presets or []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Save Preset")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QFormLayout(self)
        
        # Preset name
        self.name_input = QComboBox()
        self.name_input.setEditable(True)
        self.name_input.addItems(self.existing_presets)
        layout.addRow("Preset Name:", self.name_input)
        
        # Description
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(60)
        layout.addRow("Description:", self.description_input)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def get_preset_data(self):
        return {
            "name": self.name_input.currentText().strip(),
            "description": self.description_input.toPlainText().strip()
        }


class FloatingAppManager(QWidget):
    def __init__(self, config, virtual_desktop, process_manager):
        super().__init__()
        self.config = config
        self.virtual_desktop = virtual_desktop
        self.process_manager = process_manager
        
        # Initialize system app scanner
        self.system_scanner = SystemAppScanner(config.config_dir)
        
        self.is_minimized = False
        self.normal_height = 550  # Reduced height since we removed control buttons
        self.allow_close = False  # Flag to allow closing during shutdown
        self.saved_size = None  # Store window size before minimizing
        
        # Initialize app data storage for grid layout
        self.last_apps_data = []
        self.last_item_count = 0
        
        self.setup_window()
        self.setup_ui()
        self.setup_timer()
        
    def setup_window(self):
        """Configure window properties"""
        self.setWindowTitle("LockIn - App Manager")
        
        # Set initial size and position (left side of screen)
        screen_geometry = self.screen().geometry()
        width = 350
        height = self.normal_height
        x = 20  # 20px from left edge
        y = 80  # Below header window
        
        self.setGeometry(x, y, width, height)
        
        # Make window resizable with reasonable bounds
        self.setMinimumSize(250, 300)  # Minimum usable size
        self.setMaximumSize(600, screen_geometry.height() - 100)  # Don't exceed screen height
        
        # Window flags to make it always on top and prevent closing
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Don't show in taskbar
            Qt.WindowType.FramelessWindowHint  # Custom title bar
        )
        
        # Custom styling
        self.setStyleSheet("""
                        QWidget {
                background-color: #2d2d2d;
                color: white;
                border: none;
            }
            
            QWidget#titleBar {
                background-color: #3d3d3d;
                border-bottom: 1px solid #555;
                min-height: 30px;
                max-height: 30px;
            }
            
 
            
            QPushButton {
                background-color: #4d4d4d;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 5px 10px;
                color: white;
                font-size: 11px;
            }
            
            QPushButton:hover {
                background-color: #5d5d5d;
                border: 1px solid #777;
            }
            
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
            

            
            QPushButton#savePresetButton {
                background-color: #3d5d3d;
            }
            
            QPushButton#savePresetButton:hover {
                background-color: #4d7d4d;
            }
            
            QPushButton#deletePresetButton {
                background-color: #5d3d3d;
            }
            
            QPushButton#deletePresetButton:hover {
                background-color: #7d4d4d;
            }
            
            QComboBox {
                background-color: #4d4d4d;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 3px 8px;
                color: white;
                min-height: 20px;
            }
            
            QComboBox::drop-down {
                border: none;
            }
            
            QComboBox::down-arrow {
                border: none;
                width: 12px;
                height: 12px;
            }
            
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                color: white;
                spacing: 0px;
            }
            
            QListWidget::item {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
                margin: 0px;
                min-height: 50px;
                text-align: center;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            
            QListWidget::item:selected {
                background-color: #5d5d5d;
                border: 1px solid #777;
            }
            
            QListWidget::item:hover {
                background-color: #4d4d4d;
                border: 1px solid #666;
            }
            
            QScrollArea {
                border: none;
                background-color: #2d2d2d;
            }
            
            QWidget#appsContainer {
                background-color: #2d2d2d;
            }
        """)
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Custom title bar for consistent design
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)
        
        # Main content area
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # Preset management section
        preset_frame = QFrame()
        preset_frame.setStyleSheet("QFrame { border: 1px solid #555; border-radius: 5px; padding: 5px; }")
        preset_layout = QVBoxLayout(preset_frame)
        
        preset_label = QLabel("📋 Task Presets")
        preset_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        preset_layout.addWidget(preset_label)
        
        # Preset selection dropdown
        self.preset_dropdown = QComboBox()
        self.populate_preset_dropdown()
        preset_layout.addWidget(self.preset_dropdown)
        
        # Preset control buttons
        preset_buttons_layout = QHBoxLayout()
        
        load_preset_btn = QPushButton("🚀 Load")
        load_preset_btn.clicked.connect(self.load_selected_preset)
        preset_buttons_layout.addWidget(load_preset_btn)
        
        save_preset_btn = QPushButton("💾 Save")
        save_preset_btn.setObjectName("savePresetButton")
        save_preset_btn.clicked.connect(self.save_current_as_preset)
        preset_buttons_layout.addWidget(save_preset_btn)
        
        delete_preset_btn = QPushButton("🗑️")
        delete_preset_btn.setObjectName("deletePresetButton")
        delete_preset_btn.clicked.connect(self.delete_selected_preset)
        delete_preset_btn.setMaximumWidth(35)
        delete_preset_btn.setToolTip("Delete selected preset")
        preset_buttons_layout.addWidget(delete_preset_btn)
        
        preset_layout.addLayout(preset_buttons_layout)
        content_layout.addWidget(preset_frame)
        
        # Quick launch section with searchable interface  
        quick_launch_frame = QFrame()
        quick_launch_frame.setStyleSheet("QFrame { border: 1px solid #555; border-radius: 5px; padding: 8px; }")
        quick_layout = QVBoxLayout(quick_launch_frame)
        quick_layout.setContentsMargins(5, 5, 5, 5)
        
        # App search widget - minimal design
        self.app_search_widget = AppSearchWidget(self.config, self.system_scanner)
        self.app_search_widget.app_launch_requested.connect(self.launch_app_from_search)
        quick_layout.addWidget(self.app_search_widget)
        
        content_layout.addWidget(quick_launch_frame)
        
        # Running apps section
        running_label = QLabel("📱 Running Applications")
        running_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        content_layout.addWidget(running_label)
        
        # Running apps container with clean grid layout
        self.apps_scroll = QScrollArea()
        self.apps_scroll.setWidgetResizable(True)
        self.apps_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.apps_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.apps_scroll.setMinimumHeight(150)
        
        # Container widget for the grid
        self.apps_container = QWidget()
        self.apps_container.setObjectName("appsContainer")
        self.apps_grid_layout = QGridLayout(self.apps_container)
        self.apps_grid_layout.setSpacing(5)  # 5px spacing between items
        self.apps_grid_layout.setContentsMargins(5, 5, 5, 5)
        
        # Set the container as the scroll area's widget
        self.apps_scroll.setWidget(self.apps_container)
        
        # Add scroll area to main layout
        content_layout.addWidget(self.apps_scroll, 1)  # Give it stretch factor of 1 to expand
        
        layout.addWidget(self.content_widget)
        
        # Add resize grip for bottom-right corner
        self.resize_grip = QWidget()
        self.resize_grip.setFixedSize(15, 15)
        self.resize_grip.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 transparent, stop:0.5 #666, stop:1 #999);
                border: none;
            }
        """)
        self.resize_grip.setCursor(Qt.CursorShape.SizeFDiagCursor)
        
        # Position resize grip at bottom-right
        self.resize_grip.setParent(self)
        self.resize_grip.show()
        
        # Install event filters for resize functionality
        self.resize_grip.mousePressEvent = self.start_resize
        self.resize_grip.mouseMoveEvent = self.perform_resize
        
    def create_title_bar(self):
        """Create custom title bar with consistent design"""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(30)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        
        # Title label
        title_label = QLabel("📱 App Manager")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 12px;
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Minimize button - consistent with app design
        minimize_btn = QPushButton("─")
        minimize_btn.setObjectName("minimizeButton")
        minimize_btn.clicked.connect(self.toggle_minimize)
        minimize_btn.setToolTip("Minimize (Ctrl+T)")
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                border: 1px solid #666;
                border-radius: 12px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                max-width: 25px;
                min-width: 25px;
                max-height: 25px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
                border: 1px solid #777;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        layout.addWidget(minimize_btn)
        
        # Enable dragging by title bar
        title_bar.mousePressEvent = self.start_drag
        title_bar.mouseMoveEvent = self.perform_drag
        
        return title_bar
        
    def start_drag(self, event):
        """Start window dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint()
            
    def perform_drag(self, event):
        """Perform window dragging"""
        if hasattr(self, 'drag_start_position'):
            delta = event.globalPosition().toPoint() - self.drag_start_position
            self.move(self.pos() + delta)
            self.drag_start_position = event.globalPosition().toPoint()
    
    def resizeEvent(self, event):
        """Handle resize events to maintain resizable functionality"""
        super().resizeEvent(event)
        # Position resize grip at bottom-right corner
        if hasattr(self, 'resize_grip'):
            self.resize_grip.move(self.width() - 15, self.height() - 15)
            
        # Update grid layout when window is resized
        if hasattr(self, 'apps_grid_layout'):
            # Delay the grid update to allow widget to properly resize
            QTimer.singleShot(50, self.update_apps_grid_layout)
    
    def update_apps_grid_layout(self):
        """Update the grid layout after window resize"""
        # This will be called after resize to recalculate the grid
        # We'll refresh the grid with the current apps
        if hasattr(self, 'last_apps_data'):
            self.populate_apps_grid(self.last_apps_data)
    
    def populate_apps_grid(self, apps_data):
        """Populate the grid with uniform app buttons"""
        # Store the data for resize events
        self.last_apps_data = apps_data
        
        # Clear existing buttons first
        self.clear_apps_grid()
        
        if not apps_data:
            # Show "No apps running" message
            no_apps_label = QLabel("No applications running")
            no_apps_label.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
            no_apps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.apps_grid_layout.addWidget(no_apps_label, 0, 0)
            return
        
        # Calculate optimal number of columns based on scroll area width
        scroll_width = self.apps_scroll.width()
        button_width = 140  # Fixed button width
        spacing = 5  # Grid spacing
        margin = 10  # Container margins
        
        # Account for potential scrollbar
        available_width = scroll_width - margin - 20  # 20px for potential scrollbar
        
        # Calculate how many columns can fit
        columns = max(1, (available_width + spacing) // (button_width + spacing))
        columns = min(columns, 4)  # Maximum 4 columns for usability
        
        print(f"Grid layout: {columns} columns, available width: {available_width}px")
        
        # Create buttons in grid
        for i, app_info in enumerate(apps_data):
            row = i // columns
            col = i % columns
            
            # Truncate long names for better display
            display_name = app_info['name']
            if len(display_name) > 20:
                display_name = display_name[:17] + "..."
            
            # Truncate status for better display
            status = app_info['status']
            if len(status) > 25:
                status = status[:22] + "..."
            
            button = AppButton(
                app_name=display_name,
                status_text=status,
                app_data=app_info['data'],
                manager=self, # Pass the manager instance
                parent=self.apps_container
            )
            
            self.apps_grid_layout.addWidget(button, row, col)
        
        # Add stretch to push buttons to top-left
        self.apps_grid_layout.setRowStretch(len(apps_data) // columns + 1, 1)
        
        # Update item count for tracking
        self.last_item_count = len(apps_data)
    
    def focus_app_by_data(self, app_data):
        """Focus application by data (unified method for both managed apps and windows)"""
        if app_data.startswith("window_"):
            # This is a virtual desktop window, not a managed app
            window_hwnd = int(app_data.replace("window_", ""))
            success = self.process_manager.focus_window_by_handle(window_hwnd)
            print(f"Focusing window {window_hwnd}: {'✅ Success' if success else '❌ Failed'}")
        else:
            # This is a managed application
            app_id = app_data
            success = self.process_manager.focus_application(app_id)
            print(f"Focusing app {app_id}: {'✅ Success' if success else '❌ Failed'}")
            
    def focus_clicked_app(self, item):
        """Legacy method for compatibility - redirect to new method"""
        data = item.data(Qt.ItemDataRole.UserRole)
        self.focus_app_by_data(data)
        
    def allow_closing(self):
        """Allow the window to be closed (called during shutdown)"""
        self.allow_close = True
        
    def closeEvent(self, event):
        """Override close event to prevent closing unless shutdown is in progress"""
        if self.allow_close:
            # Allow closing during shutdown
            event.accept()
        else:
            # Prevent user from closing manually - just minimize instead
            event.ignore()
            if not self.is_minimized:
                self.toggle_minimize()
            print("ℹ️ App Manager minimized instead of closed (use Ctrl+T to toggle)")
    
    def start_resize(self, event):
        """Start window resizing from grip"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.resize_start_pos = event.globalPosition().toPoint()
            self.resize_start_size = self.size()
            
    def perform_resize(self, event):
        """Perform window resizing"""
        if hasattr(self, 'resize_start_pos') and hasattr(self, 'resize_start_size'):
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            new_width = max(self.minimumWidth(), self.resize_start_size.width() + delta.x())
            new_height = max(self.minimumHeight(), self.resize_start_size.height() + delta.y())
            self.resize(new_width, new_height)
        

    def toggle_minimize(self):
        """Toggle minimize state - keep visual presence when minimized"""
        if self.is_minimized:
            # Restore window
            # First remove height constraints
            self.setMinimumHeight(300)
            self.setMaximumHeight(self.screen().geometry().height() - 100)
            
            if self.saved_size:
                self.resize(self.saved_size)
            else:
                # Fallback to normal height if no saved size
                self.resize(self.width(), self.normal_height)
            self.content_widget.show()
            self.is_minimized = False
            
            # Focus search input when restoring (with delay to ensure window is ready)
            if hasattr(self, 'app_search_widget') and self.app_search_widget:
                QTimer.singleShot(100, self._focus_search_input)
        else:
            # Save current size BEFORE any modifications
            self.saved_size = self.size()
            print(f"App Manager: Saving size {self.saved_size.width()}x{self.saved_size.height()}")
            
            # Hide content and set fixed height for title bar only
            self.content_widget.hide()
            self.setFixedHeight(30)  # Just title bar height
            self.is_minimized = True
            
    def toggle_minimize_with_focus(self):
        """Toggle minimize state and focus search input when restoring"""
        if self.is_minimized:
            # Restore and focus search input
            self.toggle_minimize()
            # Extra delay for keyboard shortcut triggered focus
            if hasattr(self, 'app_search_widget') and self.app_search_widget:
                QTimer.singleShot(200, self._focus_search_input)
        else:
            # Just minimize
            self.toggle_minimize()
    
    def _focus_search_input(self):
        """Aggressively focus the search input"""
        if hasattr(self, 'app_search_widget') and self.app_search_widget:
            # Make sure window is active first
            self.activateWindow()
            self.raise_()
            # Then focus the input
            self.app_search_widget.search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            # Force the widget to be focused
            self.app_search_widget.search_input.activateWindow()
            print("Focused search input")
            
    def setup_timer(self):
        """Setup timer for updating app list"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_apps_list)
        self.update_timer.start(2000)  # Update every 2 seconds
        
    def launch_app_from_search(self, app_path: str, app_name: str, args: list):
        """Launch application from search widget"""
        try:
            if self.process_manager.launch_application(app_path, app_name, args):
                print(f"Successfully launched: {app_name}")
            else:
                QMessageBox.warning(self, "Launch Failed", f"Failed to launch {app_name}")
        except Exception as e:
            print(f"Error launching application: {e}")
            QMessageBox.critical(self, "Error", f"Error launching application: {e}")
        

            
    def update_apps_list(self):
        """Update the running applications list with clean grid layout"""
        try:
            # Clear existing buttons
            self.clear_apps_grid()
            
            apps_data = []
            
            # Track which windows are already handled by managed apps
            handled_windows = set()
            
            # First, add managed applications that have valid, focusable windows
            managed_apps = self.process_manager.get_managed_apps()
            
            for app_id, app in managed_apps.items():
                try:
                    # Check if the managed app has a valid, focusable window
                    has_valid_window = False
                    
                    # Check main window
                    if app.main_window and win32gui.IsWindow(app.main_window):
                        has_valid_window = True
                        handled_windows.add(app.main_window)
                    
                    # Check other windows
                    for window_hwnd in app.windows:
                        if window_hwnd != app.main_window and win32gui.IsWindow(window_hwnd):
                            has_valid_window = True
                            handled_windows.add(window_hwnd)
                    
                    # Only show managed apps that have valid windows
                    if has_valid_window:
                        # Get app status with consistent formatting
                        status = "Running"
                        try:
                            if hasattr(app, 'process') and app.process.is_running():
                                cpu_percent = app.process.cpu_percent()
                                memory_mb = app.process.memory_info().rss / 1024 / 1024
                                status = f"CPU: {cpu_percent:.1f}%\nRAM: {memory_mb:.0f}MB"
                        except:
                            status = "Managed App"
                        
                        apps_data.append({
                            'name': app.name,
                            'status': status,
                            'data': app_id,
                            'type': 'managed'
                        })
                        
                except Exception as e:
                    print(f"Error processing managed app {app_id}: {e}")
                    continue
            
            # Second, add virtual desktop windows that aren't already handled by managed apps
            if self.virtual_desktop and self.virtual_desktop.real_virtual_desktop:
                all_desktop_windows = self.process_manager._get_all_windows_on_virtual_desktop()
                
                for hwnd in all_desktop_windows:
                    if hwnd not in handled_windows:  # Not already covered by managed apps
                        try:
                            title = win32gui.GetWindowText(hwnd)
                            if title and len(title) > 0:
                                apps_data.append({
                                    'name': title,
                                    'status': "Desktop App",
                                    'data': f"window_{hwnd}",
                                    'type': 'window'
                                })
                        except Exception as e:
                            print(f"Error processing virtual desktop window {hwnd}: {e}")
                            continue
            
            # Create grid layout with uniform buttons
            self.populate_apps_grid(apps_data)
                
        except Exception as e:
            print(f"Error updating apps list: {e}")
    
    def clear_apps_grid(self):
        """Clear all widgets from the apps grid"""
        while self.apps_grid_layout.count():
            item = self.apps_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def populate_preset_dropdown(self):
        """Populate the preset dropdown with available presets"""
        try:
            self.preset_dropdown.clear()
            presets = self.config.get_presets()
            
            if not presets:
                self.preset_dropdown.addItem("No presets available", None)
                return
            
            for preset_name, preset_data in presets.items():
                description = preset_data.get('description', '')
                display_text = f"{preset_name}"
                if description:
                    display_text += f" - {description[:30]}..."
                
                self.preset_dropdown.addItem(display_text, preset_data)
                
        except Exception as e:
            print(f"Error populating preset dropdown: {e}")
            self.preset_dropdown.addItem("Error loading presets", None)

    def launch_isolated_browser(self, browser_name: str, urls: List[str]) -> bool:
        """Launch browser with isolated instance for LockIn management"""
        try:
            if not urls:
                return True
                
            browser_paths = {
                "chrome": [
                    "chrome.exe",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                ],
                "edge": [
                    "msedge.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
                ]
            }
            
            browser_commands = browser_paths.get(browser_name.lower(), [])
            
            for browser_cmd in browser_commands:
                try:
                    import tempfile
                    import uuid
                    
                    # Create unique user data directory for isolation
                    temp_dir = tempfile.gettempdir()
                    user_data_dir = os.path.join(temp_dir, f"lockin_{browser_name.lower()}_{uuid.uuid4().hex[:8]}")
                    
                    if browser_name.lower() == "chrome":
                        # Chrome flags for isolated instance
                        cmd = [
                            browser_cmd,
                            f"--user-data-dir={user_data_dir}",
                            "--new-window",
                            "--no-first-run",
                            "--no-default-browser-check",
                            "--disable-default-apps"
                        ] + urls
                        
                    elif browser_name.lower() == "edge":
                        # Edge flags for isolated instance  
                        cmd = [
                            browser_cmd,
                            f"--user-data-dir={user_data_dir}",
                            "--new-window",
                            "--no-first-run",
                            "--no-default-browser-check"
                        ] + urls
                    else:
                        cmd = [browser_cmd] + urls
                    
                    # Launch through process manager so it gets tracked
                    browser_display_name = f"{browser_name} (LockIn)"
                    
                    # Join command into a single string for process manager
                    cmd_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd)
                    
                    success = self.process_manager.launch_application(
                        cmd[0],  # Main executable
                        browser_display_name,
                        cmd[1:]  # Arguments
                    )
                    
                    if success:
                        print(f"Launched isolated {browser_name} instance with {len(urls)} tabs")
                        return True
                    else:
                        print(f"Failed to launch {browser_name} through process manager")
                        
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Error launching isolated {browser_cmd}: {e}")
                    continue
            
            print(f"Could not find {browser_name} executable")
            return False
            
        except Exception as e:
            print(f"Error launching browser {browser_name}: {e}")
            return False

    def load_selected_preset(self):
        """Load the selected preset"""
        try:
            preset_data = self.preset_dropdown.currentData()
            if not preset_data:
                print("No preset selected")
                return
            
            preset_name = preset_data.get('name', 'Unknown')
            print(f"Loading preset: {preset_name}")
            
            # Launch apps from preset
            apps = preset_data.get('apps', [])
            browser_tabs = preset_data.get('browser_tabs', {})
            
            success_count = 0
            total_apps = len(apps)
            total_browsers = len([b for b, urls in browser_tabs.items() if urls])
            total_count = total_apps + total_browsers
            
            # Launch regular applications first
            for app_info in apps:
                app_name = app_info.get('name', 'Unknown')
                app_path = app_info.get('path', '')
                app_args = app_info.get('args', [])
                
                # Skip browsers as they're handled separately
                if any(browser in app_name.lower() for browser in ['chrome', 'edge', 'msedge', 'firefox']):
                    continue
                
                # Special handling for PowerShell to keep it open
                if 'powershell' in app_name.lower():
                    # Launch PowerShell with -NoExit to keep window open
                    if not app_args:
                        app_args = ['-NoExit']
                    elif '-NoExit' not in app_args:
                        app_args.append('-NoExit')
                
                if self.process_manager.launch_application(app_path, app_name, app_args):
                    success_count += 1
                    print(f"Launched {app_name} from preset")
                    time.sleep(1)  # Longer delay to ensure apps start properly
                else:
                    print(f"Failed to launch {app_name} from preset")
            
            # Launch browsers with isolated instances
            for browser_name, urls in browser_tabs.items():
                if urls:
                    if self.launch_isolated_browser(browser_name, urls):
                        success_count += 1
                        print(f"Launched isolated {browser_name} with {len(urls)} tabs")
                        time.sleep(2)  # Wait for browser to fully start
                    else:
                        print(f"Failed to launch {browser_name}")
            
            # Update last used timestamp
            preset_data['last_used'] = time.time()
            self.config.save_preset(preset_name, preset_data)
            
            # Silent completion - just log results
            if success_count == total_count:
                print(f"✅ Successfully loaded '{preset_name}' preset! {success_count} applications launched.")
            else:
                print(f"⚠️ Loaded '{preset_name}' preset with some issues. {success_count}/{total_count} applications launched successfully.")
                
        except Exception as e:
            print(f"Error loading preset: {e}")
            QMessageBox.critical(self, "Error", f"Error loading preset: {e}")

    def save_current_as_preset(self):
        """Save current running applications as a preset"""
        try:
            managed_apps = self.process_manager.get_managed_apps()
            
            if not managed_apps:
                QMessageBox.information(
                    self,
                    "No Applications",
                    "No applications are currently running to save as a preset."
                )
                return
            
            # Get existing preset names for the dialog
            existing_presets = list(self.config.get_presets().keys())
            
            # Show preset save dialog
            dialog = PresetSaveDialog(self, existing_presets)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                preset_info = dialog.get_preset_data()
                preset_name = preset_info['name']
                description = preset_info['description']
                
                if not preset_name:
                    QMessageBox.warning(self, "Invalid Name", "Please enter a preset name.")
                    return
                
                # Check if overwriting existing preset
                if preset_name in existing_presets:
                    reply = QMessageBox.question(
                        self,
                        "Overwrite Preset",
                        f"Preset '{preset_name}' already exists. Overwrite it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                
                # Convert current apps to preset format
                preset_data = self.config.get_current_apps_as_preset_data(
                    managed_apps, preset_name, description
                )
                
                # Save preset
                if self.config.save_preset(preset_name, preset_data):
                    QMessageBox.information(
                        self,
                        "Preset Saved",
                        f"Successfully saved '{preset_name}' preset with {len(preset_data['apps'])} applications."
                    )
                    
                    # Refresh preset dropdown
                    self.populate_preset_dropdown()
                    
                    # Select the newly saved preset
                    for i in range(self.preset_dropdown.count()):
                        if self.preset_dropdown.itemText(i).startswith(preset_name):
                            self.preset_dropdown.setCurrentIndex(i)
                            break
                else:
                    QMessageBox.critical(self, "Save Failed", f"Failed to save preset '{preset_name}'.")
                    
        except Exception as e:
            print(f"Error saving preset: {e}")
            QMessageBox.critical(self, "Error", f"Error saving preset: {e}")

    def delete_selected_preset(self):
        """Delete the selected preset"""
        try:
            preset_data = self.preset_dropdown.currentData()
            if not preset_data:
                QMessageBox.information(self, "No Preset", "Please select a preset to delete.")
                return
            
            preset_name = preset_data.get('name', 'Unknown')
            
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Delete Preset",
                f"Are you sure you want to delete the '{preset_name}' preset?\nThis action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.config.delete_preset(preset_name):
                    QMessageBox.information(
                        self,
                        "Preset Deleted",
                        f"Successfully deleted '{preset_name}' preset."
                    )
                    
                    # Refresh preset dropdown
                    self.populate_preset_dropdown()
                else:
                    QMessageBox.critical(
                        self,
                        "Delete Failed",
                        f"Failed to delete preset '{preset_name}'."
                    )
                    
        except Exception as e:
            print(f"Error deleting preset: {e}")
            QMessageBox.critical(self, "Error", f"Error deleting preset: {e}")