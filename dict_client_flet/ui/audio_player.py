"""
Cross-platform Audio Player for the Flet client.
Combines Flet's ft.Audio control with direct native OS multimedia playback (Windows, macOS, Linux).
"""

from pathlib import Path
from typing import Any, Callable, Optional
import flet as ft

from dict_core.interfaces.audio import BaseAudioPlayer, PlatformAudioPlayer
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.audio_player")


class FletAudioPlayer(BaseAudioPlayer):
    """
    Audio player engine integrating Flet's ft.Audio control with native OS fallbacks.
    """

    def __init__(self, page: Optional[ft.Page] = None) -> None:
        self.page = page
        self._native_player = PlatformAudioPlayer()
        self._audio_control: Optional[ft.Audio] = None
        self._playing = False

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
                )
                if hasattr(self.page, "overlay"):
                    self.page.overlay.append(self._audio_control)
                    self.page.update()
        except Exception as exc:
            logger.debug("Could not mount ft.Audio in overlay: %s", exc)

    @property
    def player_name(self) -> str:
        return f"FletAudioPlayer -> {self._native_player.player_name}"

    @property
    def last_backend_used(self) -> str:
        return getattr(self._native_player, "last_backend_used", self._native_player.player_name)

    def speak_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Speaks text aloud using native OS Speech Synthesis."""
        self._native_player.speak_text(text, on_complete=on_complete, on_error=on_error)

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Plays audio using direct native OS multimedia backend (MCI / WPF / afplay / Linux players).
        """
        self._playing = True

        def _wrap_complete():
            self._playing = False
            if on_complete:
                on_complete()

        def _wrap_error(exc: Exception):
            self._playing = False
            if on_error:
                on_error(exc)

        self._native_player.play(
            audio_path=audio_path,
            on_complete=_wrap_complete,
            on_error=_wrap_error,
        )

    def stop(self) -> None:
        self._playing = False
        self._native_player.stop()

    def is_playing(self) -> bool:
        return self._playing or self._native_player.is_playing()
