"""
Enhanced Floating AI Chat Window for LockIn
Advanced AI interaction with OpenAI integration, conversation persistence, and semantic search
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QTextEdit, QLineEdit, QScrollArea, 
                               QFrame, QMessageBox, QComboBox, QDialog, 
                               QFormLayout, QTextEdit as QTextEditDialog,
                               QDialogButtonBox, QListWidget, QListWidgetItem,
                               QSplitter, QTabWidget, QProgressBar)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QMutex
from PySide6.QtGui import QFont, QPalette, QColor, QTextCursor, QAction, QKeySequence
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from transitions import Machine
import asyncio
import sys
import os

# Add parent directory to path for AI imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai import (AIClient, AIDatabase, AIEmbeddingsManager, AISecurityManager,
                get_openai_api_key, store_openai_api_key, has_openai_api_key)


class AIWorkerThread(QThread):
    """Enhanced worker thread for AI requests with OpenAI integration"""
    response_ready = Signal(str, str, dict)  # response, model_used, usage_stats
    error_occurred = Signal(str)
    stream_chunk = Signal(str)  # For streaming responses
    
    def __init__(self, message: str, conversation_id: str = None, preset_name: str = "Default", 
                 is_new_conversation: bool = False, streaming: bool = False):
        super().__init__()
        self.message = message
        self.conversation_id = conversation_id
        self.preset_name = preset_name
        self.is_new_conversation = is_new_conversation
        self.streaming = streaming
        self.ai_client = AIClient()
        
    def run(self):
        """Process AI request in background"""
        try:
            if not self.ai_client.has_valid_api_key():
                self.error_occurred.emit("No valid OpenAI API key. Please set one in Settings.")
                return
            
            if self.is_new_conversation:
                # Start new conversation
                conversation_id = self.ai_client.start_new_conversation(
                    self.message, self.preset_name
                )
                if conversation_id:
                    self.conversation_id = conversation_id
                    # Get the response (it was already generated)
                    messages = self.ai_client.database.get_conversation_messages(conversation_id)
                    if messages and len(messages) >= 2:
                        response = messages[-1]["content"]
                        model_used = messages[-1]["model_used"] or "unknown"
                        self.response_ready.emit(response, model_used, {"conversation_id": conversation_id})
                    else:
                        self.error_occurred.emit("Failed to start conversation")
                else:
                    self.error_occurred.emit("Failed to start new conversation")
            else:
                # Continue existing conversation
                if not self.conversation_id:
                    self.error_occurred.emit("No conversation ID provided")
                    return
                
                result = self.ai_client.continue_conversation(self.conversation_id, self.message)
                if result:
                    self.response_ready.emit(
                        result["response"], 
                        result["model_used"], 
                        result["usage"]
                    )
                else:
                    self.error_occurred.emit("Failed to get AI response")
                    
        except Exception as e:
            self.error_occurred.emit(f"AI Error: {str(e)}")


class APIKeyDialog(QDialog):
    """Dialog for setting up OpenAI API key"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenAI API Key Setup")
        self.setModal(True)
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("""
<h3>OpenAI API Key Required</h3>
<p>To use the AI assistant, you need to provide your OpenAI API key.</p>
<p><b>How to get an API key:</b></p>
<ol>
<li>Go to <a href="https://platform.openai.com/api-keys">https://platform.openai.com/api-keys</a></li>
<li>Sign in or create an account</li>
<li>Click "Create new secret key"</li>
<li>Copy the key and paste it below</li>
</ol>
<p><i>Your API key will be stored securely on your machine.</i></p>
        """)
        instructions.setWordWrap(True)
        instructions.setOpenExternalLinks(True)
        layout.addWidget(instructions)
        
        # API key input
        form_layout = QFormLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("API Key:", self.api_key_input)
        layout.addLayout(form_layout)
        
        # Show/hide key button
        show_key_btn = QPushButton("Show Key")
        show_key_btn.setCheckable(True)
        show_key_btn.toggled.connect(self.toggle_key_visibility)
        layout.addWidget(show_key_btn)
        
        # Test connection button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.test_api_key)
        layout.addWidget(self.test_btn)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_key)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def toggle_key_visibility(self, checked):
        """Toggle API key visibility"""
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def test_api_key(self):
        """Test the API key"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.status_label.setText("❌ Please enter an API key")
            return
        
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        
        try:
            ai_client = AIClient()
            if ai_client.validate_api_key(api_key):
                self.status_label.setText("✅ API key is valid!")
                self.status_label.setStyleSheet("color: green;")
            else:
                self.status_label.setText("❌ API key is invalid")
                self.status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
        
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection")
    
    def accept_key(self):
        """Accept and store the API key"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Invalid Key", "Please enter an API key")
            return
        
        try:
            result = store_openai_api_key(api_key)
            
            if result:
                # Verify storage worked
                retrieved = get_openai_api_key()
                
                if retrieved and retrieved == api_key:
                    self.accept()
                else:
                    QMessageBox.critical(self, "Error", "API key storage verification failed")
            else:
                QMessageBox.critical(self, "Error", "Failed to store API key. Please check that your API key format is correct (should start with 'sk-' or 'sk-proj-').")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to store API key: {e}")


