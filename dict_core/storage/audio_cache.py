"""
Binary audio caching manager for dict_core.
Manages disk storage of downloaded pronunciation audio files with atomic writes,
format detection, and SHA-256 hashing.
"""

import hashlib
import os
from pathlib import Path
import tempfile
from typing import Optional, Union
import urllib.parse

from dict_core.config import DEFAULT_CONFIG
from dict_core.exceptions import AudioError
from dict_core.utils.logger import get_logger

logger = get_logger("dict_core.storage.audio_cache")


class AudioCacheManager:
    """
    Manages local filesystem caching for downloaded audio files.
    """

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None) -> None:
        if cache_dir is None:
            self.cache_dir = DEFAULT_CONFIG.DEFAULT_STORAGE_DIR / "audio_cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_filename_for_url(self, url: str, data: bytes = b"") -> str:
        """
        Generates a deterministic, filesystem-safe filename from a URL using SHA-256.
        Preserves or infers the audio format extension (.mp3, .ogg, .wav).
        """
        clean_url = url.strip()
        url_hash = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:24]

        # 1. Extract file extension from URL path if available
        parsed = urllib.parse.urlparse(clean_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in (".mp3", ".ogg", ".wav", ".m4a", ".aac"):
            return f"audio_{url_hash}{suffix}"

        # 2. Inspect magic bytes if URL has no extension
        if data.startswith(b"OggS"):
            suffix = ".ogg"
        elif data.startswith(b"RIFF"):
            suffix = ".wav"
        else:
            suffix = ".mp3"

        return f"audio_{url_hash}{suffix}"

    def get_cached_path(self, url: str) -> Optional[Path]:
        """
        Returns the Path to the cached audio file if it exists and is non-empty.
        """
        if not url or not isinstance(url, str):
            return None

        clean_url = url.strip()
        url_hash = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:24]

        # Check for any matching hashed file in cache directory
        matches = list(self.cache_dir.glob(f"audio_{url_hash}.*"))
        if matches:
            file_path = matches[0]
            if file_path.is_file() and file_path.stat().st_size > 0:
                return file_path
            # Corrupted / 0-byte file: remove it
            file_path.unlink(missing_ok=True)

        return None

    def is_cached(self, url: str) -> bool:
        """Returns True if the audio file for this URL is cached on disk."""
        return self.get_cached_path(url) is not None

    def save_audio_bytes(self, url: str, data: bytes) -> Path:
        """
        Atomically saves validated binary audio bytes to the cache directory.
        
        Args:
            url: The audio URL (used for keying/filename generation).
            data: Binary audio payload.
            
        Returns:
            Path: The resulting cached file path.
            
        Raises:
            AudioError: If data is empty or cannot be written.
        """
        if not url or not isinstance(url, str):
            raise AudioError("Audio URL must be a non-empty string.")

        if not data or not isinstance(data, (bytes, bytearray)):
            raise AudioError(f"Cannot cache empty or invalid audio data for '{url}'.")

        filename = self._get_filename_for_url(url, data)
        target_path = self.cache_dir / filename

        try:
            # Atomic write: write to temp file first, then replace
            temp_fd, temp_path_str = tempfile.mkstemp(dir=str(self.cache_dir), prefix="temp_audio_")
            temp_path = Path(temp_path_str)
            with os.fdopen(temp_fd, "wb") as f:
                f.write(data)
            
            os.replace(temp_path, target_path)
            logger.debug("Cached audio for '%s' -> %s (%d bytes)", url, target_path.name, len(data))
            return target_path

        except Exception as exc:
            raise AudioError(f"Failed to write audio cache file for '{url}': {exc}") from exc

    def delete(self, url: str) -> bool:
        """Deletes a specific audio file from the cache."""
        path = self.get_cached_path(url)
        if path and path.exists():
            path.unlink(missing_ok=True)
            return True
        return False

    def clear(self) -> int:
        """Deletes all cached audio files in the directory. Returns count of removed files."""
        count = 0
        for item in self.cache_dir.glob("audio_*"):
            if item.is_file():
                item.unlink(missing_ok=True)
                count += 1
        return count

    def get_cache_size_bytes(self) -> int:
        """Returns the total disk size in bytes of all cached audio files."""
        total = 0
        for item in self.cache_dir.glob("audio_*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def cleanup_old_files(self, max_size_mb: int = 100) -> int:
        """
        Evicts oldest accessed audio files if total cache exceeds the maximum size budget.
        """
        max_bytes = max_size_mb * 1024 * 1024
        current_size = self.get_cache_size_bytes()
        if current_size <= max_bytes:
            return 0

        # Sort files by last access time (oldest first)
        files = [
            (f, f.stat().st_atime, f.stat().st_size)
            for f in self.cache_dir.glob("audio_*")
            if f.is_file()
        ]
        files.sort(key=lambda x: x[1])

        deleted_count = 0
        for file_path, _, file_size in files:
            if current_size <= max_bytes:
                break
            file_path.unlink(missing_ok=True)
            current_size -= file_size
            deleted_count += 1

        logger.info("Evicted %d audio files to maintain size limit.", deleted_count)
        return deleted_count
