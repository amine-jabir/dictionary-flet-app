"""
Word header component displaying word title, phonetic IPA badge, audio playback triggers,
status indicators, and audio diagnostics launch action.
"""

from typing import Callable, Optional
import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.components.audio_dialog import show_audio_diagnostics_dialog
from dict_client_flet.ui.flet_compat import (
    border_all,
    border_radius_all,
    create_icon,
    create_icon_button,
    create_outlined_button,
    get_icon,
    pad_all,
    pad_symmetric,
)
from dict_client_flet.ui.theme import ColorPalette
from dict_core.models.word import WordEntry


def build_header_widget(
    entry: WordEntry,
    state: AppState,
    palette: ColorPalette,
    page: Optional[ft.Page] = None,
) -> ft.Container:
    """Builds the top header section for a retrieved dictionary word."""
    has_audio = bool(entry.primary_audio_url)

    # 1. Phonetic Text Badges & Audio Play Buttons
    audio_controls = []
    if entry.primary_phonetic:
        audio_controls.append(
            ft.Container(
                content=ft.Text(
                    value=entry.primary_phonetic,
                    size=16,
                    weight="w500",
                    color=palette.primary,
                ),
                bgcolor=palette.primary_container,
                padding=pad_symmetric(horizontal=12, vertical=6),
                border_radius=border_radius_all(16),
            )
        )

    # Speaker Audio Button
    audio_controls.append(
        create_icon_button(
            icon_name="VOLUME_UP",
            icon_color=palette.primary,
            icon_size=24,
            tooltip="Listen to pronunciation stream",
            on_click=lambda _: state.play_audio(),
            bgcolor=palette.primary_container,
        )
    )

    # Voice TTS Button
    audio_controls.append(
        create_icon_button(
            icon_name="RECORD_VOICE_OVER" if get_icon("RECORD_VOICE_OVER") else "VOLUME_UP",
            icon_color=palette.secondary,
            icon_size=22,
            tooltip="Pronounce using System Voice (TTS)",
            on_click=lambda _: state.speak_tts(entry.word),
            bgcolor=palette.surface_variant,
        )
    )

    # Diagnose Button
    if page is not None:
        audio_controls.append(
            create_outlined_button(
                text="Diagnose Audio",
                icon_name="SETTINGS",
                tooltip="Inspect audio stream URL, download status, cache, and OS drivers",
                on_click=lambda _: show_audio_diagnostics_dialog(page, state, palette),
            )
        )

    # 2. Favorite Toggle Button
    favorite_btn = create_icon_button(
        icon_name="FAVORITE" if state.is_favorite else "FAVORITE_BORDER",
        icon_color="#F43F5E" if state.is_favorite else palette.text_muted,
        icon_size=24,
        tooltip="Remove from Favorites" if state.is_favorite else "Save to Favorites",
        on_click=lambda _: state.toggle_favorite(),
    )

    # 3. Audio Status & Feedback Banner
    status_row_controls = []
    if state.audio_status_message:
        is_err = "error" in state.audio_status_message.lower() or "fail" in state.audio_status_message.lower() or "⚠️" in state.audio_status_message
        status_row_controls.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            value=state.audio_status_message,
                            size=12,
                            weight="w500",
                            color=palette.error if is_err else palette.primary,
                        ),
                    ],
                    spacing=6,
                ),
                bgcolor=palette.surface_variant,
                padding=pad_symmetric(horizontal=10, vertical=4),
                border_radius=border_radius_all(8),
            )
        )

    # 4. Provider & Cache Attribution Tag
    provider_name = "Free Dictionary API" if entry.provider == "free_dict_api" else "Wiktionary REST"
    is_cached = entry.metadata.get("cached", False)
    badge_text = f"Source: {provider_name}" + (" (Cached Result)" if is_cached else "")

    attribution_badge = ft.Text(
        value=badge_text,
        size=11,
        color=palette.text_muted,
    )

    header_column_items = [
        ft.Row(
            controls=[
                ft.Text(
                    value=entry.word.capitalize(),
                    size=28,
                    weight="bold",
                    color=palette.text_primary,
                    expand=True,
                ),
                favorite_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment="center",
        ),
        ft.Row(
            controls=audio_controls,
            vertical_alignment="center",
            spacing=8,
            wrap=True,
        ),
    ]

    if status_row_controls:
        header_column_items.append(ft.Row(controls=status_row_controls, spacing=8))

    header_column_items.append(attribution_badge)

    return ft.Container(
        content=ft.Column(
            controls=header_column_items,
            spacing=8,
        ),
        padding=pad_symmetric(vertical=8),
    )
