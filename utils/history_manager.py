"""History manager for storing transcription records in SQLite."""
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TranscriptionRecord:
    """Represents a transcription history record."""
    text: str
    duration: float
    provider: str
    model: str
    cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    audio_path: Optional[str] = None
    id: Optional[int] = None


class HistoryManager:
    """Manages transcription history in SQLite database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database. If None, uses portable path next to exe.
        """
        if db_path is None:
            from utils.paths import get_database_path
            self.db_path = get_database_path()
        else:
            self.db_path = db_path
            # Ensure directory exists
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration REAL NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                cost REAL DEFAULT 0,
                text TEXT NOT NULL,
                audio_path TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON transcriptions(timestamp DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_provider ON transcriptions(provider)")
        conn.commit()
    
    def add(self, record: TranscriptionRecord) -> int:
        """Add transcription record to database.
        
        Args:
            record: TranscriptionRecord to add
            
        Returns:
            ID of the inserted record
        """
        conn = self._get_connection()
        cursor = conn.execute("""
            INSERT INTO transcriptions (timestamp, duration, provider, model, cost, text, audio_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.timestamp.isoformat(),
            record.duration,
            record.provider,
            record.model,
            record.cost,
            record.text,
            record.audio_path
        ))
        conn.commit()
        return cursor.lastrowid
    
    def get_by_id(self, record_id: int) -> Optional[TranscriptionRecord]:
        """Get record by ID.
        
        Args:
            record_id: ID of the record
            
        Returns:
            TranscriptionRecord or None if not found
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (record_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return self._row_to_record(row)
        return None
    
    def get_page(self, page: int = 1, per_page: int = 20) -> list[TranscriptionRecord]:
        """Get paginated history in reverse chronological order.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            
        Returns:
            List of TranscriptionRecord objects
        """
        offset = (page - 1) * per_page
        
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT * FROM transcriptions 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        
        return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def search(self, query: str = "", filters: Optional[dict] = None) -> list[TranscriptionRecord]:
        """Search history with optional filters.
        
        Args:
            query: Text to search for in transcription text
            filters: Optional dict with keys: 'provider', 'date_from', 'date_to'
            
        Returns:
            List of matching TranscriptionRecord objects
        """
        filters = filters or {}
        conditions = []
        params = []
        
        if query:
            conditions.append("text LIKE ?")
            params.append(f"%{query}%")
        
        if 'provider' in filters and filters['provider']:
            conditions.append("provider = ?")
            params.append(filters['provider'])
        
        if 'date_from' in filters and filters['date_from']:
            conditions.append("timestamp >= ?")
            params.append(filters['date_from'])
        
        if 'date_to' in filters and filters['date_to']:
            conditions.append("timestamp <= ?")
            params.append(filters['date_to'])
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(f"""
            SELECT * FROM transcriptions 
            WHERE {where_clause}
            ORDER BY timestamp DESC
        """, params)
        
        return [self._row_to_record(row) for row in cursor.fetchall()]
    
    def delete(self, record_id: int) -> bool:
        """Delete record by ID.
        
        Args:
            record_id: ID of the record to delete
            
        Returns:
            True if record was deleted, False if not found
        """
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM transcriptions WHERE id = ?",
            (record_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    
    def get_total_count(self) -> int:
        """Get total number of records.
        
        Returns:
            Total count of transcription records
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM transcriptions")
        return cursor.fetchone()[0]
    
    def _row_to_record(self, row: sqlite3.Row) -> TranscriptionRecord:
        """Convert database row to TranscriptionRecord."""
        return TranscriptionRecord(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            duration=row['duration'],
            provider=row['provider'],
            model=row['model'],
            cost=row['cost'],
            text=row['text'],
            audio_path=row['audio_path']
        )
