"""
Unit tests for Part 7 Production Packaging, CLI interface, and environment configuration.
"""

from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from dict_core.cli import cli_lookup, format_word_entry, main as cli_main, setup_services
from dict_core.config import AppConfig, get_default_storage_dir
from dict_core.models.word import Definition, Meaning, WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider


class TestProductionPackaging(unittest.TestCase):
    """Tests production CLI commands, configuration overrides, and packaging integrity."""

    def test_format_word_entry(self) -> None:
        entry = WordEntry(
            word="lucid",
            phonetics=[],
            meanings=[
                Meaning(
                    part_of_speech="adjective",
                    definitions=[Definition(definition="Expressed clearly; easy to understand.", example="A lucid explanation.")],
                    synonyms=["clear", "transparent"],
                )
            ],
            provider="offline_lexicon",
        )
        formatted = format_word_entry(entry)
        self.assertIn("LUCID", formatted)
        self.assertIn("ADJECTIVE", formatted)
        self.assertIn("Expressed clearly", formatted)
        self.assertIn("A lucid explanation", formatted)
        self.assertIn("clear, transparent", formatted)

    def test_cli_lookup_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "cli_test.db")
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_lookup("serendipity", db_path=db_path)
                self.assertEqual(exit_code, 0)
                output = mock_stdout.getvalue()
                self.assertIn("SERENDIPITY", output)
                self.assertIn("NOUN", output)

    def test_cli_lookup_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "cli_test.db")
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_lookup("nonexistentword12345xyz", db_path=db_path)
                # In sandbox without internet, network error returns 2; with internet 404 returns 1
                self.assertIn(exit_code, (1, 2))
                output = mock_stdout.getvalue()
                self.assertIn("Error", output)

    def test_cli_main_dispatch_positional_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "cli_test.db")
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_main(["serendipity", "--db", db_path])
                self.assertEqual(exit_code, 0)
                self.assertIn("SERENDIPITY", mock_stdout.getvalue())

    def test_cli_main_dispatch_history_and_favorites(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "cli_test.db")
            # Look up a word to populate history
            cli_main(["lookup", "serendipity", "--db", db_path])

            # Check history output
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_main(["history", "--db", db_path])
                self.assertEqual(exit_code, 0)
                self.assertIn("serendipity", mock_stdout.getvalue())

            # Check favorites output
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_main(["favorites", "--db", db_path])
                self.assertEqual(exit_code, 0)

            # Clear history
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = cli_main(["history", "--clear", "--db", db_path])
                self.assertEqual(exit_code, 0)
                self.assertIn("cleared", mock_stdout.getvalue().lower())

    def test_environment_variable_storage_override(self) -> None:
        with tempfile.TemporaryDirectory() as custom_dir:
            with patch.dict(os.environ, {"DICT_APP_STORAGE": custom_dir}):
                resolved = get_default_storage_dir()
                self.assertEqual(resolved, Path(custom_dir).resolve())

    def test_app_config_defaults_and_immutability(self) -> None:
        config = AppConfig()
        self.assertGreater(config.INTERACTIVE_TIMEOUT_SECONDS, 0)
        self.assertGreater(config.BACKGROUND_TIMEOUT_SECONDS, 0)
        self.assertGreater(config.CACHE_EXPIRATION_DAYS, 0)
        self.assertIsInstance(config.DEFAULT_STORAGE_DIR, Path)

        # Immutability check
        with self.assertRaises(Exception):
            config.INTERACTIVE_TIMEOUT_SECONDS = 99.0  # type: ignore

    def test_offline_lexicon_integrity(self) -> None:
        provider = OfflineDictionaryProvider()
        self.assertGreater(provider.count(), 0)
        self.assertTrue(provider.is_available())
        entry = provider.lookup("hello")
        self.assertEqual(entry.word.lower(), "hello")
        self.assertTrue(len(entry.meanings) > 0)

    def test_packaging_files_exist(self) -> None:
        project_root = Path(__file__).parent.parent
        self.assertTrue((project_root / "pyproject.toml").exists())
        self.assertTrue((project_root / "setup.py").exists())
        self.assertTrue((project_root / "requirements.txt").exists())
        self.assertTrue((project_root / "README.md").exists())
        self.assertTrue((project_root / "run_gui.py").exists())
        self.assertTrue((project_root / "run_cli.py").exists())
        self.assertTrue((project_root / "run_app.bat").exists())
        self.assertTrue((project_root / "run_app.sh").exists())


if __name__ == "__main__":
    unittest.main()
