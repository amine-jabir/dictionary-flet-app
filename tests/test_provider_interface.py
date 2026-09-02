"""
Unit tests for BaseDictionaryProvider interface contract and query sanitization.
"""

import unittest
from dict_core.exceptions import ValidationError, WordNotFoundError
from dict_core.interfaces.provider import BaseDictionaryProvider
from dict_core.models.word import Definition, Meaning, WordEntry


class MockConcreteProvider(BaseDictionaryProvider):
    """Concrete mock provider for testing interface contracts."""

    @property
    def provider_id(self) -> str:
        return "mock_provider"

    @property
    def display_name(self) -> str:
        return "Mock Provider"

    def is_available(self) -> bool:
        return True

    def lookup(self, word: str) -> WordEntry:
        clean_word = self.validate_query(word)
        if clean_word == "known":
            return WordEntry(
                word="known",
                meanings=[
                    Meaning(
                        part_of_speech="adjective",
                        definitions=[Definition(definition="Recognized, familiar.")],
                    )
                ],
                provider=self.provider_id,
            )
        raise WordNotFoundError(word=clean_word)


class TestProviderInterface(unittest.TestCase):
    """Tests the BaseDictionaryProvider abstraction and validation logic."""

    def setUp(self) -> None:
        self.provider = MockConcreteProvider()

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with self.assertRaises(TypeError):
            BaseDictionaryProvider()  # type: ignore

    def test_properties(self) -> None:
        self.assertEqual(self.provider.provider_id, "mock_provider")
        self.assertEqual(self.provider.display_name, "Mock Provider")
        self.assertTrue(self.provider.supports_audio)
        self.assertTrue(self.provider.is_available())

    def test_validate_query_valid_words(self) -> None:
        self.assertEqual(self.provider.validate_query("  Hello  "), "hello")
        self.assertEqual(self.provider.validate_query("WORLD"), "world")
        self.assertEqual(self.provider.validate_query("ice-cream"), "ice-cream")
        self.assertEqual(self.provider.validate_query("cul-de-sac"), "cul-de-sac")

    def test_validate_query_empty_or_whitespace(self) -> None:
        with self.assertRaises(ValidationError):
            self.provider.validate_query("")

        with self.assertRaises(ValidationError):
            self.provider.validate_query("    ")

        with self.assertRaises(ValidationError):
            self.provider.validate_query(None)  # type: ignore

        with self.assertRaises(ValidationError):
            self.provider.validate_query(123)  # type: ignore

    def test_validate_query_excessive_length(self) -> None:
        long_word = "a" * 101
        with self.assertRaises(ValidationError):
            self.provider.validate_query(long_word)

    def test_mock_lookup_success_and_not_found(self) -> None:
        entry = self.provider.lookup("KNOWN")
        self.assertEqual(entry.word, "known")
        self.assertEqual(entry.meanings[0].definitions[0].definition, "Recognized, familiar.")

        with self.assertRaises(WordNotFoundError):
            self.provider.lookup("unknown_word")


if __name__ == "__main__":
    unittest.main()
