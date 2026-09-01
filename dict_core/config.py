"""
Configuration settings for dict_core.
Defines network timeouts, retry policies, platform-standard storage paths, and environment variable overrides.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import sys


def get_default_storage_dir() -> Path:
    """
    Resolves the OS-standard persistent user data directory:
    - Windows: %APPDATA%/DictionaryApp or %LOCALAPPDATA%/DictionaryApp
    - macOS: ~/Library/Application Support/DictionaryApp
    - Linux / Unix: $XDG_DATA_HOME/dictionary_app or ~/.local/share/dictionary_app
    - Environment override: DICT_APP_STORAGE or DICT_STORAGE_DIR
    """
    env_storage = os.getenv("DICT_APP_STORAGE") or os.getenv("DICT_STORAGE_DIR")
    if env_storage:
        p = Path(env_storage).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

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
        # Test SQLite lock creation
        test_db = target / ".lock_test.db"
        conn = sqlite3.connect(str(test_db))
        conn.execute("CREATE TABLE IF NOT EXISTS _test (id INT);")
        conn.close()
        test_db.unlink(missing_ok=True)
    except Exception:
        target = Path(os.getenv("TMPDIR", "/tmp")) / "dict_app"
        target.mkdir(parents=True, exist_ok=True)

    return target


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
