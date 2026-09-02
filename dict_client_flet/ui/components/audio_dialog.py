"""
Interactive Audio Diagnostics & Test Dialog for the Flet UI.
Provides step-by-step diagnostic inspection, live network/driver testing,
and full copyable diagnostic logs for debugging audio issues.
Responsive for both mobile (narrow viewports) and desktop displays.
"""

import threading
from typing import Any, Optional
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
)
from dict_client_flet.ui.theme import ColorPalette


def show_audio_diagnostics_dialog(
    page: ft.Page,
    state: AppState,
    palette: ColorPalette,
) -> None:
    """Displays the comprehensive interactive audio diagnostics dialog with mobile-responsive layout."""
    default_test_val = state.current_entry.word if state.current_entry else "hello"

    test_input = ft.TextField(
        value=default_test_val,
        label="Test Word or Audio URL",
        hint_text="Enter a word (e.g. 'hello') or direct MP3 URL...",
        text_size=13,
        expand=True,
    )

    log_display = ft.TextField(
        value=state.audio_diagnostic_text or "Click 'Run Diagnostics' below to inspect the audio pipeline...",
        label="Diagnostic Log Output (Selectable & Copyable)",
        multiline=True,
        read_only=True,
        text_size=11,
        min_lines=6,
        max_lines=12,
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

    def on_test_play(_):
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

    def on_test_tts(_):
        val = test_input.value.strip() or default_test_val
        status_label.value = f"🗣️ Speaking '{val}' via System Voice (TTS)..."
        status_label.color = palette.primary
        safe_page_update()
        state.speak_tts(val)

    def on_copy(_):
        page.set_clipboard(log_display.value)
        status_label.value = "📋 Diagnostic report copied to clipboard!"
        status_label.color = palette.success
        safe_page_update()

    def on_close(_):
        close_dialog_compat(page, dialog)

    page_width = getattr(page, "width", 400) or 400
    dialog_width = min(max(page_width - 32, 280), 560)

    dialog_content = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        test_input,
                        create_elevated_button(
                            text="Run Diagnostics",
                            icon_name="SEARCH",
                            on_click=on_run_diag,
                            bgcolor=palette.primary,
                            color="#FFFFFF",
                        ),
                    ],
                    spacing=8,
                    wrap=True,
                ),
                ft.Row(
                    controls=[
                        create_outlined_button(
                            text="Play Stream",
                            icon_name="VOLUME_UP",
                            on_click=on_test_play,
                        ),
                        create_outlined_button(
                            text="Test Voice (TTS)",
                            icon_name="RECORD_VOICE_OVER",
                            on_click=on_test_tts,
                        ),
                        create_outlined_button(
                            text="Copy Log",
                            icon_name="CONTENT_COPY",
                            on_click=on_copy,
                        ),
                    ],
                    spacing=8,
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
        padding=pad_all(8),
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