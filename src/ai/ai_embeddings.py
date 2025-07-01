"""
AI Embeddings Manager for LockIn
Handles ChromaDB integration for semantic search of conversation summaries
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid
import json
from datetime import datetime
import hashlib


class AIEmbeddingsManager:
    def __init__(self, db_path: str = "config/chroma_db"):
        """Initialize the embeddings manager"""
        self.db_path = Path(db_path)
        self.db_path.mkdir(exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection for conversation summaries
        self.collection = self.client.get_or_create_collection(
            name="conversation_summaries",
            metadata={"description": "LockIn AI conversation summaries for semantic search"}
        )
    
    def add_conversation_summary(self, conversation_id: str, summary: str, metadata: Dict[str, Any] = None) -> bool:
        """Add a conversation summary to the embeddings database"""
        try:
            # Create document ID (use conversation_id for consistency)
            doc_id = conversation_id
            
            # Prepare metadata
            doc_metadata = {
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "summary_length": len(summary),
                **(metadata or {})
            }
            
            # Add to collection
            self.collection.add(
                documents=[summary],
                metadatas=[doc_metadata],
                ids=[doc_id]
            )
            
            return True
            
        except Exception as e:
            print(f"Error adding conversation summary to embeddings: {e}")
            return False
    
    def update_conversation_summary(self, conversation_id: str, new_summary: str, metadata: Dict[str, Any] = None) -> bool:
        """Update an existing conversation summary"""
        try:
            # Check if document exists
            existing = self.collection.get(ids=[conversation_id])
            
            if not existing['ids']:
                # Document doesn't exist, add it
                return self.add_conversation_summary(conversation_id, new_summary, metadata)
            
            # Update metadata
            doc_metadata = {
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "summary_length": len(new_summary),
                **(metadata or {})
            }
            
            # Update the document
            self.collection.update(
                ids=[conversation_id],
                documents=[new_summary],
                metadatas=[doc_metadata]
            )
            
            return True
            
        except Exception as e:
            print(f"Error updating conversation summary: {e}")
            return False
    
    def search_similar_conversations(self, query: str, n_results: int = 5, min_similarity: float = 0.5) -> List[Dict[str, Any]]:
        """Search for conversations similar to the query"""
        try:
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # Process results
            similar_conversations = []
            
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    # Calculate similarity score (ChromaDB uses distance, lower is more similar)
                    distance = results['distances'][0][i]
                    similarity = max(0, 1 - distance)  # Convert distance to similarity
                    
                    if similarity >= min_similarity:
                        similar_conversations.append({
                            "conversation_id": results['ids'][0][i],
                            "summary": results['documents'][0][i],
                            "metadata": results['metadatas'][0][i],
                            "similarity": similarity,
                            "distance": distance
                        })
            
            return similar_conversations
            
        except Exception as e:
            print(f"Error searching similar conversations: {e}")
            return []
    
    def search_by_keywords(self, keywords: List[str], n_results: int = 10) -> List[Dict[str, Any]]:
        """Search conversations by keywords"""
        # Create a query from keywords
        query = " ".join(keywords)
        return self.search_similar_conversations(query, n_results)
    
    def get_conversation_clusters(self, n_clusters: int = 5) -> List[List[str]]:
        """Get conversation clusters based on similarity"""
        try:
            # Get all conversations
            all_conversations = self.collection.get(include=["documents", "metadatas"])
            
            if not all_conversations['ids']:
                return []
            
            # For now, return a simple implementation
            # In a more advanced version, we could use clustering algorithms
            conversation_ids = all_conversations['ids']
            
            # Simple clustering by splitting into n groups
            cluster_size = max(1, len(conversation_ids) // n_clusters)
            clusters = []
            
            for i in range(0, len(conversation_ids), cluster_size):
                cluster = conversation_ids[i:i + cluster_size]
                clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            print(f"Error getting conversation clusters: {e}")
            return []
    
    def delete_conversation_summary(self, conversation_id: str) -> bool:
        """Delete a conversation summary from embeddings"""
        try:
            # Check if document exists
            existing = self.collection.get(ids=[conversation_id])
            
            if existing['ids']:
                self.collection.delete(ids=[conversation_id])
                return True
            
            return False
            
        except Exception as e:
            print(f"Error deleting conversation summary: {e}")
            return False
    
    def get_conversation_summary(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation summary"""
        try:
            result = self.collection.get(
                ids=[conversation_id],
                include=["documents", "metadatas"]
            )
            
            if result['ids']:
                return {
                    "conversation_id": conversation_id,
                    "summary": result['documents'][0],
                    "metadata": result['metadatas'][0]
                }
            
            return None
            
        except Exception as e:
            print(f"Error getting conversation summary: {e}")
            return None
    
    def get_all_conversations_count(self) -> int:
        """Get the total number of conversation summaries stored"""
        try:
            result = self.collection.count()
            return result
        except Exception as e:
            print(f"Error getting conversation count: {e}")
            return 0
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently added conversation summaries"""
        try:
            # Get all conversations and sort by timestamp
            all_conversations = self.collection.get(include=["documents", "metadatas"])
            
            if not all_conversations['ids']:
                return []
            
            # Combine data and sort by timestamp
            conversations = []
            for i in range(len(all_conversations['ids'])):
                metadata = all_conversations['metadatas'][i]
                conversations.append({
                    "conversation_id": all_conversations['ids'][i],
                    "summary": all_conversations['documents'][i],
                    "metadata": metadata,
                    "timestamp": metadata.get('timestamp', '1970-01-01T00:00:00')
                })
            
            # Sort by timestamp (newest first)
            conversations.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return conversations[:limit]
            
        except Exception as e:
            print(f"Error getting recent conversations: {e}")
            return []
    
    def cleanup_old_summaries(self, days: int = 90):
        """Clean up old conversation summaries"""
        try:
            # Get all conversations
            all_conversations = self.collection.get(include=["metadatas"])
            
            if not all_conversations['ids']:
                return
            
            # Find old conversations
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            ids_to_delete = []
            
            for i, conversation_id in enumerate(all_conversations['ids']):
                metadata = all_conversations['metadatas'][i]
                timestamp_str = metadata.get('timestamp', '1970-01-01T00:00:00')
                
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).timestamp()
                    if timestamp < cutoff_date:
                        ids_to_delete.append(conversation_id)
                except:
                    # If timestamp parsing fails, consider it old
                    ids_to_delete.append(conversation_id)
            
            # Delete old conversations
            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                print(f"Cleaned up {len(ids_to_delete)} old conversation summaries")
            
        except Exception as e:
            print(f"Error cleaning up old summaries: {e}")
    
    def export_embeddings(self, output_path: str) -> bool:
        """Export embeddings data to a JSON file"""
        try:
            all_data = self.collection.get(include=["documents", "metadatas"])
            
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "collection_name": self.collection.name,
                "conversations": []
            }
            
            for i in range(len(all_data['ids'])):
                export_data["conversations"].append({
                    "id": all_data['ids'][i],
                    "summary": all_data['documents'][i],
                    "metadata": all_data['metadatas'][i]
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error exporting embeddings: {e}")
            return False
    
    def import_embeddings(self, input_path: str) -> bool:
        """Import embeddings data from a JSON file"""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            conversations = import_data.get("conversations", [])
            
            for conv in conversations:
                self.add_conversation_summary(
                    conv["id"],
                    conv["summary"],
                    conv.get("metadata", {})
                )
            
            print(f"Imported {len(conversations)} conversation summaries")
            return True
            
        except Exception as e:
            print(f"Error importing embeddings: {e}")
            return False
    
    def reset_database(self) -> bool:
        """Reset the embeddings database (delete all data)"""
        try:
            self.client.delete_collection(name="conversation_summaries")
            self.collection = self.client.get_or_create_collection(
                name="conversation_summaries",
                metadata={"description": "LockIn AI conversation summaries for semantic search"}
            )
            return True
        except Exception as e:
            print(f"Error resetting embeddings database: {e}")
            return False


# Convenience functions
def search_conversations(query: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """Search for similar conversations using the default embeddings manager"""
    embeddings_manager = AIEmbeddingsManager()
    return embeddings_manager.search_similar_conversations(query, n_results)


def add_conversation_to_search(conversation_id: str, summary: str, metadata: Dict[str, Any] = None) -> bool:
    """Add a conversation summary to the search index"""
    embeddings_manager = AIEmbeddingsManager()
    return embeddings_manager.add_conversation_summary(conversation_id, summary, metadata) 