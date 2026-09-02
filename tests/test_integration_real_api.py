"""
Live real API integration tests for FreeDictProvider, WiktionaryProvider, and AudioService.
These tests execute live HTTP requests against api.dictionaryapi.dev and en.wiktionary.org.

To ensure the normal development test suite (python -m unittest discover) runs deterministically
and finishes in ~1-2 seconds without waiting for external API latency or timeouts, these live
tests are OPT-IN.

To run live integration tests explicitly:
    python -m unittest tests/test_integration_real_api.py -v
or:
    DICT_LIVE_TESTS=1 python -m unittest discover -s tests -p "test_*.py" -v
"""

import os
import socket
import sys
import tempfile
import unittest

from dict_core.exceptions import NetworkError, TimeoutError, WordNotFoundError
from dict_core.models.word import WordEntry
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.services.audio_service import AudioService
from dict_core.storage.audio_cache import AudioCacheManager


def is_live_test_enabled() -> bool:
    """
    Returns True only when live external API tests are explicitly requested,
    either via the DICT_LIVE_TESTS environment variable or when this test
    file is executed directly.
    """
    if os.environ.get("DICT_LIVE_TESTS", "").strip().lower() in ("1", "true", "yes"):
        return True
    # If the user targets this test file directly in command line arguments
    for arg in sys.argv:
        if "test_integration_real_api" in arg:
            return True
    return False


def is_online() -> bool:
    """Checks if external internet connectivity is currently available."""
    try:
        socket.gethostbyname("api.dictionaryapi.dev")
        return True
    except Exception:
        return False


SKIP_REASON = (
    "Live API integration tests are opt-in to keep normal unit tests fast. "
    "Run directly with: 'python -m unittest tests/test_integration_real_api.py -v' "
    "or set DICT_LIVE_TESTS=1."
)


class TestRealApiIntegration(unittest.TestCase):
    """Live API integration tests against real dictionary and audio servers."""

    def setUp(self) -> None:
        self.free_provider = FreeDictProvider()
        self.wiki_provider = WiktionaryProvider()

    @unittest.skipUnless(is_live_test_enabled() and is_online(), SKIP_REASON)
    def test_live_free_dict_lookup_hello(self) -> None:
        entry = self.free_provider.lookup("hello")
        self.assertIsInstance(entry, WordEntry)
        self.assertEqual(entry.word.lower(), "hello")
        self.assertTrue(len(entry.meanings) > 0)
        self.assertTrue(entry.total_definitions_count > 0)
        self.assertTrue(len(entry.phonetics) > 0)
        self.assertIsNotNone(entry.primary_audio_url)
        self.assertTrue(entry.primary_audio_url.startswith("http"))
        self.assertEqual(entry.provider, "free_dict_api")

    @unittest.skipUnless(is_live_test_enabled() and is_online(), SKIP_REASON)
    def test_live_wiktionary_lookup_hello(self) -> None:
        entry = self.wiki_provider.lookup("hello")
        self.assertIsInstance(entry, WordEntry)
        self.assertEqual(entry.word.lower(), "hello")
        self.assertTrue(len(entry.meanings) > 0)
        self.assertTrue(entry.total_definitions_count > 0)
        # Ensure HTML tags are stripped
        first_def = entry.meanings[0].definitions[0].definition
        self.assertNotIn("<p>", first_def)
        self.assertNotIn("</p>", first_def)
        self.assertEqual(entry.provider, "wiktionary_rest")

    @unittest.skipUnless(is_live_test_enabled() and is_online(), SKIP_REASON)
    def test_live_audio_download_and_caching(self) -> None:
        """
        Tests live download and binary caching of a real pronunciation MP3 file.
        Verifies that when the external host responds, the asset is a valid,
        non-empty binary file (>1KB) and subsequent lookups are resolved from
        local cache with zero network calls.
        """
        entry = self.free_provider.lookup("hello")
        self.assertIsNotNone(entry.primary_audio_url)

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_cache = AudioCacheManager(cache_dir=tmpdir)
            audio_service = AudioService(cache_manager=audio_cache)

            # 1. First retrieval -> Downloads and caches binary file
            try:
                audio_path = audio_service.get_audio_file(entry)
            except (TimeoutError, NetworkError) as exc:
                self.skipTest(
                    f"External media server timed out: {exc}. "
                    "This is an external media CDN latency issue, not an application bug."
                )

            self.assertTrue(audio_path.exists())
            self.assertTrue(audio_path.is_file())
            file_size = audio_path.stat().st_size
            # Pronunciation MP3 files are typically > 1 KB
            self.assertGreater(file_size, 1000)

            # Verify it is binary, not an HTML/JSON error page
            head = audio_path.read_bytes()[:64].lower()
            self.assertFalse(head.startswith(b"<!doctype"))
            self.assertFalse(head.startswith(b"<html"))
            self.assertFalse(head.startswith(b'{"'))

            # 2. Second retrieval -> Uses local cached file with zero network calls
            second_path = audio_service.get_audio_file(entry)
            self.assertEqual(audio_path, second_path)
            self.assertTrue(audio_cache.is_cached(entry.primary_audio_url))

    @unittest.skipUnless(is_live_test_enabled() and is_online(), SKIP_REASON)
    def test_live_free_dict_404_not_found(self) -> None:
        non_word = "qwertyuiopnonexistentword"
        try:
            self.free_provider.lookup(non_word)
            self.fail(f"Expected lookup for '{non_word}' to fail, but it returned a result.")
        except WordNotFoundError as exc:
            self.assertEqual(exc.word, non_word)
        except (TimeoutError, NetworkError) as exc:
            self.skipTest(
                f"Upstream api.dictionaryapi.dev timed out on cold cache miss: {exc}. "
                "This is an external community API latency issue, not an application bug."
            )

    @unittest.skipUnless(is_live_test_enabled() and is_online(), SKIP_REASON)
    def test_live_wiktionary_404_not_found(self) -> None:
        non_word = "qwertyuiopnonexistentword"
        with self.assertRaises(WordNotFoundError) as ctx:
            self.wiki_provider.lookup(non_word)
        self.assertEqual(ctx.exception.word, non_word)


if __name__ == "__main__":
    unittest.main()
