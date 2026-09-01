"""
Comprehensive End-to-End Latency Benchmark for Dictionary Engine & Application State.
Measures full pipeline latency across all caching, offline lexicon, and provider tiers.
"""

import logging
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import List, Tuple
from unittest.mock import MagicMock

from dict_client_flet.state.app_state import AppState
from dict_core.models.word import AudioSource, Definition, Meaning, Phonetic, WordEntry
from dict_core.providers.offline_provider import OfflineDictionaryProvider
from dict_core.services.audio_service import AudioService
from dict_core.services.lookup_service import LookupService
from dict_core.storage.audio_cache import AudioCacheManager
from dict_core.storage.cache_repo import CacheRepository
from dict_core.storage.database import DatabaseManager
from dict_core.storage.history_repo import HistoryRepository
from dict_core.storage.vocabulary_repo import VocabularyRepository


def create_sample_entry(word: str) -> WordEntry:
    return WordEntry(
        word=word,
        phonetics=[Phonetic(text=f"/{word}/", audio=[AudioSource(url=f"https://audio.org/{word}.mp3", accent="us")])],
        meanings=[
            Meaning(
                part_of_speech="noun",
                definitions=[Definition(definition=f"The primary definition for {word}.", example=f"An example of {word}.")],
                synonyms=["clarity", "precision"],
            )
        ],
        provider="offline_lexicon",
    )


