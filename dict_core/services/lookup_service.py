"""
LookupService orchestrator for dict_core.
Coordinates cache lookups, offline local lexicon lookups, fast interactive provider fallbacks,
cache population, sense ranking, and history tracking.
"""

from typing import List, Optional

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import (
    DictionaryError,
    NetworkError,
    ProviderUnavailableError,
    TimeoutError,
    WordNotFoundError,
)
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.ranking.sense_ranker import SenseRanker
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.history_repo import HistoryRepository
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.services.lookup")


class LookupService:
    """
    Coordinates dictionary lookups across a 4-tier hierarchy:
      Tier 1: User SQLite Cache (word_cache) [< 0.5 ms]
      Tier 2: Local Offline Lexicon (offline_lexicon) [1 - 3 ms]
      Tier 3: Online Primary Provider (e.g. Free Dictionary API) [Strict interactive timeout]
      Tier 4: Online Fallback Provider (e.g. Wiktionary REST API) [Strict interactive timeout]
      
    Applies the SenseRanker definition ranking layer before returning results to callers.
    """

    def __init__(
        self,
        provider: BaseDictionaryProvider,
        cache_repo: CacheRepository,
        history_repo: Optional[HistoryRepository] = None,
        offline_provider: Optional[BaseDictionaryProvider] = None,
        fallback_providers: Optional[List[BaseDictionaryProvider]] = None,
        cache_ttl_days: int = DEFAULT_CONFIG.CACHE_EXPIRATION_DAYS,
        interactive_timeout: float = DEFAULT_CONFIG.INTERACTIVE_TIMEOUT_SECONDS,
        interactive_max_retries: int = DEFAULT_CONFIG.INTERACTIVE_MAX_RETRIES,
    ) -> None:
        self.provider = provider
        self.cache = cache_repo
        self.history = history_repo
        self.offline_provider = offline_provider if offline_provider is not None else OfflineDictionaryProvider()
        self.fallback_providers = list(fallback_providers or [])
        self.cache_ttl_days = cache_ttl_days
        self.interactive_timeout = float(interactive_timeout)
        self.interactive_max_retries = max(0, int(interactive_max_retries))

    def lookup(
        self,
        word: str,
        force_refresh: bool = False,
        record_history: bool = True,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> WordEntry:
        """
        Executes a dictionary search following the offline-first / local-first architecture.
        
        Args:
            word: Target term to look up.
            force_refresh: If True, bypasses local cache and offline lexicon to fetch fresh online data.
            record_history: If True, logs this query to search history.
            timeout: Optional specific request timeout in seconds (defaults to interactive_timeout).
            max_retries: Optional max retry count override (defaults to interactive_max_retries).
            
        Returns:
            WordEntry: The retrieved, ranked, and validated dictionary entry.
            
        Raises:
            ValidationError: If input word is blank or invalid.
            WordNotFoundError: If word is not found across cache, offline lexicon, and online providers.
            TimeoutError: If all online providers time out.
            NetworkError: If network connection fails.
        """
        clean_word = self.provider.validate_query(word)

        # ---------------------------------------------------------
        # Tier 1: Check User SQLite Cache (Instant < 0.5ms)
        # ---------------------------------------------------------
        if not force_refresh:
            cached_entry = self.cache.get(clean_word)
            if cached_entry:
                logger.debug("Cache HIT for '%s'", clean_word)
                if record_history and self.history:
                    self.history.add(
                        word=clean_word,
                        provider_id=cached_entry.provider,
                        result_found=True,
                    )
                updated_meta = dict(cached_entry.metadata)
                updated_meta["cached"] = True
                entry_to_return = WordEntry(
                    word=cached_entry.word,
                    phonetics=list(cached_entry.phonetics),
                    meanings=list(cached_entry.meanings),
                    source_urls=list(cached_entry.source_urls),
                    provider=cached_entry.provider,
                    queried_at=cached_entry.queried_at,
                    metadata=updated_meta,
                )
                return SenseRanker.rank_word_entry(entry_to_return)

        # ---------------------------------------------------------
        # Tier 2: Check Local Offline Lexicon (Sub-3ms)
        # ---------------------------------------------------------
        if not force_refresh and self.offline_provider and self.offline_provider.is_available():
            try:
                offline_entry = self.offline_provider.lookup(clean_word)
                logger.debug("Offline Lexicon HIT for '%s'", clean_word)
                
                # Cache the local result for subsequent instant hits
                self.cache.set(offline_entry, ttl_days=self.cache_ttl_days)
                
                if record_history and self.history:
                    self.history.add(
                        word=clean_word,
                        provider_id=self.offline_provider.provider_id,
                        result_found=True,
                    )
                return SenseRanker.rank_word_entry(offline_entry)
            except WordNotFoundError:
                logger.debug("Offline Lexicon MISS for '%s'", clean_word)
            except Exception as exc:
                logger.warning("Offline provider error for '%s': %s", clean_word, exc)

        # ---------------------------------------------------------
        # Tier 3 & 4: Query Online Providers with Strict Interactive Timeout
        # ---------------------------------------------------------
        logger.debug("Local MISS for '%s' (or force_refresh=%s). Querying online providers...", clean_word, force_refresh)
        providers_to_try = [self.provider] + self.fallback_providers
        last_exception: Optional[Exception] = None

        req_timeout = timeout if timeout is not None else self.interactive_timeout
        req_max_retries = max_retries if max_retries is not None else self.interactive_max_retries

        for current_provider in providers_to_try:
            try:
                entry = current_provider.lookup(
                    clean_word,
                    timeout=req_timeout,
                    max_retries=req_max_retries,
                )
                
                # Cache the fresh online result
                self.cache.set(entry, ttl_days=self.cache_ttl_days)
                
                # Log success in search history
                if record_history and self.history:
                    self.history.add(
                        word=clean_word,
                        provider_id=current_provider.provider_id,
                        result_found=True,
                    )

                updated_meta = dict(entry.metadata)
                updated_meta["cached"] = False
                entry_to_return = WordEntry(
                    word=entry.word,
                    phonetics=list(entry.phonetics),
                    meanings=list(entry.meanings),
                    source_urls=list(entry.source_urls),
                    provider=entry.provider,
                    queried_at=entry.queried_at,
                    metadata=updated_meta,
                )
                return SenseRanker.rank_word_entry(entry_to_return)

            except WordNotFoundError as exc:
                # If primary provider explicitly returned 404, try fallback if available
                last_exception = exc
                continue

            except (TimeoutError, NetworkError, ProviderUnavailableError) as exc:
                logger.warning(
                    "Provider '%s' failed for '%s': %s. Trying next provider...",
                    current_provider.provider_id, clean_word, exc
                )
                last_exception = exc
                continue

        # If all providers exhausted and word was not found
        if record_history and self.history:
            self.history.add(
                word=clean_word,
                provider_id=self.provider.provider_id,
                result_found=False,
            )

        if isinstance(last_exception, (TimeoutError, NetworkError, ProviderUnavailableError)):\
            raise last_exception

        raise WordNotFoundError(word=clean_word)
