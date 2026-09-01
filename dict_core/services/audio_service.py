"""
AudioService for dict_core.
Coordinates binary pronunciation downloads, disk caching, and platform playback drivers.
Includes end-to-end diagnostic tracing and inspection tools.
"""

from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Union
import urllib.parse

from dict_core.exceptions import AudioError, AudioPlaybackError, NetworkError, TimeoutError
from dict_core.interfaces.audio import BaseAudioPlayer, NullAudioPlayer, PlatformAudioPlayer
from dict_core.models.word import AudioSource, Phonetic, WordEntry
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.utils.http_client import ResilientHttpClient
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.services.audio")


class AudioService:
    """
    High-level service managing audio pronunciation asset retrieval, caching, playback,
    and diagnostic inspection.
    """

    def __init__(
        self,
        cache_manager: Optional[AudioCacheManager] = None,
        http_client: Optional[ResilientHttpClient] = None,
        player: Optional[BaseAudioPlayer] = None,
    ) -> None:
        self.cache = cache_manager or AudioCacheManager()
        self.client = http_client or ResilientHttpClient()
        # Default to platform native player for real desktop sound
        self.player = player or PlatformAudioPlayer()
        logger.info("[AUDIO PIPELINE] PLAYER CREATED: %s", self.player.player_name)

    def resolve_audio_url(self, source: Union[str, AudioSource, Phonetic, WordEntry]) -> Optional[str]:
        """
        Extracts a valid audio URL string from various input types.
        """
        if isinstance(source, str) and source.strip():
            url = source.strip()
            # If URL lacks protocol (e.g. //ssl.gstatic.com/...), prepend https:
            if url.startswith("//"):
                url = "https:" + url
            elif not (url.startswith("http://") or url.startswith("https://")):
                encoded = urllib.parse.quote(url)
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
            return url

        if isinstance(source, AudioSource):
            return self.resolve_audio_url(source.url) if source.url else None

        if isinstance(source, Phonetic):
            if source.primary_audio_url:
                return self.resolve_audio_url(source.primary_audio_url)
            return None

        if isinstance(source, WordEntry):
            if source.primary_audio_url:
                return self.resolve_audio_url(source.primary_audio_url)
            if source.word:
                encoded = urllib.parse.quote(source.word)
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
                return url

        return None

    def _validate_audio_payload(self, content: bytes, content_type: Optional[str] = None, url: str = "") -> None:
        """
        Validates that downloaded bytes represent legitimate audio content rather than an HTML/JSON error page.
        """
        if not content or len(content) < 32:
            raise AudioError(f"Downloaded audio payload for '{url}' is empty or too small ({len(content) if content else 0} bytes).")

        # 1. Inspect Content-Type header if provided
        if content_type:
            ct = content_type.lower().strip()
            if ct.startswith("text/") or "html" in ct or "json" in ct or "xml" in ct or "javascript" in ct:
                raise AudioError(
                    f"Expected audio stream for '{url}', but received invalid Content-Type '{ct}'",
                    details={"content_type": ct, "url": url},
                )

        # 2. Inspect signature / magic bytes (detect HTML or JSON error responses)
        head = content[:64].strip().lower()
        if (
            head.startswith(b"<!doctype")
            or head.startswith(b"<html")
            or head.startswith(b"<?xml")
            or head.startswith(b"{\n")
            or head.startswith(b'{"')
            or head.startswith(b"{ \"")
        ):
            raise AudioError(
                f"Downloaded response for '{url}' is an HTML/JSON error page, not a binary audio file.",
                details={"snippet": head[:30].decode("latin-1", errors="ignore"), "url": url},
            )

    def get_audio_file(self, source: Union[str, AudioSource, Phonetic, WordEntry]) -> Path:
        """
        Retrieves the local Path for an audio source, downloading and caching it if not already cached.
        """
        url = self.resolve_audio_url(source)
        if not url:
            raise AudioError("No audio URL found in the provided source.")

        # 1. Check disk cache
        cached_path = self.cache.get_cached_path(url)
        if cached_path:
            logger.info("[AUDIO PIPELINE] CACHE HIT: %s (path=%s, size=%d bytes)", url, cached_path.name, cached_path.stat().st_size)
            return cached_path

        # 2. Download from remote source
        logger.info("[AUDIO PIPELINE] CACHE MISS: downloading from %s", url)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = self.client.get(url, timeout=10.0, headers=headers)
            if response.status_code != 200 or not response.content:
                raise AudioError(
                    f"Server returned HTTP {response.status_code} with empty audio content for '{url}'",
                    details={"status_code": response.status_code, "url": url},
                )

            content_type = response.headers.get("Content-Type", "audio/mpeg")
            self._validate_audio_payload(response.content, content_type=content_type, url=url)

            # Save binary content to disk cache atomically
            saved_path = self.cache.save_audio_bytes(url, response.content)
            logger.info(
                "[AUDIO PIPELINE] FILE CACHED: %s | SIZE: %d bytes | TYPE: %s",
                str(saved_path), saved_path.stat().st_size, content_type
            )
            return saved_path

        except (AudioError, TimeoutError, NetworkError):
            raise
        except Exception as exc:
            raise AudioError(f"Failed to download audio from '{url}': {exc}") from exc

    def play(
        self,
        source: Union[str, AudioSource, Phonetic, WordEntry],
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Path:
        """
        Resolves/downloads the audio file and triggers playback on the configured player engine.
        """
        logger.info("[AUDIO PIPELINE] PLAY REQUEST initiated")
        try:
            local_path = self.get_audio_file(source)
        except Exception as exc:
            logger.error("[AUDIO PIPELINE] PLAY REQUEST FAILED during download/cache: %s", exc)
            if on_error:
                on_error(exc)
            raise

        logger.info("[AUDIO PIPELINE] PLAYER SOURCE SET: %s", str(local_path))
        logger.info("[AUDIO PIPELINE] PLAYBACK STARTED on %s", self.player.player_name)

        def _wrapped_complete():
            logger.info("[AUDIO PIPELINE] PLAYBACK COMPLETE: success")
            if on_complete:
                on_complete()

        def _wrapped_error(exc: Exception):
            logger.error("[AUDIO PIPELINE] PLAYBACK ERROR: %s", exc)
            if on_error:
                on_error(exc)

        try:
            self.player.play(
                audio_path=str(local_path),
                on_complete=_wrapped_complete,
                on_error=_wrapped_error,
            )
            return local_path
        except Exception as exc:
            playback_err = AudioPlaybackError(f"Playback failed on player '{self.player.player_name}': {exc}")
            _wrapped_error(playback_err)
            raise playback_err from exc

    def stop(self) -> None:
        """Stops active audio playback."""
        logger.info("[AUDIO PIPELINE] PLAYBACK STOPPED")
        self.player.stop()

    def is_playing(self) -> bool:
        """Checks if audio is currently playing."""
        return self.player.is_playing()

    def diagnose_audio(self, source: Union[str, AudioSource, Phonetic, WordEntry]) -> Dict[str, Any]:
        """
        Performs a full diagnostic trace of the audio resolution, network download,
        disk cache, and playback driver for a given source.
        Returns a structured dictionary with log lines and diagnostic properties.
        """
        logs: List[str] = []
        start_time = time.time()

        def log(msg: str) -> None:
            elapsed = time.time() - start_time
            logs.append(f"[{elapsed:06.3f}s] {msg}")

        result: Dict[str, Any] = {
            "source_type": type(source).__name__,
            "resolved_url": None,
            "is_cached": False,
            "cache_file_path": None,
            "cache_file_size": 0,
            "http_status": None,
            "content_type": None,
            "download_size": 0,
            "player_engine": self.player.player_name,
            "status": "UNKNOWN",
            "error": None,
            "logs": logs,
        }

        # 1. Resolve URL
        log(f"Step 1: Resolving audio URL from source ({type(source).__name__})...")
        url = self.resolve_audio_url(source)
        result["resolved_url"] = url
        if not url:
            log("ERROR: No valid audio URL or text could be resolved.")
            result["status"] = "URL_RESOLUTION_FAILED"
            result["error"] = "No audio URL found in source."
            return result

        log(f"URL resolved successfully: {url}")

        # 2. Check Disk Cache
        log(f"Step 2: Checking local cache directory ({self.cache.cache_dir})...")
        cached_path = self.cache.get_cached_path(url)
        if cached_path and cached_path.exists():
            size = cached_path.stat().st_size
            result["is_cached"] = True
            result["cache_file_path"] = str(cached_path)
            result["cache_file_size"] = size
            log(f"Cache HIT: File exists on disk ({cached_path.name}, {size} bytes).")
        else:
            log("Cache MISS: File not yet cached on disk.")

        # 3. Test Network Download (if not cached or to verify server)
        if not result["is_cached"]:
            log(f"Step 3: Attempting HTTP GET request to {url} (timeout=10.0s)...")
            try:
                t0 = time.time()
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                response = self.client.get(url, timeout=10.0, headers=headers)
                t_req = time.time() - t0
                result["http_status"] = response.status_code
                result["content_type"] = response.headers.get("Content-Type", "unknown")
                result["download_size"] = len(response.content) if response.content else 0

                log(f"HTTP response received in {t_req:.2f}s: Status {response.status_code}, Content-Type: '{result['content_type']}', Body: {result['download_size']} bytes.")

                if response.status_code != 200 or not response.content:
                    log(f"ERROR: Upstream server returned HTTP {response.status_code} with empty/invalid payload.")
                    result["status"] = "HTTP_ERROR"
                    result["error"] = f"HTTP {response.status_code}"
                    return result

                # Validate payload
                self._validate_audio_payload(response.content, content_type=result["content_type"], url=url)
                log("Binary audio validation check: PASSED (valid audio stream, not HTML/JSON).")

                # Save to cache
                saved_path = self.cache.save_audio_bytes(url, response.content)
                result["cache_file_path"] = str(saved_path)
                result["cache_file_size"] = saved_path.stat().st_size
                result["is_cached"] = True
                log(f"File atomically persisted to disk cache: {saved_path.name} ({result['cache_file_size']} bytes).")

            except Exception as exc:
                log(f"ERROR during download/caching: {exc}")
                result["status"] = "DOWNLOAD_FAILED"
                result["error"] = str(exc)
                return result

        # 4. Inspect Audio Player Driver
        log(f"Step 4: Inspecting Audio Player engine ({self.player.player_name})...")
        if isinstance(self.player, PlatformAudioPlayer):
            sys_diag = self.player.get_system_diagnostics()
            result["system_diagnostics"] = sys_diag
            log(f"System Audio Backends Available: {', '.join(sys_diag['available_backends'])}")

        result["status"] = "READY_FOR_PLAYBACK"
        log("Diagnostic check finished: Audio asset is ready and verified.")
        return result