class ConversationHistoryDialog(QDialog):
    """Dialog for browsing conversation history"""
    
    conversation_selected = Signal(str)  # conversation_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conversation History")
        self.setModal(True)
        self.resize(600, 400)
        
        self.database = AIDatabase()
        self.embeddings = AIEmbeddingsManager()
        
        layout = QVBoxLayout(self)
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search conversations...")
        self.search_input.textChanged.connect(self.search_conversations)
        search_layout.addWidget(self.search_input)
        
        semantic_search_btn = QPushButton("🔍 Semantic Search")
        semantic_search_btn.clicked.connect(self.semantic_search)
        search_layout.addWidget(semantic_search_btn)
        
        layout.addLayout(search_layout)
        
        # Conversation list
        self.conversation_list = QListWidget()
        self.conversation_list.itemDoubleClicked.connect(self.select_conversation)
        layout.addWidget(self.conversation_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        select_btn = QPushButton("Open Conversation")
        select_btn.clicked.connect(self.select_conversation)
        button_layout.addWidget(select_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_conversation)
        button_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.load_conversations()
    
    def load_conversations(self, conversations=None):
        """Load conversations into the list"""
        self.conversation_list.clear()
        
        if conversations is None:
            conversations = self.database.get_conversations(50)
        
        for conv in conversations:
            item_text = f"{conv['title']} ({conv['preset_mode']}) - {conv['message_count']} messages"
            if conv['updated_at']:
                try:
                    updated_at = datetime.fromisoformat(conv['updated_at'].replace('Z', '+00:00'))
                    item_text += f" - {updated_at.strftime('%Y-%m-%d %H:%M')}"
                except:
                    pass
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, conv['id'])
            self.conversation_list.addItem(item)
    
    def search_conversations(self):
        """Search conversations by title/summary"""
        query = self.search_input.text().strip()
        if query:
            conversations = self.database.search_conversations(query, 20)
            self.load_conversations(conversations)
        else:
            self.load_conversations()
    
    def semantic_search(self):
        """Perform semantic search using embeddings"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.information(self, "Search", "Please enter a search query")
            return
        
        try:
            similar_conversations = self.embeddings.search_similar_conversations(query, 10)
            
            if similar_conversations:
                # Get full conversation details
                conversation_ids = [conv["conversation_id"] for conv in similar_conversations]
                conversations = []
                for conv_id in conversation_ids:
                    conv_data = self.database.get_conversations(1)  # This is not ideal, needs improvement
                    for conv in conv_data:
                        if conv['id'] == conv_id:
                            conversations.append(conv)
                            break
                
                self.load_conversations(conversations)
            else:
                QMessageBox.information(self, "Search", "No similar conversations found")
                
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Semantic search failed: {e}")
    
    def select_conversation(self):
        """Select and open a conversation"""
        current_item = self.conversation_list.currentItem()
        if current_item:
            conversation_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.conversation_selected.emit(conversation_id)
            self.accept()
    
    def delete_conversation(self):
        """Delete selected conversation"""
        current_item = self.conversation_list.currentItem()
        if not current_item:
            return
        
        reply = QMessageBox.question(
            self, "Delete Conversation",
            "Are you sure you want to delete this conversation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conversation_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.database.delete_conversation(conversation_id)
            self.embeddings.delete_conversation_summary(conversation_id)
            self.load_conversations()


class FloatingAIChat(QWidget):
    # State signals for PyTransitions
    state_changed = Signal(str)
    
    def __init__(self, config, virtual_desktop, process_manager):
        super().__init__()
        self.config = config
        self.virtual_desktop = virtual_desktop
        self.process_manager = process_manager
        
        # Enhanced state management
        self.is_minimized = False
        self.normal_height = 700
        self.allow_close = False
        
        # AI-related attributes
        self.ai_client = AIClient()
        self.database = AIDatabase()
        self.embeddings = AIEmbeddingsManager()
        self.security_manager = AISecurityManager()
        
        # Current conversation
        self.current_conversation_id = None
        self.current_preset = "Default"
        
        # State machine setup
        self.setup_state_machine()
        
        # UI setup
        self.setup_window()
        self.setup_ui()
        
        # Initialize based on API key availability
        self.initialize_ai_state()
        
    def setup_state_machine(self):
        """Setup PyTransitions state machine with separate model"""
        # Create a separate state model object to avoid QWidget inheritance conflicts
        class StateModel:
            def __init__(self, parent):
                self.parent = parent
                
        self.state_model = StateModel(self)
        
        # Define states
        states = [
            'idle',                 # Ready to receive input
            'setup_required',       # API key setup needed
            'waiting_for_input',    # Waiting for user input
            'processing',           # Processing AI request
            'error_state'           # Error occurred
        ]
        
        # Define transitions
        transitions = [
            # From setup_required
            {'trigger': 'api_key_set', 'source': 'setup_required', 'dest': 'idle'},
            
            # From idle
            {'trigger': 'start_chat', 'source': 'idle', 'dest': 'waiting_for_input'},
            {'trigger': 'need_setup', 'source': 'idle', 'dest': 'setup_required'},
            
            # From waiting_for_input
            {'trigger': 'message_sent', 'source': 'waiting_for_input', 'dest': 'processing'},
            {'trigger': 'cancel_input', 'source': 'waiting_for_input', 'dest': 'idle'},
            
            # From processing
            {'trigger': 'response_received', 'source': 'processing', 'dest': 'idle'},
            {'trigger': 'error_occurred_sm', 'source': 'processing', 'dest': 'error_state'},
            
            # From error_state
            {'trigger': 'retry', 'source': 'error_state', 'dest': 'idle'},
            {'trigger': 'need_setup', 'source': 'error_state', 'dest': 'setup_required'},
            
            # Universal transitions
            {'trigger': 'reset', 'source': '*', 'dest': 'idle'}
        ]
        
        # Initialize state machine with separate model
        self.machine = Machine(
            model=self.state_model,
            states=states,
            transitions=transitions,
            initial='idle',
            after_state_change='_on_state_change'
        )
        
        # Add a callback for state changes
        self.state_model._on_state_change = self._on_state_change
        
    def _on_state_change(self):
        """Handle state changes"""
        current_state = self.state_model.state
        self.state_changed.emit(current_state)
        self.update_ui_for_state()
        
    # Helper properties to access state machine methods
    def get_current_state(self):
        """Get current state"""
        return getattr(self.state_model, 'state', 'idle')
    
    def api_key_set(self):
        """Trigger API key set transition"""
        if hasattr(self.state_model, 'api_key_set'):
            self.state_model.api_key_set()
    
    def need_setup(self):
        """Trigger need setup transition"""
        if hasattr(self.state_model, 'need_setup'):
            self.state_model.need_setup()
    
    def start_chat(self):
        """Trigger start chat transition"""
        if hasattr(self.state_model, 'start_chat'):
            self.state_model.start_chat()
    
    def message_sent(self):
        """Trigger message sent transition"""
        if hasattr(self.state_model, 'message_sent'):
            self.state_model.message_sent()
    
    def response_received(self):
        """Trigger response received transition"""
        if hasattr(self.state_model, 'response_received'):
            self.state_model.response_received()
    
    def error_occurred_sm(self):
        """Trigger error occurred transition"""
        if hasattr(self.state_model, 'error_occurred_sm'):
            self.state_model.error_occurred_sm()
    
    def retry(self):
        """Trigger retry transition"""
        if hasattr(self.state_model, 'retry'):
            self.state_model.retry()
    
    def reset(self):
        """Trigger reset transition"""
        if hasattr(self.state_model, 'reset'):
            self.state_model.reset()
    
    def setup_window(self):
        """Configure window properties"""
        self.setWindowTitle("LockIn - AI Assistant")
        
        # Set initial size and position (right side of screen)
        screen_geometry = self.screen().geometry()
        width = 400
        height = self.normal_height
        x = screen_geometry.width() - width - 20
        y = 80
        
        self.setGeometry(x, y, width, height)
        
        # Window flags
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Enhanced styling
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
            
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #777;
                border: 1px solid #444;
            }
            
            QPushButton#minimizeButton {
                background-color: #5d5d3d;
                max-width: 25px;
                min-width: 25px;
                max-height: 25px;
                min-height: 25px;
                border-radius: 12px;
            }
            
            QPushButton#settingsButton {
                background-color: #4d4d5d;
                max-width: 25px;
                min-width: 25px;
                max-height: 25px;
                min-height: 25px;
                border-radius: 12px;
            }
            
            QPushButton#sendButton {
                background-color: #4d6d4d;
                min-width: 60px;
            }
            
            QPushButton#sendButton:hover {
                background-color: #5d7d5d;
            }
            
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
            
            QLineEdit {
                background-color: #3d3d3d;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 8px;
                color: white;
                font-size: 12px;
            }
            
            QLineEdit:focus {
                border: 1px solid #777;
                background-color: #4d4d4d;
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
                background: #5d5d5d;
            }
            
            QComboBox::down-arrow {
                border: none;
                width: 10px;
                height: 10px;
            }
            
            QListWidget {
                background-color: #3d3d3d;
                border: 1px solid #555;
                color: white;
            }
            
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
            
            QListWidget::item:selected {
                background-color: #4d6d4d;
            }
            
            QProgressBar {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 3px;
                text-align: center;
            }
            
            QProgressBar::chunk {
                background-color: #4d6d4d;
                border-radius: 2px;
            }
        """)
        
    def setup_ui(self):
        """Setup the enhanced user interface"""
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
        
        # Control bar with preset and history
        control_layout = QHBoxLayout()
        
        # Preset selection
        preset_label = QLabel("Mode:")
        control_layout.addWidget(preset_label)
        
        self.preset_combo = QComboBox()
        self.load_presets()
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        control_layout.addWidget(self.preset_combo)
        
        control_layout.addStretch()
        
        # History button
        history_btn = QPushButton("📚 History")
        history_btn.clicked.connect(self.show_conversation_history)
        control_layout.addWidget(history_btn)
        
        # New conversation button
        new_conv_btn = QPushButton("➕ New")
        new_conv_btn.clicked.connect(self.start_new_conversation)
        control_layout.addWidget(new_conv_btn)
        
        content_layout.addLayout(control_layout)
        
        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(350)
        content_layout.addWidget(self.chat_display)
        
        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #aaa; font-size: 10px; padding: 2px;")
        content_layout.addWidget(self.status_label)
        
        # Input area
        input_layout = QVBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)
        
        # Send button and actions
        button_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("📤 Send")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self.send_message)
        button_layout.addWidget(self.send_btn)
        
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.clicked.connect(self.clear_chat)
        button_layout.addWidget(clear_btn)
        
        input_layout.addLayout(button_layout)
        
        content_layout.addLayout(input_layout)
        
        layout.addWidget(self.content_widget)
        
    def create_title_bar(self):
        """Create custom title bar with settings and minimize buttons"""
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(30)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(5, 0, 5, 0)
        
        # Title label
        title_label = QLabel("🤖 AI Assistant")
        title_label.setObjectName("titleLabel")
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Settings button
        settings_btn = QPushButton("⚙️")
        settings_btn.setObjectName("settingsButton")
        settings_btn.clicked.connect(self.show_settings)
        settings_btn.setToolTip("Settings & API Key")
        layout.addWidget(settings_btn)
        
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
            
    def add_welcome_message(self):
        """Add welcome message to chat"""
        preset_info = self.database.get_preset(self.current_preset)
        if preset_info:
            preset_desc = preset_info.get('description', 'AI Assistant')
            model_name = preset_info.get('model', 'OpenAI')
        else:
            preset_desc = "AI Assistant"
            model_name = "OpenAI"
        
        welcome_msg = f"""🤖 <b>{preset_desc}</b>

Mode: <i>{self.current_preset}</i> | Model: <i>{model_name}</i>

Hello! I'm ready to help you. What would you like to know or discuss?
"""
        self.add_message("AI", welcome_msg, "#4d6d4d")
        
    def add_message(self, sender, message, color="#3d3d3d"):
        """Add a message to the chat display"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Format message with timestamp and sender
        formatted_message = f"""
