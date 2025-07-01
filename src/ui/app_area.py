"""
App Area - Simplified Version
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from typing import List, Dict


class AppArea(QWidget):
    # Signals
    window_focus_requested = Signal(int)  # hwnd
    
    def __init__(self):
        super().__init__()
        self.window_manager = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #555;
                gridline-color: #333;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: white;
                padding: 5px;
                border: 1px solid #555;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Application Workspace")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Window table
        self.window_table = QTableWidget()
        self.window_table.setColumnCount(3)
        self.window_table.setHorizontalHeaderLabels(["App", "Title", "Status"])
        
        header = self.window_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        layout.addWidget(self.window_table)
        
        # Status
        self.status_label = QLabel("No managed windows")
        layout.addWidget(self.status_label)
    
    def set_window_manager(self, window_manager):
        """Set the window manager"""
        self.window_manager = window_manager
    
    def update_window_list(self, window_list: List[Dict]):
        """Update the window list"""
        self.window_table.setRowCount(len(window_list))
        
        for row, window in enumerate(window_list):
            self.window_table.setItem(row, 0, QTableWidgetItem(window.get('app_name', 'Unknown')))
            self.window_table.setItem(row, 1, QTableWidgetItem(window.get('title', 'No Title')))
            
            status = "Visible" if window.get('is_visible', False) else "Hidden"
            self.window_table.setItem(row, 2, QTableWidgetItem(status))
        
        self.status_label.setText(f"Managing {len(window_list)} windows") 