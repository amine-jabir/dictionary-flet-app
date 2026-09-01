"""
Build and verification automation script for Dictionary App.
Validates dependencies, runs automated test suites, verifies offline lexicon assets,
and packages the project into distributable wheels and source archives.
"""

from pathlib import Path
import shutil
import subprocess
import sys
import unittest


def print_step(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def verify_offline_lexicon() -> bool:
    """Verifies that the offline lexicon database exists and is populated."""
    from dict_core.data.lexicon_data import EMBEDDED_LEXICON
    from dict_core.providers.offline_provider import OfflineDictionaryProvider

    print(f"[Verification] Embedded lexicon words: {len(EMBEDDED_LEXICON)}")
    assert len(EMBEDDED_LEXICON) > 0, "Embedded lexicon is empty!"

    provider = OfflineDictionaryProvider()
    entry = provider.lookup("serendipity")
    assert entry.word.lower() == "serendipity", "Offline lookup verification failed!"
    print(f"[Verification] Offline lookup for 'serendipity' OK: {entry.meanings[0].definitions[0].definition}")
    return True


def run_unit_tests() -> bool:
    """Runs the full test suite and verifies 100% pass rate."""
    suite = unittest.defaultTestLoader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        print(f"\n[Error] Test suite failed! Failures: {len(result.failures)}, Errors: {len(result.errors)}")
        return False
    
    print(f"\n[Verification] All {result.testsRun} unit tests executed successfully (Skipped: {len(result.skipped)}).")
    return True


def build_packages() -> bool:
    """Invokes standard setuptools build to generate wheel and sdist in dist/."""
    dist_dir = Path("dist")
    build_dir = Path("build")
    
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    print("[Build] Running: python3 setup.py sdist bdist_wheel")
    res = subprocess.run(
        [sys.executable, "setup.py", "sdist", "bdist_wheel"],
        capture_output=True,
        text=True,
    )

    if res.returncode != 0:
        print("[Error] Build failed:")
        print(res.stderr)
        return False

    built_files = list(dist_dir.glob("*"))
    print("\n[Build] Distribution packages successfully created:")
    for f in built_files:
        print(f"  - {f.name} ({f.stat().st_size:,} bytes)")
    
    return True


def main() -> int:
    print_step("Step 1: Verifying Offline Lexicon Assets")
    if not verify_offline_lexicon():
        return 1

    print_step("Step 2: Executing Full Automated Test Suite")
    if not run_unit_tests():
        return 2

    print_step("Step 3: Building Production Packages (Wheel & Source)")
    if not build_packages():
        return 3

    print_step("Build & Verification Completed Successfully!")
    print("The dictionary application is production-ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