<div style="background-color: {color}; border-radius: 5px; padding: 8px; margin: 5px 0;">
    <b>{sender}</b> <span style="color: #aaa; font-size: 10px;">[{timestamp}]</span><br/>
    {message}
</div>
"""
        
        # Add to chat display
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(formatted_message)
        self.chat_display.setTextCursor(cursor)
        
        # Scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def send_message(self):
        """Send user message and get AI response"""
        message = self.message_input.text().strip()
        if not message:
            return
        
        # Check if we have API key
        if not has_openai_api_key():
            self.show_api_key_dialog()
            return
        
        # Clear input
        self.message_input.clear()
        
        # Follow proper state transitions: idle -> start_chat -> waiting_for_input -> message_sent -> processing
        current_state = self.get_current_state()
        
        if current_state == 'idle':
            self.start_chat()  # idle -> waiting_for_input
        
        if self.get_current_state() == 'waiting_for_input':
            self.message_sent()  # waiting_for_input -> processing
        
        # Add user message
        self.add_message("You", message, "#4d4d6d")
        
        # Show "thinking" message
        self.add_message("AI", "🤔 Thinking...", "#5d5d3d")
        self.update_status("Processing...")
        
        # Determine if this is a new conversation
        is_new = self.current_conversation_id is None
        
        # Create and start AI worker thread
        self.ai_worker = AIWorkerThread(
            message=message,
            conversation_id=self.current_conversation_id,
            preset_name=self.current_preset,
            is_new_conversation=is_new
        )
        self.ai_worker.response_ready.connect(self.handle_ai_response)
        self.ai_worker.error_occurred.connect(self.handle_ai_error)
        self.ai_worker.start()
        

        
    def handle_ai_response(self, response, model_used, metadata):
        """Handle AI response"""
        # Remove the "thinking" message
        self.remove_last_message()
        
        # Add actual response
        self.add_message("AI", response, "#4d6d4d")
        
        # Update conversation ID if this was a new conversation
        if "conversation_id" in metadata:
            self.current_conversation_id = metadata["conversation_id"]
        
        # Update state and status
        self.response_received()
        self.update_status(f"Response from {model_used}")
        
        # Auto-summarize and add to embeddings if conversation is long enough
        if self.current_conversation_id:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            threshold = self.config.get_setting("ai", "auto_summarize_threshold", 20)
            
            if len(messages) >= threshold and len(messages) % 10 == 0:  # Every 10 messages after threshold
                self.auto_summarize_conversation()
    
    def handle_ai_error(self, error):
        """Handle AI error"""
        # Remove the "thinking" message
        self.remove_last_message()
        
        # Add error message
        self.add_message("AI", f"❌ Error: {error}", "#6d4d4d")
        
        # Update state
        self.error_occurred_sm()
        self.update_status("Error occurred")
    
    def remove_last_message(self):
        """Remove the last message from chat display"""
        # Get current content
        content = self.chat_display.toHtml()
        
        # Find and remove the last message div
        last_div_start = content.rfind('<div style="background-color:')
        if last_div_start != -1:
            # Find the end of the div
            div_count = 0
            pos = last_div_start
            while pos < len(content):
                if content[pos:pos+4] == '<div':
                    div_count += 1
                elif content[pos:pos+6] == '</div>':
                    div_count -= 1
                    if div_count == 0:
                        # Found the end of our div
                        new_content = content[:last_div_start] + content[pos+6:]
                        self.chat_display.setHtml(new_content)
                        break
                pos += 1
    
    def auto_summarize_conversation(self):
        """Auto-summarize conversation and add to embeddings"""
        if not self.current_conversation_id:
            return
        
        try:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            summary = self.ai_client.summarize_conversation(messages)
            
            if summary:
                # Update database summary
                self.database.update_conversation_summary(self.current_conversation_id, summary)
                
                # Add to embeddings
                self.embeddings.add_conversation_summary(
                    self.current_conversation_id, 
                    summary,
                    {"preset": self.current_preset, "message_count": len(messages)}
                )
                
                self.update_status("Conversation summarized")
        except Exception as e:
            print(f"Auto-summarization failed: {e}")
    
    def clear_chat(self):
        """Clear the chat history"""
        reply = QMessageBox.question(
            self,
            "Clear Chat?",
            "Are you sure you want to clear the current chat?\n(This won't delete saved conversations)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_new_conversation()
    
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
                "The AI Assistant cannot be closed while LockIn is running.\nUse the header to close LockIn."
            )

    def initialize_ai_state(self):
        """Initialize AI state based on API key availability and validity"""
        if has_openai_api_key():
            # Validate the API key with OpenAI
            self.update_status("Validating API key...")
            
            try:
                api_key = get_openai_api_key()
                if api_key and self.ai_client.validate_api_key(api_key):
                    # API key is valid
                    if hasattr(self, 'state_model'):
                        if self.get_current_state() == 'setup_required':
                            self.api_key_set()
                        else:
                            self.reset()
                    self.start_new_conversation()
                    self.update_status("✅ API key validated")
                else:
                    # API key is invalid
                    self.show_invalid_key_message()
                    if hasattr(self, 'state_model'):
                        self.need_setup()
                    
            except Exception as e:
                # Error validating API key
                print(f"API key validation error: {e}")
                self.show_validation_error_message(str(e))
                if hasattr(self, 'state_model'):
                    self.need_setup()
        else:
            # No API key found
            if hasattr(self, 'state_model'):
                self.need_setup()
            else:
                # If machine not setup yet, we'll handle this in show_api_key_dialog
                pass
    
    def update_ui_for_state(self):
        """Update UI elements based on current state"""
        if not hasattr(self, 'message_input'):
            return
            
        current_state = self.get_current_state()
        
        if current_state == 'setup_required':
            self.message_input.setEnabled(False)
            self.message_input.setPlaceholderText("API key required - click Settings")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(False)
            self.show_setup_message()
            
        elif current_state == 'idle':
            self.message_input.setEnabled(True)
            self.message_input.setPlaceholderText("Type your message here...")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
                
        elif current_state == 'processing':
            self.message_input.setEnabled(False)
            self.message_input.setPlaceholderText("Processing...")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(False)
                
        elif current_state == 'error_state':
            self.message_input.setEnabled(True)
            self.message_input.setPlaceholderText("Error occurred - try again")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
    
    def show_setup_message(self):
        """Show API key setup message"""
        if hasattr(self, 'chat_display'):
            setup_msg = """🔑 <b>API Key Setup Required</b>

