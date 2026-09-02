"""
Cross-validation tests comparing normalization output of FreeDictProvider and WiktionaryProvider.
"""

from unittest.mock import MagicMock
import unittest

from dict_core.models.word import WordEntry
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.utils.http_client import ResilientHttpClient


class TestProvidersCrossValidation(unittest.TestCase):
    """Verifies that both providers return valid, normalized WordEntry structures."""

    def setUp(self) -> None:
        self.mock_free_client = MagicMock(spec=ResilientHttpClient)
        self.free_provider = FreeDictProvider(client=self.mock_free_client)

        self.mock_wiki_client = MagicMock(spec=ResilientHttpClient)
        self.wiki_provider = WiktionaryProvider(client=self.mock_wiki_client)

    def test_normalized_structures_conformity(self) -> None:
        # FreeDict mock response
        self.mock_free_client.get_json.return_value = [
            {
                "word": "python",
                "phonetics": [{"text": "/ˈpaɪ.θən/", "audio": "https://api.dev/python-us.mp3"}],
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "A large non-venomous snake.",
                                "example": "The python wrapped around the branch."
                            }
                        ]
                    }
                ],
                "sourceUrls": ["https://en.wiktionary.org/wiki/python"]
            }
        ]

        # Wiktionary mock response
        self.mock_wiki_client.get_json.return_value = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [
                        {
                            "definition": "<p>A large non-venomous snake.</p>",
                            "examples": ["<p>The python wrapped around the branch.</p>"]
                        }
                    ]
                }
            ]
        }

        entry_free = self.free_provider.lookup("python")
        entry_wiki = self.wiki_provider.lookup("python")

        for entry in (entry_free, entry_wiki):
            self.assertIsInstance(entry, WordEntry)
            self.assertEqual(entry.word, "python")
            self.assertEqual(entry.parts_of_speech, ["noun"])
            self.assertEqual(entry.total_definitions_count, 1)
            self.assertEqual(
                entry.meanings[0].definitions[0].definition,
                "A large non-venomous snake."
            )
            self.assertEqual(
                entry.meanings[0].definitions[0].example,
                "The python wrapped around the branch."
            )
            self.assertTrue(len(entry.source_urls) > 0)
            self.assertTrue(entry.source_urls[0].startswith("https://en.wiktionary.org/wiki/"))


if __name__ == "__main__":
    unittest.main()
