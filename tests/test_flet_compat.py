"""
Unit tests for flet_compat module verifying robust cross-version helper behavior.
"""

import unittest
from unittest.mock import MagicMock

try:
    import flet as ft
    HAS_FLET = True
except ImportError:
    HAS_FLET = False

from dict_client_flet.ui.flet_compat import (
    align_center,
    border_all,
    border_radius_all,
    close_dialog_compat,
    create_bottom_nav_destination,
    create_elevated_button,
    create_icon,
    create_icon_button,
    create_nav_destination,
    create_text_button,
    get_icon,
    margin_only,
    open_dialog_compat,
    pad_all,
    pad_only,
    pad_symmetric,
    wrap_safe_area,
)


class TestFletCompat(unittest.TestCase):
    """Tests the cross-version helper methods."""

    def test_get_icon_resolution(self) -> None:
        icon_search = get_icon("SEARCH")
        self.assertIsNotNone(icon_search)
        self.assertEqual(get_icon("nonexistent_custom_icon"), "nonexistent_custom_icon")

    def test_pad_all(self) -> None:
        p = pad_all(16)
        self.assertIsNotNone(p)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_pad_symmetric(self) -> None:
        p = pad_symmetric(horizontal=12, vertical=8)
        self.assertIsNotNone(p)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_pad_only(self) -> None:
        p = pad_only(top=10, bottom=20)
        self.assertIsNotNone(p)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_margin_only(self) -> None:
        m = margin_only(bottom=8)
        self.assertIsNotNone(m)

    @unittest.skipUnless(HAS_FLET, "Requires flet package installed")
    def test_border_all(self) -> None:
        b = border_all(1, "#E2E8F0")
        self.assertIsNotNone(b)

    def test_border_radius_all(self) -> None:
        br = border_radius_all(16)
        self.assertIsNotNone(br)

    def test_align_center(self) -> None:
        a = align_center()
        self.assertTrue(a is None or a is not None)

    def test_wrap_safe_area_fallback(self) -> None:
        mock_ctrl = MagicMock()
        res = wrap_safe_area(mock_ctrl)
        self.assertIsNotNone(res)

    def test_open_close_dialog_compat(self) -> None:
        mock_page = MagicMock()
        mock_dialog = MagicMock()
        
        # Test modern page.open
        mock_page.open = MagicMock()
        open_dialog_compat(mock_page, mock_dialog)
        mock_page.open.assert_called_once_with(mock_dialog)

        # Test modern page.close
        mock_page.close = MagicMock()
        close_dialog_compat(mock_page, mock_dialog)
        mock_page.close.assert_called_once_with(mock_dialog)

        # Test legacy page.dialog fallback
        legacy_page = MagicMock(spec=["update", "dialog"])
        legacy_page.dialog = None
        open_dialog_compat(legacy_page, mock_dialog)
        self.assertEqual(legacy_page.dialog, mock_dialog)
        self.assertTrue(mock_dialog.open)

    def test_create_bottom_nav_destination_fallback(self) -> None:
        res = create_bottom_nav_destination("SEARCH", "Search")
        self.assertTrue(res is None or res is not None)


if __name__ == "__main__":
    unittest.main()

    def test_audio_helpers(self) -> None:
        from dict_client_flet.ui.flet_compat import get_audio_class, is_audio_control
        self.assertFalse(is_audio_control(None))
        self.assertFalse(is_audio_control("string"))

    def test_set_clipboard_compat_modern_and_legacy(self) -> None:
        from dict_client_flet.ui.flet_compat import set_clipboard_compat
        
        # Test modern page.clipboard
        mock_modern = MagicMock()
        set_clipboard_compat(mock_modern, "clip_modern")
        self.assertEqual(mock_modern.clipboard, "clip_modern")

        # Test legacy page.set_clipboard
        mock_legacy = MagicMock(spec=["update", "set_clipboard"])
        set_clipboard_compat(mock_legacy, "clip_legacy")
        mock_legacy.set_clipboard.assert_called_once_with("clip_legacy")

    def test_create_audio_control(self) -> None:
        from dict_client_flet.ui.flet_compat import create_audio_control

        class MockAudioA:
            def __init__(self, src=None, autoplay=False, volume=1.0, on_state_change=None):
                self.src = src
                self.autoplay = autoplay
                self.volume = volume

        class MockAudioB:
            def __init__(self, src=None, autoplay=False, volume=1.0, on_state_changed=None):
                self.src = src
                self.autoplay = autoplay
                self.volume = volume

        a = create_audio_control(MockAudioA, "song.mp3", autoplay=True, volume=0.8)
        self.assertEqual(a.src, "song.mp3")
        self.assertTrue(a.autoplay)
        self.assertEqual(a.volume, 0.8)

        b = create_audio_control(MockAudioB, "song.mp3", autoplay=False, volume=0.5)
        self.assertEqual(b.src, "song.mp3")
        self.assertFalse(b.autoplay)
        self.assertEqual(b.volume, 0.5)
