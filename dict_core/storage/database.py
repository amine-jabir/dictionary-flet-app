"""
SQLite Database Manager for dict_core.
Manages connections, PRAGMA optimizations, automated schema migrations,
and thread-safe in-memory/file-based locking with filesystem-resilient journal fallback.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import threading
from typing import Generator, List, Optional, Union

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import DictionaryError
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.storage.database")


class DatabaseError(DictionaryError):
    """Raised when an unrecoverable database or schema migration error occurs."""
    pass


class DatabaseManager:
    """
    Manages SQLite database lifecycle, schema initialization, and connections.
    """

    MIGRATIONS: List[str] = [
        # Migration 1: Initial Schema (Cache, Search History, Favorites)
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS word_cache (
            word TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_word_cache_expires_at ON word_cache (expires_at);

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            result_found INTEGER NOT NULL DEFAULT 1,
            searched_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_search_history_word ON search_history (word);
        CREATE INDEX IF NOT EXISTS idx_search_history_time ON search_history (searched_at DESC);

        CREATE TABLE IF NOT EXISTS favorites (
            word TEXT PRIMARY KEY,
            added_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]',
            payload_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_favorites_added_at ON favorites (added_at DESC);
        """
    ]

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is None:
            storage_dir = DEFAULT_CONFIG.DEFAULT_STORAGE_DIR
            storage_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(storage_dir / "dictionary.db")
        else:
            self.db_path = str(db_path)
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._is_memory = (self.db_path == ":memory:")
        self._memory_lock = threading.RLock()
        self._memory_conn: Optional[sqlite3.Connection] = None

        if self._is_memory:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._configure_pragmas(self._memory_conn)

        self._initialize_database()

    def _configure_pragmas(self, conn: sqlite3.Connection) -> None:
        """Applies high-performance, ACID-compliant PRAGMA settings with resilient fallback."""
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA busy_timeout = 5000;")
        except Exception:
            pass

        if not self._is_memory:
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                # Graceful fallback to standard DELETE journal mode on filesystems that do not support POSIX shared memory (WAL)
                try:
                    conn.execute("PRAGMA journal_mode = DELETE;")
                except Exception:
                    pass

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager yielding an open, configured SQLite connection with transaction management.
        """
        if self._is_memory and self._memory_conn:
            with self._memory_lock:
                try:
                    yield self._memory_conn
                    self._memory_conn.commit()
                except Exception as exc:
                    self._memory_conn.rollback()
                    raise DatabaseError(f"In-memory database error: {exc}") from exc
        else:
            conn = None
            try:
                conn = sqlite3.connect(self.db_path, timeout=10.0)
                self._configure_pragmas(conn)
                yield conn
                conn.commit()
            except sqlite3.Error as exc:
                if conn:
                    conn.rollback()
                raise DatabaseError(f"Database error on '{self.db_path}': {exc}") from exc
            finally:
                if conn:
                    conn.close()

    def _initialize_database(self) -> None:
        """Runs pending schema migrations."""
        logger.debug("Initializing database schema on '%s'", self.db_path)
        with self.get_connection() as conn:
            # Ensure schema_migrations table exists
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            
            # Fetch applied migration versions
            cursor = conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
            applied_versions = {row["version"] for row in cursor.fetchall()}

            for version_idx, migration_sql in enumerate(self.MIGRATIONS, start=1):
                if version_idx not in applied_versions:
                    logger.info("Applying database migration v%d...", version_idx)
                    conn.executescript(migration_sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                        (version_idx, datetime.now(timezone.utc).isoformat()),
                    )

    def close(self) -> None:
        """Closes any persistent connections (e.g. in-memory)."""
        with self._memory_lock:
            if self._memory_conn:
                self._memory_conn.close()
                self._memory_conn = None
