"""
dict_client_flet - Cross-platform Flet presentation layer for dict_core.
"""

from dict_client_flet.state.app_state import AppState
from dict_client_flet.ui.theme import DARK_PALETTE, LIGHT_PALETTE, ColorPalette, get_pos_color

try:
    from dict_client_flet.app import create_default_state, main_app
except ImportError:
    create_default_state = None  # type: ignore
    main_app = None  # type: ignore

__all__ = [
    "AppState",
    "ColorPalette",
    "LIGHT_PALETTE",
    "DARK_PALETTE",
    "get_pos_color",
    "create_default_state",
    "main_app",
]
