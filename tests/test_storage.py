"""
Unit tests for CacheRepository, HistoryRepository, and VocabularyRepository.
"""

from datetime import datetime, timezone
import time
import unittest

from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository


def create_sample_entry(word: str = "example") -> WordEntry:
    """Helper creating a sample WordEntry."""
    return WordEntry(
        word=word,
        phonetics=[Phonetic(text="/ɪɡˈzɑːm.pəl/", audio=[AudioSource(url="https://audio.org/ex.mp3", accent="uk")])],
        meanings=[
            Meaning(
                part_of_speech="noun",
                definitions=[
                    Definition(
                        definition="A representative form or pattern.",
                        example="This is a good example.",
                        synonyms=["sample", "specimen"],
                    )
                ],
            )
        ],
        source_urls=["https://en.wiktionary.org/wiki/example"],
        provider="free_dict_api",
    )


class TestStorageRepositories(unittest.TestCase):
    """Tests CRUD, edge cases, expiration, and corruption handling in SQLite repositories."""

    def setUp(self) -> None:
        self.db = DatabaseManager(":memory:")
        self.cache_repo = CacheRepository(self.db)
        self.history_repo = HistoryRepository(self.db)
        self.vocab_repo = VocabularyRepository(self.db)

    def tearDown(self) -> None:
        self.db.close()

    # --- CacheRepository Tests ---

    def test_cache_insert_and_retrieve_hit(self) -> None:
        entry = create_sample_entry("serendipity")
        self.cache_repo.set(entry, ttl_days=7)

        cached = self.cache_repo.get("serendipity")
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached.word, "serendipity")
        self.assertEqual(cached.primary_phonetic, "/ɪɡˈzɑːm.pəl/")
        self.assertEqual(cached.primary_audio_url, "https://audio.org/ex.mp3")
        self.assertEqual(self.cache_repo.count(), 1)

    def test_cache_miss_for_unseen_word(self) -> None:
        self.assertIsNone(self.cache_repo.get("unknown_word"))

    def test_cache_expiration(self) -> None:
        entry = create_sample_entry("ephemeral")
        # Set with 1 second TTL
        self.cache_repo.set(entry, ttl_seconds=1)
        self.assertIsNotNone(self.cache_repo.get("ephemeral"))

        # Wait 1.1s for expiration
        time.sleep(1.1)

        # Should return None (expired) and be automatically purged
        self.assertIsNone(self.cache_repo.get("ephemeral"))
        self.assertEqual(self.cache_repo.count(), 0)

    def test_cache_update_entry(self) -> None:
        entry_v1 = create_sample_entry("update_test")
        self.cache_repo.set(entry_v1)

        # Update with new definition
        entry_v2 = WordEntry(
            word="update_test",
            meanings=[Meaning(part_of_speech="verb", definitions=[Definition(definition="New definition")])],
            provider="wiktionary_rest",
        )
        self.cache_repo.set(entry_v2)

        cached = self.cache_repo.get("update_test")
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached.meanings[0].definitions[0].definition, "New definition")
        self.assertEqual(cached.provider, "wiktionary_rest")
        self.assertEqual(self.cache_repo.count(), 1)

    def test_cache_delete_and_clear(self) -> None:
        self.cache_repo.set(create_sample_entry("word1"))
        self.cache_repo.set(create_sample_entry("word2"))
        self.assertEqual(self.cache_repo.count(), 2)

        self.assertTrue(self.cache_repo.delete("word1"))
        self.assertFalse(self.cache_repo.delete("word1"))  # Already deleted
        self.assertEqual(self.cache_repo.count(), 1)

        self.assertEqual(self.cache_repo.clear(), 1)
        self.assertEqual(self.cache_repo.count(), 0)

    def test_cache_corrupted_json_handling(self) -> None:
        # Directly insert invalid JSON into database
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO word_cache (word, provider_id, payload_json, created_at, expires_at)
                VALUES ('corrupt', 'test', '{INVALID_JSON...', '2026-01-01T00:00:00', '2099-01-01T00:00:00');
                """
            )

        # get() must catch corruption gracefully, purge the row, and return None
        result = self.cache_repo.get("corrupt")
        self.assertIsNone(result)
        self.assertEqual(self.cache_repo.count(), 0)

    def test_cache_unicode_words(self) -> None:
        entry = create_sample_entry("résumé")
        self.cache_repo.set(entry)

        cached = self.cache_repo.get("  RÉSUMÉ  ")  # Case/whitespace insensitivity
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached.word, "résumé")

    # --- HistoryRepository Tests ---

    def test_history_logging_and_recent(self) -> None:
        self.history_repo.add("hello", provider_id="free_dict_api", result_found=True)
        self.history_repo.add("world", provider_id="wiktionary_rest", result_found=True)
        self.history_repo.add("missing", provider_id="free_dict_api", result_found=False)

        self.assertEqual(self.history_repo.count(), 3)

        recent = self.history_repo.get_recent(limit=2)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["word"], "missing")
        self.assertFalse(recent[0]["result_found"])
        self.assertEqual(recent[1]["word"], "world")
        self.assertTrue(recent[1]["result_found"])

    def test_history_unique_words_deduplication(self) -> None:
        self.history_repo.add("apple")
        self.history_repo.add("banana")
        self.history_repo.add("apple")  # Repeated search

        unique = self.history_repo.get_unique_words()
        self.assertEqual(unique, ["apple", "banana"])  # apple is most recent

    def test_history_deletion(self) -> None:
        h_id = self.history_repo.add("delete_me")
        self.assertEqual(self.history_repo.count(), 1)
        self.assertTrue(self.history_repo.delete_entry(h_id))
        self.assertEqual(self.history_repo.count(), 0)

        self.history_repo.add("word_a")
        self.history_repo.add("word_a")
        self.history_repo.add("word_b")
        deleted_count = self.history_repo.delete_word("word_a")
        self.assertEqual(deleted_count, 2)
        self.assertEqual(self.history_repo.count(), 1)

    # --- VocabularyRepository (Favorites) Tests ---

    def test_favorites_crud_lifecycle(self) -> None:
        entry = create_sample_entry("lucid")
        self.assertFalse(self.vocab_repo.is_favorite("lucid"))

        # Add favorite with notes and tags
        self.vocab_repo.add_favorite(
            word="lucid",
            notes="Easy to understand, clear thinking.",
            tags=["GRE", "adjectives"],
            entry=entry,
        )
        self.assertTrue(self.vocab_repo.is_favorite("lucid"))
        self.assertEqual(self.vocab_repo.count(), 1)

        fav = self.vocab_repo.get_favorite("lucid")
        self.assertIsNotNone(fav)
        assert fav is not None
        self.assertEqual(fav["word"], "lucid")
        self.assertEqual(fav["notes"], "Easy to understand, clear thinking.")
        self.assertEqual(fav["tags"], ["GRE", "adjectives"])
        self.assertIsNotNone(fav["entry"])
        self.assertEqual(fav["entry"].word, "lucid")

        # Update notes & tags
        self.vocab_repo.add_favorite(
            word="lucid",
            notes="Updated note.",
            tags=["vocab"],
        )
        updated_fav = self.vocab_repo.get_favorite("lucid")
        assert updated_fav is not None
        self.assertEqual(updated_fav["notes"], "Updated note.")
        self.assertEqual(updated_fav["tags"], ["vocab"])
        # Preserved previous snapshot entry
        self.assertIsNotNone(updated_fav["entry"])

        # Remove
        self.assertTrue(self.vocab_repo.remove_favorite("lucid"))
        self.assertFalse(self.vocab_repo.is_favorite("lucid"))
        self.assertEqual(self.vocab_repo.count(), 0)

    def test_favorites_tag_filtering(self) -> None:
        self.vocab_repo.add_favorite("word1", tags=["science", "physics"])
        self.vocab_repo.add_favorite("word2", tags=["literature"])
        self.vocab_repo.add_favorite("word3", tags=["science", "biology"])

        all_favs = self.vocab_repo.list_favorites()
        self.assertEqual(len(all_favs), 3)

        science_favs = self.vocab_repo.list_favorites(tag="science")
        self.assertEqual(len(science_favs), 2)
        self.assertEqual({f["word"] for f in science_favs}, {"word1", "word3"})


if __name__ == "__main__":
    unittest.main()
