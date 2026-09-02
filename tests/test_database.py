"""
Unit tests for DatabaseManager verifying initialization, migrations, transactions,
and multithreaded concurrency.
"""

import concurrent.futures
from pathlib import Path
import tempfile
import unittest

from dict_core.storage.database import DatabaseError, DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Tests the SQLite DatabaseManager lifecycle, migrations, and transactions."""

    def test_in_memory_initialization_and_schema(self) -> None:
        db = DatabaseManager(":memory:")
        with db.get_connection() as conn:
            # Check migrations table
            cursor = conn.execute("SELECT version, applied_at FROM schema_migrations;")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["version"], 1)

            # Check created tables
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                ).fetchall()
            ]
            self.assertIn("word_cache", tables)
            self.assertIn("search_history", tables)
            self.assertIn("favorites", tables)
        db.close()

    def test_file_based_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "sub_dir" / "test.db"
            db = DatabaseManager(db_file)
            self.assertTrue(db_file.exists())

            with db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) AS c FROM schema_migrations;")
                self.assertEqual(cursor.fetchone()["c"], 1)
            db.close()

    def test_transaction_rollback_on_error(self) -> None:
        db = DatabaseManager(":memory:")
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO search_history (word, provider_id, result_found, searched_at) VALUES ('test', 'p', 1, 'now');"
                )
                # Cause a syntax error
                conn.execute("INVALID SQL STATEMENT;")
        except DatabaseError:
            pass

        # Verify row was rolled back
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) AS c FROM search_history;")
            self.assertEqual(cursor.fetchone()["c"], 0)
        db.close()

    def test_multiple_sequential_connections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "sequential.db"
            db = DatabaseManager(db_file)

            for i in range(10):
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO search_history (word, provider_id, result_found, searched_at) VALUES (?, 'p', 1, 'now');",
                        (f"word_{i}",),
                    )

            with db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) AS c FROM search_history;")
                self.assertEqual(cursor.fetchone()["c"], 10)
            db.close()

    def test_multithreaded_concurrent_access(self) -> None:
        """Verifies that multiple concurrent threads can safely read and write simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "concurrent.db"
            db = DatabaseManager(db_file)

            def worker_task(idx: int) -> int:
                # Concurrent write
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO search_history (word, provider_id, result_found, searched_at) VALUES (?, 'test', 1, 'now');",
                        (f"thread_word_{idx}",),
                    )
                # Concurrent read
                with db.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT word FROM search_history WHERE word = ?;",
                        (f"thread_word_{idx}",),
                    )
                    row = cursor.fetchone()
                    assert row is not None
                    assert row["word"] == f"thread_word_{idx}"
                return idx

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(worker_task, i) for i in range(40)]
                results = [f.result() for f in futures]

            self.assertEqual(len(results), 40)
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) AS c FROM search_history;")
                self.assertEqual(cursor.fetchone()["c"], 40)
            db.close()


if __name__ == "__main__":
    unittest.main()
