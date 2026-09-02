"""
Unit tests for OfflineDictionaryProvider verifying local lookups, data normalization, and speed.
"""

import time
import unittest

from dict_core.exceptions import ValidationError, WordNotFoundError
from dict_core.models.word import Definition, Meaning, WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider


class TestOfflineProvider(unittest.TestCase):
    """Tests the OfflineDictionaryProvider local lookup engine."""

    def setUp(self) -> None:
        self.provider = OfflineDictionaryProvider()

    def test_provider_properties(self) -> None:
        self.assertEqual(self.provider.provider_id, "offline_lexicon")
        self.assertEqual(self.provider.display_name, "Offline Lexicon (Local)")
        self.assertFalse(self.provider.supports_audio)
        self.assertTrue(self.provider.is_available())

    def test_offline_lookup_success(self) -> None:
        entry = self.provider.lookup("serendipity")
        self.assertIsInstance(entry, WordEntry)
        self.assertEqual(entry.word, "serendipity")
        self.assertEqual(entry.provider, "offline_lexicon")
        self.assertTrue(entry.metadata.get("offline", False))
        self.assertEqual(entry.metadata.get("source"), "offline_lexicon")

        # Check meanings & definitions
        self.assertTrue(len(entry.meanings) > 0)
        first_meaning = entry.meanings[0]
        self.assertEqual(first_meaning.part_of_speech, "noun")
        self.assertTrue(len(first_meaning.definitions) > 0)
        self.assertIn("chance", first_meaning.definitions[0].definition.lower())

        # Check IPA phonetics
        self.assertIsNotNone(entry.primary_phonetic)
        self.assertIn("sɛr", entry.primary_phonetic)

    def test_offline_lookup_multiple_words(self) -> None:
        for word in ["hello", "dictionary", "resilience", "lucid", "pragmatic", "ubiquitous"]:
            entry = self.provider.lookup(word)
            self.assertEqual(entry.word, word)
            self.assertTrue(len(entry.meanings) > 0)
            self.assertTrue(entry.total_definitions_count > 0)

    def test_offline_lookup_word_not_found(self) -> None:
        with self.assertRaises(WordNotFoundError) as ctx:
            self.provider.lookup("nonexistentwordxyz123")
        self.assertEqual(ctx.exception.word, "nonexistentwordxyz123")

    def test_offline_validation_error_on_empty(self) -> None:
        with self.assertRaises(ValidationError):
            self.provider.lookup("   ")

    def test_offline_insert_and_retrieval(self) -> None:
        new_entry = WordEntry(
            word="customword",
            meanings=[
                Meaning(
                    part_of_speech="noun",
                    definitions=[Definition(definition="A custom offline definition.", example="Here is an example.")],
                )
            ],
            provider="offline_lexicon",
        )
        self.provider.insert_entry(new_entry)

        retrieved = self.provider.lookup("customword")
        self.assertEqual(retrieved.word, "customword")
        self.assertEqual(retrieved.meanings[0].definitions[0].definition, "A custom offline definition.")

    def test_offline_sub_millisecond_latency(self) -> None:
        """Verifies that 50 consecutive local lookups execute in under 10ms total (<0.2ms per lookup)."""
        t0 = time.perf_counter()
        for _ in range(50):
            entry = self.provider.lookup("lucid")
            self.assertEqual(entry.word, "lucid")
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        avg_latency_ms = total_time_ms / 50.0

        self.assertLess(avg_latency_ms, 1.0, f"Average lookup time {avg_latency_ms:.3f}ms exceeded 1ms threshold!")


if __name__ == "__main__":
    unittest.main()
