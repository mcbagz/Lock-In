"""
AI Module for LockIn
Enhanced AI functionality with OpenAI integration, conversation persistence, and semantic search
"""

from .ai_client import AIClient, quick_chat
from .ai_database import AIDatabase
from .ai_embeddings import AIEmbeddingsManager, search_conversations, add_conversation_to_search
from .ai_security import AISecurityManager, get_openai_api_key, store_openai_api_key, has_openai_api_key

__all__ = [
    'AIClient',
    'AIDatabase', 
    'AIEmbeddingsManager',
    'AISecurityManager',
    'quick_chat',
    'search_conversations',
    'add_conversation_to_search',
    'get_openai_api_key',
    'store_openai_api_key',
    'has_openai_api_key'
] 