"""
Audio player interface and platform-native playback engines for dict_core.
Provides cross-platform audio pronunciation playback across Windows, macOS, Linux, and headless environments.
Supports recorded audio files (MP3/OGG/WAV) and text-to-speech (TTS) fallback.
"""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.audio.player")


class BaseAudioPlayer(ABC):
    """
    Abstract interface for audio playback engines.
    Implementations may use platform multimedia backends, subprocesses,
    or headless null drivers for testing.
    """

    @property
    @abstractmethod
    def player_name(self) -> str:
        """Name of the audio player engine."""
        pass

    @abstractmethod
    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Plays an audio file from a local path.
        
        Args:
            audio_path: Local filesystem path to the audio file.
            on_complete: Optional callback invoked when playback finishes.
            on_error: Optional callback invoked if playback fails.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops any active audio playback."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Returns True if audio is currently playing."""
        pass


class NullAudioPlayer(BaseAudioPlayer):
    """
    Headless no-op audio player for unit tests and headless environments.
    """

    def __init__(self) -> None:
        self._playing = False

    @property
    def player_name(self) -> str:
        return "NullAudioPlayer (Headless)"

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self._playing = True
        try:
            self._playing = False
            if on_complete:
                on_complete()
        except Exception as exc:
            self._playing = False
            if on_error:
                on_error(exc)
            else:
                raise

    def stop(self) -> None:
        self._playing = False

    def is_playing(self) -> bool:
        return self._playing


