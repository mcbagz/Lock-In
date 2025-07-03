"""
Collaborative Text Editor Widget for LockIn
Rich text editor with syntax highlighting, file operations, and version control
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTextEdit, QToolBar, QFileDialog, QMessageBox, 
                               QLabel, QMenu, QApplication, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QAction, QKeySequence
import re
import os
from pathlib import Path
from typing import Optional, Dict, Any
import time


class CollaborativeTextEditor(QWidget):
    """Rich text editor for collaborative editing with AI"""
    
    # Signals
    text_changed = Signal(str)  # Emitted when text changes (debounced)
    save_requested = Signal(str, str)  # filename, content
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.session_id = None
        self.database = None
        self.is_ai_editing = False
        self.last_user_edit_time = 0
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._emit_text_changed)
        
        self.setup_ui()
        self.setup_syntax_highlighting()
        
    def setup_ui(self):
        """Setup the text editor interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)
        
        # Text editor
        self.text_editor = QTextEdit()
        self.text_editor.setAcceptRichText(True)
        self.text_editor.textChanged.connect(self._on_text_changed)
        
        # Set font for better code editing
        font = QFont("Consolas", 11)
        if not font.exactMatch():
            font = QFont("Courier New", 11)
        self.text_editor.setFont(font)
        
        # Styling
        self.text_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 1px solid #666;
            }
            QTextEdit:disabled {
                background-color: #2a2a2a;
                color: #888;
            }
        """)
        
        layout.addWidget(self.text_editor)
        
        # Status bar
        self.status_bar = self.create_status_bar()
        layout.addWidget(self.status_bar)
        
    def create_toolbar(self):
        """Create the toolbar with file and edit operations"""
        toolbar = QFrame()
        toolbar.setFixedHeight(40)
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #3d3d3d;
                border-bottom: 1px solid #555;
            }
            QPushButton {
                background-color: #4d4d4d;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 5px 10px;
                color: white;
                font-size: 11px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #777;
            }
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # File operations
        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setToolTip("Copy text to clipboard")
        self.copy_btn.clicked.connect(self.copy_text)
        layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setToolTip("Save as file")
        self.save_btn.clicked.connect(self.save_file)
        layout.addWidget(self.save_btn)
        
        # Edit operations
        self.undo_btn = QPushButton("↶ Undo")
        self.undo_btn.setToolTip("Undo last change")
        self.undo_btn.clicked.connect(self.undo_change)
        layout.addWidget(self.undo_btn)
        
        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.setToolTip("Clear all text")
        self.clear_btn.clicked.connect(self.clear_text)
        layout.addWidget(self.clear_btn)
        
        layout.addStretch()
        
        # Format buttons
        self.bold_btn = QPushButton("B")
        self.bold_btn.setToolTip("Bold")
        self.bold_btn.setFont(QFont("", 10, QFont.Weight.Bold))
        self.bold_btn.clicked.connect(self.toggle_bold)
        layout.addWidget(self.bold_btn)
        
        self.italic_btn = QPushButton("I")
        self.italic_btn.setToolTip("Italic")
        self.italic_btn.setFont(QFont("", 10, QFont.Weight.Normal, True))
        self.italic_btn.clicked.connect(self.toggle_italic)
        layout.addWidget(self.italic_btn)
        
        self.code_btn = QPushButton("{ }")
        self.code_btn.setToolTip("Code format")
        self.code_btn.clicked.connect(self.toggle_code)
        layout.addWidget(self.code_btn)
        
        return toolbar
        
    def create_status_bar(self):
        """Create status bar showing edit info"""
        status_bar = QFrame()
        status_bar.setFixedHeight(25)
        status_bar.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-top: 1px solid #444;
            }
            QLabel {
                color: #888;
                font-size: 10px;
                padding: 2px 5px;
            }
        """)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(5, 0, 5, 0)
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        self.edit_info_label = QLabel("")
        layout.addWidget(self.edit_info_label)
        
        return status_bar
        
    def setup_syntax_highlighting(self):
        """Setup basic syntax highlighting for code"""
        # This is a simplified version - could be expanded with proper syntax highlighting
        pass
        
    def _on_text_changed(self):
        """Handle text changes with debouncing"""
        if not self.is_ai_editing:
            self.last_user_edit_time = time.time()
            # Debounce text changes - only emit after 500ms of no changes
            self.debounce_timer.stop()
            self.debounce_timer.start(500)
            
    def _emit_text_changed(self):
        """Emit text changed signal after debounce"""
        self.text_changed.emit(self.text_editor.toPlainText())
        
    def set_session_data(self, session_id: str, database):
        """Set the collaborative session data"""
        self.session_id = session_id
        self.database = database
        
    def set_text(self, text: str, is_ai_edit: bool = False):
        """Set the editor text"""
        self.is_ai_editing = is_ai_edit
        
        if is_ai_edit:
            # For AI edits, show visual indication
            self.text_editor.setEnabled(False)
            self.status_label.setText("AI is editing...")
            
            # Set the text
            self.text_editor.setPlainText(text)
            
            # Re-enable after a short delay
            QTimer.singleShot(1000, self._enable_editor)
        else:
            self.text_editor.setPlainText(text)
            
    def _enable_editor(self):
        """Re-enable the editor after AI edit"""
        self.text_editor.setEnabled(True)
        self.is_ai_editing = False
        self.status_label.setText("Ready")
        
    def get_text(self) -> str:
        """Get the current text"""
        return self.text_editor.toPlainText()
        
    def copy_text(self):
        """Copy text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_editor.toPlainText())
        self.status_label.setText("Text copied to clipboard")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
        
    def save_file(self):
        """Save text as file"""
        text = self.text_editor.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Save File", "No text to save")
            return
            
        # Determine default extension based on content
        default_ext = ".md" if self._looks_like_markdown(text) else ".txt"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Text File", 
            f"collaborative_text{default_ext}",
            "Text files (*.txt);;Markdown files (*.md);;All files (*.*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.status_label.setText(f"Saved to {Path(filename).name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {e}")
                
    def _looks_like_markdown(self, text: str) -> bool:
        """Check if text looks like markdown"""
        markdown_patterns = [
            r'^#+\s',      # Headers
            r'^\*\s',      # Bullet points
            r'^\d+\.\s',   # Numbered lists
            r'\*\*.*\*\*', # Bold
            r'\*.*\*',     # Italic
            r'`.*`',       # Code
            r'```',        # Code blocks
        ]
        
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False
        
    def undo_change(self):
        """Undo last change using database history"""
        if self.database and self.session_id:
            if self.database.revert_text_to_previous(self.session_id):
                # Reload text from database
                session = self.database.get_collaborative_session(self.session_id)
                if session:
                    self.set_text(session["current_text"])
                    self.status_label.setText("Reverted to previous version")
                    QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))
            else:
                QMessageBox.information(self, "Undo", "No previous version available")
        else:
            # Fallback to QTextEdit undo
            self.text_editor.undo()
            
    def clear_text(self):
        """Clear all text with confirmation"""
        if self.text_editor.toPlainText().strip():
            reply = QMessageBox.question(
                self, "Clear Text", 
                "Are you sure you want to clear all text?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.text_editor.clear()
                
    def toggle_bold(self):
        """Toggle bold formatting"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            format = cursor.charFormat()
            if format.fontWeight() == QFont.Weight.Bold:
                format.setFontWeight(QFont.Weight.Normal)
            else:
                format.setFontWeight(QFont.Weight.Bold)
            cursor.mergeCharFormat(format)
            
    def toggle_italic(self):
        """Toggle italic formatting"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            format = cursor.charFormat()
            format.setFontItalic(not format.fontItalic())
            cursor.mergeCharFormat(format)
            
    def toggle_code(self):
        """Toggle code formatting"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection():
            format = cursor.charFormat()
            if format.fontFamily() == "Consolas":
                format.setFontFamily("Segoe UI")
                format.setBackground(QColor(45, 45, 45))
            else:
                format.setFontFamily("Consolas")
                format.setBackground(QColor(30, 30, 30))
            cursor.mergeCharFormat(format)
            
    def set_editing_enabled(self, enabled: bool):
        """Enable/disable editing"""
        self.text_editor.setEnabled(enabled)
        if enabled:
            self.status_label.setText("Ready")
        else:
            self.status_label.setText("Editing locked - AI is processing...")
            
    def update_edit_info(self, edit_description: str):
        """Update the edit info label"""
        self.edit_info_label.setText(f"Last edit: {edit_description}")
        QTimer.singleShot(5000, lambda: self.edit_info_label.setText("")) 