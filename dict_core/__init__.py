"""
dict_core - Core dictionary domain logic, interfaces, providers, storage, audio, ranking, and services.
"""

from dict_core.config import AppConfig, DEFAULT_CONFIG
from dict_core.exceptions import (
    AudioError,
    AudioPlaybackError,
    AuthenticationError,
    DictionaryError,
    InvalidResponseError,
    NetworkError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
    ValidationError,
    WordNotFoundError,
)
from dict_core.interfaces.audio import BaseAudioPlayer, NullAudioPlayer, PlatformAudioPlayer
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.ranking.sense_ranker import SenseRanker
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseError, DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository
from dict_core.utils.http_client import ResilientHttpClient
from dict_core.utils.logger import get_logger

__all__ = [
    "AppConfig",
    "DEFAULT_CONFIG",
    "AudioError",
    "AudioPlaybackError",
    "AuthenticationError",
    "DictionaryError",
    "InvalidResponseError",
    "NetworkError",
    "ProviderUnavailableError",
    "RateLimitError",
    "TimeoutError",
    "ValidationError",
    "WordNotFoundError",
    "BaseDictionaryProvider",
    "BaseAudioPlayer",
    "NullAudioPlayer",
    "PlatformAudioPlayer",
    "AudioSource",
    "Definition",
    "Meaning",
    "Phonetic",
    "WordEntry",
    "FreeDictProvider",
    "WiktionaryProvider",
    "OfflineDictionaryProvider",
    "SenseRanker",
    "DatabaseError",
    "DatabaseManager",
    "CacheRepository",
    "HistoryRepository",
    "VocabularyRepository",
    "AudioCacheManager",
    "AudioService",
    "LookupService",
    "ResilientHttpClient",
    "get_logger",
]
