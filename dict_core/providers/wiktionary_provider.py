"""
Wiktionary REST API provider implementation.
Connects to en.wiktionary.org/api/rest_v1/page/definition and normalizes responses to WordEntry models.
"""

from datetime import datetime, timezone
import html
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import InvalidResponseError, WordNotFoundError
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import Definition, Meaning, Phonetic, WordEntry
from dict_core.utils.http_client import ResilientHttpClient
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.providers.wiktionary")


class WiktionaryProvider(BaseDictionaryProvider):
    """
    Dictionary data provider integrating with the official Wiktionary REST API.
    """

    BASE_URL: str = "https://en.wiktionary.org/api/rest_v1/page/definition"

    def __init__(
        self,
        client: Optional[ResilientHttpClient] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.client = client or ResilientHttpClient()
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    @property
    def provider_id(self) -> str:
        return "wiktionary_rest"

    @property
    def display_name(self) -> str:
        return "Wiktionary REST API"

    @property
    def supports_audio(self) -> bool:
        return False

    def is_available(self) -> bool:
        """Indicates if the client is initialized and configured."""
        return self.client is not None

    def _clean_html(self, raw_html: str) -> str:
        """Strips HTML tags, style/script blocks, CSS classes, unescapes entities, and collapses whitespace."""
        if not raw_html or not isinstance(raw_html, str):
            return ""
        # 1. Remove style and script blocks entirely (including their contents)
        text = re.sub(r'<(style|script)[^>]*>.*?</>', '', raw_html, flags=re.IGNORECASE | re.DOTALL)
        # 2. Replace block tags and line breaks with space
        text = re.sub(r'<(br|p|/p|div|/div|li|/li|dd|/dd|dt|/dt)[^>]*>', ' ', text, flags=re.IGNORECASE)
        # 3. Strip any remaining inline tags
        text = re.sub(r'<[^>]+>', '', text)
        # 4. Strip any residual CSS selectors, rules, or MediaWiki stylesheet artifacts
        text = re.sub(r'(\.|)?mw-parser-output[^{]*(\{[^}]*\}?)?', '', text)
        text = re.sub(r'\{[^}]*\}', '', text)
        # 5. Unescape HTML entities (&quot;, &amp;, etc.)
        unescaped = html.unescape(text)
        # 6. Normalize multiple whitespace and newlines
        return re.sub(r'\s+', ' ', unescaped).strip()

    def lookup(
        self,
        word: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> WordEntry:
        """
        Queries Wiktionary REST API and normalizes the response to a WordEntry.
        
        Args:
            word: Target term to look up.
            timeout: Optional per-request timeout in seconds.
            max_retries: Optional per-request retry count override.
            
        Returns:
            WordEntry: Normalized dictionary entry.
            
        Raises:
            ValidationError: If query input is empty or invalid.
            WordNotFoundError: If word is not found in Wiktionary.
            TimeoutError: If request times out.
            NetworkError: If network connection fails.
            InvalidResponseError: If response format is malformed or unexpected.
        """
        clean_word = self.validate_query(word)
        encoded_word = urllib.parse.quote(clean_word)
        url = f"{self.base_url}/{encoded_word}"

        logger.debug("Querying WiktionaryProvider: %s", url)
        data = self.client.get_json(
            url,
            timeout=timeout,
            max_retries=max_retries,
            target_word=clean_word,
        )

        if not isinstance(data, dict):
            raise InvalidResponseError(
                f"Expected dictionary response from Wiktionary REST API for '{clean_word}', got {type(data).__name__}",
                details={"data": data},
            )

        if not data:
            raise WordNotFoundError(
                word=clean_word,
                message=f"No entries returned for '{clean_word}' from Wiktionary.",
            )

        return self._normalize_response(clean_word, data)

    def _normalize_response(self, query_word: str, response_data: Dict[str, Any]) -> WordEntry:
        """Normalizes language-keyed Wiktionary REST response into a WordEntry model."""
        # Check for English section ('en') primarily
        sections = response_data.get("en", [])
        if not sections and isinstance(response_data, dict):
            # If 'en' is missing, check if there are other languages available
            for lang_code, lang_sections in response_data.items():
                if isinstance(lang_sections, list) and lang_sections:
                    sections = lang_sections
                    break

        if not isinstance(sections, list) or not sections:
            raise WordNotFoundError(
                word=query_word,
                message=f"No definition sections found for '{query_word}' in Wiktionary.",
            )

        meanings_map: Dict[str, List[Definition]] = {}

        for section in sections:
            if not isinstance(section, dict):
                continue

            pos = str(section.get("partOfSpeech", "unknown") or "unknown").strip().lower()
            if pos not in meanings_map:
                meanings_map[pos] = []

            raw_definitions = section.get("definitions", [])
            if not isinstance(raw_definitions, list):
                continue

            for item in raw_definitions:
                if not isinstance(item, dict):
                    continue

                # 1. Extract definition text (prefer parsedDefinitions if available, else definition)
                def_text = ""
                parsed_defs = item.get("parsedDefinitions", [])
                if isinstance(parsed_defs, list) and parsed_defs:
                    for pd in parsed_defs:
                        if isinstance(pd, dict) and pd.get("definition"):
                            def_text = self._clean_html(pd.get("definition", ""))
                            break

                if not def_text:
                    def_text = self._clean_html(item.get("definition", ""))

                if not def_text:
                    continue

                # 2. Extract examples
                raw_examples = item.get("examples", [])
                examples: List[str] = []
                if isinstance(raw_examples, list):
                    for ex in raw_examples:
                        if isinstance(ex, str):
                            clean_ex = self._clean_html(ex)
                            if clean_ex and clean_ex not in examples:
                                examples.append(clean_ex)

                primary_example = examples[0] if examples else ""

                meanings_map[pos].append(
                    Definition(
                        definition=def_text,
                        example=primary_example,
                        examples=examples,
                    )
                )

        meanings: List[Meaning] = []
        for pos, defs in meanings_map.items():
            if defs:
                meanings.append(Meaning(part_of_speech=pos, definitions=defs))

        if not meanings:
            raise WordNotFoundError(
                word=query_word,
                message=f"No valid definitions could be parsed for '{query_word}' from Wiktionary.",
            )

        source_url = f"https://en.wiktionary.org/wiki/{urllib.parse.quote(query_word)}"

        return WordEntry(
            word=query_word,
            phonetics=[],
            meanings=meanings,
            source_urls=[source_url],
            provider=self.provider_id,
            queried_at=datetime.now(timezone.utc).isoformat(),
        )
