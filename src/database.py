import sqlite3
import os
import datetime
import time
from typing import Optional, List, Dict
from functools import wraps

# Database file location
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "conversations.db")

def retry_db_op(max_retries=3, delay=1):
    """Decorator to retry database operations on lock errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e) and i < max_retries - 1:
                        time.sleep(delay)
                        continue
                    raise e
            return None
        return wrapper
    return decorator

def init_database():
    """Initialize the SQLite database with required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            session_id TEXT DEFAULT 'default',
            timestamp TEXT NOT NULL,
            thread_slug TEXT,
            user_query TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            format_type TEXT,
            error_code TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create user_sessions table to track active sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            phone_number TEXT PRIMARY KEY,
            current_session_id TEXT NOT NULL,
            session_created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add session_id column if it doesn't exist (migration)
    try:
        cursor.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT DEFAULT 'default'")
    except sqlite3.OperationalError:
        pass # Column likely exists
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_phone_number 
        ON conversations(phone_number)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_thread_slug 
        ON conversations(thread_slug)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_session_id 
        ON conversations(session_id)
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")



@retry_db_op()
def get_thread_history(thread_slug: str, limit: int = 50) -> List[Dict]:
    """Retrieve conversation history for a specific thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM conversations 
        WHERE thread_slug = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (thread_slug, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@retry_db_op()
def get_user_history(phone_number: str, limit: int = 100) -> List[Dict]:
    """Retrieve all conversation history for a phone number."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM conversations 
        WHERE phone_number = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (phone_number, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@retry_db_op()
def cleanup_old_conversations(days: int = 90):
    """Delete conversations older than specified days."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        DELETE FROM conversations 
        WHERE created_at < ?
    """, (cutoff_str,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        print(f"✓ Cleaned up {deleted_count} old conversations")
    
    return deleted_count

@retry_db_op()
def create_new_session(phone_number: str) -> str:
    """Create a new session for the user and return the session ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Determine new session ID (incrementing number)
        cursor.execute("SELECT COUNT(*) FROM user_sessions WHERE phone_number = ?", (phone_number,))
        # Simple random/timestamp based ID for uniqueness is better for now:
        import uuid
        new_session_id = f"sess_{datetime.datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
        
        # Update or Insert user_sessions
        cursor.execute("""
            INSERT OR REPLACE INTO user_sessions (phone_number, current_session_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (phone_number, new_session_id))
        
        conn.commit()
        conn.close()
        return new_session_id
    except Exception as e:
        print(f"Error creating session: {e}")
        return "default"

@retry_db_op()
def get_current_session(phone_number: str) -> str:
    """Get the current active session ID for a phone number."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT current_session_id FROM user_sessions WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return row[0]
        else:
            # If no session exists, create a default one
            return create_new_session(phone_number)
    except Exception as e:
        print(f"Error getting session: {e}")
        return "default"

@retry_db_op()
def get_session_history(phone_number: str, session_id: str, limit: int = 10) -> List[Dict]:
    """Retrieve conversation history for a specific session."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM conversations 
        WHERE phone_number = ? AND session_id = ?
        ORDER BY created_at DESC 
        LIMIT ?
    """, (phone_number, session_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Return reversed list (chronological order) for context injection
    return [dict(row) for row in rows][::-1]

@retry_db_op()
def save_conversation(phone_number: str, user_query: str, ai_response: str, 
                     thread_slug: Optional[str] = None, 
                     format_type: Optional[str] = None,
                     error_code: Optional[str] = None,
                     session_id: str = "default"):
    """Save a conversation interaction to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO conversations 
        (phone_number, session_id, timestamp, thread_slug, user_query, ai_response, format_type, error_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (phone_number, session_id, timestamp, thread_slug, user_query, ai_response, format_type, error_code))
    
    conn.commit()
    conn.close()

@retry_db_op()
def clear_history(phone_number: str) -> int:
    """Clear all conversation history for a specific phone number."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM conversations 
        WHERE phone_number = ?
    """, (phone_number,))
    
    # Also reset session
    cursor.execute("DELETE FROM user_sessions WHERE phone_number = ?", (phone_number,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted_count

# Initialize database on import
# init_database() -> Moved to explicit call in main script
