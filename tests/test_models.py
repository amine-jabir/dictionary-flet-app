"""
Unit tests for dict_core domain models (WordEntry, Meaning, Definition, Phonetic, AudioSource).
"""

from dataclasses import FrozenInstanceError
import json
import unittest

from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry


class TestDomainModels(unittest.TestCase):
    """Tests data validation, immutability, and serialization of domain models."""

    def test_audio_source_creation_and_cleaning(self) -> None:
        audio = AudioSource(
            url="  https://example.com/audio.mp3  ",
            accent=" US ",
            source_text=" Wikimedia ",
            license_url=" https://cc.org ",
        )
        self.assertEqual(audio.url, "https://example.com/audio.mp3")
        self.assertEqual(audio.accent, "us")
        self.assertEqual(audio.source_text, "Wikimedia")
        self.assertEqual(audio.license_url, "https://cc.org")
        
        # Test immutability
        with self.assertRaises(FrozenInstanceError):
            audio.url = "https://other.com"  # type: ignore

    def test_audio_source_from_dict_and_to_dict(self) -> None:
        data = {
            "url": "https://api.dictionary.dev/media/hello.mp3",
            "accent": "uk",
            "source_text": "BY-SA",
            "license_url": "https://license.org",
        }
        audio = AudioSource.from_dict(data)
        self.assertEqual(audio.url, "https://api.dictionary.dev/media/hello.mp3")
        self.assertEqual(audio.accent, "uk")
        self.assertEqual(audio.to_dict(), data)

    def test_audio_source_from_dict_malformed(self) -> None:
        with self.assertRaises(TypeError):
            AudioSource.from_dict("not a dict")  # type: ignore
        
        # Handle None/empty dictionary defensively
        audio = AudioSource.from_dict({})
        self.assertEqual(audio.url, "")
        self.assertEqual(audio.accent, "")

    def test_phonetic_creation_and_properties(self) -> None:
        audio1 = AudioSource(url="https://example.com/us.mp3", accent="us")
        audio2 = AudioSource(url="https://example.com/uk.mp3", accent="uk")
        phon = Phonetic(text="/həˈloʊ/", audio=[audio1, audio2])

        self.assertEqual(phon.text, "/həˈloʊ/")
        self.assertEqual(len(phon.audio), 2)
        self.assertEqual(phon.primary_audio_url, "https://example.com/us.mp3")

    def test_phonetic_empty_audio_returns_none(self) -> None:
        phon = Phonetic(text="/test/", audio=[])
        self.assertIsNone(phon.primary_audio_url)

    def test_phonetic_string_audio_coercion(self) -> None:
        # Handles case where audio was passed as a simple URL string
        phon = Phonetic(text="/test/", audio=["https://example.com/sound.mp3"])  # type: ignore
        self.assertEqual(len(phon.audio), 1)
        self.assertEqual(phon.audio[0].url, "https://example.com/sound.mp3")
        self.assertEqual(phon.primary_audio_url, "https://example.com/sound.mp3")

    def test_definition_and_examples(self) -> None:
        d = Definition(
            definition="A greeting.",
            example="Hello, how are you?",
            examples=["Hello world!", "Hello, how are you?"],
            synonyms=["hi", "greetings"],
            antonyms=["goodbye"],
        )
        self.assertEqual(d.definition, "A greeting.")
        self.assertEqual(d.example, "Hello, how are you?")
        self.assertIn("Hello world!", d.examples)
        self.assertIn("Hello, how are you?", d.examples)
        self.assertEqual(list(d.synonyms), ["hi", "greetings"])
        self.assertEqual(list(d.antonyms), ["goodbye"])

    def test_meaning_creation_and_sub_definitions(self) -> None:
        def1 = Definition(definition="An action of moving.", example="He made a move.")
        def2 = Definition(definition="A turn in a game.")
        meaning = Meaning(
            part_of_speech=" Noun ",
            definitions=[def1, def2],
            synonyms=["motion", "step"],
        )
        self.assertEqual(meaning.part_of_speech, "noun")
        self.assertEqual(len(meaning.definitions), 2)
        self.assertEqual(meaning.definitions[0].definition, "An action of moving.")
        self.assertEqual(list(meaning.synonyms), ["motion", "step"])

    def test_word_entry_full_lifecycle(self) -> None:
        entry = WordEntry(
            word="Serendipity",
            phonetics=[
                Phonetic(text="", audio=[AudioSource(url="")]),
                Phonetic(
                    text="/ˌsɛr.ənˈdɪp.ɪ.ti/",
                    audio=[AudioSource(url="https://audio.org/serendipity.mp3", accent="us")],
                ),
            ],
            meanings=[
                Meaning(
                    part_of_speech="noun",
                    definitions=[
                        Definition(
                            definition="The occurrence of events by chance in a happy way.",
                            example="Finding this book was pure serendipity.",
                        )
                    ],
                    synonyms=["chance", "fluke"],
                )
            ],
            source_urls=["https://en.wiktionary.org/wiki/serendipity"],
            provider="test_provider",
        )

        self.assertEqual(entry.word, "Serendipity")
        self.assertEqual(entry.primary_phonetic, "/ˌsɛr.ənˈdɪp.ɪ.ti/")
        self.assertEqual(entry.primary_audio_url, "https://audio.org/serendipity.mp3")
        self.assertEqual(entry.parts_of_speech, ["noun"])
        self.assertEqual(entry.total_definitions_count, 1)
        self.assertEqual(len(entry.all_audio_sources), 2)

    def test_word_entry_json_serialization_roundtrip(self) -> None:
        entry = WordEntry(
            word="Resilience",
            phonetics=[Phonetic(text="/rɪˈzɪl.jəns/", audio=[AudioSource(url="https://audio.org/res.mp3")])],
            meanings=[
                Meaning(
                    part_of_speech="noun",
                    definitions=[Definition(definition="The capacity to recover quickly from difficulties.")],
                )
            ],
            provider="free_dict_api",
            metadata={"cached": True},
        )

        json_str = entry.to_json(indent=2)
        reconstructed = WordEntry.from_json(json_str)

        self.assertEqual(entry.word, reconstructed.word)
        self.assertEqual(entry.primary_phonetic, reconstructed.primary_phonetic)
        self.assertEqual(entry.primary_audio_url, reconstructed.primary_audio_url)
        self.assertEqual(len(reconstructed.meanings), 1)
        self.assertEqual(reconstructed.meanings[0].definitions[0].definition, "The capacity to recover quickly from difficulties.")
        self.assertEqual(reconstructed.metadata, {"cached": True})

    def test_from_dict_edge_cases(self) -> None:
        sparse_data = {"word": "Minimal"}
        entry = WordEntry.from_dict(sparse_data)
        self.assertEqual(entry.word, "Minimal")
        self.assertEqual(entry.phonetics, ())
        self.assertEqual(entry.meanings, ())
        self.assertEqual(entry.primary_phonetic, "")
        self.assertIsNone(entry.primary_audio_url)
        self.assertEqual(entry.parts_of_speech, [])

        with self.assertRaises(TypeError):
            WordEntry.from_dict([1, 2, 3])  # type: ignore

        with self.assertRaises(TypeError):
            WordEntry.from_json(12345)  # type: ignore

    def test_unicode_and_special_characters(self) -> None:
        entry = WordEntry(
            word="résumé",
            phonetics=[Phonetic(text="/ˈrɛz.juː.meɪ/", audio=[AudioSource(url="https://audio.org/resume.mp3")])],
            meanings=[
                Meaning(
                    part_of_speech="noun",
                    definitions=[Definition(definition="A summary of one's education and work experience.", example="She sent her résumé.")],
                )
            ],
            source_urls=["https://en.wiktionary.org/wiki/résumé"],
        )
        json_data = entry.to_json()
        reconstructed = WordEntry.from_json(json_data)
        self.assertEqual(reconstructed.word, "résumé")
        self.assertEqual(reconstructed.primary_phonetic, "/ˈrɛz.juː.meɪ/")
        self.assertEqual(reconstructed.meanings[0].definitions[0].example, "She sent her résumé.")

    def test_deduplication_of_examples_and_synonyms(self) -> None:
        d = Definition(
            definition="Test def",
            example="Ex 1",
            examples=["Ex 1", "Ex 2", "Ex 1", "  Ex 3  "],
            synonyms=["syn1", "syn1", "syn2"],
        )
        self.assertIn("Ex 1", d.examples)
        self.assertIn("Ex 2", d.examples)
        self.assertIn("Ex 3", d.examples)


if __name__ == "__main__":
    unittest.main()
