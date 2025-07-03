"""
Enhanced Floating AI Chat Window for LockIn
Advanced AI interaction with OpenAI integration, conversation persistence, and semantic search
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QTextEdit, QLineEdit, QScrollArea, 
                               QFrame, QMessageBox, QComboBox, QDialog, 
                               QFormLayout, QTextEdit as QTextEditDialog,
                               QDialogButtonBox, QListWidget, QListWidgetItem,
                               QSplitter, QTabWidget, QProgressBar, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QMutex
from PySide6.QtGui import QFont, QPalette, QColor, QTextCursor, QAction, QKeySequence, QCursor
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from transitions import Machine
import asyncio
import sys
import os
import re
import html
import uuid

# Try to import markdown with fallback
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    print("Warning: markdown library not available, using basic formatting")

# Add parent directory to path for AI imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ai import (AIClient, AIDatabase, AIEmbeddingsManager, AISecurityManager,
                get_openai_api_key, store_openai_api_key, has_openai_api_key)
from .collaborative_text_editor import CollaborativeTextEditor


class AIWorkerThread(QThread):
    """Enhanced worker thread for AI requests with OpenAI integration"""
    response_ready = Signal(str, str, dict)  # response, model_used, usage_stats
    error_occurred = Signal(str)
    stream_chunk = Signal(str)  # For streaming responses
    collaborative_response_ready = Signal(str, str, str, str, dict)  # response, text_edit, edit_description, model_used, usage_stats
    
    def __init__(self, message: str, conversation_id: str = None, preset_name: str = "Default", 
                 is_new_conversation: bool = False, streaming: bool = False, 
                 is_collaborative: bool = False, current_text: str = ""):
        super().__init__()
        self.message = message
        self.conversation_id = conversation_id
        self.preset_name = preset_name
        self.is_new_conversation = is_new_conversation
        self.streaming = streaming
        self.is_collaborative = is_collaborative
        self.current_text = current_text
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
                
                if self.is_collaborative:
                    # Use collaborative processing
                    result = self.ai_client.process_collaborative_message(
                        self.conversation_id, self.message, self.current_text, self.preset_name
                    )
                    if result:
                        self.collaborative_response_ready.emit(
                            result["response"],
                            result.get("text_edit", ""),
                            result.get("edit_description", ""),
                            result["model_used"],
                            result["usage"]
                        )
                    else:
                        self.error_occurred.emit("Failed to get collaborative AI response")
                else:
                    # Regular conversation
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
            
            # Add similarity score if this is a search result
            if 'similarity_percentage' in conv:
                item_text = f"[{conv['similarity_percentage']}%] " + item_text
            
            # Check if conversation has collaborative session
            collab_session = self.database.get_collaborative_session_by_conversation(conv['id'])
            if collab_session:
                item_text += " 📝"
            
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
                # Get full conversation details using the new method
                conversations = []
                for conv in similar_conversations:
                    conv_id = conv["conversation_id"]
                    conv_data = self.database.get_conversation_by_id(conv_id)
                    if conv_data:
                        # Add similarity information for display
                        conv_data["similarity"] = conv["similarity"]
                        conv_data["similarity_percentage"] = conv["similarity_percentage"]
                        conversations.append(conv_data)
                
                if conversations:
                    self.load_conversations(conversations)
                    # Show success message with result count
                    total_embeddings = self.embeddings.get_all_conversations_count()
                    QMessageBox.information(self, "Search Results", 
                        f"Found {len(conversations)} similar conversations out of {total_embeddings} total.\n\n"
                        f"Results are ranked by similarity percentage.")
                else:
                    QMessageBox.information(self, "Search", "Found embeddings but no matching conversations in database")
            else:
                # Check if there are any embeddings at all
                total_embeddings = self.embeddings.get_all_conversations_count()
                if total_embeddings == 0:
                    QMessageBox.information(self, "Search", 
                        "No conversation summaries found in embeddings database. Have conversations been summarized?")
                else:
                    QMessageBox.information(self, "Search", 
                        f"No conversations found in database (searched {total_embeddings} summaries)")
                
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Semantic search failed: {e}")
            print(f"Semantic search error: {e}")  # Debug output
    
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
        self.saved_size = None  # Store window size before minimizing
        
        # AI-related attributes
        self.ai_client = AIClient()
        self.database = AIDatabase()
        self.embeddings = AIEmbeddingsManager()
        self.security_manager = AISecurityManager()
        
        # Current conversation
        self.current_conversation_id = None
        self.current_preset = "Default"
        
        # Collaborative session attributes
        self.is_collaborative_mode = False
        self.current_session_id = None
        self.collaborative_editor = None
        self.collaborative_worker = None
        
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
            'error_state',          # Error occurred
            'collaborative_mode',   # In collaborative editing mode
            'collaborative_processing'  # Processing collaborative request
        ]
        
        # Define transitions
        transitions = [
            # From setup_required
            {'trigger': 'api_key_set', 'source': 'setup_required', 'dest': 'idle'},
            
            # From idle
            {'trigger': 'start_chat', 'source': 'idle', 'dest': 'waiting_for_input'},
            {'trigger': 'need_setup', 'source': 'idle', 'dest': 'setup_required'},
            {'trigger': 'enter_collaborative', 'source': 'idle', 'dest': 'collaborative_mode'},
            
            # From waiting_for_input
            {'trigger': 'message_sent', 'source': 'waiting_for_input', 'dest': 'processing'},
            {'trigger': 'cancel_input', 'source': 'waiting_for_input', 'dest': 'idle'},
            
            # From processing
            {'trigger': 'response_received', 'source': 'processing', 'dest': 'idle'},
            {'trigger': 'error_occurred_sm', 'source': 'processing', 'dest': 'error_state'},
            
            # From error_state
            {'trigger': 'retry', 'source': 'error_state', 'dest': 'idle'},
            {'trigger': 'need_setup', 'source': 'error_state', 'dest': 'setup_required'},
            
            # Collaborative mode transitions
            {'trigger': 'collaborative_message_sent', 'source': 'collaborative_mode', 'dest': 'collaborative_processing'},
            {'trigger': 'collaborative_response_received', 'source': 'collaborative_processing', 'dest': 'collaborative_mode'},
            {'trigger': 'collaborative_error', 'source': 'collaborative_processing', 'dest': 'collaborative_mode'},
            {'trigger': 'exit_collaborative', 'source': 'collaborative_mode', 'dest': 'idle'},
            
            # Universal transitions
            {'trigger': 'reset', 'source': '*', 'dest': 'idle'},
            {'trigger': 'enter_collaborative', 'source': ['waiting_for_input', 'error_state'], 'dest': 'collaborative_mode'}
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
    
    def enter_collaborative(self):
        """Trigger enter collaborative transition"""
        if hasattr(self.state_model, 'enter_collaborative'):
            self.state_model.enter_collaborative()
    
    def exit_collaborative(self):
        """Trigger exit collaborative transition"""
        if hasattr(self.state_model, 'exit_collaborative'):
            self.state_model.exit_collaborative()
    
    def collaborative_message_sent(self):
        """Trigger collaborative message sent transition"""
        if hasattr(self.state_model, 'collaborative_message_sent'):
            self.state_model.collaborative_message_sent()
    
    def collaborative_response_received(self):
        """Trigger collaborative response received transition"""
        if hasattr(self.state_model, 'collaborative_response_received'):
            self.state_model.collaborative_response_received()
    
    def collaborative_error(self):
        """Trigger collaborative error transition"""
        if hasattr(self.state_model, 'collaborative_error'):
            self.state_model.collaborative_error()
    
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
        
        # Make window resizable with reasonable bounds
        self.setMinimumSize(300, 400)  # Minimum usable size
        self.setMaximumSize(800, screen_geometry.height() - 100)  # Don't exceed screen height
        
        # Window flags
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint  # Custom title bar
        )
        
        # Enhanced styling with improved chat display
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
            
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #777;
                border: 1px solid #444;
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
                padding: 12px;
                color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.4;
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
        
        # Custom title bar for consistent design
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)
        
        # Main content area
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # Control bar with preset and history - organized into rows
        control_container = QWidget()
        control_main_layout = QVBoxLayout(control_container)
        control_main_layout.setContentsMargins(0, 0, 0, 0)
        control_main_layout.setSpacing(5)
        
        # First row: Mode selection and main controls
        control_row1 = QHBoxLayout()
        
        # Preset selection
        preset_label = QLabel("Mode:")
        control_row1.addWidget(preset_label)
        
        self.preset_combo = QComboBox()
        self.load_presets()
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        control_row1.addWidget(self.preset_combo)
        
        control_row1.addStretch()
        
        # Collaborative mode button - make it stand out
        self.collab_btn = QPushButton("📝 Collab")
        self.collab_btn.clicked.connect(self.toggle_collaborative_mode)
        self.collab_btn.setToolTip("Toggle collaborative text editing mode")
        self.collab_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d6d4d;
                border: 1px solid #6d8d6d;
                border-radius: 3px;
                padding: 5px 12px;
                color: white;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5d7d5d;
                border: 1px solid #7d9d7d;
            }
            QPushButton:pressed {
                background-color: #3d5d3d;
            }
            QPushButton:disabled {
                background-color: #3d3d3d;
                color: #777;
                border: 1px solid #444;
            }
        """)
        control_row1.addWidget(self.collab_btn)
        
        control_main_layout.addLayout(control_row1)
        
        # Second row: Action buttons
        control_row2 = QHBoxLayout()
        
        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.clicked.connect(self.show_settings)
        control_row2.addWidget(settings_btn)
        
        # History button
        history_btn = QPushButton("📚 History")
        history_btn.clicked.connect(self.show_conversation_history)
        control_row2.addWidget(history_btn)
        
        # New conversation button
        new_conv_btn = QPushButton("➕ New")
        new_conv_btn.clicked.connect(self.start_new_conversation)
        control_row2.addWidget(new_conv_btn)
        
        control_row2.addStretch()
        
        control_main_layout.addLayout(control_row2)
        
        content_layout.addWidget(control_container)
        
        # Create splitter for collaborative mode with better width management
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.setChildrenCollapsible(False)  # Prevent collapsing
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #555;
                border: 1px solid #444;
            }
            QSplitter::handle:hover {
                background-color: #666;
            }
        """)
        
        # Chat display area with container for minimum width control
        self.chat_container = QWidget()
        self.chat_container.setMinimumWidth(300)  # Ensure chat never gets too narrow
        chat_container_layout = QVBoxLayout(self.chat_container)
        chat_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(350)
        self.chat_display.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_display.customContextMenuRequested.connect(self.show_context_menu)
        chat_container_layout.addWidget(self.chat_display)
        
        self.main_splitter.addWidget(self.chat_container)
        
        # Collaborative text editor (initially hidden)
        self.collaborative_editor = CollaborativeTextEditor()
        self.collaborative_editor.text_changed.connect(self.on_text_changed)
        self.collaborative_editor.setVisible(False)
        self.collaborative_editor.setMinimumWidth(250)  # Minimum width for editor
        self.main_splitter.addWidget(self.collaborative_editor)
        
        # Set initial splitter sizes (chat takes full width initially)
        self.main_splitter.setSizes([1, 0])
        
        content_layout.addWidget(self.main_splitter)
        
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
        title_label = QLabel("🤖 AI Assistant")
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
        minimize_btn.setToolTip("Minimize (Ctrl+U)")
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
            self.setMinimumHeight(400)
            self.setMaximumHeight(self.screen().geometry().height() - 100)
            
            if self.saved_size:
                self.resize(self.saved_size)
            else:
                # Fallback to normal height if no saved size
                self.resize(self.width(), self.normal_height)
            self.content_widget.show()
            self.is_minimized = False
            
            # Focus message input when restoring (with delay to ensure window is ready)
            if hasattr(self, 'message_input') and self.message_input:
                QTimer.singleShot(100, self._focus_message_input)
        else:
            # Save current size BEFORE any modifications
            self.saved_size = self.size()
            print(f"AI Chat: Saving size {self.saved_size.width()}x{self.saved_size.height()}")
            
            # Hide content and set fixed height for title bar only
            self.content_widget.hide()
            self.setFixedHeight(30)  # Just title bar height
            self.is_minimized = True
            
    def toggle_minimize_with_focus(self):
        """Toggle minimize state and focus message input when restoring"""
        if self.is_minimized:
            # Restore and focus message input
            self.toggle_minimize()
            if hasattr(self, 'message_input') and self.message_input:
                QTimer.singleShot(200, self._focus_message_input)
        else:
            # Just minimize
            self.toggle_minimize()
    
    def _focus_message_input(self):
        """Aggressively focus the message input"""
        if hasattr(self, 'message_input') and self.message_input:
            # Make sure window is active first
            self.activateWindow()
            self.raise_()
            # Then focus the input
            self.message_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            # Force the widget to be focused
            self.message_input.activateWindow()
            print("Focused message input")
            
    def format_message_content(self, content: str) -> str:
        """Format message content with markdown rendering and code block handling"""
        if not MARKDOWN_AVAILABLE:
            return self.basic_format_content(content)
            
        try:
            # Configure markdown with extensions (use basic extensions if advanced ones fail)
            try:
                md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
            except:
                md = markdown.Markdown(extensions=['fenced_code'])
            
            # Convert markdown to HTML
            html_content = md.convert(content)
            
            # Add copy buttons to code blocks
            html_content = self.add_copy_buttons_to_code_blocks(html_content)
            
            return html_content
            
        except Exception as e:
            # Fallback to basic HTML escaping if markdown fails
            print(f"Markdown rendering failed: {e}")
            return self.basic_format_content(content)
    
    def basic_format_content(self, content: str) -> str:
        """Basic content formatting with HTML escaping and line breaks"""
        # Escape HTML
        escaped = html.escape(content)
        
        # Convert line breaks
        escaped = escaped.replace('\n', '<br>')
        
        # Simple inline code formatting
        escaped = re.sub(r'`([^`]+)`', r'<code style="background-color: #444; padding: 2px 4px; border-radius: 3px; font-family: \'Consolas\', monospace;">\1</code>', escaped)
        
        # Simple bold formatting
        escaped = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', escaped)
        
        # Simple italic formatting
        escaped = re.sub(r'\*([^\*]+)\*', r'<em>\1</em>', escaped)
        
        return escaped
    
    def add_copy_buttons_to_code_blocks(self, html_content: str) -> str:
        """Enhance code blocks with better styling (copy functionality via context menu)"""
        def replace_code_block(match):
            code_content = match.group(1)
            # Store code content for context menu copying
            block_id = str(uuid.uuid4())
            self.store_code_block(block_id, code_content)
            
            return f'''
            <div style="margin: 10px 0;">
                <div style="background-color: #1e1e1e; border-radius: 6px; padding: 12px; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; overflow-x: auto; border: 1px solid #444; position: relative;">
                    <div style="position: absolute; top: 8px; right: 8px; background-color: #333; color: #aaa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">Right-click to copy</div>
                    <pre data-code-block="{block_id}" style="margin: 0; padding: 0; background: none; color: #e0e0e0; white-space: pre-wrap; word-wrap: break-word; padding-top: 20px;">{html.escape(code_content)}</pre>
                </div>
            </div>
            '''
        
        # Replace code blocks with enhanced styling
        html_content = re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', replace_code_block, html_content, flags=re.DOTALL)
        
        return html_content
    
    def store_code_block(self, block_id: str, code_content: str):
        """Store code block content for copying"""
        if not hasattr(self, '_code_blocks'):
            self._code_blocks = {}
        # Clean up HTML entities
        clean_content = html.unescape(code_content)
        self._code_blocks[block_id] = clean_content
    
    def copy_text_to_clipboard(self, text: str):
        """Copy text to system clipboard"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")
    
    def show_context_menu(self, position):
        """Show context menu for chat display"""
        from PySide6.QtWidgets import QMenu
        
        menu = QMenu(self.chat_display)
        
        # Get the cursor position and text
        cursor = self.chat_display.cursorForPosition(position)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        
        # Check if we're clicking on a code block
        cursor_html = cursor.selection().toHtml()
        
        # Look for code block data attribute in the HTML around cursor
        full_html = self.chat_display.toHtml()
        cursor_pos = cursor.position()
        
        # Find any code blocks in the document
        code_block_action = None
        if hasattr(self, '_code_blocks') and self._code_blocks:
            for block_id, code_content in self._code_blocks.items():
                if f'data-code-block="{block_id}"' in full_html:
                    code_block_action = menu.addAction(f"📋 Copy Code Block")
                    code_block_action.triggered.connect(lambda checked, content=code_content: self.copy_text_to_clipboard(content))
                    break
        
        # Add standard copy action for selected text
        if cursor.hasSelection():
            copy_action = menu.addAction("📄 Copy Selected Text")
            copy_action.triggered.connect(lambda: self.copy_text_to_clipboard(cursor.selectedText()))
        
        # Add copy all action
        copy_all_action = menu.addAction("📋 Copy All Chat")
        copy_all_action.triggered.connect(lambda: self.copy_text_to_clipboard(self.chat_display.toPlainText()))
        
        # Show menu if it has actions
        if menu.actions():
            menu.exec(self.chat_display.mapToGlobal(position))

    def add_welcome_message(self):
        """Add welcome message to chat"""
        preset_info = self.database.get_preset(self.current_preset)
        if preset_info:
            preset_desc = preset_info.get('description', 'AI Assistant')
            model_name = preset_info.get('model', 'OpenAI')
        else:
            preset_desc = "AI Assistant"
            model_name = "OpenAI"
        
        welcome_msg = f"""🤖 **{preset_desc}**

*Mode: {self.current_preset}* | *Model: {model_name}*

Hello! I'm ready to help you. What would you like to know or discuss?
"""
        self.add_message("AI", welcome_msg, "ai")
        
    def add_message(self, sender, message, message_type="system"):
        """Add a message to the chat display with enhanced formatting"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Define colors and alignment based on message type
        if message_type == "user" or sender == "You":
            bg_color = "#2a4d3a"  # Green-ish for user
            text_align = "right"
            margin_left = "60px"
            margin_right = "10px"
            sender_color = "#9acd32"
        elif message_type == "ai" or sender == "AI":
            bg_color = "#3a3a4d"  # Blue-ish for AI
            text_align = "left"
            margin_left = "10px"
            margin_right = "60px"
            sender_color = "#87ceeb"
        else:  # system messages
            bg_color = "#4d3a3a"  # Red-ish for system
            text_align = "center"
            margin_left = "20px"
            margin_right = "20px"
            sender_color = "#ffa07a"
        
        # Format message content with markdown
        if message_type in ["ai", "system"] or sender in ["AI", "System"]:
            formatted_content = self.format_message_content(message)
        else:
            # For user messages, use basic formatting to preserve their input
            formatted_content = self.basic_format_content(message)
        
        # Create the message HTML with proper structure for QTextEdit
        formatted_message = f"""
