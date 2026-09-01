"""
Root Flet Application Layout.
Provides responsive layout adaptation for Desktop, Mobile, and Web platforms.
"""

from pathlib import Path
from typing import Optional
import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.audio_player import FletAudioPlayer
from dict_client_flet.ui.flet_compat import (
    align_center,
    create_elevated_button,
    create_icon,
    create_icon_button,
    create_nav_destination,
    pad_all,
)
from dict_client_flet.ui.theme import DARK_PALETTE, LIGHT_PALETTE
from dict_client_flet.ui.views.favorites_view import build_favorites_view
from dict_client_flet.ui.views.history_view import build_history_view
from dict_client_flet.ui.views.lookup_view import build_lookup_view
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository
from dict_core.utils.logger import get_logger

logger = get_logger("dict_client.app")


def create_default_state(db_path: Optional[str] = None) -> AppState:
    """Factory creating a fully wired AppState instance with dict_core services."""
    db = DatabaseManager(db_path)
    cache_repo = CacheRepository(db)
    history_repo = HistoryRepository(db)
    vocab_repo = VocabularyRepository(db)

    primary_provider = FreeDictProvider()
    fallback_provider = WiktionaryProvider()

    lookup_service = LookupService(
        provider=primary_provider,
        cache_repo=cache_repo,
        history_repo=history_repo,
        fallback_providers=[fallback_provider],
    )

    audio_cache = AudioCacheManager()
    audio_service = AudioService(cache_manager=audio_cache)

    state = AppState(
        lookup_service=lookup_service,
        audio_service=audio_service,
        vocab_repo=vocab_repo,
        history_repo=history_repo,
    )
    state.load_favorites()
    state.load_history()
    return state


def main_app(page: ft.Page, state: Optional[AppState] = None) -> None:
    """Main Flet application entrypoint."""
    page.title = "Dictionary"
    
    # Theme Mode
    if hasattr(ft, "ThemeMode") and hasattr(ft.ThemeMode, "LIGHT"):
        page.theme_mode = ft.ThemeMode.LIGHT
    else:
        page.theme_mode = "light"
    
    # Configure window dimensions with cross-version compatibility
    if hasattr(page, "window") and page.window:
        page.window.width = 800
        page.window.height = 650
        page.window.min_width = 360
        page.window.min_height = 480
    else:
        page.window_width = 800
        page.window_height = 650
        page.window_min_width = 360
        page.window_min_height = 480

    page.padding = 0

    app_state = state or create_default_state()

    # Bridge background thread updates to the Flet/Flutter event loop
    if hasattr(page, "run_thread"):
        app_state.set_ui_runner(page.run_thread)

    # Wire the real Flet / OS audio player into AudioService
    flet_player = FletAudioPlayer(page)
    app_state.audio_service.player = flet_player

    # Content container dynamically updated
    view_body = ft.Container(expand=True)

    def render_ui() -> None:
        try:
            palette = DARK_PALETTE if app_state.is_dark_mode else LIGHT_PALETTE
            if hasattr(ft, "ThemeMode"):
                page.theme_mode = ft.ThemeMode.DARK if app_state.is_dark_mode else ft.ThemeMode.LIGHT
            else:
                page.theme_mode = "dark" if app_state.is_dark_mode else "light"
                
            page.bgcolor = palette.background

            # Synchronize navigation rail index with active tab state
            nav_rail.selected_index = app_state.active_tab_index

            # Update active view
            if app_state.active_tab_index == 0:
                view_body.content = build_lookup_view(app_state, palette, page=page)
            elif app_state.active_tab_index == 1:
                view_body.content = build_favorites_view(app_state, palette)
            elif app_state.active_tab_index == 2:
                view_body.content = build_history_view(app_state, palette)

            page.update()
        except Exception as exc:
            logger.error("Error during render_ui: %s", exc, exc_info=True)
            view_body.content = ft.Container(
                content=ft.Column(
                    controls=[
                        create_icon("WARNING", size=48, color="#EF4444"),
                        ft.Text("Interface Render Notice", size=18, weight="bold"),
                        ft.Text(str(exc), size=13, color="#64748B"),
                        create_elevated_button(
                            text="Reset View",
                            icon_name="REFRESH",
                            on_click=lambda _: app_state.set_tab(0),
                        ),
                    ],
                    alignment="center",
                    horizontal_alignment="center",
                    spacing=12,
                ),
                alignment=align_center(),
                padding=pad_all(32),
            )
            try:
                page.update()
            except Exception:
                pass

    app_state.subscribe(render_ui)

    # Top App Bar with theme toggle
    def toggle_theme(_):
        app_state.set_dark_mode(not app_state.is_dark_mode)

    theme_btn = create_icon_button(
        icon_name="DARK_MODE" if not app_state.is_dark_mode else "LIGHT_MODE",
        tooltip="Toggle Dark/Light Mode",
        on_click=toggle_theme,
    )

    app_bar = ft.AppBar(
        leading=create_icon("MENU_BOOK", color="#6366F1"),
        leading_width=40,
        title=ft.Text("Dictionary", weight="bold", size=18),
        center_title=False,
        actions=[theme_btn],
    )
    page.appbar = app_bar

    # Desktop Navigation Rail
    nav_rail = ft.NavigationRail(
        selected_index=app_state.active_tab_index,
        label_type="all",
        min_width=72,
        min_extended_width=160,
        destinations=[
            create_nav_destination("SEARCH", "Search"),
            create_nav_destination("FAVORITE_BORDER", "Favorites", selected_icon_name="FAVORITE"),
            create_nav_destination("HISTORY", "History"),
        ],
        on_change=lambda e: app_state.set_tab(e.control.selected_index),
    )

    page.add(
        ft.Row(
            controls=[
                nav_rail,
                ft.VerticalDivider(width=1),
                view_body,
            ],
            expand=True,
            spacing=0,
        )
    )

    render_ui()
