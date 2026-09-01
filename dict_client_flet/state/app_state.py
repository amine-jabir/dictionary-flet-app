"""
Reactive application state manager for the Flet client.
Connects LookupService, AudioService, and Storage repositories to UI components
with background asynchronous execution, cancellation safety, and real-time audio diagnostics.
"""

import threading
from typing import Any, Callable, Dict, List, Optional, Union

from dict_core.exceptions import (
    AudioError,
    DictionaryError,
    NetworkError,
    TimeoutError,
    ValidationError,
    WordNotFoundError,
)
from dict_core.interfaces.audio import PlatformAudioPlayer
from dict_core.models.word import AudioSource, Phonetic, WordEntry
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.state")


class AppState:
    """
    Central reactive state container for the dictionary application.
    Executes I/O operations on background daemon threads to guarantee that
    the UI thread is never blocked.
    """

    def __init__(
        self,
        lookup_service: LookupService,
        audio_service: AudioService,
        vocab_repo: VocabularyRepository,
        history_repo: HistoryRepository,
        is_dark_mode: bool = False,
        debug_diagnostics: bool = True,
    ) -> None:
        self.lookup_service = lookup_service
        self.audio_service = audio_service
        self.vocab_repo = vocab_repo
        self.history_repo = history_repo
        self.debug_diagnostics = debug_diagnostics

        # State Variables
        self.current_query: str = ""
        self.current_entry: Optional[WordEntry] = None
        self.is_loading: bool = False
        self.error_message: Optional[str] = None
        self.is_dark_mode: bool = is_dark_mode
        self.active_tab_index: int = 0  # 0: Search, 1: Favorites, 2: History
        self.is_favorite: bool = False
        self.is_audio_playing: bool = False
        self.audio_status_message: Optional[str] = None
        self.audio_diagnostic_text: str = ""
        self.audio_diagnostic_data: Optional[Dict[str, Any]] = None

        # Asynchronous concurrency & cancellation controls
        self._current_request_id: int = 0
        self._lock = threading.Lock()
        self._ui_runner: Optional[Callable[..., Any]] = None

        # Cached lists for tab rendering
        self.favorites_list: List[Dict[str, Any]] = []
        self.history_list: List[Dict[str, Any]] = []

        self._listeners: List[Callable[[], None]] = []

    def set_ui_runner(self, runner: Optional[Callable[..., Any]]) -> None:
        """Sets the thread runner (e.g. page.run_thread) to safely bridge background tasks to the UI loop."""
        self._ui_runner = runner

    def _diag(self, message: str) -> None:
        """Internal diagnostic logger for tracing state and thread transitions."""
        if self.debug_diagnostics:
            logger.info("[DIAG] %s", message)

    def subscribe(self, callback: Callable[[], None]) -> None:
        """Registers a listener callback invoked when state changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[], None]) -> None:
        """Removes a registered listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self) -> None:
        """Invokes all registered state listeners."""
        self._diag(
            f"UI NOTIFY -> Tab={self.active_tab_index}, Loading={self.is_loading}, "
            f"Query='{self.current_query}', Entry={'Found' if self.current_entry else 'None'}, "
            f"Error={'Yes' if self.error_message else 'None'}"
        )
        for listener in list(self._listeners):
            try:
                listener()
            except Exception as exc:
                logger.error("Error executing state listener: %s", exc, exc_info=True)

    def set_dark_mode(self, enabled: bool) -> None:
        """Toggles between Dark Mode and Light Mode."""
        if self.is_dark_mode != enabled:
            self._diag(f"EVENT: toggle_dark_mode -> {enabled}")
            self.is_dark_mode = enabled
            self.notify()

    def set_tab(self, index: int) -> None:
        """Switches the active navigation tab."""
        target_tab = max(0, min(index, 2))
        self._diag(f"EVENT: set_tab -> from {self.active_tab_index} to {target_tab}")
        self.active_tab_index = target_tab
        
        if self.active_tab_index == 1:
            self.load_favorites()
        elif self.active_tab_index == 2:
            self.load_history()
            
        self.notify()

    def cancel_search(self) -> None:
        """Cancels any in-flight search and resets loading state."""
        with self._lock:
            self._current_request_id += 1
            req_id = self._current_request_id
            self._diag(f"EVENT: cancel_search -> incremented req_id to {req_id}")
            self.is_loading = False
            self.error_message = None
        self.notify()

    def clear_search(self) -> None:
        """Clears the search input and results."""
        self.cancel_search()
        self.current_query = ""
        self.current_entry = None
        self.is_favorite = False
        self.audio_status_message = None
        self.audio_diagnostic_text = ""
        self.notify()

    def search_word(self, word: str, force_refresh: bool = False, run_sync: bool = False) -> None:
        """
        Executes a dictionary search asynchronously in a background thread.
        Never blocks the caller / UI thread.
        """
        clean_word = str(word or "").strip()
        if not clean_word:
            return

        with self._lock:
            self._current_request_id += 1
            req_id = self._current_request_id
            self.current_query = clean_word
            self.is_loading = True
            self.error_message = None
            self.audio_status_message = None
            self.audio_diagnostic_text = ""

        self._diag(f"EVENT: search_word('{clean_word}') -> START req_id={req_id}")
        self.notify()

        def _search_worker(target_req_id: int, query_word: str, refresh: bool) -> None:
            self._diag(f"BACKGROUND TASK START: lookup('{query_word}', req_id={target_req_id})")
            
            entry_result: Optional[WordEntry] = None
            err_msg: Optional[str] = None

            try:
                entry_result = self.lookup_service.lookup(query_word, force_refresh=refresh)
                self._diag(f"BACKGROUND TASK SUCCESS: lookup('{query_word}', req_id={target_req_id})")
            except WordNotFoundError:
                err_msg = f"No definitions found for '{query_word}'. Check your spelling and try again."
                self._diag(f"BACKGROUND TASK NOT FOUND: '{query_word}'")
            except ValidationError as exc:
                err_msg = f"Invalid search term: {exc.message}"
                self._diag(f"BACKGROUND TASK VALIDATION ERROR: {exc}")
            except TimeoutError:
                err_msg = "The dictionary request timed out. Please check your internet connection and try again."
                self._diag(f"BACKGROUND TASK TIMEOUT: '{query_word}'")
            except NetworkError:
                err_msg = "Network connection error. Please verify your internet connection."
                self._diag(f"BACKGROUND TASK NETWORK ERROR: '{query_word}'")
            except Exception as exc:
                err_msg = f"An unexpected error occurred: {exc}"
                logger.error("Unexpected error during lookup of '%s': %s", query_word, exc, exc_info=True)

            # Apply results under lock checking if request is still current
            with self._lock:
                if target_req_id != self._current_request_id:
                    self._diag(
                        f"BACKGROUND TASK DISCARDED: req_id {target_req_id} is stale (current={self._current_request_id})"
                    )
                    return

                self.is_loading = False
                if entry_result:
                    self.current_entry = entry_result
                    try:
                        self.is_favorite = self.vocab_repo.is_favorite(entry_result.word)
                    except Exception:
                        pass
                    self.error_message = None
                else:
                    self.current_entry = None
                    self.is_favorite = False
                    self.error_message = err_msg

                # Refresh search history cache
                self.load_history()

            self._diag(f"BACKGROUND TASK COMPLETE: req_id={target_req_id}, applying state update")
            self.notify()

        if run_sync:
            _search_worker(req_id, clean_word, force_refresh)
        elif self._ui_runner:
            try:
                self._ui_runner(_search_worker, req_id, clean_word, force_refresh)
            except Exception:
                threading.Thread(
                    target=_search_worker,
                    args=(req_id, clean_word, force_refresh),
                    daemon=True,
                    name=f"DictSearchWorker-{req_id}",
                ).start()
        else:
            threading.Thread(
                target=_search_worker,
                args=(req_id, clean_word, force_refresh),
                daemon=True,
                name=f"DictSearchWorker-{req_id}",
            ).start()

    def run_audio_diagnostics(self, custom_input: Optional[str] = None, run_sync: bool = False) -> None:
        """
        Runs comprehensive audio diagnostics and stores the detailed formatted report.
        """
        target = custom_input.strip() if custom_input and custom_input.strip() else self.current_entry
        if not target:
            self.audio_status_message = "No word or audio URL selected for diagnosis."
            self.notify()
            return

        self._diag(f"EVENT: run_audio_diagnostics -> {target}")
        self.audio_status_message = "Running audio diagnostics..."
        self.notify()

        def _diag_worker() -> None:
            try:
                diag_result = self.audio_service.diagnose_audio(target)
                self.audio_diagnostic_data = diag_result
                
                # Format a comprehensive diagnostic report text
                lines = [
                    "=" * 50,
                    "       AUDIO SUBSYSTEM DIAGNOSTIC REPORT",
                    "=" * 50,
                    f"Target: {target if isinstance(target, str) else target.word}",
                    f"Resolved URL: {diag_result.get('resolved_url')}",
                    f"Cache Status: {'CACHED ON DISK' if diag_result.get('is_cached') else 'NOT CACHED'}",
                    f"Cache File: {diag_result.get('cache_file_path') or 'None'}",
                    f"Cache File Size: {diag_result.get('cache_file_size', 0)} bytes",
                    f"HTTP Status: {diag_result.get('http_status') or 'N/A'}",
                    f"Content-Type: {diag_result.get('content_type') or 'N/A'}",
                    f"Player Engine: {diag_result.get('player_engine')}",
                    f"Overall Diagnostic Status: {diag_result.get('status')}",
                ]
                if diag_result.get("error"):
                    lines.append(f"Error Details: {diag_result.get('error')}")

                lines.append("\nDiagnostic Execution Log:")
                lines.extend(diag_result.get("logs", []))
                lines.append("=" * 50)

                self.audio_diagnostic_text = "\n".join(lines)
                if diag_result.get("status") == "READY_FOR_PLAYBACK":
                    self.audio_status_message = "✅ Audio verified ready. Click play to listen."
                else:
                    self.audio_status_message = f"⚠️ Diagnostic Notice: {diag_result.get('status')}"

            except Exception as exc:
                self.audio_diagnostic_text = f"Audio Diagnostics Error: {exc}"
                self.audio_status_message = f"Diagnostic failed: {exc}"
                logger.error("Audio diagnostics worker failed: %s", exc, exc_info=True)

            self.notify()

        if run_sync:
            _diag_worker()
        else:
            threading.Thread(target=_diag_worker, daemon=True, name="DictAudioDiagWorker").start()

    def speak_tts(self, text: Optional[str] = None) -> None:
        """Explicitly triggers Text-To-Speech (TTS) pronunciation."""
        target_text = text or (self.current_entry.word if self.current_entry else "")
        if not target_text:
            return

        self._diag(f"EVENT: speak_tts('{target_text}')")
        self.is_audio_playing = True
        self.audio_status_message = f"Speaking '{target_text}' (Voice)..."
        self.notify()

        def on_complete() -> None:
            self.is_audio_playing = False
            self.audio_status_message = "✅ Pronunciation complete."
            self.notify()

        def on_error(exc: Exception) -> None:
            self.is_audio_playing = False
            self.audio_status_message = f"Voice speech notice: {exc}"
            self.notify()

        if hasattr(self.audio_service.player, "speak_text"):
            self.audio_service.player.speak_text(target_text, on_complete=on_complete, on_error=on_error)
        else:
            on_complete()

    def play_audio(self, run_sync: bool = False) -> None:
        """Plays pronunciation audio asynchronously on a background worker with fallback to TTS."""
        if not self.current_entry:
            self.audio_status_message = "No word selected."
            self.notify()
            return

        self._diag(f"EVENT: play_audio -> '{self.current_entry.word}'")
        self.is_audio_playing = True
        self.audio_status_message = "Playing audio..."
        self.notify()

        def on_complete() -> None:
            self.is_audio_playing = False
            backend = getattr(self.audio_service.player, "last_backend_used", "Platform Player")
            self.audio_status_message = f"✅ Played audio via {backend}"
            self._diag("EVENT: play_audio -> COMPLETE")
            self.notify()

        def on_error(exc: Exception) -> None:
            self._diag(f"EVENT: play_audio -> ERROR: {exc}. Falling back to TTS voice...")
            # Fallback to Text-To-Speech pronunciation if audio stream fails
            if hasattr(self.audio_service.player, "speak_text"):
                self.audio_status_message = "⚠️ Stream unavailable, using voice pronunciation..."
                self.notify()
                self.audio_service.player.speak_text(
                    self.current_entry.word,
                    on_complete=lambda: self._on_tts_fallback_complete(str(exc)),
                    on_error=lambda tts_err: self._on_tts_fallback_error(str(exc), str(tts_err)),
                )
            else:
                self.is_audio_playing = False
                self.audio_status_message = f"Playback notice: {exc}"
                self.notify()

        def _audio_worker(target_entry: WordEntry) -> None:
            try:
                self.audio_service.play(
                    source=target_entry,
                    on_complete=on_complete,
                    on_error=on_error,
                )
            except Exception as exc:
                on_error(exc)

        if run_sync:
            _audio_worker(self.current_entry)
        elif self._ui_runner:
            try:
                self._ui_runner(_audio_worker, self.current_entry)
            except Exception:
                threading.Thread(
                    target=_audio_worker,
                    args=(self.current_entry,),
                    daemon=True,
                    name="DictAudioWorker",
                ).start()
        else:
            threading.Thread(
                target=_audio_worker,
                args=(self.current_entry,),
                daemon=True,
                name="DictAudioWorker",
            ).start()

    def _on_tts_fallback_complete(self, original_error: str) -> None:
        self.is_audio_playing = False
        self.audio_status_message = "✅ Pronounced via System Voice (TTS)"
        self.audio_diagnostic_text = f"Audio playback fell back to System Voice.\nOriginal Stream Error: {original_error}"
        self.notify()

    def _on_tts_fallback_error(self, stream_error: str, tts_error: str) -> None:
        self.is_audio_playing = False
        self.audio_status_message = f"Audio Notice: {stream_error}"
        self.audio_diagnostic_text = (
            f"Audio Playback Failed:\n"
            f"1. Stream Download/Play: {stream_error}\n"
            f"2. Voice Synthesis: {tts_error}\n"
            f"Click 'Diagnose Audio' for detailed logs."
        )
        self.notify()

    def toggle_favorite(self) -> None:
        """Stars or unstars the currently active word."""
        if not self.current_entry:
            return

        word = self.current_entry.word
        self._diag(f"EVENT: toggle_favorite('{word}')")
        if self.vocab_repo.is_favorite(word):
            self.vocab_repo.remove_favorite(word)
            self.is_favorite = False
        else:
            self.vocab_repo.add_favorite(
                word=word,
                entry=self.current_entry,
            )
            self.is_favorite = True

        self.load_favorites()
        self.notify()

    def load_favorites(self) -> None:
        """Refreshes the favorites list from database."""
        try:
            self.favorites_list = self.vocab_repo.list_favorites(limit=200)
        except Exception as exc:
            logger.debug("Favorites list refresh suppressed: %s", exc)

    def load_history(self) -> None:
        """Refreshes the search history list from database."""
        try:
            self.history_list = self.history_repo.get_recent(limit=100)
        except Exception as exc:
            logger.debug("History list refresh suppressed: %s", exc)

    def clear_history(self) -> None:
        """Clears all search history records."""
        self._diag("EVENT: clear_history")
        try:
            self.history_repo.clear()
        except Exception:
            pass
        self.load_history()
        self.notify()

    def remove_favorite_item(self, word: str) -> None:
        """Removes a specific word from favorites."""
        self._diag(f"EVENT: remove_favorite_item('{word}')")
        try:
            self.vocab_repo.remove_favorite(word)
        except Exception:
            pass
        if self.current_entry and self.current_entry.word.lower() == word.lower():
            self.is_favorite = False
        self.load_favorites()
        self.notify()
