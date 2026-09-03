"""
Cross-platform Audio Player for the Flet client.
Provides in-app audio playback via Flet's Audio control (flet_audio / flet.Audio)
as the primary engine across desktop, mobile, and web, with robust native OS multimedia
fallbacks (Windows WMP COM / MCI winmm.dll / macOS afplay / Linux ffplay/mpv)
and Text-To-Speech (TTS) voice pronunciation.
"""

from pathlib import Path
import platform
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional
import urllib.parse
try:
    import flet as ft
except ImportError:
    ft = None  # type: ignore

from dict_client_flet.ui.flet_compat import (
    create_audio_control,
    get_audio_class,
    is_audio_control,
)
from dict_core.interfaces.audio import BaseAudioPlayer, PlatformAudioPlayer
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.audio_player")


class FletAudioPlayer(BaseAudioPlayer):
    """
    Cross-platform audio player engine combining in-app Flet Audio playback
    with native OS multimedia fallbacks and comprehensive diagnostic logging.
    """

    def __init__(self, page: Optional[Any] = None) -> None:
        self.page = page
        self._native_player = PlatformAudioPlayer()
        self._audio_control: Any = None
        self._control_attached = False
        self._playing = False
        self._last_backend = "Flet Audio"
        self._current_url: Optional[str] = None
        self._completion_callback: Optional[Callable[[], None]] = None
        self._error_callback: Optional[Callable[[Exception], None]] = None
        self._watchdog_timer: Optional[threading.Timer] = None

        logger.info("[AUDIO] PLAYER CREATED: %s", self.player_name)

        if self.page is not None:
            self._init_flet_audio()

    def set_page(self, page: Any) -> None:
        """Attaches the active Flet Page and mounts the Audio control."""
        self.page = page
        self._init_flet_audio()

    def set_current_url(self, url: Optional[str]) -> None:
        """Records the online stream URL for the current playback."""
        self._current_url = url
        logger.info("[AUDIO] SELECTED URL = %s", url)

    @property
    def player_name(self) -> str:
        AudioClass = get_audio_class()
        if AudioClass is not None:
            return f"FletAudioPlayer (Flet Audio / {AudioClass.__name__})"
        return f"FletAudioPlayer ({self._native_player.player_name})"

    @property
    def last_backend_used(self) -> str:
        return self._last_backend

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostics on the audio pipeline and available drivers."""
        native_diag = self._native_player.get_system_diagnostics()
        AudioClass = get_audio_class()
        diag = {
            "player_engine": self.player_name,
            "has_page_attached": self.page is not None,
            "flet_audio_class_available": AudioClass is not None,
            "flet_audio_mounted": self._control_attached and self._audio_control is not None,
            "last_backend_used": self.last_backend_used,
            "available_backends": [],
        }
        if AudioClass:
            diag["available_backends"].append("Flet Audio Control (In-App)")
        for b in native_diag.get("available_backends", []):
            if b not in diag["available_backends"]:
                diag["available_backends"].append(b)
        return diag

    def _on_flet_state_change(self, e: Any) -> None:
        """Handles Flet Audio state changes (e.g. playing, completed, stopped, error)."""
        state_str = str(getattr(e, "data", "") or getattr(e, "state", "")).lower()
        logger.info("[AUDIO] PLAYBACK STATE = %s", state_str)

        if "completed" in state_str or "stopped" in state_str or "disposed" in state_str:
            self._playing = False
            if self._watchdog_timer:
                self._watchdog_timer.cancel()
                self._watchdog_timer = None
            cb = self._completion_callback
            self._completion_callback = None
            if cb:
                logger.info("[AUDIO] PLAYBACK COMPLETE: success")
                cb()
        elif "error" in state_str or "failed" in state_str:
            self._playing = False
            if self._watchdog_timer:
                self._watchdog_timer.cancel()
                self._watchdog_timer = None
            err_cb = self._error_callback
            self._error_callback = None
            logger.error("[AUDIO] PLAYBACK ERROR = %s", state_str)
            if err_cb:
                err_cb(RuntimeError(f"Flet Audio playback failed: {state_str}"))

    def _init_flet_audio(self) -> bool:
        """Initializes and mounts the persistent ft.Audio control into the Page overlay or services."""
        if not self.page:
            return False

        AudioClass = get_audio_class()
        if not AudioClass:
            logger.debug("Flet Audio class not available in environment.")
            return False

        try:
            if not self._audio_control:
                self._audio_control = create_audio_control(
                    AudioClass=AudioClass,
                    src="",
                    autoplay=False,
                    volume=1.0,
                    on_state_callback=self._on_flet_state_change,
                )

            # Mount into page.services (Flet 1.0) or page.overlay (Flet 0.x)
            mounted = False
            if hasattr(self.page, "services"):
                if self._audio_control not in self.page.services:
                    self.page.services.append(self._audio_control)
                mounted = True
            elif hasattr(self.page, "overlay"):
                if self._audio_control not in self.page.overlay:
                    self.page.overlay.append(self._audio_control)
                mounted = True

            if mounted:
                try:
                    self.page.update()
                except Exception:
                    pass
                self._control_attached = True
                logger.info("[AUDIO] CONTROL ATTACHED")
                return True
        except Exception as exc:
            logger.warning("Could not initialize Flet Audio in overlay/services: %s", exc)
            self._control_attached = False

        return False

    def speak_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Speaks text aloud using native OS speech on desktop or direct TTS stream."""
        clean_text = str(text or "").strip()
        if not clean_text:
            if on_complete:
                on_complete()
            return

        # On desktop with native TTS (Windows PowerShell, macOS 'say'), use native player
        system = platform.system().lower()
        if "windows" in system or "darwin" in system:
            try:
                self._native_player.speak_text(clean_text, on_complete=on_complete, on_error=on_error)
                self._last_backend = getattr(self._native_player, "last_backend_used", "Native OS Speech")
                return
            except Exception as exc:
                logger.debug("Native desktop TTS failed (%s), falling back to online TTS stream...", exc)

        # Fallback to Google TTS audio stream
        encoded = urllib.parse.quote(clean_text)
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
        self.play(tts_url, on_complete=on_complete, on_error=on_error)
        self._last_backend = "Google TTS Stream"

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Plays audio using Flet's Audio control as the primary engine.
        If Flet Audio is unavailable or encounters an error, seamlessly
        falls back to native OS multimedia players (WMP COM, MCI winmm.dll, afplay, ffplay/mpv).
        """
        self.stop()
        self._playing = True
        logger.info("[AUDIO] PLAY REQUESTED")
        logger.info("[AUDIO] SOURCE ASSIGNED = %s", audio_path)

        self._completion_callback = on_complete
        self._error_callback = on_error

        # 1. Primary Engine: In-App Flet Audio Control
        flet_audio_ready = self._control_attached and self._audio_control is not None
        if not flet_audio_ready and self.page is not None:
            flet_audio_ready = self._init_flet_audio()

        if flet_audio_ready and self.page is not None and self._audio_control is not None:
            try:
                # Use remote URL if audio_path is a URL or if local file doesn't exist
                src_to_use = audio_path
                if not (audio_path.startswith("http://") or audio_path.startswith("https://")):
                    p = Path(audio_path)
                    if p.exists():
                        src_to_use = str(p.resolve())

                self._audio_control.src = src_to_use
                self._audio_control.autoplay = True
                try:
                    self.page.update()
                except Exception:
                    pass

                if hasattr(self._audio_control, "play"):
                    self._audio_control.play()

                self._last_backend = "Flet Audio"
                logger.info("[AUDIO] PLAYBACK STARTED on Flet Audio")

                # Set a safety watchdog timer (3.5s) to guarantee completion if platform event drops
                def _watchdog():
                    if self._playing:
                        self._playing = False
                        cb = self._completion_callback
                        self._completion_callback = None
                        if cb:
                            logger.info("[AUDIO] PLAYBACK COMPLETE: (watchdog)")
                            cb()

                self._watchdog_timer = threading.Timer(3.5, _watchdog)
                self._watchdog_timer.daemon = True
                self._watchdog_timer.start()
                return

            except Exception as exc:
                logger.warning("[AUDIO] Flet Audio playback error: %s. Falling back to native OS...", exc)
                logger.info("[AUDIO] PLAYBACK ERROR = %s", exc)

        # 2. Secondary Engine: Native OS Multimedia Drivers (Windows WMP COM / MCI winmm.dll, macOS afplay, Linux ffplay/mpv)
        def _wrap_complete():
            self._playing = False
            self._completion_callback = None
            if on_complete:
                on_complete()

        def _wrap_error(exc: Exception):
            self._playing = False
            self._error_callback = None
            logger.error("[AUDIO] PLAYBACK ERROR = %s", exc)
            if on_error:
                on_error(exc)
            else:
                raise

        try:
            self._native_player.play(
                audio_path=audio_path,
                on_complete=_wrap_complete,
                on_error=_wrap_error,
            )
            self._last_backend = getattr(self._native_player, "last_backend_used", self._native_player.player_name)
        except Exception as exc:
            self._playing = False
            logger.error("[AUDIO] Native player dispatch error: %s", exc)
            if on_error:
                on_error(exc)
            else:
                raise

    def stop(self) -> None:
        """Stops any active audio playback."""
        self._playing = False
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._watchdog_timer = None
        self._completion_callback = None
        self._error_callback = None

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
