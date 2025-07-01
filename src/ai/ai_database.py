"""
AI Database Manager for LockIn
Handles SQLite operations for conversations, messages, and AI presets
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import uuid


class AIDatabase:
    def __init__(self, db_path: str = "config/ai_data.db"):
        """Initialize the AI database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    preset_mode TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0
                )
            """)
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    model_used TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                )
            """)
            
            # AI Presets table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    model TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    description TEXT,
                    is_custom BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    settings TEXT DEFAULT '{}'
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations (updated_at)")
            
            conn.commit()
            
        # Insert default presets if they don't exist
        self._insert_default_presets()
    
    def _insert_default_presets(self):
        """Insert default AI presets if they don't exist"""
        default_presets = [
            {
                "name": "Default",
                "model": "gpt-4.1-mini",
                "system_prompt": "You are a helpful AI assistant for the LockIn productivity app. Help users with their tasks, provide clear and useful information, and assist with productivity and focus.",
                "description": "Normal chat experience with balanced responses",
                "is_custom": False
            },
            {
                "name": "Brief", 
                "model": "gpt-4.1-mini",
                "system_prompt": "Provide concise, direct answers with no fluff. The user wants quick, accurate information. Be brief but complete.",
                "description": "Quick answers with no unnecessary detail",
                "is_custom": False
            },
            {
                "name": "Research",
                "model": "gpt-4.1-mini", 
                "system_prompt": "You are a research assistant. Provide thorough, well-researched responses with relevant sources and detailed explanations. Include citations and references when possible.",
                "description": "Detailed research with sources and summaries",
                "is_custom": False
            },
            {
                "name": "Learn",
                "model": "gpt-4.1-mini",
                "system_prompt": "You are a patient teacher. Explain topics clearly with examples, breaking down complex concepts into understandable parts. Adapt your explanations to the user's level of knowledge.",
                "description": "Educational explanations tailored to learning",
                "is_custom": False
            },
            {
                "name": "Solve",
                "model": "o3-mini",
                "system_prompt": "You are a problem-solving expert. Analyze complex problems systematically, break them down into steps, and provide clear solutions with reasoning.",
                "description": "Complex problem solving with step-by-step analysis",
                "is_custom": False
            }
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for preset in default_presets:
                cursor.execute("""
                    INSERT OR IGNORE INTO ai_presets (id, name, model, system_prompt, description, is_custom, settings)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()),
                    preset["name"],
                    preset["model"],
                    preset["system_prompt"],
                    preset["description"],
                    preset["is_custom"],
                    "{}"
                ))
            conn.commit()
    
    def create_conversation(self, title: str, preset_mode: str) -> str:
        """Create a new conversation and return its ID"""
        conversation_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (id, title, preset_mode)
                VALUES (?, ?, ?)
            """, (conversation_id, title, preset_mode))
            conn.commit()
        
        return conversation_id
    
    def add_message(self, conversation_id: str, role: str, content: str, model_used: str = None) -> str:
        """Add a message to a conversation and return message ID"""
        message_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert message
            cursor.execute("""
                INSERT INTO messages (id, conversation_id, role, content, model_used)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, conversation_id, role, content, model_used))
            
            # Update conversation's updated_at and message_count
            cursor.execute("""
                UPDATE conversations 
                SET updated_at = CURRENT_TIMESTAMP,
                    message_count = message_count + 1
                WHERE id = ?
            """, (conversation_id,))
            
            conn.commit()
        
        return message_id
    
    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, role, content, model_used, timestamp
                FROM messages 
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            
            return [
                {
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "model_used": row[3],
                    "timestamp": row[4]
                }
                for row in cursor.fetchall()
            ]
    
    def get_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent conversations"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, summary, preset_mode, created_at, updated_at, message_count
                FROM conversations 
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "summary": row[2],
                    "preset_mode": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "message_count": row[6]
                }
                for row in cursor.fetchall()
            ]
    
    def update_conversation_summary(self, conversation_id: str, summary: str):
        """Update conversation summary"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations 
                SET summary = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (summary, conversation_id))
            conn.commit()
    
    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
    
    def get_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Get an AI preset by name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, model, system_prompt, description, is_custom, settings
                FROM ai_presets 
                WHERE name = ?
            """, (name,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "model": row[2],
                    "system_prompt": row[3],
                    "description": row[4],
                    "is_custom": bool(row[5]),
                    "settings": json.loads(row[6] or "{}")
                }
        return None
    
    def get_all_presets(self) -> List[Dict[str, Any]]:
        """Get all AI presets"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, model, system_prompt, description, is_custom, settings
                FROM ai_presets 
                ORDER BY is_custom ASC, name ASC
            """)
            
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "model": row[2],
                    "system_prompt": row[3],
                    "description": row[4],
                    "is_custom": bool(row[5]),
                    "settings": json.loads(row[6] or "{}")
                }
                for row in cursor.fetchall()
            ]
    
    def create_preset(self, name: str, model: str, system_prompt: str, description: str = "", settings: Dict = None) -> str:
        """Create a new custom preset"""
        preset_id = str(uuid.uuid4())
        settings_json = json.dumps(settings or {})
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_presets (id, name, model, system_prompt, description, is_custom, settings)
                VALUES (?, ?, ?, ?, ?, TRUE, ?)
            """, (preset_id, name, model, system_prompt, description, settings_json))
            conn.commit()
        
        return preset_id
    
    def update_preset(self, preset_id: str, **kwargs):
        """Update an existing preset"""
        allowed_fields = ["name", "model", "system_prompt", "description", "settings"]
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == "settings" and isinstance(value, dict):
                    value = json.dumps(value)
                updates.append(f"{field} = ?")
                values.append(value)
        
        if updates:
            values.append(preset_id)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE ai_presets 
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, values)
                conn.commit()
    
    def delete_preset(self, preset_id: str):
        """Delete a custom preset (cannot delete default presets)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM ai_presets 
                WHERE id = ? AND is_custom = TRUE
            """, (preset_id,))
            conn.commit()
    
    def cleanup_old_conversations(self, days: int = 90):
        """Clean up conversations older than specified days"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM conversations 
                WHERE updated_at < datetime('now', '-{} days')
            """.format(days))
            conn.commit()
    
    def get_conversation_count(self) -> int:
        """Get total number of conversations"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM conversations")
            return cursor.fetchone()[0]
    
    def search_conversations(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search conversations by title or summary"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, summary, preset_mode, created_at, updated_at, message_count
                FROM conversations 
                WHERE title LIKE ? OR summary LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            
            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "summary": row[2],
                    "preset_mode": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "message_count": row[6]
                }
                for row in cursor.fetchall()
            ] 