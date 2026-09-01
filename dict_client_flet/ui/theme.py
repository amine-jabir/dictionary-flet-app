"""
Theme definitions, color tokens, and typography for the Flet cross-platform client.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ColorPalette:
    """Color palette definition for light and dark themes."""
    primary: str
    primary_container: str
    secondary: str
    background: str
    surface: str
    surface_variant: str
    border: str
    text_primary: str
    text_secondary: str
    text_muted: str
    success: str
    warning: str
    error: str
    card_bg: str


# Light Theme (Clean modern slate & indigo palette)
LIGHT_PALETTE = ColorPalette(
    primary="#4F46E5",          # Indigo-600
    primary_container="#EEF2FF",# Indigo-50
    secondary="#06B6D4",        # Cyan-500
    background="#F8FAFC",       # Slate-50
    surface="#FFFFFF",          # Pure white
    surface_variant="#F1F5F9",  # Slate-100
    border="#E2E8F0",           # Slate-200
    text_primary="#0F172A",     # Slate-900
    text_secondary="#475569",   # Slate-600
    text_muted="#94A3B8",       # Slate-400
    success="#10B981",          # Emerald-500
    warning="#F59E0B",          # Amber-500
    error="#EF4444",            # Red-500
    card_bg="#FFFFFF",
)

# Dark Theme (Deep slate & vibrant indigo palette)
DARK_PALETTE = ColorPalette(
    primary="#818CF8",          # Indigo-400
    primary_container="#312E81",# Indigo-900
    secondary="#22D3EE",        # Cyan-400
    background="#0F172A",       # Slate-900
    surface="#1E293B",          # Slate-800
    surface_variant="#334155",  # Slate-700
    border="#334155",           # Slate-700
    text_primary="#F8FAFC",     # Slate-50
    text_secondary="#CBD5E1",   # Slate-300
    text_muted="#64748B",       # Slate-500
    success="#34D399",          # Emerald-400
    warning="#FBBF24",          # Amber-400
    error="#F87171",            # Red-400
    card_bg="#1E293B",
)

# Part of Speech Badge Color Mapping
POS_COLORS: Dict[str, str] = {
    "noun": "#3B82F6",         # Blue
    "verb": "#10B981",         # Emerald
    "adjective": "#F59E0B",    # Amber
    "adverb": "#8B5CF6",       # Purple
    "pronoun": "#06B6D4",      # Cyan
    "preposition": "#EC4899",  # Pink
    "conjunction": "#14B8A6",  # Teal
    "interjection": "#F43F5E", # Rose
    "unknown": "#6B7280",      # Gray
}


def get_pos_color(part_of_speech: str) -> str:
    """Returns the accent color for a given part of speech."""
    cleaned = str(part_of_speech or "").strip().lower()
    return POS_COLORS.get(cleaned, POS_COLORS["unknown"])