To use the AI assistant, you need to provide your OpenAI API key.

Click the Settings button (⚙️) in the title bar to get started.

<i>Your API key will be stored securely on your machine.</i>
"""
            self.add_message("System", setup_msg, "#5d4d4d")
    
    def show_invalid_key_message(self):
        """Show invalid API key message"""
        if hasattr(self, 'chat_display'):
            invalid_msg = """❌ <b>Invalid API Key</b>

Your stored OpenAI API key appears to be invalid or has been revoked.

Click the Settings button (⚙️) to update your API key.

<i>Please verify your API key at https://platform.openai.com/api-keys</i>
"""
            self.add_message("System", invalid_msg, "#6d4d4d")
    
    def show_validation_error_message(self, error):
        """Show API key validation error message"""
        if hasattr(self, 'chat_display'):
            error_msg = f"""⚠️ <b>API Key Validation Error</b>

Unable to validate your OpenAI API key: {error}

This could be due to:
• Network connectivity issues
• OpenAI service unavailable
• Rate limiting

Click the Settings button (⚙️) to check your API key or try again later.
"""
            self.add_message("System", error_msg, "#6d5d4d")
    
    def load_presets(self):
        """Load AI presets into the combo box"""
        self.preset_combo.clear()
        presets = self.database.get_all_presets()
        for preset in presets:
            self.preset_combo.addItem(f"{preset['name']}", preset['name'])
        
        # Set default preset
        default_preset = self.config.get_setting("ai", "default_preset", "Default")
        index = self.preset_combo.findData(default_preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
            self.current_preset = default_preset
    
    def on_preset_changed(self, preset_name):
        """Handle preset change"""
        if preset_name:
            self.current_preset = preset_name
            self.update_status(f"Mode: {preset_name}")
    
    def show_settings(self):
        """Show settings dialog"""
        if not has_openai_api_key():
            self.show_api_key_dialog()
        else:
            # Show full settings dialog (could be expanded later)
            reply = QMessageBox.question(
                self, "Settings",
                "API Key is already set. Do you want to change it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.show_api_key_dialog()
    
    def show_api_key_dialog(self):
        """Show API key setup dialog"""
        dialog = APIKeyDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # API key was set successfully
            self.api_key_set()
            self.update_status("API key configured")
            QMessageBox.information(self, "Success", "API key configured successfully!")
            self.start_new_conversation()
    
    def show_conversation_history(self):
        """Show conversation history dialog"""
        dialog = ConversationHistoryDialog(self)
        dialog.conversation_selected.connect(self.load_conversation)
        dialog.exec()
    
    def load_conversation(self, conversation_id):
        """Load a conversation from history"""
        try:
            messages = self.database.get_conversation_messages(conversation_id)
            self.current_conversation_id = conversation_id
            
            # Clear current chat
            self.chat_display.clear()
            
            # Load messages
            for msg in messages:
                sender = "You" if msg["role"] == "user" else "AI"
                color = "#4d4d6d" if msg["role"] == "user" else "#4d6d4d"
                self.add_message(sender, msg["content"], color)
            
            self.update_status(f"Loaded conversation: {conversation_id[:8]}...")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load conversation: {e}")
    
    def start_new_conversation(self):
        """Start a new conversation"""
        self.current_conversation_id = None
        self.chat_display.clear()
        
        if has_openai_api_key():
            self.add_welcome_message()
            self.update_status("Ready for new conversation")
        else:
            self.show_setup_message()
            self.update_status("API key required")
    
    def update_status(self, message):
        """Update status label"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)