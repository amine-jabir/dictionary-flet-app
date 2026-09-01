"""
Domain and infrastructure exception hierarchy for dict_core.
"""

from typing import Any, Dict, Optional


class DictionaryError(Exception):
    """Base exception for all dictionary-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


class WordNotFoundError(DictionaryError):
    """Raised when the requested word is not found in the dictionary."""

    def __init__(self, word: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.word = word
        msg = message or f"Word '{word}' was not found in dictionary."
        super().__init__(msg, details)


class NetworkError(DictionaryError):
    """Raised when network connectivity fails (DNS failure, connection refused, connection reset)."""
    pass


class TimeoutError(NetworkError):
    """Raised when a network or I/O request exceeds its time limit."""
    pass


class RateLimitError(DictionaryError):
    """Raised when an API endpoint rate limit is exceeded (e.g. HTTP 429)."""

    def __init__(
        self,
        message: str = "API rate limit exceeded. Please wait before retrying.",
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, details)


class InvalidResponseError(DictionaryError):
    """Raised when an API returns malformed JSON or an unexpected payload structure."""
    pass


class ProviderUnavailableError(DictionaryError):
    """Raised when a dictionary provider service is offline, misconfigured, or unreachable."""
    pass


class ValidationError(DictionaryError):
    """Raised when query input validation fails (e.g., empty string, invalid characters)."""
    pass


class AuthenticationError(DictionaryError):
    """Raised when an API key or authentication token is missing or invalid."""
    pass


class AudioError(DictionaryError):
    """Raised when audio download, caching, or file validation fails."""
    pass


class AudioPlaybackError(AudioError):
    """Raised when the audio player engine fails during audio playback."""
    pass
