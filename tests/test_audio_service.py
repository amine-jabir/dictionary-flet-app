"""
Unit tests for AudioCacheManager, BaseAudioPlayer, and AudioService.
Verifies binary validation, format detection, atomic writes, and error handling.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
import requests

from dict_core.exceptions import AudioError, AudioPlaybackError, TimeoutError
from dict_core.interfaces.audio import BaseAudioPlayer, NullAudioPlayer, PlatformAudioPlayer
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.services.audio_service import AudioService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.utils.http_client import ResilientHttpClient


class CustomMockPlayer(BaseAudioPlayer):
    """Mock player tracking play/stop invocations and callback triggers."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.played_files = []
        self._playing = False

    @property
    def player_name(self) -> str:
        return "CustomMockPlayer"

    def play(self, audio_path: str, on_complete=None, on_error=None) -> None:
        self._playing = True
        self.played_files.append(audio_path)
        if self.should_fail:
            self._playing = False
            err = RuntimeError("Audio device busy")
            if on_error:
                on_error(err)
            raise err
        self._playing = False
        if on_complete:
            on_complete()

    def stop(self) -> None:
        self._playing = False

    def is_playing(self) -> bool:
        return self._playing


class TestAudioCacheManager(unittest.TestCase):
    """Tests AudioCacheManager file operations, hashing, and size management."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = AudioCacheManager(cache_dir=self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_filename_hashing_and_extensions(self) -> None:
        name_mp3 = self.cache._get_filename_for_url("https://api.dev/media/hello.mp3")
        self.assertTrue(name_mp3.startswith("audio_"))
        self.assertTrue(name_mp3.endswith(".mp3"))

        name_ogg = self.cache._get_filename_for_url("https://api.dev/media/hello.ogg")
        self.assertTrue(name_ogg.endswith(".ogg"))

        # URL without extension infers from OggS magic bytes
        name_inferred_ogg = self.cache._get_filename_for_url("https://api.dev/audio/123", data=b"OggS\x00\x02...")
        self.assertTrue(name_inferred_ogg.endswith(".ogg"))

        # Same URL produces identical hash
        name_mp3_again = self.cache._get_filename_for_url("https://api.dev/media/hello.mp3")
        self.assertEqual(name_mp3, name_mp3_again)

    def test_save_and_retrieve_cached_audio(self) -> None:
        url = "https://example.com/audio/sample.mp3"
        fake_audio_bytes = b"\xff\xfb\x90\x44" + b"\x00" * 100  # Simulated MP3 header & frames

        self.assertFalse(self.cache.is_cached(url))
        self.assertIsNone(self.cache.get_cached_path(url))

        # Save bytes
        saved_path = self.cache.save_audio_bytes(url, fake_audio_bytes)
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.stat().st_size, len(fake_audio_bytes))

        # Check retrieval
        cached_path = self.cache.get_cached_path(url)
        self.assertIsNotNone(cached_path)
        assert cached_path is not None
        self.assertEqual(cached_path, saved_path)
        self.assertTrue(self.cache.is_cached(url))
        self.assertEqual(self.cache.get_cache_size_bytes(), len(fake_audio_bytes))

    def test_corrupted_0_byte_file_is_purged_on_get(self) -> None:
        url = "https://example.com/corrupt.mp3"
        # Manually create empty 0-byte file
        filename = self.cache._get_filename_for_url(url)
        corrupt_file = Path(self.temp_dir.name) / filename
        corrupt_file.touch()

        # get_cached_path should detect empty file, delete it, and return None
        self.assertIsNone(self.cache.get_cached_path(url))
        self.assertFalse(corrupt_file.exists())

    def test_delete_and_clear_cache(self) -> None:
        url1 = "https://example.com/1.mp3"
        url2 = "https://example.com/2.mp3"
        self.cache.save_audio_bytes(url1, b"audio_one_bytes_123456789012345678901234567890")
        self.cache.save_audio_bytes(url2, b"audio_two_bytes_123456789012345678901234567890")

        self.assertTrue(self.cache.delete(url1))
        self.assertFalse(self.cache.is_cached(url1))
        self.assertTrue(self.cache.is_cached(url2))

        # Clear remaining
        self.assertEqual(self.cache.clear(), 1)
        self.assertFalse(self.cache.is_cached(url2))
        self.assertEqual(self.cache.get_cache_size_bytes(), 0)

    def test_save_empty_bytes_raises_error(self) -> None:
        with self.assertRaises(AudioError):
            self.cache.save_audio_bytes("https://example.com/empty.mp3", b"")


class TestAudioService(unittest.TestCase):
    """Tests AudioService URL resolution, downloads, caching, and playback coordination."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_manager = AudioCacheManager(cache_dir=self.temp_dir.name)
        self.mock_http = MagicMock(spec=ResilientHttpClient)
        self.mock_player = CustomMockPlayer()

        self.service = AudioService(
            cache_manager=self.cache_manager,
            http_client=self.mock_http,
            player=self.mock_player,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resolve_audio_url_from_various_types(self) -> None:
        url_str = "https://api.dev/sound.mp3"
        self.assertEqual(self.service.resolve_audio_url(url_str), url_str)

        # Protocol-relative URL
        self.assertEqual(
            self.service.resolve_audio_url("//ssl.gstatic.com/audio.mp3"),
            "https://ssl.gstatic.com/audio.mp3",
        )

        audio_src = AudioSource(url="https://api.dev/source.mp3", accent="us")
        self.assertEqual(self.service.resolve_audio_url(audio_src), "https://api.dev/source.mp3")

        phonetic = Phonetic(text="/test/", audio=[audio_src])
        self.assertEqual(self.service.resolve_audio_url(phonetic), "https://api.dev/source.mp3")

        word_entry = WordEntry(
            word="test",
            phonetics=[phonetic],
            meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition="test")])],
        )
        self.assertEqual(self.service.resolve_audio_url(word_entry), "https://api.dev/source.mp3")

        # WordEntry without phonetics resolves to fallback TTS stream
        no_audio_entry = WordEntry(
            word="fallback",
            meanings=[Meaning(part_of_speech="noun", definitions=[Definition(definition="test")])],
        )
        resolved_fallback = self.service.resolve_audio_url(no_audio_entry)
        self.assertIsNotNone(resolved_fallback)
        self.assertIn("translate.google.com", resolved_fallback)

    def test_download_and_cache_audio_file(self) -> None:
        url = "https://api.dictionaryapi.dev/media/hello-us.mp3"
        fake_binary = b"RIFF....WAVEfmt ...." + b"\x00" * 50

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = fake_binary
        mock_resp.headers = {"Content-Type": "audio/mpeg"}
        self.mock_http.get.return_value = mock_resp

        # 1. First retrieval -> Cache MISS -> Download -> Cache Write
        path1 = self.service.get_audio_file(url)
        self.assertTrue(path1.exists())
        self.assertEqual(path1.read_bytes(), fake_binary)
        self.assertTrue(self.mock_http.get.called)

        # 2. Second retrieval -> Cache HIT -> Zero HTTP requests
        self.mock_http.get.reset_mock()
        path2 = self.service.get_audio_file(url)
        self.assertEqual(path1, path2)
        self.mock_http.get.assert_not_called()  # Verified 0 network calls!

    def test_html_error_response_rejected(self) -> None:
        url = "https://api.dev/fake_audio.mp3"
        html_payload = b"<!DOCTYPE html><html><body>Error 404 Page Not Found</body></html>"

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = html_payload
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.mock_http.get.return_value = mock_resp

        with self.assertRaises(AudioError) as ctx:
            self.service.get_audio_file(url)
        self.assertIn("Content-Type", str(ctx.exception))
        self.assertFalse(self.cache_manager.is_cached(url))

    def test_json_error_response_rejected(self) -> None:
        url = "https://api.dev/fake_audio.mp3"
        json_payload = b'{"error": "file_not_found", "message": "Audio does not exist"}'

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = json_payload
        mock_resp.headers = {"Content-Type": "application/json"}
        self.mock_http.get.return_value = mock_resp

        with self.assertRaises(AudioError):
            self.service.get_audio_file(url)
        self.assertFalse(self.cache_manager.is_cached(url))

    def test_download_http_error_raises_audio_error(self) -> None:
        url = "https://api.dev/missing.mp3"
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 404
        mock_resp.content = b""
        self.mock_http.get.return_value = mock_resp

        with self.assertRaises(AudioError):
            self.service.get_audio_file(url)

    def test_download_timeout_propagates(self) -> None:
        url = "https://api.dev/slow.mp3"
        self.mock_http.get.side_effect = TimeoutError("Download timed out")

        with self.assertRaises(TimeoutError):
            self.service.get_audio_file(url)

    def test_play_successful_flow(self) -> None:
        url = "https://api.dev/play.mp3"
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"\xff\xfb\x90\x44" + b"\x00" * 60
        mock_resp.headers = {"Content-Type": "audio/mpeg"}
        self.mock_http.get.return_value = mock_resp

        complete_called = False

        def on_complete_callback():
            nonlocal complete_called
            complete_called = True

        played_path = self.service.play(url, on_complete=on_complete_callback)
        self.assertTrue(played_path.exists())
        self.assertTrue(complete_called)
        self.assertEqual(len(self.mock_player.played_files), 1)
        self.assertEqual(self.mock_player.played_files[0], str(played_path))

    def test_play_driver_error_handling(self) -> None:
        failing_player = CustomMockPlayer(should_fail=True)
        service = AudioService(
            cache_manager=self.cache_manager,
            http_client=self.mock_http,
            player=failing_player,
        )

        url = "https://api.dev/error_play.mp3"
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.content = b"\xff\xfb\x90\x44" + b"\x00" * 60
        mock_resp.headers = {"Content-Type": "audio/mpeg"}
        self.mock_http.get.return_value = mock_resp

        error_caught = None

        def on_error_callback(exc):
            nonlocal error_caught
            error_caught = exc

        with self.assertRaises(AudioPlaybackError):
            service.play(url, on_error=on_error_callback)

        self.assertIsNotNone(error_caught)

    def test_null_player_default_behavior(self) -> None:
        null_player = NullAudioPlayer()
        self.assertEqual(null_player.player_name, "NullAudioPlayer (Headless)")
        self.assertFalse(null_player.is_playing())

        completed = False
        null_player.play("/fake/path.mp3", on_complete=lambda: None)
        null_player.stop()
        self.assertFalse(null_player.is_playing())


if __name__ == "__main__":
    unittest.main()
