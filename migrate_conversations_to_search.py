#!/usr/bin/env python3
"""
One-time migration script to add summaries and embeddings to existing conversations
Run this once to enable semantic search for all existing conversations.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent / 'src'))

from ai.ai_client import AIClient
from ai.ai_database import AIDatabase
from ai.ai_embeddings import AIEmbeddingsManager

def migrate_conversations_to_search():
    """Process all existing conversations and add summaries/embeddings for semantic search"""
    try:
        # Initialize components
        print("🔧 Initializing AI components...")
        database = AIDatabase()
        embeddings = AIEmbeddingsManager() 
        ai_client = AIClient()
        
        # Get all conversations
        conversations = database.get_conversations(1000)  # Get up to 1000 conversations
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        print(f"📊 Found {len(conversations)} total conversations to process...")
        
        for i, conv in enumerate(conversations, 1):
            conv_id = conv['id']
            
            print(f"🔍 [{i}/{len(conversations)}] Processing conversation {conv_id[:8]}...")
            
            # Check if already has embedding
            existing_summary = embeddings.get_conversation_summary(conv_id)
            if existing_summary:
                print(f"   ⏭️  Already has summary, skipping")
                skipped_count += 1
                continue
            
            # Get messages for this conversation
            messages = database.get_conversation_messages(conv_id)
            if len(messages) < 2:  # Skip very short conversations
                print(f"   ⏭️  Too short ({len(messages)} messages), skipping")
                skipped_count += 1
                continue
            
            try:
                # Generate summary
                print(f"   🤖 Generating summary for {len(messages)} messages...")
                summary = ai_client.summarize_conversation(messages)
                
                if summary:
                    # Update database
                    database.update_conversation_summary(conv_id, summary)
                    
                    # Check if it's a collaborative conversation
                    collab_session = database.get_collaborative_session_by_conversation(conv_id)
                    
                    # Add to embeddings with appropriate metadata
                    metadata = {
                        "preset": conv.get('preset_mode', 'Default'),
                        "message_count": len(messages),
                        "has_collaborative_session": bool(collab_session)
                    }
                    
                    if collab_session:
                        metadata["session_id"] = collab_session["id"]
                        metadata["text_length"] = len(collab_session.get("current_text", ""))
                        metadata["collaborative_summary"] = True
                        print(f"   📝 Found collaborative session with {metadata['text_length']} chars of text")
                    
                    result = embeddings.add_conversation_summary(conv_id, summary, metadata)
                    
                    if result:
                        processed_count += 1
                        conv_type = "collaborative" if collab_session else "regular"
                        print(f"   ✅ Successfully processed ({conv_type})")
                    else:
                        error_count += 1
                        print(f"   ❌ Failed to add to embeddings")
                else:
                    error_count += 1
                    print(f"   ❌ Failed to generate summary")
                    
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error processing: {e}")
        
        # Final results
        print(f"\n🎉 Migration Complete!")
        print(f"   ✅ Processed: {processed_count} conversations")
        print(f"   ⏭️  Skipped: {skipped_count} conversations")
        print(f"   ❌ Errors: {error_count} conversations")
        
        total_embeddings = embeddings.get_all_conversations_count()
        print(f"   📚 Total embeddings available: {total_embeddings}")
        
        print(f"\n🔍 Semantic search is now available for all processed conversations!")
        
        return processed_count
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    print("🚀 Starting conversation migration for semantic search...")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("src/ai"):
        print("❌ Error: Run this script from the Lock-In root directory")
        print("   Current directory:", os.getcwd())
        print("   Expected to find: src/ai/")
        sys.exit(1)
    
    # Run the migration
    processed = migrate_conversations_to_search()
    
    print("=" * 60)
    if processed > 0:
        print(f"✅ Migration successful! {processed} conversations processed.")
        print("🔍 You can now use semantic search in the History dialog.")
    else:
        print("⚠️  No conversations were processed. Check for errors above.") 