class PlatformAudioPlayer(BaseAudioPlayer):
    """
    Cross-platform native audio player supporting Windows (winmm.dll MCI / WPF / PowerShell / winsound),
    macOS (afplay), and Linux (paplay/aplay/ffplay/mpv/mpg123).
    Supports fallback text-to-speech pronunciation for words without audio recordings.
    Executes playback asynchronously in a background thread to prevent UI freezing.
    """

    def __init__(self) -> None:
        self._playing = False
        self._stop_requested = False
        self._active_thread: Optional[threading.Thread] = None
        self.last_backend_used: str = "None"

    @property
    def player_name(self) -> str:
        system = platform.system().lower()
        if "windows" in system:
            return "Windows Native Player (MCI winmm.dll / WPF MediaPlayer / PowerShell)"
        elif "darwin" in system:
            return "macOS Native Player (afplay)"
        return "Linux Native Player"

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostic details on available system audio backends."""
        system = platform.system().lower()
        diag = {
            "os": platform.system(),
            "os_release": platform.release(),
            "available_backends": [],
        }

        if "windows" in system:
            try:
                import ctypes
                if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm"):
                    diag["available_backends"].append("Windows MCI (winmm.dll)")
            except Exception:
                pass
            if shutil.which("powershell"):
                diag["available_backends"].append("PowerShell WPF (presentationCore)")
                diag["available_backends"].append("PowerShell WMP COM (WMPlayer.OCX)")
                diag["available_backends"].append("PowerShell Speech Synthesis (TTS)")
        elif "darwin" in system:
            if shutil.which("afplay"):
                diag["available_backends"].append("macOS afplay")
            if shutil.which("say"):
                diag["available_backends"].append("macOS say (TTS)")
        else:
            for cmd in ["paplay", "aplay", "ffplay", "mpv", "mpg123", "cvlc"]:
                if shutil.which(cmd):
                    diag["available_backends"].append(f"Linux {cmd}")
            for tts in ["spd-say", "espeak", "festival"]:
                if shutil.which(tts):
                    diag["available_backends"].append(f"Linux {tts} (TTS)")

        return diag

    def _play_windows(self, audio_path: str) -> None:
        """
        Plays audio on Windows using multiple redundant native backends:
        1. winmm.dll MCI (instant C-level call, zero subprocess)
        2. PowerShell WPF MediaPlayer
        3. PowerShell WMP COM
        4. winsound (WAV)
        """
        abs_path = str(Path(audio_path).resolve())

        # 1. Try Windows Multimedia API (winmm.dll) -> Highest performance, zero subprocesses
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            alias = f"dict_audio_{threading.get_ident()}_{int(time.time()*1000) % 10000}"
            
            # Close previous if any
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)
            
            # Open with type mpegvideo (supports MP3, WAV, WMA)
            ret = winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, 0)
            if ret != 0:
                # Try generic open
                ret = winmm.mciSendStringW(f'open "{abs_path}" alias {alias}', None, 0, 0)

            if ret == 0:
                logger.info("[AUDIO DRIVER] Playing via Windows MCI (winmm.dll)...")
                winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
                winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                self.last_backend_used = "Windows MCI (winmm.dll)"
                return
            else:
                logger.debug("winmm.dll returned code %d, falling back to WPF...", ret)
        except Exception as exc:
            logger.debug("winmm.dll MCI playback failed: %s", exc)

        # 2. Try PowerShell WPF MediaPlayer (standard in .NET on Windows)
        ps_wpf = (
            f"Add-Type -AssemblyName presentationCore; "
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([System.Uri]'{abs_path}'); "
            f"$p.Play(); "
            f"Start-Sleep -Milliseconds 400; "
            f"$timeout = 0; "
            f"while ($p.NaturalDuration.HasTimeSpan -and ($p.Position -lt $p.NaturalDuration.TimeSpan) -and $timeout -lt 50) {{ "
            f"  Start-Sleep -Milliseconds 100; $timeout++ "
            f"}}; "
            f"Start-Sleep -Milliseconds 200; "
            f"$p.Close()"
        )
        try:
            logger.info("[AUDIO DRIVER] Playing via PowerShell WPF MediaPlayer...")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_wpf],
                capture_output=True,
                timeout=8,
            )
            if res.returncode == 0:
                self.last_backend_used = "PowerShell WPF (System.Windows.Media.MediaPlayer)"
                return
        except Exception as exc:
            logger.debug("PowerShell WPF playback failed: %s", exc)

        # 3. Try Windows Media Player COM via PowerShell
        ps_wmp = (
            f"$wmp = New-Object -ComObject WMPlayer.OCX; "
            f"$wmp.settings.volume = 100; "
            f"$wmp.URL = '{abs_path}'; "
            f"$wmp.controls.play(); "
            f"$timeout = 0; "
            f"while (($wmp.playState -eq 3 -or $wmp.playState -eq 9 -or $wmp.playState -eq 6) -and $timeout -lt 60) {{ "
            f"  Start-Sleep -Milliseconds 100; $timeout++ "
            f"}}; "
            f"Start-Sleep -Milliseconds 300; "
            f"$wmp.close()"
        )
        try:
            logger.info("[AUDIO DRIVER] Playing via PowerShell WMP COM...")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_wmp],
                capture_output=True,
                timeout=8,
            )
            if res.returncode == 0:
                self.last_backend_used = "PowerShell WMP COM (WMPlayer.OCX)"
                return
        except Exception as exc:
            logger.debug("PowerShell WMP COM playback failed: %s", exc)

        # 4. For WAV files, try winsound
        if abs_path.lower().endswith(".wav"):
            try:
                import winsound
                logger.info("[AUDIO DRIVER] Playing via Python winsound...")
                winsound.PlaySound(abs_path, winsound.SND_FILENAME)
                self.last_backend_used = "Python winsound"
                return
            except Exception as exc:
                logger.debug("winsound playback skipped: %s", exc)

        raise RuntimeError("All Windows native audio backends (MCI, WPF, WMP COM, winsound) failed.")

    def _play_macos(self, audio_path: str) -> None:
        """Plays audio on macOS using afplay."""
        abs_path = str(Path(audio_path).resolve())
        subprocess.run(["afplay", abs_path], capture_output=True, timeout=6, check=True)
        self.last_backend_used = "macOS afplay"

    def _play_linux(self, audio_path: str) -> None:
        """Plays audio on Linux using available CLI audio tools."""
        abs_path = str(Path(audio_path).resolve())
        for player_cmd in ["paplay", "aplay", "ffplay", "mpv", "mpg123"]:
            if shutil.which(player_cmd):
                if player_cmd == "ffplay":
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", abs_path], capture_output=True, timeout=6, check=True)
                elif player_cmd == "mpv":
                    subprocess.run(["mpv", "--no-video", abs_path], capture_output=True, timeout=6, check=True)
                else:
                    subprocess.run([player_cmd, abs_path], capture_output=True, timeout=6, check=True)
                self.last_backend_used = f"Linux {player_cmd}"
                return
        raise RuntimeError("No Linux audio playback utility found (mpv, ffplay, paplay, aplay).")

    def speak_text(
        self,
        text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Speaks a word or phrase aloud using platform-native Text-To-Speech (TTS)."""
        clean_text = str(text or "").strip()
        if not clean_text:
            if on_complete:
                on_complete()
            return

        def _tts_worker() -> None:
            self._playing = True
            system = platform.system().lower()
            try:
                if "windows" in system:
                    ps_tts = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.Rate = 0; "
                        f"$synth.Speak('{clean_text}')"
                    )
                    subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_tts],
                        capture_output=True,
                        timeout=8,
                        check=True,
                    )
                    self.last_backend_used = "Windows Speech Synthesis (TTS)"
                elif "darwin" in system:
                    subprocess.run(["say", clean_text], capture_output=True, timeout=8, check=True)
                    self.last_backend_used = "macOS say (TTS)"
                else:
                    for tts_cmd in ["spd-say", "espeak", "festival"]:
                        if shutil.which(tts_cmd):
                            subprocess.run([tts_cmd, clean_text], capture_output=True, timeout=8, check=True)
                            self.last_backend_used = f"Linux {tts_cmd} (TTS)"
                            break

                self._playing = False
                if on_complete and not self._stop_requested:
                    on_complete()
            except Exception as exc:
                self._playing = False
                logger.error("TTS speech error: %s", exc)
                if on_error:
                    on_error(exc)

        self.stop()
        self._stop_requested = False
        self._active_thread = threading.Thread(target=_tts_worker, daemon=True, name="DictTTSWorker")
        self._active_thread.start()

    def _playback_worker(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]],
        on_error: Optional[Callable[[Exception], None]],
    ) -> None:
        self._playing = True
        system = platform.system().lower()
        try:
            if "windows" in system:
                self._play_windows(audio_path)
            elif "darwin" in system:
                self._play_macos(audio_path)
            else:
                self._play_linux(audio_path)

            self._playing = False
            if on_complete and not self._stop_requested:
                on_complete()

        except Exception as exc:
            self._playing = False
            logger.error("Audio playback error: %s", exc)
            if on_error:
                on_error(exc)

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.stop()
        self._stop_requested = False
        self._active_thread = threading.Thread(
            target=self._playback_worker,
            args=(audio_path, on_complete, on_error),
            daemon=True,
            name="DictAudioPlaybackWorker",
        )
        self._active_thread.start()

    def stop(self) -> None:
        self._stop_requested = True
        self._playing = False

    def is_playing(self) -> bool:
        return self._playing
