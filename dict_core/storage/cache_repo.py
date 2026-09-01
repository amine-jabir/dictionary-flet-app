"""
Repository for managing cached WordEntry API responses in SQLite.
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional

from dict_core.config import DEFAULT_CONFIG
from dict_core.models.word import WordEntry
from dict_core.storage.database import DatabaseError, DatabaseManager
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.storage.cache")


class CacheRepository:
    """
    Handles persisting and retrieving normalized WordEntry objects to/from SQLite cache.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    def get(self, word: str) -> Optional[WordEntry]:
        """
        Retrieves a cached WordEntry by word if it exists and has not expired.
        Corrupted cache entries are safely purged and treated as cache misses.
        
        Args:
            word: Target search word.
            
        Returns:
            Optional[WordEntry]: Deserialized WordEntry or None.
        """
        if not word or not isinstance(word, str):
            return None

        clean_word = word.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT word, provider_id, payload_json, created_at, expires_at
                FROM word_cache
                WHERE word = ?;
                """,
                (clean_word,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            expires_at = row["expires_at"]
            if expires_at <= now_iso:
                logger.debug("Cache expired for '%s' (expired at %s)", clean_word, expires_at)
                conn.execute("DELETE FROM word_cache WHERE word = ?;", (clean_word,))
                return None

            try:
                entry = WordEntry.from_json(row["payload_json"])
                return entry
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                logger.warning("Corrupted cache payload detected for '%s': %s. Purging entry...", clean_word, exc)
                conn.execute("DELETE FROM word_cache WHERE word = ?;", (clean_word,))
                return None

    def is_cached(self, word: str) -> bool:
        """Returns True if a valid unexpired cached entry exists for the word."""
        return self.get(word) is not None

    def set(
        self,
        entry: WordEntry,
        ttl_days: int = DEFAULT_CONFIG.CACHE_EXPIRATION_DAYS,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Saves or updates a WordEntry in the local cache with a configured TTL.
        
        Args:
            entry: WordEntry instance to store.
            ttl_days: Time-to-live in days.
            ttl_seconds: Optional precise time-to-live override in seconds.
        """
        if not isinstance(entry, WordEntry) or not entry.word:
            raise TypeError("Expected valid WordEntry with a non-empty word.")

        clean_word = entry.word.strip().lower()
        now = datetime.now(timezone.utc)
        
        if ttl_seconds is not None:
            expires_dt = now + timedelta(seconds=max(1, ttl_seconds))
        else:
            expires_dt = now + timedelta(days=max(1, ttl_days))

        created_at_iso = now.isoformat()
        expires_at_iso = expires_dt.isoformat()
        payload_json = entry.to_json()

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO word_cache (word, provider_id, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (clean_word, entry.provider or "unknown", payload_json, created_at_iso, expires_at_iso),
            )
        logger.debug("Cached word '%s' (expires: %s)", clean_word, expires_at_iso)

    def delete(self, word: str) -> bool:
        """Deletes a specific word from the cache. Returns True if deleted."""
        if not word or not isinstance(word, str):
            return False

        clean_word = word.strip().lower()
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM word_cache WHERE word = ?;", (clean_word,))
            return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """Purges all expired entries from the cache. Returns count of deleted entries."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM word_cache WHERE expires_at <= ?;", (now_iso,))
            count = cursor.rowcount
            if count > 0:
                logger.info("Cleaned up %d expired cache records.", count)
            return count

    def clear(self) -> int:
        """Clears all records in the word_cache table. Returns count of removed items."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM word_cache;")
            return cursor.rowcount

    def count(self) -> int:
        """Returns the total number of unexpired entries currently in cache."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS total FROM word_cache WHERE expires_at > ?;", (now_iso,))
            row = cursor.fetchone()
            return int(row["total"]) if row else 0
