"""
Interfaces package for dict_core.
"""

from dict_core.interfaces.audio import BaseAudioPlayer, NullAudioPlayer
from dict_core.interfaces.provider import BaseDictionaryProvider

__all__ = [
    "BaseDictionaryProvider",
    "BaseAudioPlayer",
    "NullAudioPlayer",
]
