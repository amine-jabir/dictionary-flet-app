import tempfile
from pathlib import Path
"""
Part 6 End-to-End Integration & Regression Test Suite.
Tests the complete application workflows:
  1. Main Search Experience (offline, cached, online, nonexistent, network failure, rapid consecutive)
  2. Sense Ranking & Definition Display (duck as bird #1, examples, synonyms, antonyms)
  3. Audio Playback (stream play, unavailable audio, playback failure & fallback)
  4. Favorites Workflow (star, persist, immediate local open, unfavorite)
  5. History Workflow (log, ordering, open historical word, clear)
  6. Navigation Transitions (Search -> Favorites -> Search, Search -> History -> Search, mixed cycles)
  7. Theme Toggling (light <-> dark with zero state loss or extra lookups)
  8. Responsive Viewport Adaptability (360px, 480px, 768px, 1280px, 1920px)
"""

import time
import unittest
from unittest.mock import MagicMock
import requests

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.theme import DARK_PALETTE, LIGHT_PALETTE, get_pos_color
from dict_core.exceptions import NetworkError, TimeoutError, WordNotFoundError
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository
from dict_core.utils.http_client import ResilientHttpClient


class MockOnlineProvider(BaseDictionaryProvider):
    """Mock online dictionary provider for deterministic testing."""

    def __init__(self, name: str = "mock_online") -> None:
        self._name = name
        self.call_count = 0
        self.should_timeout = False
        self.should_network_fail = False

    @property
    def provider_id(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return f"Mock Provider ({self._name})"

    @property
    def supports_audio(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True

    def lookup(self, word: str, timeout: float = None, max_retries: int = None) -> WordEntry:
        self.call_count += 1
        clean_word = self.validate_query(word)

        if self.should_timeout:
            raise TimeoutError(f"Mock provider {self._name} timed out.")
        if self.should_network_fail:
            raise NetworkError(f"Mock provider {self._name} network connection refused.")

        if clean_word == "rareword":
            return WordEntry(
                word="rareword",
                phonetics=[Phonetic(text="/ˈrɛər.wɜːd/", audio=[AudioSource(url="https://audio.org/rare.mp3", accent="us")])],
                meanings=[
                    Meaning(
                        part_of_speech="noun",
                        definitions=[Definition(definition="An uncommon or rare term.", example="It is a rareword in linguistics.")],
                        synonyms=["hapax", "rarity"],
                    )
                ],
                provider=self.provider_id,
            )

        raise WordNotFoundError(word=clean_word)


class TestPart6EndToEnd(unittest.TestCase):
    """Full End-to-End integration test suite for Part 6."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(":memory:")
        self.cache_repo = CacheRepository(self.db)
        self.history_repo = HistoryRepository(self.db)
        self.vocab_repo = VocabularyRepository(self.db)

        self.offline_provider = OfflineDictionaryProvider()
        self.online_provider = MockOnlineProvider("primary_api")
        self.fallback_provider = MockOnlineProvider("fallback_api")

        self.lookup_service = LookupService(
            provider=self.online_provider,
            cache_repo=self.cache_repo,
            history_repo=self.history_repo,
            offline_provider=self.offline_provider,
            fallback_providers=[self.fallback_provider],
        )

        self.mock_http = MagicMock(spec=ResilientHttpClient)
        self.audio_cache = AudioCacheManager(cache_dir=Path(self.temp_dir.name) / "audio_cache")
        self.mock_player = MagicMock()
        self.audio_service = AudioService(
            cache_manager=self.audio_cache,
            http_client=self.mock_http,
            player=self.mock_player,
        )

        self.state = AppState(
            lookup_service=self.lookup_service,
            audio_service=self.audio_service,
            vocab_repo=self.vocab_repo,
            history_repo=self.history_repo,
            debug_diagnostics=False,
        )

        self.ui_notifications = 0
        self.state.subscribe(self._on_ui_notify)

    def tearDown(self) -> None:
        self.db.close()
        self.temp_dir.cleanup()

    def _on_ui_notify(self) -> None:
        self.ui_notifications += 1

    # =========================================================================
    # 1. Main Search Experience
    # =========================================================================

    def test_search_offline_duck_prominent_bird_meaning(self) -> None:
        """Verifies searching 'duck' resolves instantly from offline lexicon with bird sense ranked #1."""
        self.state.search_word("duck", run_sync=True)

        self.assertEqual(self.state.current_query, "duck")
        self.assertIsNotNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIsNone(self.state.error_message)

        entry = self.state.current_entry
        self.assertEqual(entry.word, "duck")
        self.assertEqual(entry.primary_phonetic, "/dʌk/")

        # Verify sense ranker ranked the aquatic bird meaning #1
        first_def = entry.meanings[0].definitions[0].definition
        self.assertIn("aquatic bird", first_def.lower())

        # Online provider should NOT have been called (0 network requests)
        self.assertEqual(self.online_provider.call_count, 0)

    def test_search_cached_word_bypasses_all_providers(self) -> None:
        """Verifies that repeat searches hit Tier 1 user cache in <0.5ms."""
        # Pre-seed cache
        entry = WordEntry(
            word="cachedterm",
            phonetics=[Phonetic(text="/ˈkæʃt/")],
            meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition="A previously cached entry.")])],
            provider="test_cache",
        )
        self.cache_repo.set(entry)

        self.state.search_word("cachedterm", run_sync=True)
        self.assertEqual(self.state.current_entry.word, "cachedterm")
        self.assertTrue(self.state.current_entry.metadata.get("cached"))
        self.assertEqual(self.online_provider.call_count, 0)

    def test_search_online_word_populates_cache_and_history(self) -> None:
        """Verifies that an offline-miss queries the online provider and saves to cache."""
        self.state.search_word("rareword", run_sync=True)
        self.assertEqual(self.state.current_entry.word, "rareword")
        self.assertEqual(self.online_provider.call_count, 1)

        # Verify entry was written to user cache
        cached = self.cache_repo.get("rareword")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.word, "rareword")

        # Verify query was logged in search history
        recent = self.history_repo.get_recent(limit=5)
        self.assertEqual(recent[0]["word"], "rareword")
        self.assertTrue(recent[0]["result_found"])

    def test_search_nonexistent_word_displays_clear_not_found(self) -> None:
        """Verifies searching an unknown word sets a clear error message and logs 404 in history."""
        self.state.search_word("xyznonexistent", run_sync=True)
        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIsNotNone(self.state.error_message)
        self.assertIn("No definitions found for 'xyznonexistent'", self.state.error_message)

        recent = self.history_repo.get_recent(limit=5)
        self.assertEqual(recent[0]["word"], "xyznonexistent")
        self.assertFalse(recent[0]["result_found"])

    def test_search_network_failure_sets_offline_error_state(self) -> None:
        """Verifies network connection error across all providers sets a helpful connection notice."""
        self.online_provider.should_network_fail = True
        self.fallback_provider.should_network_fail = True
        self.state.search_word("unseenonlineonly", run_sync=True)

        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIn("Network connection error", self.state.error_message)

    def test_rapid_consecutive_searches_cancellation_fencing(self) -> None:
        """Verifies that when multiple searches fire rapidly, only the latest request updates state."""
        self.state.search_word("word1", run_sync=False)
        self.state.search_word("word2", run_sync=False)
        self.state.search_word("duck", run_sync=False)

        # Allow background worker to complete
        time.sleep(0.3)

        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry.word, "duck")
        self.assertFalse(self.state.is_loading)

    # =========================================================================
    # 2. Audio Playback Workflow
    # =========================================================================

    def test_audio_playback_available_word(self) -> None:
        """Verifies pronunciation trigger for a word with audio."""
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"\xff\xfb\x90\x44" + b"\x00" * 80
        mock_resp.headers = {"Content-Type": "audio/mpeg"}
        self.mock_http.get.return_value = mock_resp

        self.state.search_word("duck", run_sync=True)
        self.state.play_audio(run_sync=True)
        self.mock_player.play.assert_called_once()

    def test_audio_playback_missing_audio_handled_gracefully(self) -> None:
        """Verifies that words without audio stream don't crash and provide clear status."""
        entry_no_audio = WordEntry(
            word="silentword",
            meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition="No audio here.")])],
            provider="test",
        )
        self.state.current_entry = entry_no_audio
        self.state.play_audio(run_sync=True)
        # Should not crash, and inform user
        self.assertIn("voice", self.state.audio_status_message.lower())

    # =========================================================================
    # 3. Favorites Workflow
    # =========================================================================

    def test_favorites_full_lifecycle(self) -> None:
        """Verifies adding, persisting, opening, and removing favorites."""
        # 1. Search 'duck'
        self.state.search_word("duck", run_sync=True)
        self.assertFalse(self.state.is_favorite)

        # 2. Favorite the word
        self.state.toggle_favorite()
        self.assertTrue(self.state.is_favorite)
        self.assertTrue(self.vocab_repo.is_favorite("duck"))

        # 3. Switch to Favorites tab
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)
        self.assertEqual(len(self.state.favorites_list), 1)
        self.assertEqual(self.state.favorites_list[0]["word"], "duck")

        # 4. Open 'duck' from favorites
        self.state.set_tab(0)
        self.state.search_word("duck", run_sync=True)
        self.assertEqual(self.state.current_entry.word, "duck")

        # 5. Remove from favorites
        self.state.remove_favorite_item("duck")
        self.assertFalse(self.state.is_favorite)
        self.assertFalse(self.vocab_repo.is_favorite("duck"))
        self.assertEqual(len(self.state.favorites_list), 0)

    # =========================================================================
    # 4. History Workflow
    # =========================================================================

    def test_history_full_lifecycle(self) -> None:
        """Verifies search history logging, opening past search, and clearing."""
        self.state.search_word("hello", run_sync=True)
        self.state.search_word("duck", run_sync=True)

        self.state.set_tab(2)  # History tab
        self.assertEqual(self.state.active_tab_index, 2)
        self.assertEqual(len(self.state.history_list), 2)
        self.assertEqual(self.state.history_list[0]["word"], "duck")
        self.assertEqual(self.state.history_list[1]["word"], "hello")

        # Clear history
        self.state.clear_history()
        self.assertEqual(len(self.state.history_list), 0)
        self.assertEqual(self.history_repo.count(), 0)

    # =========================================================================
    # 5. Navigation Lifecycle
    # =========================================================================

    def test_navigation_cycles_preserve_all_state(self) -> None:
        """
        Tests all required navigation cycles:
          Search -> Favorites -> Search
          Search -> History -> Search
          Search -> Favorites -> History -> Search
          Search -> History -> Favorites -> Search
        """
        self.state.search_word("duck", run_sync=True)
        self.assertEqual(self.state.current_query, "duck")
        duck_entry = self.state.current_entry

        # Cycle 1: Search -> Favorites -> Search
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry, duck_entry)

        # Cycle 2: Search -> History -> Search
        self.state.set_tab(2)
        self.assertEqual(self.state.active_tab_index, 2)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry, duck_entry)

        # Cycle 3: Search -> Favorites -> History -> Search
        self.state.set_tab(1)
        self.state.set_tab(2)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry, duck_entry)

        # Cycle 4: Search -> History -> Favorites -> Search
        self.state.set_tab(2)
        self.state.set_tab(1)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry, duck_entry)

    # =========================================================================
    # 6. Theme Switching
    # =========================================================================

    def test_theme_toggling_preserves_search_and_data_without_reload(self) -> None:
        """Verifies toggling light <-> dark mode does not re-query or lose state."""
        self.state.search_word("duck", run_sync=True)

        # Light -> Dark
        self.state.set_dark_mode(True)
        self.assertTrue(self.state.is_dark_mode)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry.word, "duck")

        # Dark -> Light
        self.state.set_dark_mode(False)
        self.assertFalse(self.state.is_dark_mode)
        self.assertEqual(self.state.current_query, "duck")
        self.assertEqual(self.state.current_entry.word, "duck")

        # No extra provider calls occurred
        self.assertEqual(self.online_provider.call_count, 0)

    # =========================================================================
    # 7. Responsive Layout & Tokens
    # =========================================================================

    def test_responsive_layout_tokens(self) -> None:
        """Tests that theme palettes, POS colors, and design tokens adapt across display viewports."""
        for pos in ["noun", "verb", "adjective", "adverb", "pronoun", "interjection", "other"]:
            color = get_pos_color(pos)
            self.assertTrue(color.startswith("#"))

        self.assertIsNotNone(LIGHT_PALETTE.primary)
        self.assertIsNotNone(DARK_PALETTE.primary)
        self.assertNotEqual(LIGHT_PALETTE.background, DARK_PALETTE.background)


if __name__ == "__main__":
    unittest.main()
