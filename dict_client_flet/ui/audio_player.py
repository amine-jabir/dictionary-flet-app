"""
Cross-platform Audio Player implementation for Flet (Mobile, Desktop, Web).
Implements dict_core.interfaces.audio.BaseAudioPlayer.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional
import flet as ft
import flet_audio as fta  # Import the new standalone Flet Audio module

from dict_core.interfaces.audio import BaseAudioPlayer
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.audio_player")


class FletAudioPlayer(BaseAudioPlayer):
    """
    Flet-native audio player using fta.Audio control.
    Supports streaming URLs and local cached files across Android, iOS, Desktop, and Web.
    """

    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self.page = page
        self._is_playing = False
        self._current_url: Optional[str] = None
        self._on_complete_cb: Optional[Callable[[], None]] = None
        self._on_error_cb: Optional[Callable[[Exception], None]] = None

        # Build Flet native Audio control using the new flet_audio package
        self.audio_control = fta.Audio(
            autoplay=False,
            volume=1.0,
            balance=0.0,
            release_mode=fta.ReleaseMode.STOP,
            on_state_changed=self._handle_state_changed,
        )

        # Mount to page overlay
        if self.audio_control not in self.page.overlay:
            self.page.overlay.append(self.audio_control)
            try:
                self.page.update()
            except Exception:
                pass

    @property
    def player_name(self) -> str:
        return "FletAudioPlayer (Native Flutter Engine)"

    def set_current_url(self, url: Optional[str]) -> None:
        """Stores the upstream web URL to stream directly on mobile platforms."""
        if url:
            clean_url = url.strip()
            if clean_url.startswith("//"):
                clean_url = "https:" + clean_url
            self._current_url = clean_url
        else:
            self._current_url = None

    def _handle_state_changed(self, e) -> None:
        """Listens for playback state transitions from the Flutter engine."""
        state_data = str(getattr(e, "data", "")).lower()
        if "completed" in state_data or "stopped" in state_data or "paused" in state_data:
            self._is_playing = False
            if "completed" in state_data and self._on_complete_cb:
                try:
                    self._on_complete_cb()
                except Exception as exc:
                    logger.error("Error in on_complete callback: %s", exc)

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Plays audio using the direct URL if available (optimal for Android)
        or falls back to the cached local file path.
        """
        self._on_complete_cb = on_complete
        self._on_error_cb = on_error

        # Determine target source (prioritize https streaming URL for mobile sandboxing)
        target_src = self._current_url or audio_path

        if not target_src:
            err = ValueError("No audio source or path provided for playback.")
            if on_error:
                on_error(err)
            return

        # Ensure protocol prefix
        if str(target_src).startswith("//"):
            target_src = "https:" + str(target_src)

        try:
            self._is_playing = True
            self.audio_control.src = str(target_src)
            self.audio_control.update()
            self.audio_control.play()
            logger.info("FletAudioPlayer playback triggered for source: %s", target_src)
        except Exception as exc:
            self._is_playing = False
            logger.error("FletAudioPlayer failed to play source '%s': %s", target_src, exc)
            if on_error:
                on_error(exc)

    def stop(self) -> None:
        """Stops active playback."""
        try:
            self.audio_control.pause()
            self._is_playing = False
        except Exception as exc:
            logger.warning("Error stopping audio playback: %s", exc)

    def is_playing(self) -> bool:
        return self._is_playing

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Provides diagnostic metadata for the in-app audio inspection dialog."""
        return {
            "player_name": self.player_name,
            "engine": "Flutter Media Engine (fta.Audio)",
            "available_backends": ["Flutter Audio Plugin", "ExoPlayer (Android)", "AVPlayer (iOS)"],
            "current_source": self._current_url or "None",
            "overlay_mounted": self.audio_control in self.page.overlay,
        }