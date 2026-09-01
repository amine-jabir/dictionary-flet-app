"""
Favorites View: Managing bookmarked vocabulary, study notes, and tags.
"""

import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.flet_compat import (
    align_center,
    border_all,
    border_radius_all,
    create_icon,
    create_icon_button,
    margin_only,
    pad_all,
    pad_symmetric,
)
from dict_client_flet.ui.theme import ColorPalette


def build_favorites_view(state: AppState, palette: ColorPalette) -> ft.Container:
    """Constructs the bookmarked vocabulary view."""
    if not state.favorites_list:
        return ft.Container(
            content=ft.Column(
                controls=[
                    create_icon("FAVORITE_BORDER", size=56, color=palette.text_muted),
                    ft.Text(value="No Favorites Yet", size=20, weight="bold", color=palette.text_primary),
                    ft.Text(
                        value="Star any word while searching to build your personal vocabulary list.",
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

    fav_cards = []
    for fav in state.favorites_list:
        word = fav["word"]
        notes = fav.get("notes", "")
        tags = fav.get("tags", [])

        tag_controls = [
            ft.Container(
                content=ft.Text(value=t, size=11, color=palette.primary),
                bgcolor=palette.primary_container,
                padding=pad_symmetric(horizontal=8, vertical=2),
                border_radius=border_radius_all(10),
            )
            for t in tags
        ]

        card_rows = [
            ft.Row(
                controls=[
                    ft.Text(
                        value=word.capitalize(),
                        size=18,
                        weight="bold",
                        color=palette.text_primary,
                        expand=True,
                    ),
                    create_icon_button(
                        icon_name="SEARCH",
                        icon_size=20,
                        tooltip=f"Lookup '{word}'",
                        on_click=lambda _, w=word: (state.set_tab(0), state.search_word(w)),
                    ),
                    create_icon_button(
                        icon_name="DELETE_OUTLINE",
                        icon_size=20,
                        icon_color=palette.error,
                        tooltip="Remove from Favorites",
                        on_click=lambda _, w=word: state.remove_favorite_item(w),
                    ),
                ],
                alignment="spaceBetween",
                vertical_alignment="center",
            )
        ]

        if notes:
            card_rows.append(
                ft.Text(value=notes, size=13, italic=True, color=palette.text_secondary)
            )

        if tag_controls:
            card_rows.append(ft.Row(controls=tag_controls, spacing=6))

        fav_cards.append(
            ft.Container(
                content=ft.Column(controls=card_rows, spacing=8),
                bgcolor=palette.surface,
                border=border_all(1, palette.border),
                border_radius=border_radius_all(12),
                padding=pad_all(14),
                margin=margin_only(bottom=8),
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(value="Saved Vocabulary", size=22, weight="bold", color=palette.text_primary),
                        ft.Text(value=f"{len(state.favorites_list)} words", size=13, color=palette.text_muted),
                    ],
                    alignment="spaceBetween",
                ),
                ft.Divider(height=1, color=palette.border),
                ft.ListView(controls=fav_cards, spacing=8, expand=True),
            ],
            spacing=12,
            expand=True,
        ),
        padding=pad_symmetric(horizontal=16, vertical=12),
        expand=True,
    )
