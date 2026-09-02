"""
Cross-platform Audio Player for the Flet client.
Provides native OS audio playback on desktop (Windows, macOS, Linux)
and seamless zero-widget direct stream playback on mobile (Android/iOS)
via page.launch_url, preventing Flutter 'Unknown control: Audio' exceptions.
"""

import os
from pathlib import Path
import platform
import sys
from typing import Any, Callable, Dict, Optional
import urllib.parse
import flet as ft

from dict_core.interfaces.audio import BaseAudioPlayer, PlatformAudioPlayer
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.audio_player")


class FletAudioPlayer(BaseAudioPlayer):
    """
    Cross-platform audio player engine combining native OS multimedia players
    with safe direct-stream launching on mobile devices.
    """

    def __init__(self, page: Optional[ft.Page] = None) -> None:
        self.page = page
        self._native_player = PlatformAudioPlayer()
        self._playing = False
        self._last_backend = "System Audio"
        self._current_url: Optional[str] = None

    def set_page(self, page: ft.Page) -> None:
        """Attaches the active Flet Page."""
        self.page = page

    def set_current_url(self, url: Optional[str]) -> None:
        """Records the online stream URL for the pending audio playback."""
        self._current_url = url

    @property
    def player_name(self) -> str:
        return f"FletAudioPlayer ({self.last_backend_used})"

    @property
    def last_backend_used(self) -> str:
        return self._last_backend

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostics on the audio pipeline and available drivers."""
        native_diag = self._native_player.get_system_diagnostics()
        diag = {
            "player_engine": "FletAudioPlayer",
            "has_page_attached": self.page is not None,
            "is_mobile": self.is_mobile_or_android(),
            "last_backend_used": self.last_backend_used,
            "available_backends": ["Mobile Direct Stream (Zero-Widget Native Audio)"],
        }
        for b in native_diag.get("available_backends", []):
            if b not in diag["available_backends"]:
                diag["available_backends"].append(b)
        return diag

    def is_mobile_or_android(self) -> bool:
        """Detects whether running on Android, iOS, or a mobile client."""
        if hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
            return True
        if self.page:
            plat = str(getattr(self.page, "platform", "")).lower()
            if "android" in plat or "ios" in plat:
                return True
            w = getattr(self.page, "width", None)
            if w is not None and w < 640:
                return True
        return False

    def speak_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Speaks text aloud using native OS speech on desktop or direct TTS stream on mobile."""
        clean_text = str(text or "").strip()
        if not clean_text:
            if on_complete:
                on_complete()
            return

        # On desktop with native TTS (Windows PowerShell, macOS 'say'), use native player
        system = platform.system().lower()
        if not self.is_mobile_or_android() and ("windows" in system or "darwin" in system):
            try:
                self._native_player.speak_text(clean_text, on_complete=on_complete, on_error=on_error)
                self._last_backend = getattr(self._native_player, "last_backend_used", "Native OS Speech")
                return
            except Exception as exc:
                logger.debug("Native desktop TTS failed (%s), falling back to TTS stream...", exc)

        # On mobile/Android or systems without local TTS engine, stream Google TTS audio directly
        encoded = urllib.parse.quote(clean_text)
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
        self.play(tts_url, on_complete=on_complete, on_error=on_error)
        self._last_backend = "Google TTS (Native Stream)"

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Plays audio stream or file.
        On mobile: launches audio stream directly via page.launch_url without mounting
        any widget, completely preventing the 'Unknown control: Audio' Flutter error.
        On desktop: plays via native OS drivers (Windows PowerShell, macOS afplay, Linux mpv/aplay).
        """
        self.stop()
        self._playing = True

        # 1. Mobile (Android / iOS): Direct System Stream Playback (No Widget, No Unknown Control)
        if self.is_mobile_or_android():
            try:
                stream_url = self._current_url
                if not stream_url:
                    if audio_path.startswith("http://") or audio_path.startswith("https://"):
                        stream_url = audio_path
                    else:
                        # Fallback to Google TTS pronunciation for the word
                        stem = Path(audio_path).stem
                        word = stem.replace("audio_", "").split("_")[0]
                        encoded = urllib.parse.quote(word or "word")
                        stream_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"

                if self.page and hasattr(self.page, "launch_url"):
                    self.page.launch_url(stream_url)
                    self._last_backend = "Android System Audio (Direct Stream)"
                    logger.info("[AUDIO PLAYER] Dispatched via page.launch_url for %s", stream_url)
                    self._playing = False
                    if on_complete:
                        on_complete()
                    return
                else:
                    raise RuntimeError("Active Flet page unavailable for audio launching.")
            except Exception as exc:
                logger.warning("Mobile audio dispatch error: %s", exc)
                self._playing = False
                if on_error:
                    on_error(exc)
                else:
                    raise
                return

        # 2. Desktop OS Player Fallback (Windows, macOS, Linux)
        def _wrap_complete():
            self._playing = False
            if on_complete:
                on_complete()

        def _wrap_error(exc: Exception):
            self._playing = False
            if on_error:
                on_error(exc)

        try:
            self._native_player.play(
                audio_path=audio_path,
                on_complete=_wrap_complete,
                on_error=_wrap_error,
            )
            self._last_backend = getattr(self._native_player, "last_backend_used", self._native_player.player_name)
        except Exception as exc:
            self._playing = False
            if on_error:
                on_error(exc)
            else:
                raise

    def stop(self) -> None:
        self._playing = False
        self._native_player.stop()

    def is_playing(self) -> bool:
        return self._playing or self._native_player.is_playing()
