"""
Empty, Loading, and Error state views for the Flet UI.
"""

from typing import Any, Callable
import flet as ft

from dict_client_flet.ui.flet_compat import (
    align_center,
    create_elevated_button,
    create_icon,
    get_icon,
    pad_all,
)
from dict_client_flet.ui.theme import ColorPalette


def build_welcome_view(palette: ColorPalette) -> ft.Container:
    """Builds the initial empty state view welcoming the user to search."""
    return ft.Container(
        content=ft.Column(
            controls=[
                create_icon(
                    "MENU_BOOK",
                    size=64,
                    color=palette.primary,
                ),
                ft.Text(
                    value="Search the Dictionary",
                    size=22,
                    weight="bold",
                    color=palette.text_primary,
                ),
                ft.Text(
                    value="Type any English word to explore clear definitions, example sentences, and phonetic audio pronunciations.",
                    size=14,
                    color=palette.text_secondary,
                    text_align="center",
                ),
            ],
            alignment="center",
            horizontal_alignment="center",
            spacing=12,
        ),
        alignment=align_center(),
        padding=pad_all(32),
        expand=True,
    )


def build_loading_view(palette: ColorPalette) -> ft.Container:
    """Builds the animated progress view while searching."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.ProgressRing(
                    width=48,
                    height=48,
                    stroke_width=4,
                    color=palette.primary,
                ),
                ft.Text(
                    value="Searching dictionary...",
                    size=15,
                    color=palette.text_secondary,
                ),
            ],
            alignment="center",
            horizontal_alignment="center",
            spacing=16,
        ),
        alignment=align_center(),
        padding=pad_all(32),
        expand=True,
    )


def build_error_view(message: str, on_retry: Callable[[], None], palette: ColorPalette) -> ft.Container:
    """Builds the error state view with message and retry button."""
    return ft.Container(
        content=ft.Column(
            controls=[
                create_icon(
                    "SEARCH_OFF",
                    size=56,
                    color=palette.error,
                ),
                ft.Text(
                    value="Search Notice",
                    size=18,
                    weight="bold",
                    color=palette.text_primary,
                ),
                ft.Text(
                    value=message,
                    size=14,
                    color=palette.text_secondary,
                    text_align="center",
                ),
                create_elevated_button(
                    text="Retry Search",
                    icon_name="REFRESH",
                    on_click=lambda _: on_retry(),
                    bgcolor=palette.primary,
                    color="#FFFFFF",
                ),
            ],
            alignment="center",
            horizontal_alignment="center",
            spacing=14,
        ),
        alignment=align_center(),
        padding=pad_all(32),
        expand=True,
    )