def run_e2e_benchmark(iterations: int = 100) -> None:
    print("=" * 70)
    print(f" End-to-End Latency Benchmark ({iterations} iterations per tier)")
    print(" Pipeline: UI Event -> LookupService -> Storage/Provider -> AppState")
    print("=" * 70)

    # Temporarily silence verbose migration logs during rapid iteration benchmark
    logging.getLogger("dict_core.storage.database").setLevel(logging.WARNING)

    # Use ignore_cleanup_errors=True for Python 3.10+ Windows lock resilience
    kwargs = {"ignore_cleanup_errors": True} if sys.version_info >= (3, 10) else {}
    with tempfile.TemporaryDirectory(**kwargs) as tmpdir:
        db_path = Path(tmpdir) / "bench.db"
        offline_db_path = Path(tmpdir) / "offline.db"

        # 1. Cold Application Startup Benchmark
        print("\n[1/4] Benchmarking Cold Application Startup...")
        startup_latencies: List[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            temp_db_path = Path(tmpdir) / f"temp_startup_{_}.db"
            db = DatabaseManager(temp_db_path)
            cache_repo = CacheRepository(db)
            hist_repo = HistoryRepository(db)
            vocab_repo = VocabularyRepository(db)
            offline_prov = OfflineDictionaryProvider(db_path=offline_db_path)
            mock_online = MagicMock()
            mock_online.validate_query.side_effect = lambda w: w.strip().lower()
            mock_online.provider_id = "mock_online_api"
            mock_online.display_name = "Mock Online API"
            lookup_srv = LookupService(
                provider=mock_online,
                cache_repo=cache_repo,
                history_repo=hist_repo,
                offline_provider=offline_prov,
            )
            audio_srv = AudioService(cache_manager=AudioCacheManager(Path(tmpdir) / "audio"))
            app_state = AppState(
                lookup_service=lookup_srv,
                audio_service=audio_srv,
                vocab_repo=vocab_repo,
                history_repo=hist_repo,
                debug_diagnostics=False,
            )
            app_state.load_favorites()
            app_state.load_history()
            t1 = time.perf_counter()
            startup_latencies.append((t1 - t0) * 1000.0)
            db.close()

        # Setup persistent environment for lookup tiers
        db = DatabaseManager(db_path)
        cache_repo = CacheRepository(db)
        hist_repo = HistoryRepository(db)
        vocab_repo = VocabularyRepository(db)

        # Populate offline lexicon
        offline_prov = OfflineDictionaryProvider(db_path=offline_db_path)
        offline_prov.insert_entry(create_sample_entry("serendipity"))
        offline_prov.insert_entry(create_sample_entry("resilience"))
        offline_prov.insert_entry(create_sample_entry("eloquent"))

        # Pre-seed user cache for cache hit test
        cache_repo.set(create_sample_entry("lucid"), ttl_days=30)

        # Mock online provider
        mock_online = MagicMock()
        mock_online.provider_id = "mock_online_api"
        mock_online.display_name = "Mock Online API"
        mock_online.validate_query.side_effect = lambda w: w.strip().lower()
        mock_online.lookup.return_value = create_sample_entry("uncommonword")

        lookup_srv = LookupService(
            provider=mock_online,
            cache_repo=cache_repo,
            history_repo=hist_repo,
            offline_provider=offline_prov,
        )
        audio_srv = AudioService(cache_manager=AudioCacheManager(Path(tmpdir) / "audio"))
        app_state = AppState(
            lookup_service=lookup_srv,
            audio_service=audio_srv,
            vocab_repo=vocab_repo,
            history_repo=hist_repo,
            debug_diagnostics=False,
        )

        # 2. End-to-End User Cache Hit Benchmark
        print("[2/4] Benchmarking SQLite User Cache Hits...")
        cache_hit_latencies: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            app_state.search_word("lucid", force_refresh=False, run_sync=True)
            t1 = time.perf_counter()
            assert app_state.current_entry is not None
            assert app_state.current_entry.word == "lucid"
            cache_hit_latencies.append((t1 - t0) * 1000.0)

        # 3. End-to-End Local / Offline Lexicon Hit Benchmark
        print("[3/4] Benchmarking Offline Lexicon Hits...")
        offline_hit_latencies: List[float] = []
        for i in range(iterations):
            word = "serendipity" if i % 2 == 0 else "resilience"
            cache_repo.delete(word)
            t0 = time.perf_counter()
            app_state.search_word(word, force_refresh=False, run_sync=True)
            t1 = time.perf_counter()
            assert app_state.current_entry is not None
            assert app_state.current_entry.word == word
            offline_hit_latencies.append((t1 - t0) * 1000.0)

        # 4. End-to-End Online Provider Fallback (Simulated Provider)
        print("[4/4] Benchmarking Online Fallback Tier...")
        online_fallback_latencies: List[float] = []
        for _ in range(iterations):
            cache_repo.delete("uncommonword")
            t0 = time.perf_counter()
            app_state.search_word("uncommonword", force_refresh=False, run_sync=True)
            t1 = time.perf_counter()
            assert app_state.current_entry is not None
            assert app_state.current_entry.word == "uncommonword"
            online_fallback_latencies.append((t1 - t0) * 1000.0)

        db.close()

    logging.getLogger("dict_core.storage.database").setLevel(logging.INFO)

    def print_stats(title: str, data: List[float]) -> Tuple[float, float]:
        med = statistics.median(data)
        p95 = statistics.quantiles(data, n=20)[18] if len(data) >= 20 else max(data)
        avg = statistics.mean(data)
        minimum = min(data)
        maximum = max(data)
        print(f"\n{title}:")
        print(f"  • Median (P50):  {med:6.3f} ms")
        print(f"  • 95th % (P95):  {p95:6.3f} ms")
        print(f"  • Average:       {avg:6.3f} ms")
        print(f"  • Min / Max:     {minimum:6.3f} ms / {maximum:6.3f} ms")
        return med, p95

    print("\n--- MEASUREMENTS ---")
    med_cache, p95_cache = print_stats("1. End-to-End User SQLite Cache Hit (search_word -> AppState)", cache_hit_latencies)
    med_off, p95_off = print_stats("2. End-to-End Local Offline Lexicon Hit (search_word -> AppState)", offline_hit_latencies)
    med_on, p95_on = print_stats("3. End-to-End Online Provider Fallback (Mocked Network)", online_fallback_latencies)
    med_start, p95_start = print_stats("4. Cold Application Startup (DB + Migrations + Wiring + State)", startup_latencies)

    print("\n" + "=" * 70)
    print(" SUMMARY TABLE (Milliseconds)")
    print("=" * 70)
    print(f"{'Pipeline Tier':<35} | {'Median (P50)':<14} | {'95th % (P95)':<14}")
    print("-" * 70)
    print(f"{'User SQLite Cache Hit':<35} | {med_cache:<11.3f} ms | {p95_cache:<11.3f} ms")
    print(f"{'Local Offline Lexicon Hit':<35} | {med_off:<11.3f} ms | {p95_off:<11.3f} ms")
    print(f"{'Online Fallback (Mocked)':<35} | {med_on:<11.3f} ms | {p95_on:<11.3f} ms")
    print(f"{'Cold Application Startup':<35} | {med_start:<11.3f} ms | {p95_start:<11.3f} ms")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_benchmark(100)
