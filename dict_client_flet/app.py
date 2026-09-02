"""
Root Flet Application Layout.
Provides responsive layout adaptation for Desktop, Mobile (Android/iOS), and Web platforms.
Features dynamic bottom navigation for narrow/mobile screens, safe-area handling, and resilient audio engine wiring.
"""

import os
from pathlib import Path
import sys
from typing import Optional
import flet as ft

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.audio_player import FletAudioPlayer
from dict_client_flet.ui.flet_compat import (
    align_center,
    create_bottom_nav_destination,
    create_elevated_button,
    create_icon,
    create_icon_button,
    create_nav_destination,
    pad_all,
    wrap_safe_area,
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


def is_mobile_layout(page: ft.Page) -> bool:
    """Detects whether mobile responsive layout should be activated (< 640px or mobile platform)."""
    w = getattr(page, "width", None)
    if w is not None and w < 640:
        return True
    plat = str(getattr(page, "platform", "")).lower()
    if "android" in plat or "ios" in plat or hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ:
        return True
    return False


def main_app(page: ft.Page, state: Optional[AppState] = None) -> None:
    """Main Flet application entrypoint."""
    page.title = "Dictionary"

    # Theme Mode Initialization
    if hasattr(ft, "ThemeMode") and hasattr(ft.ThemeMode, "LIGHT"):
        page.theme_mode = ft.ThemeMode.LIGHT
    else:
        page.theme_mode = "light"

    # Configure window dimensions safely for desktop environments
    plat = str(getattr(page, "platform", "")).lower()
    is_mobile_plat = "android" in plat or "ios" in plat or hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ
    if not is_mobile_plat:
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

    # Wire the cross-platform Flet audio player into AudioService
    flet_player = FletAudioPlayer(page)
    app_state.audio_service.player = flet_player

    # Content container dynamically updated
    view_body = ft.Container(expand=True)
    safe_content = wrap_safe_area(view_body)

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

    # Mobile Bottom Navigation Bar
    bottom_destinations = [
        create_bottom_nav_destination("SEARCH", "Search"),
        create_bottom_nav_destination("FAVORITE_BORDER", "Favorites", selected_icon_name="FAVORITE"),
        create_bottom_nav_destination("HISTORY", "History"),
    ]
    valid_bottom_destinations = [d for d in bottom_destinations if d is not None]

    bottom_nav_bar = None
    if valid_bottom_destinations:
        bottom_nav_bar = ft.NavigationBar(
            selected_index=app_state.active_tab_index,
            destinations=valid_bottom_destinations,
            on_change=lambda e: app_state.set_tab(e.control.selected_index),
        )

    divider = ft.VerticalDivider(width=1)

    def update_navigation_mode() -> None:
        """Dynamically adjusts navigation between desktop sidebar and mobile bottom bar."""
        is_mobile = is_mobile_layout(page)
        if is_mobile:
            nav_rail.visible = False
            divider.visible = False
            if bottom_nav_bar:
                page.navigation_bar = bottom_nav_bar
                bottom_nav_bar.selected_index = app_state.active_tab_index
        else:
            nav_rail.visible = True
            divider.visible = True
            page.navigation_bar = None
            nav_rail.selected_index = app_state.active_tab_index

    def render_ui() -> None:
        try:
            palette = DARK_PALETTE if app_state.is_dark_mode else LIGHT_PALETTE
            if hasattr(ft, "ThemeMode"):
                page.theme_mode = ft.ThemeMode.DARK if app_state.is_dark_mode else ft.ThemeMode.LIGHT
            else:
                page.theme_mode = "dark" if app_state.is_dark_mode else "light"

            page.bgcolor = palette.background

            # Update responsive navigation and sync indices
            update_navigation_mode()

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

    # Responsive resize handling for rotation and window resizing
    def on_page_resize(_):
        update_navigation_mode()
        try:
            page.update()
        except Exception:
            pass

    if hasattr(page, "on_resized"):
        page.on_resized = on_page_resize
    if hasattr(page, "on_resize"):
        page.on_resize = on_page_resize

    page.add(
        ft.Row(
            controls=[
                nav_rail,
                divider,
                safe_content,
            ],
            expand=True,
            spacing=0,
        )
    )

    render_ui()