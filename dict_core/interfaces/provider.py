"""
Base provider interface for dictionary data sources.
Defines the contract that any online or offline dictionary provider must fulfill.
"""

from abc import ABC, abstractmethod
from typing import Optional

from dict_core.exceptions import ValidationError
from dict_core.models.word import WordEntry


class BaseDictionaryProvider(ABC):
    """
    Abstract interface for dictionary data providers.
    
    Implementations may query online REST APIs (e.g., FreeDictionaryAPI, Wiktionary,
    Merriam-Webster) or local offline databases (e.g., SQLite, WordNet).
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Machine-friendly identifier (e.g., 'free_dict_api', 'wiktionary_rest')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name (e.g., 'Free Dictionary API', 'Wiktionary')."""
        pass

    @property
    def supports_audio(self) -> bool:
        """Indicates whether this provider natively supplies pronunciation audio assets."""
        return True

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if the provider is properly configured and reachable.
        For API providers, checks connectivity/API keys.
        For offline providers, checks database file existence.
        """
        pass

    @abstractmethod
    def lookup(
        self,
        word: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> WordEntry:
        """
        Looks up a word and returns a normalized WordEntry domain model.
        
        Args:
            word: The word or term to look up.
            timeout: Optional specific request timeout in seconds.
            max_retries: Optional max retry count override.
            
        Returns:
            WordEntry: Normalized dictionary entry.
            
        Raises:
            ValidationError: If word is empty or invalid.
            WordNotFoundError: If the word is not in the dictionary.
            NetworkError: If a network/connection error occurs.
            TimeoutError: If the request times out.
            RateLimitError: If API rate limit is exceeded.
            InvalidResponseError: If the response is malformed.
            DictionaryError: For other unexpected provider errors.
        """
        pass

    def validate_query(self, word: str) -> str:
        """
        Sanitizes and validates a lookup term.
        
        Args:
            word: Input word.
            
        Returns:
            Cleaned and normalized lowercase word string.
            
        Raises:
            ValidationError: If word is empty or contains only whitespace/control characters.
        """
        if not word or not isinstance(word, str):
            raise ValidationError("Search query cannot be empty or non-string.")
        
        cleaned = word.strip().lower()
        if not cleaned:
            raise ValidationError("Search query cannot be blank.")
        
        # Guard against absurdly long strings / potential abuse
        if len(cleaned) > 100:
            raise ValidationError("Search query exceeds maximum allowed length (100 characters).")
            
        return cleaned
