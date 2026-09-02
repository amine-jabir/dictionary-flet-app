"""
Unit tests for SenseRanker definition and sense ranking layer.
Verifies learner-relevant prioritization of common everyday meanings (e.g. 'duck' as bird).
"""

import unittest

from dict_core.models.word import Definition, Meaning, Phonetic, WordEntry
from dict_core.ranking.sense_ranker import SenseRanker


class TestSenseRanker(unittest.TestCase):
    """Tests the non-destructive sense and definition ranking algorithm."""

    def test_duck_bird_meaning_prioritized_over_textile_and_cricket(self) -> None:
        """Verifies that the aquatic bird sense of 'duck' is ranked ahead of fabric and cricket."""
        fabric_def = Definition(definition="A heavy, plain-woven cotton fabric.")
        bird_def = Definition(
            definition="An aquatic bird of the family Anatidae, having a flat bill and webbed feet.",
            example="We fed the ducks bread crumbs in the park.",
            synonyms=["waterfowl"],
        )
        cricket_def = Definition(
            definition="(cricket) A batsman's score of zero after getting out.",
            example="He was dismissed for a duck.",
        )
        archaic_def = Definition(
            definition="(archaic) A term of endearment for a pet or person."
        )

        unranked_meaning = Meaning(
            part_of_speech="noun",
            definitions=[fabric_def, archaic_def, cricket_def, bird_def],
        )

        entry = WordEntry(
            word="duck",
            phonetics=[Phonetic(text="/dʌk/")],
            meanings=[unranked_meaning],
            provider="free_dict_api",
        )

        ranked_entry = SenseRanker.rank_word_entry(entry)

        # 1. Total definitions preserved (Zero data loss)
        self.assertEqual(len(ranked_entry.meanings[0].definitions), 4)

        # 2. Bird definition is ranked #1 at the top
        ranked_defs = ranked_entry.meanings[0].definitions
        self.assertEqual(ranked_defs[0].definition, bird_def.definition)
        self.assertIn("aquatic bird", ranked_defs[0].definition)

        # 3. Archaic and cricket definitions are ranked at the bottom
        last_def_texts = [ranked_defs[2].definition, ranked_defs[3].definition]
        self.assertTrue(any("archaic" in t for t in last_def_texts))
        self.assertTrue(any("cricket" in t for t in last_def_texts))

    def test_part_of_speech_priority_ordering(self) -> None:
        """Verifies that primary parts of speech (noun/verb) are prioritized ahead of rare interjections."""
        interjection_meaning = Meaning(
            part_of_speech="interjection",
            definitions=[Definition(definition="An exclamation of surprise.")],
        )
        noun_meaning = Meaning(
            part_of_speech="noun",
            definitions=[Definition(definition="A common physical object.", example="A wooden set.")],
        )
        verb_meaning = Meaning(
            part_of_speech="verb",
            definitions=[Definition(definition="To place in a particular spot.", example="Set the cup down.")],
        )

        entry = WordEntry(
            word="set",
            meanings=[interjection_meaning, verb_meaning, noun_meaning],
            provider="wiktionary_rest",
        )

        ranked_entry = SenseRanker.rank_word_entry(entry)
        pos_order = [m.part_of_speech for m in ranked_entry.meanings]

        # Noun and Verb come before interjection
        self.assertEqual(pos_order[0], "noun")
        self.assertEqual(pos_order[1], "verb")
        self.assertEqual(pos_order[2], "interjection")

    def test_ranking_is_non_destructive(self) -> None:
        """Verifies that all phonetics, metadata, and fields are preserved."""
        entry = WordEntry(
            word="lucid",
            phonetics=[Phonetic(text="/ˈluː.sɪd/")],
            meanings=[
                Meaning(
                    part_of_speech="adjective",
                    definitions=[
                        Definition(definition="Expressed clearly; easy to understand.", example="A lucid explanation."),
                        Definition(definition="(rare) Shining; bright."),
                    ],
                    synonyms=["clear", "intelligible"],
                    antonyms=["vague", "opaque"],
                )
            ],
            provider="free_dict_api",
        )

        ranked_entry = SenseRanker.rank_word_entry(entry)

        self.assertEqual(ranked_entry.word, "lucid")
        self.assertEqual(len(ranked_entry.phonetics), 1)
        self.assertEqual(ranked_entry.phonetics[0].text, "/ˈluː.sɪd/")
        self.assertEqual(tuple(ranked_entry.meanings[0].synonyms), ("clear", "intelligible"))
        self.assertEqual(tuple(ranked_entry.meanings[0].antonyms), ("vague", "opaque"))
        self.assertEqual(ranked_entry.metadata.get("ranked"), True)


if __name__ == "__main__":
    unittest.main()
