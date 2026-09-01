"""
Definition card component rendering part-of-speech groupings, definitions, examples, and synonyms.
Prioritizes top learner-relevant senses and provides an expandable view for secondary/niche meanings.
"""

from typing import List
import flet as ft

from dict_client_flet.ui.flet_compat import (
    border_all,
    border_radius_all,
    create_text_button,
    margin_only,
    pad_all,
    pad_only,
    pad_symmetric,
)
from dict_client_flet.ui.theme import ColorPalette, get_pos_color
from dict_core.models.word import Definition, Meaning


def _build_definition_item(
    idx: int,
    d: Definition,
    pos_color: str,
    palette: ColorPalette,
) -> ft.Column:
    """Builds the UI elements for a single numbered definition with examples and synonyms."""
    item_rows = [
        ft.Row(
            controls=[
                ft.Text(
                    value=f"{idx}.",
                    size=14,
                    weight="bold",
                    color=pos_color,
                ),
                ft.Text(
                    value=d.definition,
                    size=14,
                    color=palette.text_primary,
                    expand=True,
                ),
            ],
            vertical_alignment="start",
            spacing=8,
        )
    ]

    # Example sentence callout box
    if d.example:
        item_rows.append(
            ft.Container(
                content=ft.Text(
                    value=f'"{d.example}"',
                    size=13,
                    italic=True,
                    color=palette.text_secondary,
                ),
                padding=pad_only(left=24, top=4, bottom=4),
            )
        )

    # Definition-specific synonyms
    if d.synonyms:
        item_rows.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text(value="Synonyms:", size=11, weight="bold", color=palette.text_muted),
                        ft.Text(value=", ".join(d.synonyms[:5]), size=12, color=palette.primary),
                    ],
                    spacing=6,
                ),
                padding=pad_only(left=24, bottom=6),
            )
        )

    return ft.Column(
        controls=item_rows,
        spacing=2,
    )


def build_definition_card(
    meaning: Meaning,
    palette: ColorPalette,
    initial_limit: int = 3,
) -> ft.Container:
    """
    Builds a structured card displaying definitions and examples for a part of speech.
    Displays primary definitions first with an expandable toggle for secondary/niche meanings.
    """
    pos_color = get_pos_color(meaning.part_of_speech)

    # 1. Part of speech header badge
    pos_badge = ft.Container(
        content=ft.Text(
            value=meaning.part_of_speech.upper(),
            size=12,
            weight="bold",
            color="#FFFFFF",
        ),
        bgcolor=pos_color,
        padding=pad_symmetric(horizontal=10, vertical=4),
        border_radius=border_radius_all(12),
    )

    # 2. Numbered definitions list
    primary_defs: List[ft.Control] = []
    secondary_defs: List[ft.Control] = []

    for idx, d in enumerate(meaning.definitions, start=1):
        item_widget = _build_definition_item(idx, d, pos_color, palette)
        if idx <= initial_limit:
            primary_defs.append(item_widget)
        else:
            secondary_defs.append(item_widget)

    defs_column = ft.Column(controls=list(primary_defs), spacing=12)

    # 3. Expandable container for secondary / niche definitions
    if secondary_defs:
        secondary_container = ft.Column(controls=secondary_defs, spacing=12, visible=False)
        remaining_count = len(secondary_defs)

        def toggle_expand(e):
            secondary_container.visible = not secondary_container.visible
            new_text = "Show fewer meanings" if secondary_container.visible else f"More meanings (+{remaining_count})"
            if hasattr(expand_btn, "content") and hasattr(expand_btn.content, "controls"):
                for c in expand_btn.content.controls:
                    if isinstance(c, ft.Text):
                        c.value = new_text
            elif hasattr(expand_btn, "text"):
                expand_btn.text = new_text
            defs_column.update()

        expand_btn = create_text_button(
            text=f"More meanings (+{remaining_count})",
            icon_name="EXPAND_MORE",
            on_click=toggle_expand,
            color=palette.primary,
        )
        defs_column.controls.append(secondary_container)
        defs_column.controls.append(expand_btn)

    # 4. Meaning-level synonyms / antonyms
    extra_controls = []
    if meaning.synonyms:
        extra_controls.append(
            ft.Row(
                controls=[
                    ft.Text(value="Similar:", size=12, weight="bold", color=palette.text_muted),
                    ft.Text(value=", ".join(meaning.synonyms[:8]), size=13, color=palette.primary),
                ],
                spacing=6,
            )
        )

    if meaning.antonyms:
        extra_controls.append(
            ft.Row(
                controls=[
                    ft.Text(value="Opposites:", size=12, weight="bold", color=palette.text_muted),
                    ft.Text(value=", ".join(meaning.antonyms[:8]), size=13, color=palette.text_secondary),
                ],
                spacing=6,
            )
        )

    card_content = [
        ft.Row(
            controls=[
                pos_badge,
                ft.Divider(height=1, color=palette.border, expand=True),
            ],
            vertical_alignment="center",
            spacing=10,
        ),
        defs_column,
    ]

    if extra_controls:
        card_content.append(ft.Column(controls=extra_controls, spacing=4))

    return ft.Container(
        content=ft.Column(
            controls=card_content,
            spacing=14,
        ),
        bgcolor=palette.surface,
        border=border_all(1, palette.border),
        border_radius=border_radius_all(16),
        padding=pad_all(16),
        margin=margin_only(bottom=12),
    )
