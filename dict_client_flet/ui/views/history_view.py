"""
History View: Chronological list of searched words with quick re-search and clear history actions.
"""

import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.flet_compat import (
    align_center,
    border_all,
    border_radius_all,
    create_icon,
    create_icon_button,
    create_text_button,
    margin_only,
    pad_all,
    pad_symmetric,
)
from dict_client_flet.ui.theme import ColorPalette


def build_history_view(state: AppState, palette: ColorPalette) -> ft.Container:
    """Constructs the search history view."""
    if not state.history_list:
        return ft.Container(
            content=ft.Column(
                controls=[
                    create_icon("HISTORY", size=56, color=palette.text_muted),
                    ft.Text(value="No Search History", size=20, weight="bold", color=palette.text_primary),
                    ft.Text(
                        value="Your recent dictionary queries will automatically appear here.",
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

    history_items = []
    for item in state.history_list:
        word = item["word"]
        result_found = item.get("result_found", True)
        searched_at = str(item.get("searched_at", "") or "")[:16].replace("T", " ")

        status_badge = ft.Container(
            content=ft.Text(
                value="Found" if result_found else "404",
                size=11,
                weight="bold",
                color=palette.success if result_found else palette.error,
            ),
            bgcolor=palette.surface_variant,
            padding=pad_symmetric(horizontal=8, vertical=2),
            border_radius=border_radius_all(8),
        )

        history_items.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    value=word.capitalize(),
                                    size=16,
                                    weight="w600",
                                    color=palette.text_primary,
                                ),
                                ft.Text(
                                    value=searched_at,
                                    size=12,
                                    color=palette.text_muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        status_badge,
                        create_icon_button(
                            icon_name="SEARCH",
                            icon_size=20,
                            tooltip=f"Lookup '{word}'",
                            on_click=lambda _, w=word: (state.set_tab(0), state.search_word(w)),
                        ),
                    ],
                    alignment="spaceBetween",
                    vertical_alignment="center",
                ),
                bgcolor=palette.surface,
                border=border_all(1, palette.border),
                border_radius=border_radius_all(10),
                padding=pad_symmetric(horizontal=14, vertical=10),
                margin=margin_only(bottom=6),
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(value="Recent Searches", size=22, weight="bold", color=palette.text_primary),
                        create_text_button(
                            text="Clear History",
                            icon_name="DELETE_SWEEP",
                            on_click=lambda _: state.clear_history(),
                            color=palette.error,
                        ),
                    ],
                    alignment="spaceBetween",
                ),
                ft.Divider(height=1, color=palette.border),
                ft.ListView(controls=history_items, spacing=6, expand=True),
            ],
            spacing=12,
            expand=True,
        ),
        padding=pad_symmetric(horizontal=16, vertical=12),
        expand=True,
    )
