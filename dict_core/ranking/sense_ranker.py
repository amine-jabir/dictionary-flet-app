"""
Sense & Definition Ranking Engine for dict_core.
Prioritizes common everyday, learner-relevant word senses over specialized, archaic, or niche meanings.
Operates non-destructively on normalized WordEntry domain models.
"""

import re
from typing import List, Tuple
from dict_core.models.word import Definition, Meaning, WordEntry
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.ranking.sense_ranker")

# Regex patterns identifying archaic, obsolete, or historical registers
ARCHAIC_PATTERNS = re.compile(
    r"\b(?:archaic|obsolete|dated|historical|rare|obsolescent|dialectal|poetic)\b",
    re.IGNORECASE,
)

# Regex patterns identifying highly specialized, niche, or technical jargon
NICHE_DOMAIN_PATTERNS = re.compile(
    r"\b(?:cricket|baseball|golf|fencing|chess|cards|heraldry|nautical|seamanship|"
    r"textile|textiles|weaving|typography|printing|mineralogy|metallurgy|"
    r"slang|cant|jargon|vulgar|derogatory|ecclesiastical|entomology)\b",
    re.IGNORECASE,
)

# Preferred Part of Speech priority weights
POS_PRIORITY = {
    "noun": 100,
    "verb": 95,
    "adjective": 90,
    "adverb": 85,
    "pronoun": 80,
    "preposition": 75,
    "conjunction": 70,
    "interjection": 65,
    "unknown": 50,
}


class SenseRanker:
    """
    Ranks meanings and definitions within a WordEntry to present the most common
    modern everyday senses first while preserving all specialized definitions.
    """

    @classmethod
    def score_definition(cls, defn: Definition, word: str = "", part_of_speech: str = "") -> float:
        """
        Calculates a relevance score for an individual definition.
        Higher scores indicate everyday learner relevance.
        """
        score = 100.0
        text = defn.definition.strip()
        text_lower = text.lower()

        # 1. Heavily penalize archaic or obsolete definitions
        if ARCHAIC_PATTERNS.search(text_lower):
            score -= 60.0

        # 2. Penalize specialized jargon or niche domain registers
        if NICHE_DOMAIN_PATTERNS.search(text_lower):
            score -= 40.0

        # 3. Bonus for definitions with validated real-world usage examples
        if defn.example and len(defn.example.strip()) > 0:
            score += 25.0

        # 4. Bonus for definitions with associated synonyms
        if defn.synonyms and len(defn.synonyms) > 0:
            score += 15.0

        # 5. Core prototypical lexical heuristics
        # Definitions starting with direct class words (e.g. "An aquatic bird...", "A person who...", "To move...")
        if re.match(r"^(?:an?|the|to|a\s+type\s+of|a\s+kind\s+of)\s+[a-z]+", text_lower):
            score += 10.0

        # Shorter, concise definitions are often clearer and more general
        if 20 <= len(text) <= 180:
            score += 5.0

        return score

    @classmethod
    def score_meaning(cls, meaning: Meaning, word: str = "") -> float:
        """
        Calculates a priority score for a Meaning group (part of speech).
        """
        pos = meaning.part_of_speech.strip().lower()
        base_pos_score = float(POS_PRIORITY.get(pos, POS_PRIORITY["unknown"]))

        # Aggregate top definition scores
        if meaning.definitions:
            def_scores = [cls.score_definition(d, word, pos) for d in meaning.definitions]
            top_def_score = max(def_scores) if def_scores else 0.0
            avg_def_score = sum(def_scores) / len(def_scores)
            return base_pos_score + (top_def_score * 0.7) + (avg_def_score * 0.3)

        return base_pos_score

    @classmethod
    def rank_word_entry(cls, entry: WordEntry) -> WordEntry:
        """
        Non-destructively reorders the meanings and definitions of a WordEntry.
        
        Args:
            entry: The original normalized WordEntry.
            
        Returns:
            WordEntry: A new WordEntry with ranked definitions and meanings.
        """
        if not entry.meanings:
            return entry

        ranked_meanings: List[Meaning] = []

        for m in entry.meanings:
            # Score and sort definitions within each meaning
            scored_defs: List[Tuple[float, Definition]] = [
                (cls.score_definition(d, entry.word, m.part_of_speech), d)
                for d in m.definitions
            ]
            # Stable sort descending by score
            scored_defs.sort(key=lambda item: item[0], reverse=True)
            sorted_definitions = [d for _, d in scored_defs]

            ranked_meanings.append(
                Meaning(
                    part_of_speech=m.part_of_speech,
                    definitions=sorted_definitions,
                    synonyms=m.synonyms,
                    antonyms=m.antonyms,
                )
            )

        # Score and sort meanings by aggregate relevance
        scored_meanings: List[Tuple[float, Meaning]] = [
            (cls.score_meaning(m, entry.word), m)
            for m in ranked_meanings
        ]
        scored_meanings.sort(key=lambda item: item[0], reverse=True)
        sorted_meanings = [m for _, m in scored_meanings]

        # Return a new WordEntry with ranked meanings and metadata flag
        updated_metadata = dict(entry.metadata)
        updated_metadata["ranked"] = True

        return WordEntry(
            word=entry.word,
            phonetics=entry.phonetics,
            meanings=sorted_meanings,
            provider=entry.provider,
            metadata=updated_metadata,
        )
