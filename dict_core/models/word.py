"""
Domain models for dictionary data representations.
Provides immutable, typed data structures for words, definitions, phonetics, and audio.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AudioSource:
    """Represents a pronunciation audio stream or file."""
    url: str
    accent: str = ""  # e.g., "us", "uk", "au", "generic"
    source_text: str = ""
    license_url: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", str(self.url).strip())
        object.__setattr__(self, "accent", str(self.accent or "").strip().lower())
        object.__setattr__(self, "source_text", str(self.source_text or "").strip())
        object.__setattr__(self, "license_url", str(self.license_url or "").strip())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AudioSource:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for AudioSource, got {type(data).__name__}")
        return cls(
            url=str(data.get("url", "") or ""),
            accent=str(data.get("accent", "") or ""),
            source_text=str(data.get("source_text", "") or ""),
            license_url=str(data.get("license_url", "") or ""),
        )


@dataclass(frozen=True)
class Phonetic:
    """Represents phonetic transcription (IPA) and associated audio pronunciations."""
    text: str = ""
    audio: List[AudioSource] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", str(self.text or "").strip())
        # Ensure audio items are AudioSource instances
        audio_sources: List[AudioSource] = []
        for item in self.audio or []:
            if isinstance(item, AudioSource):
                audio_sources.append(item)
            elif isinstance(item, dict):
                audio_sources.append(AudioSource.from_dict(item))
            elif isinstance(item, str) and item.strip():
                audio_sources.append(AudioSource(url=item.strip()))
        object.__setattr__(self, "audio", tuple(audio_sources))

    @property
    def primary_audio_url(self) -> Optional[str]:
        """Returns the first non-empty audio URL if available."""
        for src in self.audio:
            if src.url:
                return src.url
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "audio": [src.to_dict() for src in self.audio],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Phonetic:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for Phonetic, got {type(data).__name__}")
        raw_audio = data.get("audio", [])
        if isinstance(raw_audio, (list, tuple)):
            audio_list = [
                AudioSource.from_dict(a) if isinstance(a, dict) else a
                for a in raw_audio
                if a
            ]
        elif isinstance(raw_audio, str) and raw_audio.strip():
            audio_list = [AudioSource(url=raw_audio.strip())]
        else:
            audio_list = []

        return cls(
            text=str(data.get("text", "") or ""),
            audio=audio_list,
        )


@dataclass(frozen=True)
class Definition:
    """Represents a specific definition, example usages, and synonyms/antonyms."""
    definition: str
    example: str = ""
    examples: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition", str(self.definition or "").strip())
        primary_example = str(self.example or "").strip()
        object.__setattr__(self, "example", primary_example)

        # Consolidate examples list
        raw_examples = list(self.examples or [])
        if primary_example and primary_example not in raw_examples:
            raw_examples.insert(0, primary_example)
        cleaned_examples = tuple(str(e).strip() for e in raw_examples if str(e).strip())
        object.__setattr__(self, "examples", cleaned_examples)

        # Clean synonyms and antonyms
        cleaned_synonyms = tuple(str(s).strip() for s in (self.synonyms or []) if str(s).strip())
        cleaned_antonyms = tuple(str(a).strip() for a in (self.antonyms or []) if str(a).strip())
        object.__setattr__(self, "synonyms", cleaned_synonyms)
        object.__setattr__(self, "antonyms", cleaned_antonyms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "definition": self.definition,
            "example": self.example,
            "examples": list(self.examples),
            "synonyms": list(self.synonyms),
            "antonyms": list(self.antonyms),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Definition:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for Definition, got {type(data).__name__}")
        return cls(
            definition=str(data.get("definition", "") or ""),
            example=str(data.get("example", "") or ""),
            examples=list(data.get("examples", []) or []),
            synonyms=list(data.get("synonyms", []) or []),
            antonyms=list(data.get("antonyms", []) or []),
        )


@dataclass(frozen=True)
class Meaning:
    """Represents a grouped part of speech (noun, verb, etc.) with definitions."""
    part_of_speech: str
    definitions: List[Definition] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "part_of_speech", str(self.part_of_speech or "").strip().lower())
        
        # Ensure definitions are Definition objects
        defs: List[Definition] = []
        for d in self.definitions or []:
            if isinstance(d, Definition):
                defs.append(d)
            elif isinstance(d, dict):
                defs.append(Definition.from_dict(d))
            elif isinstance(d, str) and d.strip():
                defs.append(Definition(definition=d.strip()))
        object.__setattr__(self, "definitions", tuple(defs))

        cleaned_synonyms = tuple(str(s).strip() for s in (self.synonyms or []) if str(s).strip())
        cleaned_antonyms = tuple(str(a).strip() for a in (self.antonyms or []) if str(a).strip())
        object.__setattr__(self, "synonyms", cleaned_synonyms)
        object.__setattr__(self, "antonyms", cleaned_antonyms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_of_speech": self.part_of_speech,
            "definitions": [d.to_dict() for d in self.definitions],
            "synonyms": list(self.synonyms),
            "antonyms": list(self.antonyms),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Meaning:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for Meaning, got {type(data).__name__}")
        raw_defs = data.get("definitions", [])
        defs_list = [
            Definition.from_dict(d) if isinstance(d, dict) else d
            for d in (raw_defs if isinstance(raw_defs, (list, tuple)) else [])
            if d
        ]
        return cls(
            part_of_speech=str(data.get("part_of_speech", "") or ""),
            definitions=defs_list,
            synonyms=list(data.get("synonyms", []) or []),
            antonyms=list(data.get("antonyms", []) or []),
        )


@dataclass(frozen=True)
class WordEntry:
    """Root domain model representing a complete dictionary entry for a queried word."""
    word: str
    phonetics: List[Phonetic] = field(default_factory=list)
    meanings: List[Meaning] = field(default_factory=list)
    source_urls: List[str] = field(default_factory=list)
    provider: str = ""
    queried_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "word", str(self.word or "").strip())
        
        # Ensure phonetics are Phonetic instances
        phon_list: List[Phonetic] = []
        for p in self.phonetics or []:
            if isinstance(p, Phonetic):
                phon_list.append(p)
            elif isinstance(p, dict):
                phon_list.append(Phonetic.from_dict(p))
            elif isinstance(p, str) and p.strip():
                phon_list.append(Phonetic(text=p.strip()))
        object.__setattr__(self, "phonetics", tuple(phon_list))

        # Ensure meanings are Meaning instances
        mean_list: List[Meaning] = []
        for m in self.meanings or []:
            if isinstance(m, Meaning):
                mean_list.append(m)
            elif isinstance(m, dict):
                mean_list.append(Meaning.from_dict(m))
        object.__setattr__(self, "meanings", tuple(mean_list))

        cleaned_sources = tuple(str(u).strip() for u in (self.source_urls or []) if str(u).strip())
        object.__setattr__(self, "source_urls", cleaned_sources)
        object.__setattr__(self, "provider", str(self.provider or "").strip())
        object.__setattr__(self, "queried_at", str(self.queried_at or datetime.now(timezone.utc).isoformat()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def primary_phonetic(self) -> str:
        """Returns the first non-empty IPA phonetic transcription."""
        for p in self.phonetics:
            if p.text:
                return p.text
        return ""

    @property
    def primary_audio_url(self) -> Optional[str]:
        """Returns the first non-empty audio pronunciation URL available from phonetics."""
        for p in self.phonetics:
            url = p.primary_audio_url
            if url:
                return url
        return None

    @property
    def all_audio_sources(self) -> List[AudioSource]:
        """Returns a flat list of all audio sources across all phonetics."""
        sources: List[AudioSource] = []
        for p in self.phonetics:
            sources.extend(p.audio)
        return sources

    @property
    def parts_of_speech(self) -> List[str]:
        """Returns a deduplicated list of parts of speech present in this entry."""
        seen = set()
        result = []
        for m in self.meanings:
            pos = m.part_of_speech
            if pos and pos not in seen:
                seen.add(pos)
                result.append(pos)
        return result

    @property
    def total_definitions_count(self) -> int:
        """Returns total count of definitions across all meanings."""
        return sum(len(m.definitions) for m in self.meanings)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the WordEntry to a standard Python dictionary."""
        return {
            "word": self.word,
            "phonetics": [p.to_dict() for p in self.phonetics],
            "meanings": [m.to_dict() for m in self.meanings],
            "source_urls": list(self.source_urls),
            "provider": self.provider,
            "queried_at": self.queried_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WordEntry:
        """Deserializes a Python dictionary into a WordEntry instance."""
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for WordEntry, got {type(data).__name__}")
        
        raw_phonetics = data.get("phonetics", [])
        phonetics = [
            Phonetic.from_dict(p) if isinstance(p, dict) else p
            for p in (raw_phonetics if isinstance(raw_phonetics, (list, tuple)) else [])
            if p
        ]

        raw_meanings = data.get("meanings", [])
        meanings = [
            Meaning.from_dict(m) if isinstance(m, dict) else m
            for m in (raw_meanings if isinstance(raw_meanings, (list, tuple)) else [])
            if m
        ]

        raw_sources = data.get("source_urls", [])
        sources = list(raw_sources) if isinstance(raw_sources, (list, tuple)) else []

        return cls(
            word=str(data.get("word", "") or ""),
            phonetics=phonetics,
            meanings=meanings,
            source_urls=sources,
            provider=str(data.get("provider", "") or ""),
            queried_at=str(data.get("queried_at", "") or ""),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Converts the WordEntry to a JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> WordEntry:
        """Parses a JSON string into a WordEntry instance."""
        if not isinstance(json_str, str):
            raise TypeError(f"Expected str for from_json, got {type(json_str).__name__}")
        data = json.loads(json_str)
        return cls.from_dict(data)