<div style="margin: 15px 0; clear: both;">
    <div style="
        background: {bg_color};
        border-radius: 12px;
        padding: 12px 16px;
        margin-left: {margin_left};
        margin-right: {margin_right};
        border-left: 3px solid {sender_color};
    ">
        <p style="margin: 0 0 8px 0;">
            <strong style="
                color: {sender_color};
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            ">{sender}</strong>
            <span style="
                color: #888;
                font-size: 10px;
                font-family: monospace;
                float: right;
            ">{timestamp}</span>
        </p>
        <div style="
            color: #e0e0e0;
            line-height: 1.5;
            word-wrap: break-word;
            clear: both;
        ">
            {formatted_content}
        </div>
    </div>
</div><br>
"""
        
        # Add to chat display with proper cursor handling
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(formatted_message)
        
        # Ensure cursor is at the end
        cursor.movePosition(QTextCursor.MoveOperation.End)
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
        
        # Handle collaborative mode
        if self.is_collaborative_mode:
            if self.get_current_state() == 'collaborative_mode':
                self.collaborative_message_sent()  # collaborative_mode -> collaborative_processing
            
            # Add user message
            self.add_message("You", message, "user")
            
            # Show "thinking" message
            self.add_message("AI", "🤔 Thinking...", "ai")
            self.update_status("Processing collaborative request...")
            
            # Send collaborative message
            self.send_collaborative_message(message)
            return
        
        # Regular chat mode
        if self.get_current_state() == 'waiting_for_input':
            self.message_sent()  # waiting_for_input -> processing
        
        # Add user message
        self.add_message("You", message, "user")
        
        # Show "thinking" message
        self.add_message("AI", "🤔 Thinking...", "ai")
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
        self.add_message("AI", response, "ai")
        
        # Update conversation ID if this was a new conversation
        if "conversation_id" in metadata:
            self.current_conversation_id = metadata["conversation_id"]
        
        # Update state and status
        self.response_received()
        self.update_status(f"Response from {model_used}")
        
        # Auto-summarize and add to embeddings if conversation is long enough
        if self.current_conversation_id:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            
            # Always summarize after significant interaction (3+ messages)
            if len(messages) >= 3:
                # Check if we need to update the summary
                should_update_summary = False
                
                # Get existing summary
                existing_summary = self.embeddings.get_conversation_summary(self.current_conversation_id)
                
                if not existing_summary:
                    # No summary exists, create one
                    should_update_summary = True
                    print(f"🔍 Creating new summary for conversation {self.current_conversation_id[:8]} with {len(messages)} messages")
                else:
                    # Summary exists, check if it needs updating
                    existing_msg_count = existing_summary.get('metadata', {}).get('message_count', 0)
                    
                    # Update if we have significantly more messages (every 5 new messages)
                    if len(messages) >= existing_msg_count + 5:
                        should_update_summary = True
                        print(f"🔍 Updating summary for conversation {self.current_conversation_id[:8]} ({existing_msg_count} -> {len(messages)} messages)")
                
                if should_update_summary:
                    self.auto_summarize_conversation()
    
    def handle_ai_error(self, error):
        """Handle AI error"""
        # Remove the "thinking" message
        self.remove_last_message()
        
        # Add error message
        self.add_message("AI", f"❌ Error: {error}", "ai")
        
        # Update state
        self.error_occurred_sm()
        self.update_status("Error occurred")
    
    def remove_last_message(self):
        """Remove the last message from chat display"""
        # Get current content
        content = self.chat_display.toHtml()
        
        # Find and remove the last message div (with <br> prefix)
        last_br_div_start = content.rfind('<br><div style="margin: 15px 0; clear: both;">')
        if last_br_div_start != -1:
            # Find the end of the message (including trailing <br>)
            div_count = 0
            pos = last_br_div_start + 4  # Skip the initial <br>
            while pos < len(content):
                if content[pos:pos+4] == '<div':
                    div_count += 1
                elif content[pos:pos+6] == '</div>':
                    div_count -= 1
                    if div_count == 0:
                        # Look for the trailing <br>
                        end_pos = pos + 6
                        if content[end_pos:end_pos+4] == '<br>':
                            end_pos += 4
                        new_content = content[:last_br_div_start] + content[end_pos:]
                        self.chat_display.setHtml(new_content)
                        break
                pos += 1
        else:
            # Fallback: try without the <br> prefix
            last_div_start = content.rfind('<div style="margin: 15px 0; clear: both;">')
            if last_div_start != -1:
                div_count = 0
                pos = last_div_start
                while pos < len(content):
                    if content[pos:pos+4] == '<div':
                        div_count += 1
                    elif content[pos:pos+6] == '</div>':
                        div_count -= 1
                        if div_count == 0:
                            new_content = content[:last_div_start] + content[pos+6:]
                            self.chat_display.setHtml(new_content)
                            break
                    pos += 1
    
    def auto_summarize_conversation(self):
        """Auto-summarize conversation and add to embeddings"""
        if not self.current_conversation_id:
            print("🔍 Auto-summarization skipped: No current conversation ID")
            return
        
        try:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            print(f"🔍 Auto-summarizing conversation {self.current_conversation_id[:8]} with {len(messages)} messages")
            
            summary = self.ai_client.summarize_conversation(messages)
            
            if summary:
                print(f"🔍 Generated summary: {summary[:100]}...")
                
                # Update database summary
                self.database.update_conversation_summary(self.current_conversation_id, summary)
                print(f"🔍 Updated database summary")
                
                # Add to embeddings
                result = self.embeddings.add_conversation_summary(
                    self.current_conversation_id, 
                    summary,
                    {"preset": self.current_preset, "message_count": len(messages)}
                )
                print(f"🔍 Added to embeddings: {result}")
                
                # Verify it was added
                stored_summary = self.embeddings.get_conversation_summary(self.current_conversation_id)
                if stored_summary:
                    print(f"🔍 ✅ Verified embeddings storage: {stored_summary['summary'][:50]}...")
                else:
                    print(f"🔍 ❌ Failed to verify embeddings storage")
                
                self.update_status("Conversation summarized")
            else:
                print(f"🔍 ❌ Failed to generate summary")
                
        except Exception as e:
            print(f"Auto-summarization failed: {e}")
            import traceback
            traceback.print_exc()
    
    def auto_summarize_collaborative_session(self):
        """Auto-summarize collaborative session including text content"""
        if not self.current_conversation_id or not self.current_session_id:
            return
        
        try:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            session = self.database.get_collaborative_session(self.current_session_id)
            
            if not session:
                return
            
            current_text = session["current_text"]
            
            # Create enhanced summary that includes text content
            summary_prompt = f"""
