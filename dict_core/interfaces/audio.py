"""
Audio player interface and platform-native playback engines for dict_core.
Provides cross-platform audio pronunciation playback across Windows, macOS, Linux, and Android.
Supports recorded audio files (MP3/OGG/WAV) and text-to-speech (TTS) fallback.
"""

from abc import ABC, abstractmethod
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
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
        Plays an audio file from a local path or URL.
        
        Args:
            audio_path: Local filesystem path or URL to the audio file.
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
    Cross-platform native audio player supporting Windows (WMP COM / MCI winmm.dll / winsound),
    macOS (afplay), Linux (ffplay / mpv / mpg123 / paplay / aplay), and Android detection.
    Supports fallback text-to-speech pronunciation for words without audio recordings.
    Executes playback asynchronously in a background thread to prevent UI freezing.
    """

    def __init__(self) -> None:
        self._playing = False
        self._stop_requested = False
        self._active_thread: Optional[threading.Thread] = None
        self.last_backend_used: str = "None"
        logger.info("[AUDIO] PLAYER CREATED: %s", self.player_name)

    @property
    def player_name(self) -> str:
        system = platform.system().lower()
        is_android = hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
        if is_android:
            return "Android Platform (audioplayers / Flet Audio)"
        if "windows" in system:
            return "Windows Native Player (WMP COM / MCI winmm.dll / winsound)"
        elif "darwin" in system:
            return "macOS Native Player (afplay)"
        return "Linux Native Player"

    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Returns diagnostic details on available system audio backends."""
        system = platform.system().lower()
        is_android = hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ

        diag = {
            "os": "Android" if is_android else platform.system(),
            "os_release": platform.release(),
            "available_backends": [],
        }

        if is_android:
            diag["available_backends"].append("Android Flutter Audio Engine (audioplayers / Flet Audio)")
            diag["available_backends"].append("Online TTS Audio Stream (HTTPS)")
            return diag

        if "windows" in system:
            if shutil.which("powershell"):
                diag["available_backends"].append("PowerShell WMP COM (WMPlayer.OCX)")
                diag["available_backends"].append("PowerShell Speech Synthesis (TTS)")
            try:
                import ctypes
                if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "winmm"):
                    diag["available_backends"].append("Windows MCI (winmm.dll)")
            except Exception:
                pass
            diag["available_backends"].append("Python winsound (WAV)")
        elif "darwin" in system:
            if shutil.which("afplay"):
                diag["available_backends"].append("macOS afplay")
            if shutil.which("say"):
                diag["available_backends"].append("macOS say (TTS)")
        else:
            for cmd in ["ffplay", "mpv", "mpg123", "cvlc", "paplay", "aplay"]:
                if shutil.which(cmd):
                    diag["available_backends"].append(f"Linux {cmd}")
            for tts in ["spd-say", "espeak", "festival"]:
                if shutil.which(tts):
                    diag["available_backends"].append(f"Linux {tts} (TTS)")

        return diag

    def _play_windows(self, audio_path: str) -> None:
        """
        Plays audio on Windows using reliable native backends:
        1. Windows Media Player COM via PowerShell (most reliable for MP3/WAV, works without WPF Dispatcher)
        2. Windows Multimedia API (winmm.dll) using 8.3 short paths
        3. Python winsound for WAV files
        """
        abs_path = str(Path(audio_path).resolve())

        # 1. Try Windows Media Player COM via PowerShell
        # Note: WMPlayer.OCX is available on all standard Windows desktop editions and
        # plays MP3/WAV/AAC asynchronously without needing a WPF Dispatcher frame.
        if shutil.which("powershell"):
            ps_wmp = (
                f"$wmp = New-Object -ComObject WMPlayer.OCX; "
                f"$wmp.settings.volume = 100; "
                f"$wmp.URL = '{abs_path}'; "
                f"$wmp.controls.play(); "
                f"$t = 0; "
                f"while ($wmp.playState -ne 3 -and $wmp.playState -ne 1 -and $wmp.playState -ne 8 -and $t -lt 40) {{ "
                f"  Start-Sleep -Milliseconds 50; $t++ "
                f"}}; "
                f"while ($wmp.playState -eq 3 -or $wmp.playState -eq 9 -or $wmp.playState -eq 6) {{ "
                f"  Start-Sleep -Milliseconds 50 "
                f"}}; "
                f"$wmp.close()"
            )
            try:
                logger.info("[AUDIO] Playing via PowerShell WMP COM...")
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_wmp],
                    capture_output=True,
                    timeout=10,
                )
                if res.returncode == 0:
                    self.last_backend_used = "PowerShell WMP COM (WMPlayer.OCX)"
                    return
                else:
                    logger.debug("PowerShell WMP COM returned code %d, stderr: %s", res.returncode, res.stderr)
            except Exception as exc:
                logger.debug("PowerShell WMP COM playback failed: %s", exc)

        # 2. Try Windows Multimedia API (winmm.dll) with ShortPathName
        try:
            import ctypes
            short_path = abs_path
            try:
                buf = ctypes.create_unicode_buffer(512)
                if ctypes.windll.kernel32.GetShortPathNameW(abs_path, buf, 512):
                    short_path = buf.value
            except Exception:
                pass

            winmm = ctypes.windll.winmm
            alias = f"dict_audio_{threading.get_ident()}_{int(time.time()*1000) % 10000}"
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)

            ret = winmm.mciSendStringW(f'open "{short_path}" alias {alias}', None, 0, 0)
            if ret != 0:
                ret = winmm.mciSendStringW(f'open "{short_path}" type mpegvideo alias {alias}', None, 0, 0)

            if ret == 0:
                logger.info("[AUDIO] Playing via Windows MCI (winmm.dll)...")
                winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
                winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                self.last_backend_used = "Windows MCI (winmm.dll)"
                return
            else:
                logger.debug("winmm.dll MCI open returned error code %d", ret)
        except Exception as exc:
            logger.debug("winmm.dll MCI playback failed: %s", exc)

        # 3. For WAV files, try winsound
        if abs_path.lower().endswith(".wav"):
            try:
                import winsound
                logger.info("[AUDIO] Playing via Python winsound...")
                winsound.PlaySound(abs_path, winsound.SND_FILENAME)
                self.last_backend_used = "Python winsound"
                return
            except Exception as exc:
                logger.debug("winsound playback skipped: %s", exc)

        raise RuntimeError("All Windows native audio backends (WMP COM, MCI winmm.dll, winsound) failed.")

    def _play_macos(self, audio_path: str) -> None:
        """Plays audio on macOS using afplay."""
        abs_path = str(Path(audio_path).resolve())
        logger.info("[AUDIO] Playing via macOS afplay: %s", abs_path)
        subprocess.run(["afplay", abs_path], capture_output=True, timeout=6, check=True)
        self.last_backend_used = "macOS afplay"

    def _play_linux(self, audio_path: str) -> None:
        """Plays audio on Linux using available CLI audio tools."""
        is_android = hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
        if is_android:
            raise RuntimeError("Direct Linux CLI audio utilities unavailable on Android. Use FletAudioPlayer (flet_audio / ft.Audio).")

        abs_path = str(Path(audio_path).resolve())
        is_wav = abs_path.lower().endswith(".wav")

        # Prioritize tools capable of playing compressed MP3/OGG files
        candidates = ["ffplay", "mpv", "mpg123", "cvlc"]
        if is_wav:
            candidates.extend(["paplay", "aplay"])

        last_err = None
        for player_cmd in candidates:
            if shutil.which(player_cmd):
                try:
                    logger.info("[AUDIO] Attempting Linux playback via '%s'...", player_cmd)
                    if player_cmd == "ffplay":
                        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", abs_path], capture_output=True, timeout=6, check=True)
                    elif player_cmd == "mpv":
                        subprocess.run(["mpv", "--no-video", "--really-quiet", abs_path], capture_output=True, timeout=6, check=True)
                    elif player_cmd == "cvlc":
                        subprocess.run(["cvlc", "--play-and-exit", "--quiet", abs_path], capture_output=True, timeout=6, check=True)
                    else:
                        subprocess.run([player_cmd, abs_path], capture_output=True, timeout=6, check=True)
                    self.last_backend_used = f"Linux {player_cmd}"
                    return
                except Exception as exc:
                    logger.debug("Linux player '%s' failed: %s", player_cmd, exc)
                    last_err = exc

        raise RuntimeError(f"No functional Linux audio player succeeded (tried: {candidates}). Last error: {last_err}")

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
            is_android = hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
            try:
                if is_android:
                    raise RuntimeError("Native Linux speech commands unavailable on Android. Use TTS audio stream.")
                elif "windows" in system:
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
                    tts_found = False
                    for tts_cmd in ["spd-say", "espeak", "festival"]:
                        if shutil.which(tts_cmd):
                            subprocess.run([tts_cmd, clean_text], capture_output=True, timeout=8, check=True)
                            self.last_backend_used = f"Linux {tts_cmd} (TTS)"
                            tts_found = True
                            break
                    if not tts_found:
                        raise RuntimeError("No Linux TTS engine found (spd-say, espeak, festival).")

                self._playing = False
                if on_complete and not self._stop_requested:
                    on_complete()
            except Exception as exc:
                self._playing = False
                logger.error("[AUDIO] TTS speech error: %s", exc)
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
            logger.info("[AUDIO] PLAYBACK STARTED on %s", self.player_name)
            if "windows" in system:
                self._play_windows(audio_path)
            elif "darwin" in system:
                self._play_macos(audio_path)
            else:
                self._play_linux(audio_path)

            self._playing = False
            logger.info("[AUDIO] PLAYBACK COMPLETE: %s", self.last_backend_used)
            if on_complete and not self._stop_requested:
                on_complete()

        except Exception as exc:
            self._playing = False
            logger.error("[AUDIO] PLAYBACK ERROR: %s", exc)
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
