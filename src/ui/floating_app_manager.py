"""
Floating App Manager Window for LockIn
Manages applications in a floating, always-on-top window
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QScrollArea, QFrame, QListWidget, 
                               QListWidgetItem, QComboBox, QMessageBox, QInputDialog,
                               QTextEdit, QDialog, QDialogButtonBox, QFormLayout)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPalette, QColor, QIcon
import os
import time
from typing import List


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
        
        self.is_minimized = False
        self.normal_height = 550  # Reduced height since we removed control buttons
        self.allow_close = False  # Flag to allow closing during shutdown
        
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
        
        # Window flags to make it always on top and prevent closing
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Don't show in taskbar
            Qt.WindowType.FramelessWindowHint
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
            
            QLabel#titleLabel {
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding-left: 10px;
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
            
            QPushButton#minimizeButton {
                background-color: #5d5d3d;
                max-width: 25px;
                min-width: 25px;
                max-height: 25px;
                min-height: 25px;
                border-radius: 12px;
            }
            
            QPushButton#minimizeButton:hover {
                background-color: #7d7d5d;
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
            }
            
            QListWidget::item {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 8px;
                margin: 2px;
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
        """)
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
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
        
        # Quick launch section
        quick_launch_frame = QFrame()
        quick_launch_frame.setStyleSheet("QFrame { border: 1px solid #555; border-radius: 5px; padding: 5px; }")
        quick_layout = QVBoxLayout(quick_launch_frame)
        
        quick_label = QLabel("🚀 Quick Launch")
        quick_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        quick_layout.addWidget(quick_label)
        
        # App selection dropdown
        self.app_dropdown = QComboBox()
        self.populate_app_dropdown()
        quick_layout.addWidget(self.app_dropdown)
        
        # Launch button
        launch_btn = QPushButton("▶ Launch Application")
        launch_btn.clicked.connect(self.launch_selected_app)
        quick_layout.addWidget(launch_btn)
        
        content_layout.addWidget(quick_launch_frame)
        
        # Running apps section
        running_label = QLabel("📱 Running Applications")
        running_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        content_layout.addWidget(running_label)
        
        # Running apps list
        self.apps_list = QListWidget()
        self.apps_list.setMaximumHeight(250)  # Increased height since no buttons below
        self.apps_list.itemClicked.connect(self.focus_clicked_app)  # Add click-to-focus
        content_layout.addWidget(self.apps_list)
        
        # Add spacer to fill remaining space
        content_layout.addStretch()
        
        layout.addWidget(self.content_widget)
        
    def create_title_bar(self):
        """Create custom title bar with minimize button"""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(30)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title label
        title_label = QLabel("📱 App Manager")
        title_label.setObjectName("titleLabel")
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Minimize button
        minimize_btn = QPushButton("−")
        minimize_btn.setObjectName("minimizeButton")
        minimize_btn.clicked.connect(self.toggle_minimize)
        minimize_btn.setToolTip("Minimize to title bar")
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
            
    def toggle_minimize(self):
        """Toggle minimize state"""
        if self.is_minimized:
            # Restore
            self.setFixedHeight(self.normal_height)
            self.content_widget.show()
            self.is_minimized = False
        else:
            # Minimize to title bar only
            self.normal_height = self.height()
            self.setFixedHeight(30)  # Title bar height
            self.content_widget.hide()
            self.is_minimized = True
            
    def setup_timer(self):
        """Setup timer for updating app list"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_apps_list)
        self.update_timer.start(2000)  # Update every 2 seconds
        
    def populate_app_dropdown(self):
        """Populate the app dropdown with available applications"""
        try:
            apps_list = self.config.get_applications()  # This returns a list
            self.app_dropdown.clear()
            
            # Handle list format from config
            if isinstance(apps_list, list):
                for app_info in apps_list:
                    app_name = app_info.get('name', 'Unknown')
                    icon = app_info.get('icon', '📱')
                    if not icon:  # If icon is empty string, use default
                        icon = '📱'
                    self.app_dropdown.addItem(f"{icon} {app_name}", app_info)
            else:
                # Handle dictionary format (legacy)
                for app_name, app_info in apps_list.items():
                    icon = app_info.get('icon', '📱')
                    if not icon:
                        icon = '📱'
                    self.app_dropdown.addItem(f"{icon} {app_name}", app_info)
                
        except Exception as e:
            print(f"Error populating app dropdown: {e}")
            # Add fallback items
            self.app_dropdown.addItem("📝 Notepad", {"name": "Notepad", "path": "notepad.exe"})
            self.app_dropdown.addItem("🔢 Calculator", {"name": "Calculator", "path": "calc.exe"})
            
    def launch_selected_app(self):
        """Launch the selected application"""
        try:
            current_data = self.app_dropdown.currentData()
            if current_data:
                app_path = current_data.get('path')
                app_name = current_data.get('name', 'Unknown App')
                
                if self.process_manager.launch_application(app_path, app_name):
                    print(f"Successfully launched: {app_name}")
                else:
                    QMessageBox.warning(self, "Launch Failed", f"Failed to launch {app_name}")
                    
        except Exception as e:
            print(f"Error launching application: {e}")
            QMessageBox.critical(self, "Error", f"Error launching application: {e}")
            
    def update_apps_list(self):
        """Update the running applications list"""
        try:
            self.apps_list.clear()
            managed_apps = self.process_manager.get_managed_apps()
            
            for app_id, app in managed_apps.items():
                try:
                    status = "Running"
                    if hasattr(app, 'process') and app.process.is_running():
                        cpu_percent = app.process.cpu_percent()
                        memory_mb = app.process.memory_info().rss / 1024 / 1024
                        status = f"CPU: {cpu_percent:.1f}% | RAM: {memory_mb:.1f}MB"
                except:
                    status = "Unknown"
                
                item_text = f"📱 {app.name}\n   {status}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, app_id)
                self.apps_list.addItem(item)
                
        except Exception as e:
            print(f"Error updating apps list: {e}")
            
    def focus_clicked_app(self, item):
        """Focus the clicked application"""
        app_id = item.data(Qt.ItemDataRole.UserRole)
        self.process_manager.focus_application(app_id)
        print(f"Focusing app: {app_id}")
            
    def allow_closing(self):
        """Allow the window to be closed (called during shutdown)"""
        self.allow_close = True
        
    def closeEvent(self, event):
        """Override close event to prevent closing unless shutdown is in progress"""
        if self.allow_close:
            # Allow closing during shutdown
            event.accept()
        else:
            # Prevent user from closing manually
            event.ignore()
            QMessageBox.information(
                self, 
                "Cannot Close", 
                "The App Manager cannot be closed while LockIn is running.\nUse the header to close LockIn."
            )

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
                QMessageBox.information(self, "No Preset", "Please select a preset to load.")
                return
            
            preset_name = preset_data.get('name', 'Unknown')
            
            # Confirm loading
            reply = QMessageBox.question(
                self,
                "Load Preset",
                f"Load '{preset_name}' preset?\nThis will launch all applications in the preset.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Show loading feedback
            QMessageBox.information(
                self, 
                "Loading Preset", 
                f"Loading '{preset_name}' preset...\nApplications will launch in sequence."
            )
            
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
            
            # Show completion message
            if success_count == total_count:
                QMessageBox.information(
                    self,
                    "Preset Loaded",
                    f"Successfully loaded '{preset_name}' preset!\n{success_count} applications launched."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Preset Partially Loaded",
                    f"Loaded '{preset_name}' preset with some issues.\n{success_count}/{total_count} applications launched successfully."
                )
                
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