Summarize this collaborative AI session briefly, including both the conversation and the current state of the text document:

CONVERSATION ({len(messages)} messages):
{chr(10).join([f"{msg['role']}: {msg['content'][:200]}..." for msg in messages[-10:]])}

CURRENT TEXT DOCUMENT:
{current_text[:500]}...

Provide a concise summary (max 200 words) that captures:
1. What the conversation was about
2. What kind of text was being worked on
3. Key edits or improvements made
"""
            
            summary = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "Summarize collaborative AI sessions concisely."},
                    {"role": "user", "content": summary_prompt}
                ],
                model="gpt-4.1-mini",
                temperature=0.3
            )
            
            if summary and summary.get("content"):
                summary_text = summary["content"]
                
                # Update database summary
                self.database.update_conversation_summary(self.current_conversation_id, summary_text)
                
                # Add to embeddings with collaborative metadata
                self.embeddings.add_conversation_summary(
                    self.current_conversation_id,
                    summary_text,
                    {
                        "preset": self.current_preset,
                        "message_count": len(messages),
                        "has_collaborative_session": True,
                        "session_id": self.current_session_id,
                        "text_length": len(current_text),
                        "collaborative_summary": True
                    }
                )
                
                self.update_status("Collaborative session summarized")
                
        except Exception as e:
            print(f"Collaborative auto-summarization failed: {e}")
    
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
            # Prevent user from closing manually - just minimize instead
            event.ignore()
            if not self.is_minimized:
                self.toggle_minimize()
            print("ℹ️ AI Chat minimized instead of closed (use Ctrl+U to toggle)")

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
                    
                    # Quick check for recent conversations that might need summarization
                    self.update_status("Checking recent conversations...")
                    self.check_recent_conversations_for_summaries()
                    self.update_status("✅ Ready")
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
    
    def check_recent_conversations_for_summaries(self):
        """Lightweight check for recent conversations that might need summarization"""
        try:
            # Only check the 10 most recent conversations
            recent_conversations = self.database.get_conversations(10)
            missing_summaries = 0
            
            for conv in recent_conversations:
                conv_id = conv['id']
                
                # Quick check if this conversation has an embedding
                existing_summary = self.embeddings.get_conversation_summary(conv_id)
                if not existing_summary:
                    # Check if it has enough messages to warrant summarization
                    messages = self.database.get_conversation_messages(conv_id)
                    if len(messages) >= 3:
                        missing_summaries += 1
            
            if missing_summaries > 0:
                print(f"ℹ️  Found {missing_summaries} recent conversations without summaries")
                print(f"ℹ️  Run 'python migrate_conversations_to_search.py' to enable semantic search")
            
        except Exception as e:
            print(f"Warning: Could not check recent conversations: {e}")
    
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
                
        elif current_state == 'collaborative_mode':
            self.message_input.setEnabled(True)
            self.message_input.setPlaceholderText("Collaborate with AI on the text...")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(True)
            if hasattr(self, 'collaborative_editor'):
                self.collaborative_editor.set_editing_enabled(True)
                
        elif current_state == 'collaborative_processing':
            self.message_input.setEnabled(False)
            self.message_input.setPlaceholderText("AI is processing...")
            if hasattr(self, 'send_btn'):
                self.send_btn.setEnabled(False)
            if hasattr(self, 'collaborative_editor'):
                self.collaborative_editor.set_editing_enabled(False)
    
    def show_setup_message(self):
        """Show API key setup message"""
        if hasattr(self, 'chat_display'):
            setup_msg = """🔑 <b>API Key Setup Required</b>

