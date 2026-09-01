"""
Resilient HTTP Client with automatic retries, backoff, timeout enforcement,
and standardized exception mapping for dict_core.
"""

from datetime import datetime, timezone
import email.utils
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import requests

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import (
    InvalidResponseError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    WordNotFoundError,
)
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.http_client")


class ResilientHttpClient:
    """
    Production-grade HTTP client engineered for network resilience.
    
    Features:
    - Connection pooling and keep-alive
    - Configurable exponential backoff with retry budget
    - Explicit timeout enforcement (interactive vs background policies)
    - HTTP 429 'Retry-After' compliance
    - Standardized exception mapping to dict_core domain exceptions
    """

    RETRYABLE_STATUS_CODES: Tuple[int, ...] = (429, 500, 502, 503, 504)

    def __init__(
        self,
        timeout: float = DEFAULT_CONFIG.HTTP_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_CONFIG.HTTP_MAX_RETRIES,
        backoff_factor: float = DEFAULT_CONFIG.HTTP_BACKOFF_FACTOR,
        user_agent: str = DEFAULT_CONFIG.HTTP_USER_AGENT,
        sleeper: Callable[[float], None] = time.sleep,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.backoff_factor = float(backoff_factor)
        self.user_agent = user_agent
        self.sleeper = sleeper
        
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent, "Accept": "application/json"})

    def __enter__(self) -> "ResilientHttpClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Closes the underlying HTTP session."""
        if self._session:
            self._session.close()

    def _parse_retry_after(self, retry_after_header: Optional[str], default_backoff: float) -> float:
        """Parses the HTTP Retry-After header (seconds or HTTP date)."""
        if not retry_after_header:
            return default_backoff
        
        header_str = retry_after_header.strip()
        # Case 1: Integer / float seconds
        try:
            val = float(header_str)
            return max(0.1, min(val, 60.0))  # Cap at 60s max
        except ValueError:
            pass

        # Case 2: HTTP date (RFC 2822)
        try:
            parsed_date = email.utils.parsedate_to_datetime(header_str)
            now = datetime.now(timezone.utc)
            delta = (parsed_date - now).total_seconds()
            return max(0.1, min(delta, 60.0))
        except Exception:
            return default_backoff

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        target_word: Optional[str] = None,
    ) -> requests.Response:
        """
        Executes a GET request with retry logic and error mapping.
        
        Args:
            url: Target URL.
            params: Optional query parameters.
            headers: Additional request headers.
            timeout: Specific timeout override in seconds.
            max_retries: Specific max retries override (e.g. 0 for interactive lookup).
            backoff_factor: Specific backoff multiplier override in seconds.
            target_word: Optional word context to enrich WordNotFoundError if 404 is encountered.
            
        Returns:
            requests.Response: Successful response object.
            
        Raises:
            WordNotFoundError: If HTTP 404 is returned.
            RateLimitError: If HTTP 429 is encountered and retries are exhausted.
            TimeoutError: If connection or read exceeds timeout limit.
            NetworkError: If network connection fails.
        """
        effective_timeout = float(timeout) if timeout is not None else self.timeout
        effective_max_retries = max(0, int(max_retries)) if max_retries is not None else self.max_retries
        effective_backoff = float(backoff_factor) if backoff_factor is not None else self.backoff_factor
        merged_headers = dict(headers or {})
        
        attempt = 0
        while True:
            attempt += 1
            try:
                logger.debug(
                    "Executing GET request: %s (attempt %d/%d, timeout=%.1fs)",
                    url, attempt, effective_max_retries + 1, effective_timeout
                )
                response = self._session.get(
                    url=url,
                    params=params,
                    headers=merged_headers,
                    timeout=effective_timeout,
                )

                # HTTP 404: Word Not Found (Never retry 404)
                if response.status_code == 404:
                    word_label = target_word or "requested term"
                    raise WordNotFoundError(
                        word=word_label,
                        message=f"Dictionary entry for '{word_label}' was not found (HTTP 404).",
                        details={"url": url, "status_code": 404},
                    )

                # Check if status code warrants a retry
                if response.status_code in self.RETRYABLE_STATUS_CODES and attempt <= effective_max_retries:
                    if response.status_code == 429:
                        delay = self._parse_retry_after(response.headers.get("Retry-After"), effective_backoff)
                        logger.warning("Rate limit hit (HTTP 429). Backing off for %.2fs...", delay)
                    else:
                        delay = effective_backoff * (2 ** (attempt - 1))
                        logger.warning(
                            "Server returned HTTP %d. Retrying in %.2fs (attempt %d/%d)...",
                            response.status_code, delay, attempt, effective_max_retries
                        )
                    self.sleeper(delay)
                    continue

                # If status code is 429 and retries exhausted
                if response.status_code == 429:
                    raise RateLimitError(
                        message="API rate limit exceeded and maximum retry attempts exhausted.",
                        retry_after=self._parse_retry_after(response.headers.get("Retry-After"), effective_backoff),
                        details={"url": url, "status_code": 429},
                    )

                # Raise for 4xx (non-404) or 5xx that exhausted retries
                if 400 <= response.status_code < 500:
                    raise NetworkError(
                        f"Client error HTTP {response.status_code} querying {url}",
                        details={"status_code": response.status_code, "response_text": response.text[:200]},
                    )
                elif response.status_code >= 500:
                    raise NetworkError(
                        f"Server error HTTP {response.status_code} querying {url}",
                        details={"status_code": response.status_code, "response_text": response.text[:200]},
                    )

                return response

            except requests.exceptions.Timeout as exc:
                if attempt <= effective_max_retries:
                    delay = effective_backoff * (2 ** (attempt - 1))
                    logger.warning("Request timed out (%s). Retrying in %.2fs...", exc, delay)
                    self.sleeper(delay)
                    continue
                raise TimeoutError(
                    f"Request timed out after {attempt} attempts: {url}",
                    details={"url": url, "timeout": effective_timeout, "attempts": attempt},
                ) from exc

            except requests.exceptions.ConnectionError as exc:
                if attempt <= effective_max_retries:
                    delay = effective_backoff * (2 ** (attempt - 1))
                    logger.warning("Connection failed (%s). Retrying in %.2fs...", exc, delay)
                    self.sleeper(delay)
                    continue
                raise NetworkError(
                    f"Network connection failed after {attempt} attempts: {url}",
                    details={"url": url, "error": str(exc), "attempts": attempt},
                ) from exc

            except (WordNotFoundError, RateLimitError, TimeoutError, NetworkError):
                raise

            except Exception as exc:
                raise NetworkError(
                    f"Unexpected communication failure while requesting {url}: {exc}",
                    details={"url": url, "error": str(exc)},
                ) from exc

    def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        target_word: Optional[str] = None,
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Executes GET request and parses the response as JSON.
        
        Raises:
            InvalidResponseError: If the response is not valid JSON or is empty.
        """
        response = self.get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            target_word=target_word,
        )
        
        content_text = response.text.strip() if response.text else ""
        if not content_text:
            raise InvalidResponseError(
                f"Empty response body received from {url}",
                details={"url": url, "status_code": response.status_code},
            )

        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise InvalidResponseError(
                f"Malformed JSON returned from {url}: {exc}",
                details={"url": url, "snippet": content_text[:200]},
            ) from exc
