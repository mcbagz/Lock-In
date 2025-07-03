"""
AI Client for LockIn
OpenAI API wrapper with conversation management and error handling
"""

import openai
from openai import OpenAI
from typing import List, Dict, Any, Optional, Iterator, AsyncIterator
import time
import json
from pathlib import Path
import asyncio
from datetime import datetime

from .ai_security import AISecurityManager
from .ai_database import AIDatabase


class AIClient:
    def __init__(self):
        """Initialize the AI client"""
        self.security_manager = AISecurityManager()
        self.database = AIDatabase()
        self._client = None
        self._last_api_key_check = 0
        self._api_key_check_interval = 300  # 5 minutes
        
    def _get_client(self) -> Optional[OpenAI]:
        """Get or create OpenAI client with current API key"""
        current_time = time.time()
        
        # Check if we need to refresh the client
        if (self._client is None or 
            current_time - self._last_api_key_check > self._api_key_check_interval):
            
            api_key = self.security_manager.get_api_key("openai")
            if not api_key:
                return None
            
            try:
                self._client = OpenAI(api_key=api_key)
                self._last_api_key_check = current_time
            except Exception as e:
                print(f"Error creating OpenAI client: {e}")
                return None
        
        return self._client
    
    def validate_api_key(self, api_key: str = None) -> bool:
        """Validate the OpenAI API key"""
        try:
            if api_key:
                client = OpenAI(api_key=api_key)
            else:
                client = self._get_client()
                if not client:
                    return False
            
            # Try a simple API call to validate
            response = client.models.list()
            return True
            
        except Exception as e:
            print(f"API key validation failed: {e}")
            return False
    
    def set_api_key(self, api_key: str) -> bool:
        """Set and validate a new API key"""
        if not self.security_manager.validate_api_key_format("openai", api_key):
            return False
        
        if not self.validate_api_key(api_key):
            return False
        
        if self.security_manager.store_api_key("openai", api_key):
            self._client = None  # Force client refresh
            return True
        
        return False
    
    def has_valid_api_key(self) -> bool:
        """Check if we have a valid API key"""
        return self.security_manager.has_api_key("openai") and self.validate_api_key()
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        client = self._get_client()
        if not client:
            return []
        
        try:
            models = client.models.list()
            # Filter to chat models only
            chat_models = [
                model.id for model in models.data 
                if any(prefix in model.id for prefix in ["gpt-", "o3-"])
            ]
            return sorted(chat_models)
        except Exception as e:
            print(f"Error getting models: {e}")
            return ["gpt-4.1-mini", "gpt-4.1", "o3-mini"]  # Fallback list
    
    def chat_completion(self, messages: List[Dict[str, str]], model: str = "gpt-4.1-mini", 
                       temperature: float = 0.7, max_tokens: int = None) -> Optional[Dict[str, Any]]:
        """Get a chat completion from OpenAI"""
        client = self._get_client()
        if not client:
            raise ValueError("No valid OpenAI API key available")
        
        try:
            # Prepare parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Special handling for o3 models
            if model.startswith("o3"):
                # o3 models don't support temperature or system messages
                params.pop("temperature", None)
                # Remove system messages for o3 models
                params["messages"] = [msg for msg in messages if msg.get("role") != "system"]
            
            response = client.chat.completions.create(**params)
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "finish_reason": response.choices[0].finish_reason
            }
            
        except Exception as e:
            print(f"Error in chat completion: {e}")
            raise
    
    def stream_chat_completion(self, messages: List[Dict[str, str]], model: str = "gpt-4.1-mini", 
                              temperature: float = 0.7) -> Iterator[str]:
        """Stream a chat completion from OpenAI"""
        client = self._get_client()
        if not client:
            raise ValueError("No valid OpenAI API key available")
        
        try:
            # Prepare parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }
            
            # Special handling for o3 models
            if model.startswith("o3"):
                params.pop("temperature", None)
                params["messages"] = [msg for msg in messages if msg.get("role") != "system"]
            
            stream = client.chat.completions.create(**params)
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error in streaming chat completion: {e}")
            raise
    
    def summarize_conversation(self, messages: List[Dict[str, str]], max_length: int = 200) -> Optional[str]:
        """Generate a summary of a conversation"""
        if not messages:
            return None
        
        # Create a summary prompt
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in messages
        ])
        
        summary_messages = [
            {
                "role": "system",
                "content": f"Summarize the following conversation in {max_length} characters or less. Focus on the main topics and key points discussed."
            },
            {
                "role": "user",
                "content": conversation_text
            }
        ]
        
        try:
            response = self.chat_completion(
                messages=summary_messages,
                model="gpt-4.1-mini",  # Use fast model for summaries
                temperature=0.3,
                max_tokens=100
            )
            
            return response["content"] if response else None
            
        except Exception as e:
            print(f"Error summarizing conversation: {e}")
            return None
    
    def process_conversation_message(self, conversation_id: str, user_message: str, 
                                   preset_name: str = "Default") -> Optional[Dict[str, Any]]:
        """Process a user message in the context of a conversation"""
        try:
            # Get preset configuration
            preset = self.database.get_preset(preset_name)
            if not preset:
                preset = self.database.get_preset("Default")
                if not preset:
                    raise ValueError("No default preset available")
            
            # Get conversation history
            conversation_messages = self.database.get_conversation_messages(conversation_id)
            
            # Build messages for API
            api_messages = []
            
            # Add system message if not o3 model
            if not preset["model"].startswith("o3"):
                api_messages.append({
                    "role": "system",
                    "content": preset["system_prompt"]
                })
            
            # Add conversation history
            for msg in conversation_messages:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message
            api_messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Get response from OpenAI
            response = self.chat_completion(
                messages=api_messages,
                model=preset["model"],
                temperature=preset.get("settings", {}).get("temperature", 0.7)
            )
            
            if not response:
                return None
            
            # Store messages in database
            self.database.add_message(conversation_id, "user", user_message)
            self.database.add_message(
                conversation_id, 
                "assistant", 
                response["content"], 
                response["model"]
            )
            
            return {
                "response": response["content"],
                "model_used": response["model"],
                "usage": response["usage"],
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            print(f"Error processing conversation message: {e}")
            return None
    
    def start_new_conversation(self, initial_message: str, preset_name: str = "Default", 
                              title: str = None) -> Optional[str]:
        """Start a new conversation"""
        try:
            # Generate title if not provided
            if not title:
                title = self._generate_conversation_title(initial_message)
            
            # Create conversation in database
            conversation_id = self.database.create_conversation(title, preset_name)
            
            # Process the initial message
            result = self.process_conversation_message(conversation_id, initial_message, preset_name)
            
            if result:
                return conversation_id
            else:
                # Clean up failed conversation
                self.database.delete_conversation(conversation_id)
                return None
                
        except Exception as e:
            print(f"Error starting new conversation: {e}")
            return None
    
    def _generate_conversation_title(self, initial_message: str) -> str:
        """Generate a title for a conversation based on the initial message"""
        try:
            title_messages = [
                {
                    "role": "system",
                    "content": "Generate a short, descriptive title (5 words or less) for a conversation that starts with this message:"
                },
                {
                    "role": "user",
                    "content": initial_message[:200]  # Truncate long messages
                }
            ]
            
            response = self.chat_completion(
                messages=title_messages,
                model="gpt-4.1-nano",
                temperature=0.5,
                max_tokens=20
            )
            
            if response:
                title = response["content"].strip().strip('"\'')
                return title[:50]  # Limit title length
            
        except Exception as e:
            print(f"Error generating conversation title: {e}")
        
        # Fallback title
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"Conversation {timestamp}"
    
    def get_conversation_response(self, conversation_id: str, message: str) -> Optional[str]:
        """Get a response for a message in an existing conversation"""
        result = self.process_conversation_message(conversation_id, message)
        return result["response"] if result else None
    
    def continue_conversation(self, conversation_id: str, message: str) -> Optional[Dict[str, Any]]:
        """Continue an existing conversation with a new message"""
        return self.process_conversation_message(conversation_id, message)
    
    def process_collaborative_message(self, conversation_id: str, user_message: str, 
                                    current_text: str, preset_name: str = "Default") -> Optional[Dict[str, Any]]:
        """Process a user message in collaborative mode with text context"""
        try:
            # Get preset configuration
            preset = self.database.get_preset(preset_name)
            if not preset:
                preset = self.database.get_preset("Default")
                if not preset:
                    raise ValueError("No default preset available")
            
            # Get conversation history
            conversation_messages = self.database.get_conversation_messages(conversation_id)
            
            # Build enhanced system prompt for collaborative mode
            collaborative_system_prompt = f"""
{preset["system_prompt"]}

You are now in collaborative text editing mode. The user has a text document that you can both read and edit. 

Current text document content:
---
{current_text}
---

IMPORTANT INSTRUCTIONS:
1. You can respond with a message, edit the text, or both
2. If you want to edit the text, include your response in this JSON format:
   {{"message": "Your explanation here", "text_edit": "The complete new text content", "edit_description": "Brief description of what you changed"}}
3. If you only want to respond without editing, respond normally
4. Always be helpful and explain your changes clearly
5. The user can see the current text and will see your edits immediately
6. Focus on being collaborative - ask questions, suggest improvements, and work together

The user's message might be about the text content, a request to edit it, or a general question.
"""
            
            # Build messages for API
            api_messages = []
            
            # Add system message if not o3 model
            if not preset["model"].startswith("o3"):
                api_messages.append({
                    "role": "system",
                    "content": collaborative_system_prompt
                })
            
            # Add recent conversation history (last 10 messages to keep context manageable)
            recent_messages = conversation_messages[-10:] if len(conversation_messages) > 10 else conversation_messages
            for msg in recent_messages:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user message with text context
            user_message_with_context = f"""
User message: {user_message}

Current text document:
---
{current_text}
---
"""
            
            api_messages.append({
                "role": "user",
                "content": user_message_with_context
            })
            
            # Get response from OpenAI
            response = self.chat_completion(
                messages=api_messages,
                model=preset["model"],
                temperature=preset.get("settings", {}).get("temperature", 0.7)
            )
            
            if not response:
                return None
            
            # Parse response to check for text edits
            ai_response = response["content"]
            text_edit = None
            edit_description = None
            
            # Try to parse JSON response for text edits
            try:
                import json
                # Look for JSON in the response
                if ai_response.strip().startswith('{') and ai_response.strip().endswith('}'):
                    parsed = json.loads(ai_response)
                    if "text_edit" in parsed:
                        text_edit = parsed["text_edit"]
                        edit_description = parsed.get("edit_description", "AI edit")
                        ai_response = parsed.get("message", "I've made some changes to the text.")
                elif "```json" in ai_response:
                    # Extract JSON from markdown code block
                    json_start = ai_response.find("```json") + 7
                    json_end = ai_response.find("```", json_start)
                    if json_end > json_start:
                        json_str = ai_response[json_start:json_end].strip()
                        parsed = json.loads(json_str)
                        if "text_edit" in parsed:
                            text_edit = parsed["text_edit"]
                            edit_description = parsed.get("edit_description", "AI edit")
                            ai_response = parsed.get("message", "I've made some changes to the text.")
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as regular message
                pass
            
            # Store messages in database
            self.database.add_message(conversation_id, "user", user_message)
            self.database.add_message(
                conversation_id, 
                "assistant", 
                ai_response, 
                response["model"]
            )
            
            return {
                "response": ai_response,
                "text_edit": text_edit,
                "edit_description": edit_description,
                "model_used": response["model"],
                "usage": response["usage"],
                "conversation_id": conversation_id
            }
            
        except Exception as e:
            print(f"Error processing collaborative message: {e}")
            return None
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        # This would require tracking usage over time
        # For now, return basic info
        return {
            "has_api_key": self.has_valid_api_key(),
            "conversation_count": self.database.get_conversation_count(),
            "available_models": len(self.get_available_models())
        }


# Convenience functions
def quick_chat(message: str, preset_name: str = "Default") -> Optional[str]:
    """Quick chat without conversation persistence"""
    client = AIClient()
    if not client.has_valid_api_key():
        return None
    
    preset = client.database.get_preset(preset_name)
    if not preset:
        return None
    
    messages = []
    if not preset["model"].startswith("o3"):
        messages.append({
            "role": "system",
            "content": preset["system_prompt"]
        })
    
    messages.append({
        "role": "user",
        "content": message
    })
    
    try:
        response = client.chat_completion(messages, preset["model"])
        return response["content"] if response else None
    except:
        return None 