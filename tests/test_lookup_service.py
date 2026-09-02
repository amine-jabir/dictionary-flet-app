"""
Unit tests for LookupService verifying the offline-first / local-first 4-tier pipeline.
"""

import unittest
from unittest.mock import MagicMock

from dict_core.exceptions import NetworkError, TimeoutError, WordNotFoundError
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.services.lookup_service import LookupService
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository


def create_sample_word_entry(word: str = "serendipity", provider: str = "mock_provider") -> WordEntry:
    return WordEntry(
        word=word,
        phonetics=[Phonetic(text=f"/{word}/", audio=[AudioSource(url=f"https://audio.org/{word}.mp3", accent="us")])],
        meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition=f"Definition of {word}")])],
        provider=provider,
    )


class TestLookupService(unittest.TestCase):
    """Tests LookupService offline-first resolution, caching, and fallback flow."""

    def setUp(self) -> None:
        self.db = DatabaseManager(":memory:")
        self.cache_repo = CacheRepository(self.db)
        self.history_repo = HistoryRepository(self.db)
        self.mock_primary = MagicMock(spec=BaseDictionaryProvider)
        self.mock_primary.provider_id = "primary_api"
        self.mock_primary.validate_query.side_effect = lambda w: w.strip().lower()

        self.mock_fallback = MagicMock(spec=BaseDictionaryProvider)
        self.mock_fallback.provider_id = "fallback_api"
        self.mock_fallback.validate_query.side_effect = lambda w: w.strip().lower()

        self.offline_provider = OfflineDictionaryProvider()

        self.service = LookupService(
            provider=self.mock_primary,
            cache_repo=self.cache_repo,
            history_repo=self.history_repo,
            offline_provider=self.offline_provider,
            fallback_providers=[self.mock_fallback],
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_tier1_cache_hit_bypasses_offline_and_online(self) -> None:
        """Verifies that an existing entry in the cache returns immediately with 0 provider calls."""
        entry = create_sample_word_entry("customcache", provider="custom_provider")
        self.cache_repo.set(entry)

        res = self.service.lookup("customcache")
        self.assertEqual(res.word, "customcache")
        self.assertTrue(res.metadata.get("cached", False))
        self.mock_primary.lookup.assert_not_called()
        self.mock_fallback.lookup.assert_not_called()

    def test_tier2_offline_lexicon_hit_populates_cache_and_bypasses_online(self) -> None:
        """Verifies that an offline dictionary hit returns immediately and populates user cache with 0 online calls."""
        self.assertFalse(self.cache_repo.is_cached("serendipity"))

        # Look up word present in offline lexicon
        res = self.service.lookup("serendipity")
        self.assertEqual(res.word, "serendipity")
        self.assertEqual(res.provider, "offline_lexicon")
        self.assertTrue(res.metadata.get("offline", False))

        # Online APIs were never called!
        self.mock_primary.lookup.assert_not_called()
        self.mock_fallback.lookup.assert_not_called()

        # Verified that the offline entry is now cached in user SQLite cache for future instant hits
        self.assertTrue(self.cache_repo.is_cached("serendipity"))

    def test_tier3_online_lookup_on_offline_miss(self) -> None:
        """Verifies that a rare word missing from offline lexicon queries the online provider."""
        rare_word = "rareonlinelexiconterm"
        online_entry = create_sample_word_entry(rare_word, provider="primary_api")
        self.mock_primary.lookup.return_value = online_entry

        res = self.service.lookup(rare_word)
        self.assertEqual(res.word, rare_word)
        self.assertEqual(res.provider, "primary_api")
        self.assertFalse(res.metadata.get("cached", False))

        # Verified primary provider called with interactive timeout
        self.mock_primary.lookup.assert_called_once()
        self.assertTrue(self.cache_repo.is_cached(rare_word))

    def test_tier4_fallback_provider_on_primary_timeout(self) -> None:
        """Verifies that if primary provider times out on an offline miss, fallback provider is queried."""
        word = "unseenterm"
        self.mock_primary.lookup.side_effect = TimeoutError("Primary API timed out")
        fallback_entry = create_sample_word_entry(word, provider="fallback_api")
        self.mock_fallback.lookup.return_value = fallback_entry

        res = self.service.lookup(word)
        self.assertEqual(res.word, word)
        self.assertEqual(res.provider, "fallback_api")
        self.mock_primary.lookup.assert_called_once()
        self.mock_fallback.lookup.assert_called_once()
        self.assertTrue(self.cache_repo.is_cached(word))

    def test_force_refresh_bypasses_cache_and_offline_lexicon(self) -> None:
        """Verifies that force_refresh=True goes directly to online providers."""
        # Pre-seed cache
        self.cache_repo.set(create_sample_word_entry("serendipity", provider="old_cached"))
        fresh_entry = create_sample_word_entry("serendipity", provider="primary_api")
        self.mock_primary.lookup.return_value = fresh_entry

        res = self.service.lookup("serendipity", force_refresh=True)
        self.assertEqual(res.word, "serendipity")
        self.assertEqual(res.provider, "primary_api")
        self.mock_primary.lookup.assert_called_once()

    def test_word_not_found_records_history_and_raises(self) -> None:
        """Verifies that if word is not in cache, offline lexicon, or online APIs, WordNotFoundError is raised."""
        self.mock_primary.lookup.side_effect = WordNotFoundError(word="unknownterm")
        self.mock_fallback.lookup.side_effect = WordNotFoundError(word="unknownterm")

        with self.assertRaises(WordNotFoundError) as ctx:
            self.service.lookup("unknownterm")
        self.assertEqual(ctx.exception.word, "unknownterm")

        # Verified recorded in history with result_found = False
        recent = self.history_repo.get_recent(limit=1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["word"], "unknownterm")
        self.assertFalse(bool(recent[0]["result_found"]))


if __name__ == "__main__":
    unittest.main()
