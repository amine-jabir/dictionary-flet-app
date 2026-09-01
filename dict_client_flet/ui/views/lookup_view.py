"""
Lookup View: The main dictionary search and definition viewing interface.
"""

from typing import Optional
import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.components.definition_card import build_definition_card
from dict_client_flet.ui.components.header_widget import build_header_widget
from dict_client_flet.ui.components.search_bar import build_search_bar
from dict_client_flet.ui.components.state_views import (
    build_error_view,
    build_loading_view,
    build_welcome_view,
)
from dict_client_flet.ui.flet_compat import pad_only, pad_symmetric
from dict_client_flet.ui.theme import ColorPalette


def build_lookup_view(state: AppState, palette: ColorPalette, page: Optional[ft.Page] = None) -> ft.Container:
    """Constructs the primary search and definition view."""
    # 1. Search Bar at the top
    search_bar_widget = build_search_bar(
        on_search=lambda q: state.search_word(q),
        initial_query=state.current_query,
        palette=palette,
    )

    # 2. Main content container depending on current state
    if state.is_loading:
        content_view = build_loading_view(palette)
    elif state.error_message:
        content_view = build_error_view(
            message=state.error_message,
            on_retry=lambda: state.search_word(state.current_query, force_refresh=True),
            palette=palette,
        )
    elif state.current_entry:
        # Header + Definition cards list
        cards = [build_header_widget(state.current_entry, state, palette, page=page)]
        for meaning in state.current_entry.meanings:
            cards.append(build_definition_card(meaning, palette))

        content_view = ft.ListView(
            controls=cards,
            spacing=10,
            padding=pad_only(top=12, bottom=32),
            expand=True,
        )
    else:
        content_view = build_welcome_view(palette)

    return ft.Container(
        content=ft.Column(
            controls=[
                search_bar_widget,
                ft.Container(content=content_view, expand=True),
            ],
            spacing=12,
            expand=True,
        ),
        padding=pad_symmetric(horizontal=16, vertical=12),
        expand=True,
    )
