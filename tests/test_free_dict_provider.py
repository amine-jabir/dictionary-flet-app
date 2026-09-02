"""
Unit tests for FreeDictProvider with comprehensive mocked responses and edge cases.
"""

from unittest.mock import MagicMock
import unittest

from dict_core.exceptions import (
    InvalidResponseError,
    NetworkError,
    TimeoutError,
    ValidationError,
    WordNotFoundError,
)
from dict_core.models.word import WordEntry
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.utils.http_client import ResilientHttpClient


class TestFreeDictProvider(unittest.TestCase):
    """Tests the FreeDictProvider normalization, error handling, and accent detection."""

    def setUp(self) -> None:
        self.mock_client = MagicMock(spec=ResilientHttpClient)
        self.provider = FreeDictProvider(client=self.mock_client)

    def test_provider_properties(self) -> None:
        self.assertEqual(self.provider.provider_id, "free_dict_api")
        self.assertEqual(self.provider.display_name, "Free Dictionary API")
        self.assertTrue(self.provider.supports_audio)
        self.assertTrue(self.provider.is_available())

    def test_accent_detection(self) -> None:
        self.assertEqual(self.provider._detect_accent("https://api.dev/media/hello-us.mp3"), "us")
        self.assertEqual(self.provider._detect_accent("https://api.dev/media/en-uk-hello.mp3"), "uk")
        self.assertEqual(self.provider._detect_accent("https://api.dev/media/hello-au.ogg"), "au")
        self.assertEqual(self.provider._detect_accent("https://api.dev/media/en-ca-hello.mp3"), "ca")
        self.assertEqual(self.provider._detect_accent("https://api.dev/media/hello-generic.mp3"), "generic")
        self.assertEqual(self.provider._detect_accent(""), "")

    def test_successful_lookup_full_data(self) -> None:
        payload = [
            {
                "word": "hello",
                "phonetic": "/həˈloʊ/",
                "phonetics": [
                    {
                        "text": "/həˈloʊ/",
                        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-au.mp3",
                        "sourceUrl": "https://commons.wikimedia.org/wiki/File:Hello-au.ogg",
                        "license": {"name": "BY-SA 4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0"}
                    },
                    {
                        "text": "/hɛˈloʊ/",
                        "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/hello-uk.mp3",
                        "sourceUrl": "https://commons.wikimedia.org/wiki/File:En-uk-hello.ogg"
                    },
                    {
                        "audio": ""
                    }
                ],
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "\"Hello!\" or an equivalent greeting.",
                                "synonyms": ["greeting", "salutation"],
                                "antonyms": ["goodbye"],
                                "example": "He greeted her with a warm hello."
                            }
                        ],
                        "synonyms": ["hi", "howdy"],
                        "antonyms": ["farewell"]
                    },
                    {
                        "partOfSpeech": "verb",
                        "definitions": [
                            {
                                "definition": "To greet with \"hello\".",
                                "synonyms": [],
                                "antonyms": []
                            }
                        ]
                    }
                ],
                "sourceUrls": ["https://en.wiktionary.org/wiki/hello"]
            }
        ]

        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("hello")
        self.assertIsInstance(entry, WordEntry)
        self.assertEqual(entry.word, "hello")
        self.assertEqual(entry.primary_phonetic, "/həˈloʊ/")
        self.assertEqual(entry.primary_audio_url, "https://api.dictionaryapi.dev/media/pronunciations/en/hello-au.mp3")
        self.assertEqual(entry.parts_of_speech, ["noun", "verb"])
        self.assertEqual(entry.total_definitions_count, 2)
        
        noun_meaning = next(m for m in entry.meanings if m.part_of_speech == "noun")
        self.assertEqual(noun_meaning.definitions[0].example, "He greeted her with a warm hello.")
        self.assertIn("hi", noun_meaning.synonyms)
        self.assertIn("farewell", noun_meaning.antonyms)
        self.assertIn("https://en.wiktionary.org/wiki/hello", entry.source_urls)
        self.assertEqual(entry.provider, "free_dict_api")

    def test_lookup_multiple_sub_entries_merged(self) -> None:
        payload = [
            {
                "word": "lead",
                "phonetics": [{"text": "/liːd/", "audio": "https://api.dev/lead-verb-uk.mp3"}],
                "meanings": [
                    {
                        "partOfSpeech": "verb",
                        "definitions": [{"definition": "To guide or conduct in a certain direction."}]
                    }
                ]
            },
            {
                "word": "lead",
                "phonetics": [{"text": "/lɛd/", "audio": "https://api.dev/lead-noun-us.mp3"}],
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [{"definition": "A heavy, soft, malleable metallic element."}]
                    }
                ]
            }
        ]
        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("lead")
        self.assertEqual(entry.word, "lead")
        self.assertEqual(len(entry.phonetics), 2)
        self.assertEqual(len(entry.meanings), 2)
        self.assertEqual(entry.parts_of_speech, ["verb", "noun"])

    def test_lookup_missing_audio_and_examples(self) -> None:
        payload = [
            {
                "word": "obscure",
                "phonetic": "/əbˈskjʊər/",
                "phonetics": [],
                "meanings": [
                    {
                        "partOfSpeech": "adjective",
                        "definitions": [
                            {"definition": "Not discovered or known about; uncertain."}
                        ]
                    }
                ]
            }
        ]
        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("obscure")
        self.assertEqual(entry.word, "obscure")
        self.assertEqual(entry.primary_phonetic, "/əbˈskjʊər/")
        self.assertIsNone(entry.primary_audio_url)
        self.assertEqual(entry.meanings[0].definitions[0].example, "")

    def test_lookup_unicode_and_accented_words(self) -> None:
        payload = [
            {
                "word": "résumé",
                "phonetic": "/ˈrɛz.juː.meɪ/",
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [{"definition": "A curriculum vitae or summary of qualifications."}]
                    }
                ]
            }
        ]
        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("résumé")
        self.assertEqual(entry.word, "résumé")
        self.assertEqual(entry.primary_phonetic, "/ˈrɛz.juː.meɪ/")

    def test_lookup_404_raises_word_not_found(self) -> None:
        self.mock_client.get_json.side_effect = WordNotFoundError(word="nonexistent")

        with self.assertRaises(WordNotFoundError) as ctx:
            self.provider.lookup("nonexistent")
        self.assertEqual(ctx.exception.word, "nonexistent")

    def test_lookup_dict_no_definitions_found_raises_word_not_found(self) -> None:
        self.mock_client.get_json.return_value = {
            "title": "No Definitions Found",
            "message": "Sorry pal, we couldn't find definitions for the word you were looking for."
        }

        with self.assertRaises(WordNotFoundError):
            self.provider.lookup("xyzabc")

    def test_lookup_empty_list_raises_word_not_found(self) -> None:
        self.mock_client.get_json.return_value = []

        with self.assertRaises(WordNotFoundError):
            self.provider.lookup("emptyword")

    def test_lookup_unexpected_structure_raises_invalid_response(self) -> None:
        self.mock_client.get_json.return_value = "unexpected string"

        with self.assertRaises(InvalidResponseError):
            self.provider.lookup("badresponse")

    def test_network_failure_propagates_network_error(self) -> None:
        self.mock_client.get_json.side_effect = NetworkError("Connection refused")

        with self.assertRaises(NetworkError):
            self.provider.lookup("networkfail")

    def test_timeout_propagates_timeout_error(self) -> None:
        self.mock_client.get_json.side_effect = TimeoutError("Request timed out")

        with self.assertRaises(TimeoutError):
            self.provider.lookup("slowquery")

    def test_validation_error_on_blank_query(self) -> None:
        with self.assertRaises(ValidationError):
            self.provider.lookup("   ")


if __name__ == "__main__":
    unittest.main()
