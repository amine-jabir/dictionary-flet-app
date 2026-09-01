"""
Reusable search bar component with clear button, submit action, and clean rounded styling.
"""

from typing import Callable, Optional
import flet as ft

from dict_client_flet.ui.flet_compat import (
    border_all,
    border_radius_all,
    create_icon_button,
    get_icon,
    pad_symmetric,
)
from dict_client_flet.ui.theme import ColorPalette


def build_search_bar(
    on_search: Callable[[str], None],
    on_clear: Optional[Callable[[], None]] = None,
    initial_query: str = "",
    palette: ColorPalette = None,  # type: ignore
) -> ft.Container:
    """Builds a modern search bar widget with cancellation/clearing support."""
    text_input = ft.TextField(
        value=initial_query,
        hint_text="Search a word (e.g. serendipity, lucid, resilience)...",
        prefix_icon=get_icon("SEARCH"),
        border=ft.InputBorder.NONE,
        content_padding=pad_symmetric(horizontal=16, vertical=12),
        text_size=15,
        autofocus=True,
        expand=True,
        on_submit=lambda e: on_search(e.control.value),
    )

    def handle_clear(_):
        text_input.value = ""
        try:
            text_input.update()
            text_input.focus()
        except Exception:
            pass
        if on_clear:
            on_clear()

    clear_button = create_icon_button(
        icon_name="CLEAR",
        icon_size=18,
        tooltip="Clear search",
        on_click=handle_clear,
    )

    search_button = create_icon_button(
        icon_name="ARROW_FORWARD",
        icon_size=20,
        tooltip="Search",
        bgcolor=palette.primary if palette else "#4F46E5",
        icon_color="#FFFFFF",
        on_click=lambda _: on_search(text_input.value),
    )

    return ft.Container(
        content=ft.Row(
            controls=[
                text_input,
                clear_button,
                search_button,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        bgcolor=palette.surface if palette else "#FFFFFF",
        border=border_all(1, palette.border if palette else "#E2E8F0"),
        border_radius=border_radius_all(24),
        padding=pad_symmetric(horizontal=8, vertical=4),
    )
