"""
Interactive Audio Diagnostics & Test Dialog for the Flet UI.
Provides step-by-step diagnostic inspection, live network/driver testing,
and full copyable diagnostic logs for debugging audio issues.
Responsive for both mobile (narrow viewports) and desktop displays.
"""

import threading
from typing import Any, Optional
import urllib.parse
import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.flet_compat import (
    border_all,
    border_radius_all,
    close_dialog_compat,
    create_elevated_button,
    create_icon,
    create_outlined_button,
    create_text_button,
    get_icon,
    open_dialog_compat,
    pad_all,
    pad_symmetric,
    set_clipboard_compat,
)
from dict_client_flet.ui.theme import ColorPalette


def show_audio_diagnostics_dialog(
    page: ft.Page,
    state: AppState,
    palette: ColorPalette,
) -> None:
    """Displays the interactive audio diagnostics dialog with mobile-safe layout."""
    default_test_val = state.current_entry.word if state.current_entry else "hello"

    test_input = ft.TextField(
        value=default_test_val,
        label="Test Word or Audio URL",
        hint_text="Enter a word (e.g. 'hello') or direct MP3 URL...",
        text_size=13,
        autofocus=False,
    )

    log_display = ft.TextField(
        value=state.audio_diagnostic_text or "Click 'Run Diagnostics' below to inspect the audio pipeline...",
        label="Diagnostic Log Output",
        multiline=True,
        read_only=True,
        text_size=11,
        min_lines=6,
        max_lines=10,
        text_style=ft.TextStyle(font_family="monospace"),
    )

    status_label = ft.Text(
        value="Ready to test audio.",
        size=12,
        weight="w500",
        color=palette.text_secondary,
    )

    def safe_page_update() -> None:
        try:
            if hasattr(state, "ui_runner") and state.ui_runner:
                state.ui_runner(page.update)
            else:
                page.update()
        except Exception:
            pass

    def on_run_diag(_):
        try:
            val = test_input.value.strip() or default_test_val
            status_label.value = "⏳ Running audio resolution and network tests..."
            status_label.color = palette.primary
            safe_page_update()

            def _sync_worker():
                try:
                    diag_result = state.audio_service.diagnose_audio(val)
                    lines = [
                        "=" * 50,
                        "       AUDIO SUBSYSTEM DIAGNOSTIC REPORT",
                        "=" * 50,
                        f"Target Input: {val}",
                        f"Resolved URL: {diag_result.get('resolved_url')}",
                        f"Cache Status: {'CACHED ON DISK' if diag_result.get('is_cached') else 'NOT CACHED'}",
                        f"Cache File: {diag_result.get('cache_file_path') or 'None'}",
                        f"Cache File Size: {diag_result.get('cache_file_size', 0)} bytes",
                        f"HTTP Response: {diag_result.get('http_status') or 'N/A'}",
                        f"Content-Type: {diag_result.get('content_type') or 'N/A'}",
                        f"Player Engine: {diag_result.get('player_engine')}",
                        f"Diagnostic Result: {diag_result.get('status')}",
                    ]
                    if diag_result.get("error"):
                        lines.append(f"Reported Error: {diag_result.get('error')}")

                    lines.append("\nStep-by-Step Execution Log:")
                    lines.extend(diag_result.get("logs", []))
                    lines.append("=" * 50)

                    report_str = "\n".join(lines)
                    log_display.value = report_str
                    status_label.value = f"Diagnostic Status: {diag_result.get('status')}"
                    status_label.color = palette.success if diag_result.get("status") == "READY_FOR_PLAYBACK" else palette.error
                except Exception as exc:
                    log_display.value = f"Diagnostic Execution Failed: {exc}"
                    status_label.value = f"Error: {exc}"
                    status_label.color = palette.error
                safe_page_update()

            threading.Thread(target=_sync_worker, daemon=True).start()
        except Exception as exc:
            status_label.value = f"Notice: {exc}"
            safe_page_update()

    def on_test_play(_):
        try:
            val = test_input.value.strip() or default_test_val
            status_label.value = f"🔊 Triggering playback for '{val}'..."
            status_label.color = palette.primary
            safe_page_update()

            def _play_worker():
                try:
                    state.audio_service.play(val)
                    backend = getattr(state.audio_service.player, "last_backend_used", state.audio_service.player.player_name)
                    status_label.value = f"✅ Playback dispatched via: {backend}"
                    status_label.color = palette.success
                except Exception as exc:
                    status_label.value = f"⚠️ Playback error: {exc}"
                    status_label.color = palette.error
                safe_page_update()

            threading.Thread(target=_play_worker, daemon=True).start()
        except Exception as exc:
            status_label.value = f"Playback notice: {exc}"
            safe_page_update()

    def on_test_tts(_):
        try:
            val = test_input.value.strip() or default_test_val
            status_label.value = f"🗣️ Speaking '{val}' via Voice..."
            status_label.color = palette.primary
            safe_page_update()
            state.speak_tts(val)
        except Exception as exc:
            status_label.value = f"Voice notice: {exc}"
            safe_page_update()

    def on_open_external(_):
        try:
            val = test_input.value.strip() or default_test_val
            url = None
            if val.startswith("http://") or val.startswith("https://"):
                url = val
            else:
                url = state.audio_service.resolve_audio_url(val)
                if not url:
                    encoded = urllib.parse.quote(val)
                    url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={encoded}"
            if url:
                if hasattr(page, "launch_url"):
                    page.launch_url(url)
                    status_label.value = "🌐 Opening audio URL in external browser/player..."
                    status_label.color = palette.success
                else:
                    status_label.value = f"URL: {url}"
            else:
                status_label.value = "Could not resolve audio URL."
            safe_page_update()
        except Exception as exc:
            status_label.value = f"Launch notice: {exc}"
            safe_page_update()

    def on_copy(_):
        try:
            set_clipboard_compat(page, log_display.value)
            status_label.value = "📋 Diagnostic report copied to clipboard!"
            status_label.color = palette.success
            safe_page_update()
        except Exception as exc:
            status_label.value = f"Copy notice: {exc}"
            safe_page_update()

    def on_close(_):
        try:
            close_dialog_compat(page, dialog)
        except Exception:
            pass

    page_width = getattr(page, "width", 400) or 400
    dialog_width = min(max(page_width - 32, 280), 540)

    run_btn = create_elevated_button(
        text="Run Diagnostics",
        icon_name="SEARCH",
        on_click=on_run_diag,
        bgcolor=palette.primary,
        color="#FFFFFF",
    )
    play_btn = create_outlined_button(
        text="Play Stream",
        icon_name="VOLUME_UP",
        on_click=on_test_play,
    )
    voice_btn = create_outlined_button(
        text="Test Voice (TTS)",
        icon_name="RECORD_VOICE_OVER",
        on_click=on_test_tts,
    )
    open_btn = create_outlined_button(
        text="Open in Browser",
        icon_name="OPEN_IN_BROWSER",
        on_click=on_open_external,
    )
    copy_btn = create_outlined_button(
        text="Copy Log",
        icon_name="CONTENT_COPY",
        on_click=on_copy,
    )

    action_buttons = [b for b in [run_btn, play_btn, voice_btn, open_btn, copy_btn] if b is not None]

    dialog_content = ft.Container(
        content=ft.Column(
            controls=[
                test_input,
                ft.Row(
                    controls=action_buttons,
                    spacing=6,
                    wrap=True,
                ),
                ft.Container(
                    content=log_display,
                    border=border_all(1, palette.border),
                    border_radius=border_radius_all(8),
                ),
                status_label,
            ],
            spacing=10,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=dialog_width,
        padding=pad_all(6),
    )

    dialog = ft.AlertDialog(
        title=ft.Row(
            controls=[
                create_icon("SETTINGS", color=palette.primary),
                ft.Text("Audio Diagnostics & Test", weight="bold", size=16),
            ],
            spacing=8,
        ),
        content=dialog_content,
        actions=[
            create_text_button(
                text="Close",
                on_click=on_close,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    open_dialog_compat(page, dialog)
