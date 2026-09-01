"""
Production CLI entry point for dict_core.
Supports single lookups, interactive dictionary REPL, cache inspection, and benchmarks.
"""

import argparse
import sys
from typing import List, Optional

from dict_core.exceptions import DictionaryError, WordNotFoundError
from dict_core.models.word import WordEntry
from dict_core.providers.free_dict_provider import FreeDictProvider
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.providers.wiktionary_provider import WiktionaryProvider
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository


def format_word_entry(entry: WordEntry) -> str:
    """Formats a WordEntry into a clean, human-readable terminal output."""
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append(f"  {entry.word.upper()}  {entry.primary_phonetic or ''}")
    lines.append(f"{'=' * 60}")
    
    meta_info = []
    if entry.provider:
        meta_info.append(f"Source: {entry.provider}")
    if entry.metadata.get("cached"):
        meta_info.append("Cached: Yes")
    if meta_info:
        lines.append(f"[{' | '.join(meta_info)}]\n")

    for m_idx, meaning in enumerate(entry.meanings, 1):
        lines.append(f"  [{meaning.part_of_speech.upper()}]")
        for d_idx, defn in enumerate(meaning.definitions, 1):
            lines.append(f"    {d_idx}. {defn.definition}")
            if defn.example:
                lines.append(f"       Example: \"{defn.example}\"")
            if defn.synonyms:
                lines.append(f"       Synonyms: {', '.join(defn.synonyms[:6])}")
        
        if meaning.synonyms:
            lines.append(f"    Similar words: {', '.join(meaning.synonyms[:8])}")
        lines.append("")

    if entry.primary_audio_url:
        lines.append(f"Pronunciation Audio: {entry.primary_audio_url}")

    return "\n".join(lines)


def setup_services(db_path: Optional[str] = None):
    """Initializes and wires all core services."""
    db = DatabaseManager(db_path)
    cache_repo = CacheRepository(db)
    history_repo = HistoryRepository(db)
    vocab_repo = VocabularyRepository(db)

    offline_prov = OfflineDictionaryProvider()
    free_prov = FreeDictProvider()
    wiki_prov = WiktionaryProvider()

    lookup_service = LookupService(
        provider=free_prov,
        cache_repo=cache_repo,
        history_repo=history_repo,
        offline_provider=offline_prov,
        fallback_providers=[wiki_prov],
    )

    audio_cache = AudioCacheManager()
    audio_service = AudioService(cache_manager=audio_cache)

    return db, cache_repo, history_repo, vocab_repo, lookup_service, audio_service


def cli_lookup(word: str, force_refresh: bool = False, play_audio: bool = False, db_path: Optional[str] = None) -> int:
    """Performs a single word lookup and prints the result."""
    db, cache_repo, history_repo, vocab_repo, lookup_service, audio_service = setup_services(db_path)
    try:
        entry = lookup_service.lookup(word, force_refresh=force_refresh)
        print(format_word_entry(entry))

        if play_audio and entry.primary_audio_url:
            print("\nPlaying pronunciation audio...")
            audio_service.play(entry)

        return 0
    except WordNotFoundError as exc:
        print(f"\n[Error] Word '{exc.word}' was not found in the dictionary.")
        return 1
    except DictionaryError as exc:
        print(f"\n[Error] Dictionary error: {exc.message}")
        return 2
    except Exception as exc:
        print(f"\n[Error] Unexpected error: {exc}")
        return 3
    finally:
        db.close()


def cli_interactive(db_path: Optional[str] = None) -> None:
    """Runs an interactive REPL dictionary shell."""
    db, cache_repo, history_repo, vocab_repo, lookup_service, audio_service = setup_services(db_path)
    print("\n" + "=" * 60)
    print("  Dictionary Interactive CLI Shell")
    print("  Type any English word to look up (or 'exit' / 'quit' to close)")
    print("=" * 60 + "\n")

    try:
        while True:
            try:
                query = input("dict> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not query:
                continue
            if query.lower() in ("exit", "quit", ":q"):
                print("Goodbye!")
                break

            try:
                entry = lookup_service.lookup(query)
                print(format_word_entry(entry))
            except WordNotFoundError as exc:
                print(f"-> Word '{exc.word}' was not found.\n")
            except Exception as exc:
                print(f"-> Error: {exc}\n")
    finally:
        db.close()


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI argument parser and command dispatcher."""
    parser = argparse.ArgumentParser(
        prog="dict-cli",
        description="Cross-Platform Production Dictionary Engine (CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: lookup (or default positional word)
    lookup_parser = subparsers.add_parser("lookup", help="Look up an English word definition")
    lookup_parser.add_argument("word", type=str, help="Word to look up")
    lookup_parser.add_argument("--force-refresh", "-f", action="store_true", help="Bypass local cache")
    lookup_parser.add_argument("--audio", "-a", action="store_true", help="Play pronunciation audio")
    lookup_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database file path")

    # Command: interactive
    interactive_parser = subparsers.add_parser("interactive", help="Start interactive dictionary REPL shell")
    interactive_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database file path")

    # Command: history
    history_parser = subparsers.add_parser("history", help="List recent search history")
    history_parser.add_argument("--limit", "-n", type=int, default=20, help="Number of records to show")
    history_parser.add_argument("--clear", action="store_true", help="Clear all search history")
    history_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database file path")

    # Command: favorites
    fav_parser = subparsers.add_parser("favorites", help="List starred vocabulary words")
    fav_parser.add_argument("--limit", "-n", type=int, default=50, help="Number of records to show")
    fav_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database file path")

    # Command: benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run multi-tier dictionary latency benchmarks")
    bench_parser.add_argument("--words", type=int, default=20, help="Number of iterations")

    # If first arg is a word without explicit subcommand, treat as lookup
    raw_args = args if args is not None else sys.argv[1:]
    if raw_args and raw_args[0] not in ("lookup", "interactive", "history", "favorites", "benchmark", "-h", "--help"):
        raw_args = ["lookup"] + raw_args

    parsed = parser.parse_args(raw_args)

    if parsed.command == "lookup":
        return cli_lookup(parsed.word, force_refresh=parsed.force_refresh, play_audio=parsed.audio, db_path=parsed.db)
    elif parsed.command == "interactive":
        cli_interactive(db_path=parsed.db)
        return 0
    elif parsed.command == "history":
        db, cache_repo, history_repo, vocab_repo, _, _ = setup_services(parsed.db)
        if parsed.clear:
            history_repo.clear()
            print("Search history cleared successfully.")
        else:
            items = history_repo.get_recent(limit=parsed.limit)
            print(f"\nRecent Search History ({len(items)} items):")
            for item in items:
                status = "Found" if item.get("result_found") else "404"
                print(f"  - {item['word']:<20} [{status}] ({item['searched_at'][:16]})")
            print("")
        db.close()
        return 0
    elif parsed.command == "favorites":
        db, cache_repo, history_repo, vocab_repo, _, _ = setup_services(parsed.db)
        items = vocab_repo.list_favorites(limit=parsed.limit)
        print(f"\nSaved Vocabulary ({len(items)} words):")
        for item in items:
            tags = f" | Tags: {', '.join(item.get('tags', []))}" if item.get('tags') else ""
            notes = f" | Notes: {item.get('notes')}" if item.get('notes') else ""
            print(f"  ★ {item['word']:<20} (Added: {item['added_at'][:10]}){tags}{notes}")
        print("")
        db.close()
        return 0
    elif parsed.command == "benchmark":
        from dict_core.benchmark import run_comprehensive_benchmark
        run_comprehensive_benchmark(iterations=parsed.words)
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
