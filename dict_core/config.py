"""
Configuration settings for dict_core.
Defines network timeouts, retry policies, platform-standard storage paths, and environment variable overrides.
Supports mobile application sandboxing (Android app_storage) and standard desktop paths.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def _verify_writable_sqlite(target: Path) -> bool:
    """Verifies that the target directory exists and can create/lock SQLite database files."""
    test_db = target / ".lock_test.db"
    try:
        conn = sqlite3.connect(str(test_db), timeout=1.0)
        conn.execute("CREATE TABLE IF NOT EXISTS _test (id INT);")
        conn.close()
        test_db.unlink(missing_ok=True)
        return True
    except Exception:
        try:
            test_db.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def get_default_storage_dir() -> Path:
    """
    Resolves the standard persistent user data directory:
    - Mobile (Android Sandbox): app_storage within application internal files directory
    - Windows: %APPDATA%/DictionaryApp or %LOCALAPPDATA%/DictionaryApp
    - macOS: ~/Library/Application Support/DictionaryApp
    - Linux / Unix: $XDG_DATA_HOME/dictionary_app or ~/.local/share/dictionary_app
    - Environment overrides: DICT_APP_STORAGE, DICT_STORAGE_DIR, FLET_APP_STORAGE, APP_STORAGE
    """
    # 1. Check explicit environment overrides
    for env_var in ("DICT_APP_STORAGE", "DICT_STORAGE_DIR", "FLET_APP_STORAGE", "APP_STORAGE", "INTERNAL_STORAGE"):
        env_storage = os.getenv(env_var)
        if env_storage:
            p = Path(env_storage).expanduser().resolve()
            try:
                p.mkdir(parents=True, exist_ok=True)
                return p
            except Exception:
                pass

    is_android = hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ

    # 2. Android Mobile Application Sandboxing:
    if is_android:
        candidates = [
            Path.cwd() / "app_storage",
            Path.home() / "app_storage",
            Path(tempfile.gettempdir()) / "dictionary_app",
        ]
        for cand in candidates:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                if _verify_writable_sqlite(cand):
                    return cand
            except Exception:
                continue

    # 3. Standard Desktop OS Directories:
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if appdata:
            target = Path(appdata) / "DictionaryApp"
        else:
            target = home / "AppData" / "Roaming" / "DictionaryApp"
    elif sys.platform == "darwin":
        target = home / "Library" / "Application Support" / "DictionaryApp"
    else:
        if str(home) == "/working_dir":
            target = Path("/tmp/dict_app")
        else:
            xdg_data = os.getenv("XDG_DATA_HOME")
            if xdg_data:
                target = Path(xdg_data) / "dictionary_app"
            else:
                target = home / ".local" / "share" / "dictionary_app"

    try:
        target.mkdir(parents=True, exist_ok=True)
        if _verify_writable_sqlite(target):
            return target
    except Exception:
        pass

    # 4. Universal Resilient Fallback:
    fallback = Path(tempfile.gettempdir()) / "dict_app"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@dataclass(frozen=True)
class AppConfig:
    """Immutable application-wide configuration with environment overrides."""

    # Interactive Network Settings (for real-time user dictionary lookups)
    INTERACTIVE_TIMEOUT_SECONDS: float = float(os.getenv("DICT_INTERACTIVE_TIMEOUT", "2.5"))
    INTERACTIVE_MAX_RETRIES: int = int(os.getenv("DICT_INTERACTIVE_RETRIES", "0"))
    INTERACTIVE_BACKOFF_FACTOR: float = 0.2

    # Background / General Network Settings (for binary audio downloads and caching)
    BACKGROUND_TIMEOUT_SECONDS: float = float(os.getenv("DICT_BACKGROUND_TIMEOUT", "8.0"))
    BACKGROUND_MAX_RETRIES: int = int(os.getenv("DICT_BACKGROUND_RETRIES", "2"))
    BACKGROUND_BACKOFF_FACTOR: float = 0.5

    # General HTTP defaults
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("DICT_HTTP_TIMEOUT", "8.0"))
    HTTP_MAX_RETRIES: int = 2
    HTTP_BACKOFF_FACTOR: float = 0.5
    HTTP_USER_AGENT: str = os.getenv("DICT_USER_AGENT", "CrossPlatformDictionaryCore/1.0 (Python)")

    # Default Provider
    DEFAULT_PROVIDER: str = os.getenv("DICT_DEFAULT_PROVIDER", "free_dict_api")

    # Cache settings
    CACHE_EXPIRATION_DAYS: int = int(os.getenv("DICT_CACHE_TTL_DAYS", "30"))
    DEFAULT_STORAGE_DIR: Path = get_default_storage_dir()


DEFAULT_CONFIG = AppConfig()