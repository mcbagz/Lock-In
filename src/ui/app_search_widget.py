"""
Searchable App Launch Widget
Provides autocomplete search functionality for launching applications
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                               QListWidget, QListWidgetItem, QPushButton, QLabel,
                               QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QFont, QKeyEvent
from typing import List, Optional
import threading

from utils.system_app_scanner import SystemAppScanner, SystemApp


class AppSearchWidget(QWidget):
    # Signals
    app_launch_requested = Signal(str, str, list)  # path, name, args
    
    def __init__(self, config_manager, system_app_scanner: SystemAppScanner):
        super().__init__()
        self.config = config_manager
        self.system_scanner = system_app_scanner
        self.all_apps: List[SystemApp] = []
        self.filtered_apps: List[SystemApp] = []
        self.selected_index = -1
        
        self.setup_ui()
        self.setup_connections()
        self.load_applications()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search input - ONLY this field, nothing else by default
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quick Launch")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #4d4d4d;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 8px;
                color: white;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #777;
                background-color: #5d5d5d;
            }
        """)
        layout.addWidget(self.search_input)
        
        # Results list - now as a non-focus-stealing popup window
        self.results_popup = QWidget()
        self.results_popup.setWindowFlags(
            Qt.WindowType.Tool |  # Changed from Popup to Tool to not steal focus
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus  # Prevent focus stealing
        )
        self.results_popup.setVisible(False)
        self.results_popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)  # Show without activating
        
        popup_layout = QVBoxLayout(self.results_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        
        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(200)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Prevent taking focus
        popup_layout.addWidget(self.results_list)
        self.results_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 1px solid #555;
                border-radius: 3px;
                color: white;
                outline: none;
                margin-top: 2px;
            }
            QListWidget::item {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 2px;
                padding: 6px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #5d5d5d;
                border: 1px solid #777;
            }
            QListWidget::item:hover {
                background-color: #4d4d4d;
                border: 1px solid #666;
            }
        """)
        # Don't add results_list to main layout anymore since it's in popup
        
        # Status label - initially hidden
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999; font-size: 10px; margin-top: 4px;")
        self.status_label.setVisible(False)  # Hidden by default
        layout.addWidget(self.status_label)
        
        # Refresh button - make it smaller and less prominent
        refresh_button = QPushButton("🔄")
        refresh_button.setMaximumSize(25, 25)
        refresh_button.setToolTip("Refresh application list")
        refresh_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555;
                border-radius: 12px;
                color: #999;
                font-size: 10px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border: 1px solid #666;
                color: white;
            }
        """)
        refresh_button.clicked.connect(self.refresh_applications)
        
        # Create a small layout for the refresh button (right-aligned)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(refresh_button)
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """Setup signal connections"""
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.launch_selected_app)
        self.search_input.focusInEvent = self.on_search_focus_in
        self.search_input.focusOutEvent = self.on_search_focus_out
        self.results_list.itemClicked.connect(self.on_item_clicked)
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # Install event filter for keyboard navigation
        self.search_input.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Handle keyboard navigation"""
        if obj == self.search_input and event.type() == event.Type.KeyPress:
            key = event.key()
            
            if key == Qt.Key.Key_Down:
                if self.results_popup.isVisible():
                    self.move_selection(1)
                    return True
            elif key == Qt.Key.Key_Up:
                if self.results_popup.isVisible():
                    self.move_selection(-1)
                    return True
            elif key == Qt.Key.Key_Enter or key == Qt.Key.Key_Return:
                if self.results_popup.isVisible() and self.filtered_apps:
                    self.launch_selected_app()
                    return True
            elif key == Qt.Key.Key_Escape:
                if self.results_popup.isVisible():
                    self.hide_results_popup()
                    return True
                else:
                    self.search_input.clear()
                    return True
        
        return super().eventFilter(obj, event)
    
    def move_selection(self, direction: int):
        """Move selection up or down in results list"""
        if not self.filtered_apps:
            return
        
        new_index = self.selected_index + direction
        max_index = len(self.filtered_apps) - 1
        
        if new_index < 0:
            new_index = max_index
        elif new_index > max_index:
            new_index = 0
        
        self.selected_index = new_index
        self.results_list.setCurrentRow(new_index)
    
    def load_applications(self):
        """Load applications in background thread"""
        def load_apps():
            try:
                self.all_apps = self.system_scanner.get_installed_apps()
                print(f"Loaded {len(self.all_apps)} applications for search")
                
                # Don't show any results initially - clean interface
                self.filtered_apps = []
                
            except Exception as e:
                print(f"Error loading applications: {e}")
        
        # Run in background thread
        thread = threading.Thread(target=load_apps, daemon=True)
        thread.start()
    
    def refresh_applications(self):
        """Refresh application cache"""
        print("Refreshing application cache...")
        
        def refresh_apps():
            try:
                self.all_apps = self.system_scanner.get_installed_apps(force_refresh=True)
                print(f"Refreshed {len(self.all_apps)} applications")
                
                # Update current search results if there's text
                current_text = self.search_input.text().strip()
                if current_text:
                    self.on_search_changed(current_text)
                
            except Exception as e:
                print(f"Error refreshing applications: {e}")
        
        # Run in background thread
        thread = threading.Thread(target=refresh_apps, daemon=True)
        thread.start()
    
    def on_search_focus_in(self, event):
        """Handle search field gaining focus"""
        # Show results and status if there's text
        text = self.search_input.text().strip()
        if text:
            self.show_results_popup()
            self.status_label.setVisible(True)
        
        # Call original focus in event
        QLineEdit.focusInEvent(self.search_input, event)
    
    def on_search_focus_out(self, event):
        """Handle search field losing focus"""
        # Hide results and status when focus is lost
        # But delay it slightly to allow for clicking on results
        QTimer.singleShot(150, self.hide_results_if_not_focused)
        
        # Call original focus out event
        QLineEdit.focusOutEvent(self.search_input, event)
    
    def hide_results_if_not_focused(self):
        """Hide results if search field doesn't have focus"""
        # Only hide if search field doesn't have focus
        # Don't check results_list focus since it can't take focus anymore
        if not self.search_input.hasFocus():
            self.hide_results_popup()
            self.status_label.setVisible(False)
    
    def on_search_changed(self, text: str):
        """Handle search text changes"""
        text = text.strip()
        
        if not text:
            # Clear results when no text
            self.filtered_apps = []
            self.hide_results_popup()
            self.status_label.setVisible(False)
        else:
            # Search for matching apps
            self.filtered_apps = self.system_scanner.search_apps(text)
            
            # Show results if search field has focus
            if self.search_input.hasFocus():
                self.show_results_popup()
                self.status_label.setVisible(True)
                self.update_status(f"Found {len(self.filtered_apps)} applications")
        
        self.selected_index = 0 if self.filtered_apps else -1
        self.update_results_list()
    
    def show_results_popup(self):
        """Show the results popup below the search input"""
        if not self.filtered_apps:
            return
            
        # Position popup below the search input
        search_pos = self.search_input.mapToGlobal(self.search_input.rect().bottomLeft())
        popup_x = search_pos.x()
        popup_y = search_pos.y() + 2  # Small gap below search input
        
        # Adjust if popup would go off-screen
        screen = self.search_input.screen().geometry()
        if popup_y + 200 > screen.bottom():
            # Show above instead if not enough space below
            search_top = self.search_input.mapToGlobal(self.search_input.rect().topLeft())
            popup_y = search_top.y() - 202  # 200px height + 2px margin
        
        self.results_popup.move(popup_x, popup_y)
        self.results_popup.resize(self.search_input.width(), 200)
        self.results_popup.show()
        self.results_popup.raise_()  # Bring to front
    
    def hide_results_popup(self):
        """Hide the results popup"""
        self.results_popup.hide()
    
    def update_results_list(self):
        """Update the results list widget"""
        self.results_list.clear()
        
        for i, app in enumerate(self.filtered_apps):
            # Format display text
            display_text = f"{app.icon} {app.name}"
            
            # Add category and source info
            category_info = f" ({app.category})"
            if app.source != "registry":
                category_info += f" [{app.source}]"
            
            item = QListWidgetItem(display_text + category_info)
            item.setData(Qt.ItemDataRole.UserRole, app)
            item.setToolTip(f"Path: {app.path}\nCategory: {app.category}\nSource: {app.source}")
            
            self.results_list.addItem(item)
            
            # Select first item by default
            if i == 0:
                self.results_list.setCurrentRow(0)
    
    def update_status(self, message: str):
        """Update status label"""
        self.status_label.setText(message)
    
    def on_item_clicked(self, item: QListWidgetItem):
        """Handle item click"""
        self.selected_index = self.results_list.currentRow()
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """Handle item double click - launch app"""
        self.launch_selected_app()
    
    def launch_selected_app(self):
        """Launch the selected application"""
        if self.selected_index < 0 or self.selected_index >= len(self.filtered_apps):
            return
        
        app = self.filtered_apps[self.selected_index]
        
        # Get additional args for known applications
        args = self.get_app_args(app)
        
        print(f"Launching: {app.name} ({app.path})")
        self.app_launch_requested.emit(app.path, app.name, args)
        
        # Clear search after launching and hide results
        self.search_input.clear()
        self.hide_results_popup()
        self.status_label.setVisible(False)
        self.filtered_apps = []
    
    def get_app_args(self, app: SystemApp) -> List[str]:
        """Get additional arguments for specific applications"""
        app_name_lower = app.name.lower()
        
        # PowerShell needs -NoExit to keep window open
        if 'powershell' in app_name_lower and 'core' not in app_name_lower:
            return ['-NoExit']
        
        # Add other specific app arguments as needed
        return []
    
    def get_current_app(self) -> Optional[SystemApp]:
        """Get currently selected app"""
        if self.selected_index < 0 or self.selected_index >= len(self.filtered_apps):
            return None
        return self.filtered_apps[self.selected_index] 