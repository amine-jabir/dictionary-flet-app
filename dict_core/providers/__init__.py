"""
Providers package for dict_core.
"""

from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider

__all__ = [
    "FreeDictProvider",
    "WiktionaryProvider",
    "OfflineDictionaryProvider",
]
