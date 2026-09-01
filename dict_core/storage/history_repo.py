"""
Repository for managing search history records in SQLite.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dict_core.storage.database import DatabaseManager
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.storage.history")


class HistoryRepository:
    """
    Manages search history logs with timestamps, result status, and pagination.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    def add(
        self,
        word: str,
        provider_id: str = "",
        result_found: bool = True,
        searched_at: Optional[str] = None,
    ) -> int:
        """
        Inserts a new search query into the history log.
        
        Args:
            word: The searched term.
            provider_id: The provider ID used for lookup.
            result_found: Whether a definition was found (True) or 404 (False).
            searched_at: ISO timestamp string override.
            
        Returns:
            int: Inserted row ID.
        """
        if not word or not isinstance(word, str):
            raise ValueError("History search word cannot be empty or non-string.")

        clean_word = word.strip().lower()
        timestamp = searched_at or datetime.now(timezone.utc).isoformat()
        found_int = 1 if result_found else 0

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO search_history (word, provider_id, result_found, searched_at)
                VALUES (?, ?, ?, ?);
                """,
                (clean_word, provider_id or "unknown", found_int, timestamp),
            )
            return cursor.lastrowid or 0

    def get_recent(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent search history records.
        
        Returns:
            List[Dict[str, Any]]: List of history record dictionaries.
        """
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, word, provider_id, result_found, searched_at
                FROM search_history
                ORDER BY id DESC
                LIMIT ? OFFSET ?;
                """,
                (safe_limit, safe_offset),
            )
            return [
                {
                    "id": row["id"],
                    "word": row["word"],
                    "provider_id": row["provider_id"],
                    "result_found": bool(row["result_found"]),
                    "searched_at": row["searched_at"],
                }
                for row in cursor.fetchall()
            ]

    def get_unique_words(self, limit: int = 50) -> List[str]:
        """
        Returns deduplicated recently searched words ordered by latest search timestamp.
        """
        safe_limit = max(1, min(limit, 500))
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT word, MAX(id) AS latest_id
                FROM search_history
                GROUP BY word
                ORDER BY latest_id DESC
                LIMIT ?;
                """,
                (safe_limit,),
            )
            return [row["word"] for row in cursor.fetchall()]

    def delete_entry(self, history_id: int) -> bool:
        """Deletes a specific history record by ID."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM search_history WHERE id = ?;", (int(history_id),))
            return cursor.rowcount > 0

    def delete_word(self, word: str) -> int:
        """Deletes all history records associated with a specific word."""
        if not word or not isinstance(word, str):
            return 0
        clean_word = word.strip().lower()
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM search_history WHERE word = ?;", (clean_word,))
            return cursor.rowcount

    def clear(self) -> int:
        """Clears all search history records. Returns count of deleted entries."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM search_history;")
            return cursor.rowcount

    def count(self) -> int:
        """Returns the total number of history records."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS total FROM search_history;")
            row = cursor.fetchone()
            return int(row["total"]) if row else 0
