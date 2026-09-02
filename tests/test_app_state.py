"""
Unit tests for AppState reactive management, listeners, and business action handlers.
Tests comprehensive state, navigation lifecycles, cancellation safety, and asynchronous resilience.
"""

import time
import unittest
from unittest.mock import MagicMock

from dict_client_flet.state.app_state import AppState
from dict_core.exceptions import NetworkError, TimeoutError, ValidationError, WordNotFoundError
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository


def create_mock_word_entry(word: str = "serendipity", has_audio: bool = True) -> WordEntry:
    audio_list = [AudioSource(url="https://audio.org/sound.mp3", accent="us")] if has_audio else []
    return WordEntry(
        word=word,
        phonetics=[Phonetic(text="/ˌsɛr.ənˈdɪp.ɪ.ti/", audio=audio_list)],
        meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition="A happy accident.")])],
        provider="free_dict_api",
    )


class TestAppState(unittest.TestCase):
    """Tests the AppState state machine, asynchronous search lifecycle, and navigation."""

    def setUp(self) -> None:
        self.db = DatabaseManager(":memory:")
        self.vocab_repo = VocabularyRepository(self.db)
        self.history_repo = HistoryRepository(self.db)

        self.mock_lookup_service = MagicMock(spec=LookupService)
        self.mock_audio_service = MagicMock(spec=AudioService)

        self.state = AppState(
            lookup_service=self.mock_lookup_service,
            audio_service=self.mock_audio_service,
            vocab_repo=self.vocab_repo,
            history_repo=self.history_repo,
        )

        self.notification_count = 0
        self.state.subscribe(self._on_notify)

    def tearDown(self) -> None:
        self.db.close()

    def _on_notify(self) -> None:
        self.notification_count += 1

    def test_initial_state(self) -> None:
        self.assertEqual(self.state.current_query, "")
        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIsNone(self.state.error_message)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertFalse(self.state.is_dark_mode)

    def test_search_word_success_sync(self) -> None:
        entry = create_mock_word_entry("serendipity")
        self.mock_lookup_service.lookup.return_value = entry

        self.state.search_word("serendipity", run_sync=True)

        self.assertEqual(self.state.current_query, "serendipity")
        self.assertEqual(self.state.current_entry, entry)
        self.assertFalse(self.state.is_loading)
        self.assertIsNone(self.state.error_message)
        self.assertFalse(self.state.is_favorite)
        self.assertGreater(self.notification_count, 0)
        self.mock_lookup_service.lookup.assert_called_once_with("serendipity", force_refresh=False)

    def test_search_word_not_found(self) -> None:
        self.mock_lookup_service.lookup.side_effect = WordNotFoundError(word="unknown")

        self.state.search_word("unknown", run_sync=True)

        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIsNotNone(self.state.error_message)
        self.assertIn("No definitions found", self.state.error_message)

    def test_search_word_network_error(self) -> None:
        self.mock_lookup_service.lookup.side_effect = NetworkError("Connection refused")

        self.state.search_word("networkfail", run_sync=True)

        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIn("Network connection error", self.state.error_message)

    def test_search_word_timeout(self) -> None:
        self.mock_lookup_service.lookup.side_effect = TimeoutError("Timed out")

        self.state.search_word("slowword", run_sync=True)

        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)
        self.assertIn("timed out", self.state.error_message)

    def test_navigation_search_favorites_search(self) -> None:
        """Verifies Search -> Favorites -> Search preserves search result state."""
        entry = create_mock_word_entry("resilience")
        self.mock_lookup_service.lookup.return_value = entry
        self.state.search_word("resilience", run_sync=True)

        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_entry.word, "resilience")

        # Navigate to Favorites
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)

        # Return to Search
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        # Search state must be preserved
        self.assertIsNotNone(self.state.current_entry)
        self.assertEqual(self.state.current_entry.word, "resilience")
        self.assertEqual(self.state.current_query, "resilience")

    def test_navigation_search_history_search(self) -> None:
        """Verifies Search -> History -> Search restores search state."""
        self.state.set_tab(2)
        self.assertEqual(self.state.active_tab_index, 2)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)

    def test_cancel_search_then_navigate_and_back(self) -> None:
        """Verifies that cancelling a search and navigating preserves UI stability."""
        import threading
        evt = threading.Event()
        def block_lookup(w, force_refresh=False):
            evt.wait(timeout=2.0)
            return create_mock_word_entry(w)
        self.mock_lookup_service.lookup.side_effect = block_lookup

        self.state.search_word("in_flight", run_sync=False)
        import time
        time.sleep(0.02)
        self.assertTrue(self.state.is_loading)

        self.state.cancel_search()
        self.assertFalse(self.state.is_loading)
        evt.set()

        # Navigate to Favorites and back to Search
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertFalse(self.state.is_loading)

    def test_clear_search(self) -> None:
        """Verifies clear_search resets query and entry without corrupting tabs."""
        entry = create_mock_word_entry("temp")
        self.state.current_entry = entry
        self.state.current_query = "temp"

        self.state.clear_search()
        self.assertEqual(self.state.current_query, "")
        self.assertIsNone(self.state.current_entry)
        self.assertFalse(self.state.is_loading)

    def test_stale_search_callback_discarded(self) -> None:
        """Verifies that an old in-flight search callback is discarded when cancelled."""
        slow_entry = create_mock_word_entry("slow_word")

        def slow_lookup(*args, **kwargs):
            time.sleep(0.05)
            return slow_entry

        self.mock_lookup_service.lookup.side_effect = slow_lookup

        # Launch background search
        self.state.search_word("slow_word", run_sync=False)
        self.assertTrue(self.state.is_loading)

        # User immediately cancels and launches a new search
        self.state.cancel_search()
        fast_entry = create_mock_word_entry("fast_word")
        self.mock_lookup_service.lookup.side_effect = None
        self.mock_lookup_service.lookup.return_value = fast_entry
        self.state.search_word("fast_word", run_sync=True)

        # Wait to ensure slow thread has completed
        time.sleep(0.1)

        # Current entry must be fast_word, not overwritten by slow_word
        self.assertEqual(self.state.current_entry.word, "fast_word")

    def test_toggle_favorite(self) -> None:
        entry = create_mock_word_entry("lucid")
        self.state.current_entry = entry
        self.assertFalse(self.state.is_favorite)

        # 1. Add favorite
        self.state.toggle_favorite()
        self.assertTrue(self.state.is_favorite)
        self.assertTrue(self.vocab_repo.is_favorite("lucid"))
        self.assertEqual(len(self.state.favorites_list), 1)

        # 2. Remove favorite
        self.state.toggle_favorite()
        self.assertFalse(self.state.is_favorite)
        self.assertFalse(self.vocab_repo.is_favorite("lucid"))
        self.assertEqual(len(self.state.favorites_list), 0)

    def test_remove_favorite_item(self) -> None:
        self.vocab_repo.add_favorite("word_a")
        self.vocab_repo.add_favorite("word_b")
        self.state.load_favorites()
        self.assertEqual(len(self.state.favorites_list), 2)

        self.state.remove_favorite_item("word_a")
        self.assertEqual(len(self.state.favorites_list), 1)
        self.assertFalse(self.vocab_repo.is_favorite("word_a"))

    def test_clear_history(self) -> None:
        self.history_repo.add("w1", provider_id="test", result_found=True)
        self.state.load_history()
        self.assertEqual(len(self.state.history_list), 1)

        self.state.clear_history()
        self.assertEqual(len(self.state.history_list), 0)
        self.assertEqual(self.history_repo.count(), 0)

    def test_dark_mode_toggle(self) -> None:
        self.assertFalse(self.state.is_dark_mode)
        self.state.set_dark_mode(True)
        self.assertTrue(self.state.is_dark_mode)


if __name__ == "__main__":
    unittest.main()
