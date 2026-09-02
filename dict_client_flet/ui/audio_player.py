"""
Cross-platform Audio Player for the Flet client.
Integrates Flet's ft.Audio control for mobile (Android/iOS) and web with
native OS fallback playback (Windows, macOS, Linux). Supports live pronunciation
playback and Text-to-Speech (TTS).
"""

import os
from pathlib import Path
import platform
import sys
import threading
from typing import Any, Callable, Dict, Optional
import urllib.parse
import flet as ft

from dict_core.interfaces.audio import BaseAudioPlayer, PlatformAudioPlayer
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.audio_player")


class FletAudioPlayer(BaseAudioPlayer):
    """
    Cross-platform audio player engine combining Flet's ft.Audio control
    with native OS multimedia fallbacks.
    """

    def __init__(self, page: Optional[ft.Page] = None) -> None:
        self.page = page
        self._native_player = PlatformAudioPlayer()
        self._audio_control: Optional[ft.Audio] = None
        self._playing = False
        self._last_backend = "Flet ft.Audio"

        if self.page is not None:
            self._init_flet_audio()

    def set_page(self, page: ft.Page) -> None:
        """Attaches the active Flet Page."""
        self.page = page
        self._init_flet_audio()

    def _init_flet_audio(self) -> None:
        """Initializes and mounts the ft.Audio control into the Page overlay."""
        if not self.page:
            return
        try:
            if not self._audio_control:
                self._audio_control = ft.Audio(
                    src="",
                    autoplay=False,
                    volume=1.0,
                    on_state_changed=self._on_state_changed,
                )
                if hasattr(self.page, "overlay"):
                    self.page.overlay.append(self._audio_control)
                    self.page.update()
        except Exception as exc:
            logger.debug("Could not mount ft.Audio in overlay: %s", exc)

    def _on_state_changed(self, e: Any) -> None:
        state = str(getattr(e, "data", "") or getattr(e, "state", "") or "").lower()
        if "completed" in state or "stopped" in state:
            self._playing = False

    @property
    def player_name(self) -> str:
        return f"FletAudioPlayer ({self.last_backend_used})"

    @property
    def last_backend_used(self) -> str:
        return self._last_backend

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostics on the Flet audio pipeline and underlying platform drivers."""
        native_diag = self._native_player.get_system_diagnostics()
        diag = {
            "player_engine": "FletAudioPlayer",
            "has_page_attached": self.page is not None,
            "flet_audio_mounted": self._audio_control is not None,
            "last_backend_used": self.last_backend_used,
            "available_backends": ["Flet ft.Audio (Android / iOS / Desktop Cross-Platform)"],
        }
        for b in native_diag.get("available_backends", []):
            if b not in diag["available_backends"]:
                diag["available_backends"].append(b)
        return diag

    def is_mobile_or_android(self) -> bool:
        """Detects whether running on Android or a mobile client."""
        if hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
            return True
        if self.page:
            plat = str(getattr(self.page, "platform", "")).lower()
            if "android" in plat or "ios" in plat:
                return True
        return False

    def speak_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Speaks text aloud using native OS Speech Synthesis or TTS audio stream fallback."""
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
                logger.debug("Native TTS failed (%s), falling back to TTS stream...", exc)

        # On mobile / Android or Linux without speech engine, synthesize via online TTS audio stream
        encoded = urllib.parse.quote(clean_text)
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
        self.play(tts_url, on_complete=on_complete, on_error=on_error)
        self._last_backend = "Google TTS Audio Stream (Flet Audio)"

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Plays audio stream or file using Flet's ft.Audio engine, with native OS fallback."""
        self.stop()
        self._playing = True

        # 1. Attempt playback via Flet ft.Audio (Primary for Mobile / Android / Cross-Platform)
        if self.page and hasattr(self.page, "overlay"):
            try:
                # Recreate ft.Audio control cleanly to avoid Flutter audioplayers state collisions
                if self._audio_control:
                    try:
                        if hasattr(self._audio_control, "release"):
                            self._audio_control.release()
                        if self._audio_control in self.page.overlay:
                            self.page.overlay.remove(self._audio_control)
                    except Exception:
                        pass

                def _handle_state_changed(e: Any) -> None:
                    state = str(getattr(e, "data", "") or getattr(e, "state", "") or "").lower()
                    if "completed" in state or "stopped" in state:
                        self._playing = False
                        if on_complete:
                            try:
                                on_complete()
                            except Exception:
                                pass

                src_uri = audio_path
                if not (audio_path.startswith("http://") or audio_path.startswith("https://")):
                    src_uri = str(Path(audio_path).resolve())

                self._audio_control = ft.Audio(
                    src=src_uri,
                    autoplay=True,
                    volume=1.0,
                    on_state_changed=_handle_state_changed,
                )
                self.page.overlay.append(self._audio_control)
                self.page.update()

                if hasattr(self._audio_control, "play"):
                    try:
                        self._audio_control.play()
                    except Exception:
                        pass

                self._last_backend = "Flet ft.Audio (Flutter audioplayers)"
                logger.info("[AUDIO PLAYER] Playback dispatched via Flet ft.Audio: %s", src_uri)
                return
            except Exception as exc:
                logger.warning("Flet ft.Audio dispatch error (%s), attempting native fallback...", exc)

        # 2. Native OS Player Fallback (Desktop Windows, macOS, Linux)
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
        if self._audio_control:
            try:
                if hasattr(self._audio_control, "pause"):
                    self._audio_control.pause()
                if hasattr(self._audio_control, "release"):
                    self._audio_control.release()
            except Exception:
                pass
        self._native_player.stop()

    def is_playing(self) -> bool:
        return self._playing or self._native_player.is_playing()