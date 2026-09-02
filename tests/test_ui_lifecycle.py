"""
UI Lifecycle, View Construction, and Navigation Sequence Tests.
Verifies that all views build cleanly and navigation cycles preserve application state.
"""

import time
import unittest
from unittest.mock import MagicMock

try:
    import flet as ft
    HAS_FLET = True
except ImportError:
    HAS_FLET = False

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.theme import DARK_PALETTE, LIGHT_PALETTE
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository


def create_sample_word(word: str = "resilience") -> WordEntry:
    return WordEntry(
        word=word,
        phonetics=[Phonetic(text="/rɪˈzɪl.jəns/", audio=[AudioSource(url="https://audio.org/res.mp3", accent="us")])],
        meanings=[
            Meaning(
                part_of_speech="noun",
                definitions=[
                    Definition(
                        definition="The capacity to recover quickly from difficulties.",
                        example="Her resilience in the face of adversity was remarkable.",
                        synonyms=["toughness", "flexibility"],
                    )
                ],
                synonyms=["endurance", "strength"],
            )
        ],
        provider="free_dict_api",
    )


class TestUILifecycleAndNavigation(unittest.TestCase):
    """Verifies UI view creation, navigation transitions, and search lifecycles."""

    def setUp(self) -> None:
        self.db = DatabaseManager(":memory:")
        self.vocab_repo = VocabularyRepository(self.db)
        self.history_repo = HistoryRepository(self.db)
        self.mock_lookup = MagicMock(spec=LookupService)
        self.mock_audio = MagicMock(spec=AudioService)

        self.state = AppState(
            lookup_service=self.mock_lookup,
            audio_service=self.mock_audio,
            vocab_repo=self.vocab_repo,
            history_repo=self.history_repo,
            debug_diagnostics=False,
        )

    def tearDown(self) -> None:
        self.db.close()

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_search_screen_creation_welcome_state(self) -> None:
        from dict_client_flet.ui.views.lookup_view import build_lookup_view
        view = build_lookup_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(view)
        self.assertEqual(self.state.active_tab_index, 0)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_search_screen_creation_results_state(self) -> None:
        from dict_client_flet.ui.views.lookup_view import build_lookup_view
        entry = create_sample_word("resilience")
        self.mock_lookup.lookup.return_value = entry
        self.state.search_word("resilience", run_sync=True)

        view = build_lookup_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(view)
        self.assertEqual(self.state.current_entry, entry)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_search_screen_creation_loading_state(self) -> None:
        from dict_client_flet.ui.views.lookup_view import build_lookup_view
        self.state.is_loading = True
        self.state.current_query = "loading_word"
        view = build_lookup_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(view)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_search_screen_creation_error_state(self) -> None:
        from dict_client_flet.ui.views.lookup_view import build_lookup_view
        self.state.error_message = "Sample error message"
        view = build_lookup_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(view)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_favorites_screen_creation_empty_and_populated(self) -> None:
        from dict_client_flet.ui.views.favorites_view import build_favorites_view
        empty_view = build_favorites_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(empty_view)

        self.vocab_repo.add_favorite("word_1", notes="Study note", tags=["tag1"])
        self.state.load_favorites()
        populated_view = build_favorites_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(populated_view)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_history_screen_creation_empty_and_populated(self) -> None:
        from dict_client_flet.ui.views.history_view import build_history_view
        empty_view = build_history_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(empty_view)

        self.history_repo.add("searched_word", provider_id="test", result_found=True)
        self.state.load_history()
        populated_view = build_history_view(self.state, LIGHT_PALETTE)
        self.assertIsNotNone(populated_view)

    def test_navigation_sequence_search_favorites_search(self) -> None:
        entry = create_sample_word("lucid")
        self.mock_lookup.lookup.return_value = entry
        self.state.search_word("lucid", run_sync=True)

        # Tab 0 -> Tab 1 -> Tab 0
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)

        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertEqual(self.state.current_query, "lucid")
        self.assertEqual(self.state.current_entry, entry)

    def test_navigation_sequence_cancel_search_favorites_search(self) -> None:
        def slow_lookup(*args, **kwargs):
            time.sleep(0.1)
            return create_sample_word("slow")

        self.mock_lookup.lookup.side_effect = slow_lookup
        self.state.search_word("slow", run_sync=False)
        self.assertTrue(self.state.is_loading)

        # Cancel search
        self.state.cancel_search()
        self.assertFalse(self.state.is_loading)

        # Open Favorites
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)

        # Return to Search
        self.state.set_tab(0)
        self.assertEqual(self.state.active_tab_index, 0)
        self.assertFalse(self.state.is_loading)

    def test_stale_search_callback_does_not_overwrite_navigated_screen(self) -> None:
        def very_slow_lookup(*args, **kwargs):
            time.sleep(0.15)
            return create_sample_word("stale_term")

        self.mock_lookup.lookup.side_effect = very_slow_lookup
        self.state.search_word("stale_term", run_sync=False)

        # Navigate to Favorites while search is in flight
        self.state.set_tab(1)
        self.assertEqual(self.state.active_tab_index, 1)

        # Cancel or start a new search
        self.state.cancel_search()

        time.sleep(0.2)
        # Verify stale search did not corrupt active tab
        self.assertEqual(self.state.active_tab_index, 1)


if __name__ == "__main__":
    unittest.main()