To use the AI assistant, you need to provide your OpenAI API key.

Click the Settings button (⚙️) in the title bar to get started.

<i>Your API key will be stored securely on your machine.</i>
"""
            self.add_message("System", setup_msg, "system")
    
    def show_invalid_key_message(self):
        """Show invalid API key message"""
        if hasattr(self, 'chat_display'):
            invalid_msg = """❌ <b>Invalid API Key</b>

Your stored OpenAI API key appears to be invalid or has been revoked.

Click the Settings button (⚙️) to update your API key.

<i>Please verify your API key at https://platform.openai.com/api-keys</i>
"""
            self.add_message("System", invalid_msg, "system")
    
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
            self.add_message("System", error_msg, "system")
    
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
    
    def update_welcome_message_if_needed(self):
        """Update welcome message if we're in a new conversation or only have welcome message"""
        try:
            # Check if we should update the welcome message
            should_update = False
            
            if not self.current_conversation_id:
                # New conversation - always update
                should_update = True
            else:
                # Check if conversation only has system/AI messages (no user messages yet)
                messages = self.database.get_conversation_messages(self.current_conversation_id)
                user_messages = [msg for msg in messages if msg["role"] == "user"]
                if len(user_messages) == 0:
                    should_update = True
            
            if should_update:
                # Check if the current chat only has a welcome message by looking at HTML content
                content = self.chat_display.toPlainText().strip()
                
                # If content looks like a welcome message (contains mode info), update it
                if ("Mode:" in content and "Hello! I'm ready to help" in content) or not content:
                    self.chat_display.clear()
                    self.add_welcome_message()
                    
        except Exception as e:
            print(f"Error updating welcome message: {e}")
            # Fallback - just clear and add new welcome message for new conversations
            if not self.current_conversation_id:
                self.chat_display.clear()
                self.add_welcome_message()

    def on_preset_changed(self, preset_name):
        """Handle preset change"""
        if preset_name:
            self.current_preset = preset_name
            self.update_status(f"Mode: {preset_name}")
            # Update the welcome message if this is a new conversation or conversation has only welcome message
            self.update_welcome_message_if_needed()
    
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
            
            # Exit collaborative mode if active
            if self.is_collaborative_mode:
                self.exit_collaborative_mode()
            
            # Check if conversation has collaborative session
            collab_session = self.database.get_collaborative_session_by_conversation(conversation_id)
            if collab_session:
                self.current_session_id = collab_session["id"]
                # Auto-enter collaborative mode
                self.enter_collaborative_mode()
                # Load the collaborative text
                self.collaborative_editor.set_text(collab_session["current_text"])
            
            # Load messages
            for msg in messages:
                sender = "You" if msg["role"] == "user" else "AI"
                message_type = "user" if msg["role"] == "user" else "ai"
                self.add_message(sender, msg["content"], message_type)
            
            # Check if this conversation needs to be summarized for semantic search
            if len(messages) >= 3:
                existing_summary = self.embeddings.get_conversation_summary(conversation_id)
                if not existing_summary:
                    print(f"🔍 Loaded conversation {conversation_id[:8]} needs summarization")
                    # Schedule summarization for this conversation
                    if collab_session:
                        summary = self.ai_client.summarize_conversation(messages)
                        if summary:
                            # Create enhanced summary for collaborative session
                            self.create_collaborative_summary(conversation_id, messages, collab_session["current_text"])
                    else:
                        summary = self.ai_client.summarize_conversation(messages)
                        if summary:
                            self.database.update_conversation_summary(conversation_id, summary)
                            self.embeddings.add_conversation_summary(
                                conversation_id, 
                                summary,
                                {"preset": "Default", "message_count": len(messages)}
                            )
                            print(f"🔍 ✅ Summarized loaded conversation {conversation_id[:8]}")
            
            status_msg = f"Loaded conversation: {conversation_id[:8]}..."
            if collab_session:
                status_msg += " (with collaborative session)"
            self.update_status(status_msg)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load conversation: {e}")
    
    def create_collaborative_summary(self, conversation_id, messages, current_text):
        """Create a summary specifically for collaborative sessions"""
        try:
            # Create enhanced summary that includes text content
            summary_prompt = f"""
Summarize this collaborative AI session briefly, including both the conversation and the current state of the text document:

CONVERSATION ({len(messages)} messages):
{chr(10).join([f"{msg['role']}: {msg['content'][:200]}..." for msg in messages[-10:]])}

CURRENT TEXT DOCUMENT:
{current_text[:500]}...

Provide a concise summary (max 200 words) that captures:
1. What the conversation was about
2. What kind of text was being worked on
3. Key edits or improvements made
"""
            
            summary = self.ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "Summarize collaborative AI sessions concisely."},
                    {"role": "user", "content": summary_prompt}
                ],
                model="gpt-4.1-mini",
                temperature=0.3
            )
            
            if summary and summary.get("content"):
                summary_text = summary["content"]
                
                # Update database summary
                self.database.update_conversation_summary(conversation_id, summary_text)
                
                # Add to embeddings with collaborative metadata
                self.embeddings.add_conversation_summary(
                    conversation_id,
                    summary_text,
                    {
                        "preset": "Default",
                        "message_count": len(messages),
                        "has_collaborative_session": True,
                        "session_id": self.current_session_id,
                        "text_length": len(current_text),
                        "collaborative_summary": True
                    }
                )
                
                print(f"🔍 ✅ Created collaborative summary for loaded conversation {conversation_id[:8]}")
                
        except Exception as e:
            print(f"❌ Failed to create collaborative summary: {e}")
    
    def start_new_conversation(self):
        """Start a new conversation"""
        # Ensure current conversation is summarized before starting new one
        if self.current_conversation_id:
            self.ensure_conversation_summarized(self.current_conversation_id)
        
        self.current_conversation_id = None
        self.current_session_id = None
        self.chat_display.clear()
        
        # Exit collaborative mode if active
        if self.is_collaborative_mode:
            self.toggle_collaborative_mode()
        
        if has_openai_api_key():
            self.add_welcome_message()
            self.update_status("Ready for new conversation")
        else:
            self.show_setup_message()
            self.update_status("API key required")
    
    def ensure_conversation_summarized(self, conversation_id):
        """Ensure a conversation is summarized before ending it"""
        try:
            messages = self.database.get_conversation_messages(conversation_id)
            
            # Only summarize if we have meaningful conversation
            if len(messages) >= 3:
                existing_summary = self.embeddings.get_conversation_summary(conversation_id)
                
                if not existing_summary:
                    print(f"🔍 Ensuring conversation {conversation_id[:8]} is summarized before ending")
                    
                    # Check if it's a collaborative session
                    collab_session = self.database.get_collaborative_session_by_conversation(conversation_id)
                    
                    if collab_session:
                        # Use collaborative summary
                        self.create_collaborative_summary(conversation_id, messages, collab_session["current_text"])
                    else:
                        # Use regular summary
                        summary = self.ai_client.summarize_conversation(messages)
                        if summary:
                            self.database.update_conversation_summary(conversation_id, summary)
                            self.embeddings.add_conversation_summary(
                                conversation_id,
                                summary,
                                {"preset": self.current_preset, "message_count": len(messages)}
                            )
                            print(f"🔍 ✅ Summarized conversation {conversation_id[:8]} before ending")
                else:
                    # Check if summary needs updating
                    existing_msg_count = existing_summary.get('metadata', {}).get('message_count', 0)
                    if len(messages) > existing_msg_count + 2:  # More lenient threshold for final summary
                        print(f"🔍 Updating final summary for conversation {conversation_id[:8]} ({existing_msg_count} -> {len(messages)} messages)")
                        
                        collab_session = self.database.get_collaborative_session_by_conversation(conversation_id)
                        
                        if collab_session:
                            self.create_collaborative_summary(conversation_id, messages, collab_session["current_text"])
                        else:
                            summary = self.ai_client.summarize_conversation(messages)
                            if summary:
                                self.database.update_conversation_summary(conversation_id, summary)
                                self.embeddings.update_conversation_summary(
                                    conversation_id,
                                    summary,
                                    {"preset": self.current_preset, "message_count": len(messages)}
                                )
                                print(f"🔍 ✅ Updated final summary for conversation {conversation_id[:8]}")
                
        except Exception as e:
            print(f"❌ Failed to ensure conversation summarized: {e}")
    
    def update_status(self, message):
        """Update status label"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(message)
    
    def ensure_splitter_proportions(self):
        """Ensure splitter maintains reasonable proportions for both sides"""
        if not self.is_collaborative_mode or not hasattr(self, 'main_splitter'):
            return
        
        current_sizes = self.main_splitter.sizes()
        if len(current_sizes) != 2:
            return
        
        total_width = sum(current_sizes)
        if total_width < 600:
            return
        
        chat_width, editor_width = current_sizes
        min_chat_width = 300
        min_editor_width = 250
        
        # If chat is too narrow, adjust
        if chat_width < min_chat_width:
            chat_width = min_chat_width
            editor_width = total_width - chat_width
            
        # If editor is too narrow, adjust
        if editor_width < min_editor_width:
            editor_width = min_editor_width
            chat_width = total_width - editor_width
            
        # Apply the corrected sizes
        if chat_width != current_sizes[0] or editor_width != current_sizes[1]:
            self.main_splitter.setSizes([chat_width, editor_width])
    
    def toggle_collaborative_mode(self):
        """Toggle collaborative text editing mode"""
        if not has_openai_api_key():
            self.show_api_key_dialog()
            return
        
        if not self.is_collaborative_mode:
            # Enter collaborative mode
            self.enter_collaborative_mode()
        else:
            # Exit collaborative mode
            self.exit_collaborative_mode()
    
    def enter_collaborative_mode(self):
        """Enter collaborative text editing mode"""
        try:
            # Ensure we have a conversation
            if not self.current_conversation_id:
                self.current_conversation_id = self.database.create_conversation(
                    "Collaborative Session", self.current_preset
                )
            
            # Create or get collaborative session
            existing_session = self.database.get_collaborative_session_by_conversation(
                self.current_conversation_id
            )
            
            if existing_session:
                self.current_session_id = existing_session["id"]
                # Load existing text
                self.collaborative_editor.set_text(existing_session["current_text"])
            else:
                # Create new session
                self.current_session_id = self.database.create_collaborative_session(
                    self.current_conversation_id, "Collaborative Text"
                )
                self.collaborative_editor.set_text("")
            
            # Setup editor with session data
            self.collaborative_editor.set_session_data(self.current_session_id, self.database)
            
            # Show the editor and update layout
            self.collaborative_editor.setVisible(True)
            self.main_splitter.setSizes([1, 1])  # Equal sizes
            
            # Update state and UI
            self.is_collaborative_mode = True
            self.enter_collaborative()
            self.collab_btn.setText("📄 Exit Collab")
            self.collab_btn.setToolTip("Exit collaborative text editing mode")
            
            # Update window size for split view and ensure proper proportions
            current_width = self.width()
            if current_width < 800:
                self.resize(800, self.height())
            
            # Set better proportions for collaborative mode
            # Give more space to text editor, but ensure chat has minimum
            QTimer.singleShot(100, lambda: self.main_splitter.setSizes([400, 350]))
            QTimer.singleShot(200, self.ensure_splitter_proportions)
            
            self.add_message("System", "🎯 **Collaborative Mode Activated**\n\nYou can now edit text on the left while chatting with AI on the right. The AI can see and edit your text based on your instructions.", "system")
            self.update_status("Collaborative mode active")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to enter collaborative mode: {e}")
    
    def exit_collaborative_mode(self):
        """Exit collaborative text editing mode"""
        try:
            # Hide editor and reset layout
            self.collaborative_editor.setVisible(False)
            self.main_splitter.setSizes([1, 0])  # Chat takes full width
            
            # Update state and UI
            self.is_collaborative_mode = False
            self.exit_collaborative()
            self.collab_btn.setText("📝 Collab")
            self.collab_btn.setToolTip("Toggle collaborative text editing mode")
            
            # Save current session state
            if self.current_session_id and self.collaborative_editor:
                current_text = self.collaborative_editor.get_text()
                self.database.update_collaborative_session_text(
                    self.current_session_id, current_text, 'user_edit', 'Session paused'
                )
            
            self.add_message("System", "📄 **Collaborative Mode Deactivated**\n\nText editing session has been saved and can be resumed later.", "system")
            self.update_status("Collaborative mode deactivated")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to exit collaborative mode: {e}")
    
    def on_text_changed(self, text):
        """Handle text changes from the collaborative editor"""
        if not self.is_collaborative_mode or not self.current_session_id:
            return
        
        try:
            # Save text changes to database
            self.database.update_collaborative_session_text(
                self.current_session_id, text, 'user_edit', 'User text edit'
            )
        except Exception as e:
            print(f"Error saving text changes: {e}")
    
    def send_collaborative_message(self, message):
        """Send a message in collaborative mode"""
        if not self.current_conversation_id or not self.current_session_id:
            self.handle_ai_error("No active collaborative session")
            return
        
        # Get current text from editor
        current_text = self.collaborative_editor.get_text()
        
        # Create collaborative AI worker
        self.collaborative_worker = AIWorkerThread(
            message=message,
            conversation_id=self.current_conversation_id,
            preset_name=self.current_preset,
            is_collaborative=True,
            current_text=current_text
        )
        
        # Connect signals
        self.collaborative_worker.collaborative_response_ready.connect(self.handle_collaborative_response)
        self.collaborative_worker.error_occurred.connect(self.handle_collaborative_error)
        
        # Start processing
        self.collaborative_worker.start()
    
    def handle_collaborative_response(self, response, text_edit, edit_description, model_used, metadata):
        """Handle collaborative AI response"""
        # Remove the "thinking" message
        self.remove_last_message()
        
        # Add AI response
        self.add_message("AI", response, "ai")
        
        # Apply text edit if provided
        if text_edit:
            # Store current splitter sizes to maintain proportions
            current_sizes = self.main_splitter.sizes()
            
            self.collaborative_editor.set_text(text_edit, is_ai_edit=True)
            self.collaborative_editor.update_edit_info(edit_description or "AI edit")
            
            # Restore splitter sizes after a brief delay to prevent chat from shrinking
            if current_sizes and len(current_sizes) == 2:
                QTimer.singleShot(50, lambda: self.main_splitter.setSizes(current_sizes))
                QTimer.singleShot(100, self.ensure_splitter_proportions)
            
            # Save the edit to database
            if self.current_session_id:
                try:
                    self.database.update_collaborative_session_text(
                        self.current_session_id, text_edit, 'ai_edit', edit_description
                    )
                except Exception as e:
                    print(f"Error saving AI text edit: {e}")
        
        # Update state and status
        self.collaborative_response_received()
        status_msg = f"Response from {model_used}"
        if text_edit:
            status_msg += " (with text edit)"
        self.update_status(status_msg)
        
        # Auto-summarize collaborative session if conversation is long enough
        if self.current_conversation_id:
            messages = self.database.get_conversation_messages(self.current_conversation_id)
            
            # Always summarize after significant interaction (3+ messages)
            if len(messages) >= 3:
                # Check if we need to update the summary
                should_update_summary = False
                
                # Get existing summary
                existing_summary = self.embeddings.get_conversation_summary(self.current_conversation_id)
                
                if not existing_summary:
                    # No summary exists, create one
                    should_update_summary = True
                    print(f"🔍 Creating new collaborative summary for conversation {self.current_conversation_id[:8]} with {len(messages)} messages")
                else:
                    # Summary exists, check if it needs updating
                    existing_msg_count = existing_summary.get('metadata', {}).get('message_count', 0)
                    
                    # Update if we have significantly more messages (every 5 new messages)
                    if len(messages) >= existing_msg_count + 5:
                        should_update_summary = True
                        print(f"🔍 Updating collaborative summary for conversation {self.current_conversation_id[:8]} ({existing_msg_count} -> {len(messages)} messages)")
                
                if should_update_summary:
                    self.auto_summarize_collaborative_session()
    
    def handle_collaborative_error(self, error):
        """Handle collaborative AI error"""
        # Remove the "thinking" message
        self.remove_last_message()
        
        # Add error message
        self.add_message("AI", f"❌ Error: {error}", "ai")
        
        # Update state
        self.collaborative_error()
        self.update_status("Error in collaborative mode")
    
