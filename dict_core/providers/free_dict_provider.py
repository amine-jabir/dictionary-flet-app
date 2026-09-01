"""
Free Dictionary API provider implementation.
Connects to api.dictionaryapi.dev and normalizes payloads to WordEntry models.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import InvalidResponseError, WordNotFoundError
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.utils.http_client import ResilientHttpClient
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.providers.free_dict")


class FreeDictProvider(BaseDictionaryProvider):
    """
    Dictionary data provider integrating with Free Dictionary API (api.dictionaryapi.dev).
    """

    BASE_URL: str = "https://api.dictionaryapi.dev/api/v2/entries/en"

    def __init__(
        self,
        client: Optional[ResilientHttpClient] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.client = client or ResilientHttpClient()
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    @property
    def provider_id(self) -> str:
        return "free_dict_api"

    @property
    def display_name(self) -> str:
        return "Free Dictionary API"

    @property
    def supports_audio(self) -> bool:
        return True

    def is_available(self) -> bool:
        """Indicates if the client is initialized and configured."""
        return self.client is not None

    def _detect_accent(self, url: str) -> str:
        """Infers audio pronunciation accent (us, uk, au, ca) from the audio filename/URL."""
        if not url:
            return ""
        lower = url.lower()
        if re.search(r"[-_/](us|en-us|usa)[-_\.]", lower):
            return "us"
        if re.search(r"[-_/](uk|en-uk|gb|en-gb|british)[-_\.]", lower):
            return "uk"
        if re.search(r"[-_/](au|en-au|australian)[-_\.]", lower):
            return "au"
        if re.search(r"[-_/](ca|en-ca|canadian)[-_\.]", lower):
            return "ca"
        if re.search(r"[-_/](nz|en-nz)[-_\.]", lower):
            return "nz"
        return "generic"

    def lookup(
        self,
        word: str,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> WordEntry:
        """
        Queries Free Dictionary API and normalizes the response to a WordEntry.
        
        Args:
            word: Target term to look up.
            timeout: Optional per-request timeout in seconds.
            max_retries: Optional per-request retry count override.
            
        Returns:
            WordEntry: Normalized dictionary entry.
            
        Raises:
            ValidationError: If query input is empty or invalid.
            WordNotFoundError: If word is not found in dictionary.
            TimeoutError: If request times out.
            NetworkError: If network connection fails.
            InvalidResponseError: If response format is malformed or unexpected.
        """
        clean_word = self.validate_query(word)
        encoded_word = urllib.parse.quote(clean_word)
        url = f"{self.base_url}/{encoded_word}"

        logger.debug("Querying FreeDictProvider: %s", url)
        data = self.client.get_json(
            url,
            timeout=timeout,
            max_retries=max_retries,
            target_word=clean_word,
        )

        if not isinstance(data, list):
            # Check if API returned a 'No Definitions Found' dictionary object with 200 OK
            if isinstance(data, dict) and (
                data.get("title") == "No Definitions Found" or "message" in data
            ):
                raise WordNotFoundError(
                    word=clean_word,
                    message=f"Word '{clean_word}' was not found in Free Dictionary API.",
                    details={"response": data},
                )
            raise InvalidResponseError(
                f"Expected list response from Free Dictionary API for '{clean_word}', got {type(data).__name__}",
                details={"data": data},
            )

        if not data:
            raise WordNotFoundError(
                word=clean_word,
                message=f"No definitions returned for '{clean_word}'.",
            )

        return self._normalize_response(clean_word, data)

    def _normalize_response(self, query_word: str, entries_data: List[Dict[str, Any]]) -> WordEntry:
        """Normalizes multiple API entry dictionaries into a unified WordEntry model."""
        phonetics_list: List[Phonetic] = []
        seen_phonetics = set()
        seen_audio_urls = set()

        meanings_map: Dict[str, List[Definition]] = {}
        meanings_synonyms: Dict[str, List[str]] = {}
        meanings_antonyms: Dict[str, List[str]] = {}
        source_urls_set = set()

        matched_word = query_word

        for entry in entries_data:
            if not isinstance(entry, dict):
                continue

            entry_word = entry.get("word", "")
            if entry_word and matched_word == query_word:
                matched_word = str(entry_word).strip()

            # 1. Parse top-level source URLs
            for src in entry.get("sourceUrls", []):
                if isinstance(src, str) and src.strip():
                    source_urls_set.add(src.strip())

            # 2. Parse Phonetics & Audio
            raw_phonetics = entry.get("phonetics", [])
            if isinstance(raw_phonetics, list):
                for p in raw_phonetics:
                    if not isinstance(p, dict):
                        continue

                    ipa_text = str(p.get("text", "") or "").strip()
                    audio_url = str(p.get("audio", "") or "").strip()
                    source_url = str(p.get("sourceUrl", "") or "").strip()
                    
                    license_info = p.get("license", {})
                    license_url = str(license_info.get("url", "") or "").strip() if isinstance(license_info, dict) else ""

                    audio_sources: List[AudioSource] = []
                    if audio_url and audio_url not in seen_audio_urls:
                        seen_audio_urls.add(audio_url)
                        accent = self._detect_accent(audio_url)
                        audio_sources.append(
                            AudioSource(
                                url=audio_url,
                                accent=accent,
                                source_text=source_url,
                                license_url=license_url,
                            )
                        )

                    if ipa_text or audio_sources:
                        key = (ipa_text, tuple(a.url for a in audio_sources))
                        if key not in seen_phonetics:
                            seen_phonetics.add(key)
                            phonetics_list.append(Phonetic(text=ipa_text, audio=audio_sources))

            # Check standalone top-level 'phonetic' string field if phonetics list lacks text
            standalone_phonetic = str(entry.get("phonetic", "") or "").strip()
            if standalone_phonetic and not any(p.text == standalone_phonetic for p in phonetics_list):
                phonetics_list.insert(0, Phonetic(text=standalone_phonetic))

            # 3. Parse Meanings & Definitions grouped by Part of Speech
            raw_meanings = entry.get("meanings", [])
            if isinstance(raw_meanings, list):
                for m in raw_meanings:
                    if not isinstance(m, dict):
                        continue

                    pos = str(m.get("partOfSpeech", "unknown") or "unknown").strip().lower()
                    if pos not in meanings_map:
                        meanings_map[pos] = []
                        meanings_synonyms[pos] = []
                        meanings_antonyms[pos] = []

                    # Meaning-level synonyms/antonyms
                    for s in m.get("synonyms", []):
                        if isinstance(s, str) and s.strip() and s.strip() not in meanings_synonyms[pos]:
                            meanings_synonyms[pos].append(s.strip())
                    for a in m.get("antonyms", []):
                        if isinstance(a, str) and a.strip() and a.strip() not in meanings_antonyms[pos]:
                            meanings_antonyms[pos].append(a.strip())

                    # Definitions
                    for d in m.get("definitions", []):
                        if not isinstance(d, dict):
                            continue

                        def_text = str(d.get("definition", "") or "").strip()
                        if not def_text:
                            continue

                        example = str(d.get("example", "") or "").strip()
                        def_synonyms = [
                            str(s).strip()
                            for s in d.get("synonyms", [])
                            if isinstance(s, str) and str(s).strip()
                        ]
                        def_antonyms = [
                            str(a).strip()
                            for a in d.get("antonyms", [])
                            if isinstance(a, str) and str(a).strip()
                        ]

                        meanings_map[pos].append(
                            Definition(
                                definition=def_text,
                                example=example,
                                synonyms=def_synonyms,
                                antonyms=def_antonyms,
                            )
                        )

        # Assemble Meanings
        meanings: List[Meaning] = []
        for pos, defs in meanings_map.items():
            if defs:
                meanings.append(
                    Meaning(
                        part_of_speech=pos,
                        definitions=defs,
                        synonyms=meanings_synonyms.get(pos, []),
                        antonyms=meanings_antonyms.get(pos, []),
                    )
                )

        if not meanings:
            raise WordNotFoundError(
                word=query_word,
                message=f"No valid definitions could be parsed for '{query_word}'.",
            )

        # Default source url if none provided
        if not source_urls_set:
            source_urls_set.add(f"https://en.wiktionary.org/wiki/{urllib.parse.quote(matched_word)}")

        return WordEntry(
            word=matched_word,
            phonetics=phonetics_list,
            meanings=meanings,
            source_urls=sorted(list(source_urls_set)),
            provider=self.provider_id,
            queried_at=datetime.now(timezone.utc).isoformat(),
        )
