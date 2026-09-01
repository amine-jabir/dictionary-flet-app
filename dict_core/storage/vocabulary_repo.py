"""
Repository for managing user favorites and vocabulary bookmarks in SQLite.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from dict_core.models.word import WordEntry
from dict_core.storage.database import DatabaseManager
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.storage.vocabulary")


class VocabularyRepository:
    """
    Manages starred words (favorites), user notes, and categorization tags.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    def add_favorite(
        self,
        word: str,
        notes: str = "",
        tags: Optional[List[str]] = None,
        entry: Optional[WordEntry] = None,
        added_at: Optional[str] = None,
    ) -> bool:
        """
        Stars/bookmarks a word with optional notes, tags, and cached snapshot payload.
        
        Returns:
            bool: True if inserted/updated.
        """
        if not word or not isinstance(word, str):
            raise ValueError("Favorite word cannot be empty or non-string.")

        clean_word = word.strip().lower()
        timestamp = added_at or datetime.now(timezone.utc).isoformat()
        clean_tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        tags_json = json.dumps(clean_tags)
        payload_json = entry.to_json() if isinstance(entry, WordEntry) else None

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO favorites (word, added_at, notes, tags_json, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    notes = excluded.notes,
                    tags_json = excluded.tags_json,
                    payload_json = COALESCE(excluded.payload_json, favorites.payload_json);
                """,
                (clean_word, timestamp, str(notes or "").strip(), tags_json, payload_json),
            )
            return True

    def remove_favorite(self, word: str) -> bool:
        """Removes a word from favorites. Returns True if was present and deleted."""
        if not word or not isinstance(word, str):
            return False

        clean_word = word.strip().lower()
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM favorites WHERE word = ?;", (clean_word,))
            return cursor.rowcount > 0

    def is_favorite(self, word: str) -> bool:
        """Checks if a word is currently bookmarked as favorite."""
        if not word or not isinstance(word, str):
            return False

        clean_word = word.strip().lower()
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM favorites WHERE word = ? LIMIT 1;", (clean_word,))
            return cursor.fetchone() is not None

    def get_favorite(self, word: str) -> Optional[Dict[str, Any]]:
        """Retrieves details of a bookmarked word, including deserialized entry if available."""
        if not word or not isinstance(word, str):
            return None

        clean_word = word.strip().lower()
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT word, added_at, notes, tags_json, payload_json
                FROM favorites
                WHERE word = ?;
                """,
                (clean_word,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            entry_obj = None
            if row["payload_json"]:
                try:
                    entry_obj = WordEntry.from_json(row["payload_json"])
                except Exception as exc:
                    logger.warning("Could not deserialize favorite snapshot for '%s': %s", clean_word, exc)

            try:
                tags = json.loads(row["tags_json"])
            except Exception:
                tags = []

            return {
                "word": row["word"],
                "added_at": row["added_at"],
                "notes": row["notes"],
                "tags": tags,
                "entry": entry_obj,
            }

    def list_favorites(
        self,
        limit: int = 100,
        offset: int = 0,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lists all bookmarked words, optionally filtered by tag.
        """
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        with self.db.get_connection() as conn:
            if tag and tag.strip():
                clean_tag = tag.strip()
                # Use JSON extraction or LIKE pattern for tags
                cursor = conn.execute(
                    """
                    SELECT word, added_at, notes, tags_json, payload_json
                    FROM favorites
                    WHERE tags_json LIKE ?
                    ORDER BY added_at DESC
                    LIMIT ? OFFSET ?;
                    """,
                    (f'%"{clean_tag}"%', safe_limit, safe_offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT word, added_at, notes, tags_json, payload_json
                    FROM favorites
                    ORDER BY added_at DESC
                    LIMIT ? OFFSET ?;
                    """,
                    (safe_limit, safe_offset),
                )

            results = []
            for row in cursor.fetchall():
                try:
                    tags = json.loads(row["tags_json"])
                except Exception:
                    tags = []

                entry_obj = None
                if row["payload_json"]:
                    try:
                        entry_obj = WordEntry.from_json(row["payload_json"])
                    except Exception:
                        entry_obj = None

                results.append(
                    {
                        "word": row["word"],
                        "added_at": row["added_at"],
                        "notes": row["notes"],
                        "tags": tags,
                        "entry": entry_obj,
                    }
                )
            return results

    def clear(self) -> int:
        """Clears all favorites. Returns count of deleted entries."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM favorites;")
            return cursor.rowcount

    def count(self) -> int:
        """Returns the total number of favorite bookmarks."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS total FROM favorites;")
            row = cursor.fetchone()
            return int(row["total"]) if row else 0
