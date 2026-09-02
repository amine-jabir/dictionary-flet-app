"""
Unit tests for Flet theme tokens, color palettes, and part-of-speech badge mappings.
"""

import unittest

from dict_client_flet.ui.theme import DARK_PALETTE, LIGHT_PALETTE, get_pos_color


class TestThemeTokens(unittest.TestCase):
    """Tests theme palettes and POS color resolution."""

    def test_palette_properties(self) -> None:
        self.assertTrue(LIGHT_PALETTE.primary.startswith("#"))
        self.assertTrue(LIGHT_PALETTE.background.startswith("#"))
        self.assertTrue(DARK_PALETTE.primary.startswith("#"))
        self.assertTrue(DARK_PALETTE.background.startswith("#"))
        self.assertNotEqual(LIGHT_PALETTE.background, DARK_PALETTE.background)

    def test_pos_color_mapping(self) -> None:
        self.assertEqual(get_pos_color("noun"), "#3B82F6")
        self.assertEqual(get_pos_color(" Noun "), "#3B82F6")
        self.assertEqual(get_pos_color("verb"), "#10B981")
        self.assertEqual(get_pos_color("adjective"), "#F59E0B")
        self.assertEqual(get_pos_color("adverb"), "#8B5CF6")
        self.assertEqual(get_pos_color("nonexistent_pos"), "#6B7280")
        self.assertEqual(get_pos_color(""), "#6B7280")


if __name__ == "__main__":
    unittest.main()
