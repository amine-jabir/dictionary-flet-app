"""
Unit tests for WiktionaryProvider with mocked responses and HTML cleaning.
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
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.utils.http_client import ResilientHttpClient


class TestWiktionaryProvider(unittest.TestCase):
    """Tests the WiktionaryProvider normalization, HTML cleaning, and error handling."""

    def setUp(self) -> None:
        self.mock_client = MagicMock(spec=ResilientHttpClient)
        self.provider = WiktionaryProvider(client=self.mock_client)

    def test_provider_properties(self) -> None:
        self.assertEqual(self.provider.provider_id, "wiktionary_rest")
        self.assertEqual(self.provider.display_name, "Wiktionary REST API")
        self.assertFalse(self.provider.supports_audio)
        self.assertTrue(self.provider.is_available())

    def test_html_cleaning_utility(self) -> None:
        raw = "<p>A <b>greeting</b> &amp; <i>salutation</i>.<br>Used when meeting.</p>"
        cleaned = self.provider._clean_html(raw)
        self.assertEqual(cleaned, "A greeting & salutation. Used when meeting.")

        # Test embedded CSS / style tags and mw-parser-output artifacts
        raw_css = "to have as one's intention.<style data-mw-deduplicate='TemplateStyles:r123'>.mw-parser-output .defdate{font-size:smaller}</style>"
        cleaned_css = self.provider._clean_html(raw_css)
        self.assertEqual(cleaned_css, "to have as one's intention.")

        raw_css2 = "to have as one's intention. mw-parser-output.defdate{font-size:smaller"
        cleaned_css2 = self.provider._clean_html(raw_css2)
        self.assertEqual(cleaned_css2, "to have as one's intention.")

        self.assertEqual(self.provider._clean_html(""), "")
        self.assertEqual(self.provider._clean_html(None), "")  # type: ignore

    def test_successful_lookup_full_data(self) -> None:
        payload = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "language": "en",
                    "definitions": [
                        {
                            "definition": "<p>A greeting (greeting word or expression).</p>",
                            "parsedDefinitions": [
                                {"definition": "A greeting (greeting word or expression)."}
                            ],
                            "examples": [
                                "<p>Say <i>hello</i> to your friend.</p>",
                                "<p>A hearty <i>hello</i> echoed across the hall.</p>"
                            ]
                        }
                    ]
                },
                {
                    "partOfSpeech": "Verb",
                    "language": "en",
                    "definitions": [
                        {
                            "definition": "<p>To greet someone with &quot;hello&quot;.</p>",
                            "examples": []
                        }
                    ]
                }
            ]
        }

        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("hello")
        self.assertIsInstance(entry, WordEntry)
        self.assertEqual(entry.word, "hello")
        self.assertEqual(entry.parts_of_speech, ["noun", "verb"])
        self.assertEqual(entry.total_definitions_count, 2)
        
        noun_meaning = next(m for m in entry.meanings if m.part_of_speech == "noun")
        self.assertEqual(noun_meaning.definitions[0].definition, "A greeting (greeting word or expression).")
        self.assertEqual(noun_meaning.definitions[0].example, "Say hello to your friend.")
        self.assertEqual(len(noun_meaning.definitions[0].examples), 2)
        self.assertEqual(noun_meaning.definitions[0].examples[1], "A hearty hello echoed across the hall.")

        verb_meaning = next(m for m in entry.meanings if m.part_of_speech == "verb")
        self.assertEqual(verb_meaning.definitions[0].definition, 'To greet someone with "hello".')

        self.assertIn("https://en.wiktionary.org/wiki/hello", entry.source_urls)
        self.assertEqual(entry.provider, "wiktionary_rest")

    def test_lookup_fallback_to_other_language_section_if_en_missing(self) -> None:
        payload = {
            "fr": [
                {
                    "partOfSpeech": "Nom",
                    "definitions": [
                        {"definition": "<p>Un salut ou salutation.</p>"}
                    ]
                }
            ]
        }
        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("bonjour")
        self.assertEqual(entry.word, "bonjour")
        self.assertEqual(entry.parts_of_speech, ["nom"])
        self.assertEqual(entry.meanings[0].definitions[0].definition, "Un salut ou salutation.")

    def test_lookup_empty_dict_raises_word_not_found(self) -> None:
        self.mock_client.get_json.return_value = {}

        with self.assertRaises(WordNotFoundError):
            self.provider.lookup("missingword")

    def test_lookup_invalid_type_raises_invalid_response(self) -> None:
        self.mock_client.get_json.return_value = ["unexpected", "list"]

        with self.assertRaises(InvalidResponseError):
            self.provider.lookup("badpayload")

    def test_lookup_404_raises_word_not_found(self) -> None:
        self.mock_client.get_json.side_effect = WordNotFoundError(word="notfound")

        with self.assertRaises(WordNotFoundError):
            self.provider.lookup("notfound")

    def test_lookup_unicode_and_accents(self) -> None:
        payload = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [
                        {"definition": "<p>A résumé or summary of work.</p>"}
                    ]
                }
            ]
        }
        self.mock_client.get_json.return_value = payload

        entry = self.provider.lookup("résumé")
        self.assertEqual(entry.word, "résumé")
        self.assertEqual(entry.meanings[0].definitions[0].definition, "A résumé or summary of work.")

    def test_network_failure_propagates_network_error(self) -> None:
        self.mock_client.get_json.side_effect = NetworkError("Socket dropped")

        with self.assertRaises(NetworkError):
            self.provider.lookup("errorword")

    def test_timeout_propagates_timeout_error(self) -> None:
        self.mock_client.get_json.side_effect = TimeoutError("HTTP timeout")

        with self.assertRaises(TimeoutError):
            self.provider.lookup("slowword")

    def test_validation_error_on_empty(self) -> None:
        with self.assertRaises(ValidationError):
            self.provider.lookup("")


if __name__ == "__main__":
    unittest.main()
