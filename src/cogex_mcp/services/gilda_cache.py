"""
File-based cache for GILDA grounding results.

Provides persistent caching of entity grounding results with:
- Triple limits: age (days), count (entries), size (MB)
- LRU eviction strategy based on file modification time
- Probabilistic cleanup to minimize overhead
- MD5 hash-based cache keys for safe filenames
- Graceful error handling (never crashes)
"""

import hashlib
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GildaCache:
    """
    Simple file-based cache for GILDA grounding results.

    Features:
    - LRU eviction based on file modification time
    - Triple limits: age, count, total size
    - Probabilistic cleanup to avoid overhead on every write
    - No external dependencies (no Redis)
    - Graceful error handling (never crashes, just skips caching)

    Cache file format:
        {
            "term": "original term",
            "results": [...],  # GILDA grounding results
            "cached_at": "2025-11-26T12:00:00.123456"  # ISO8601 timestamp
        }
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_entries: int = 10_000,
        max_size_mb: int = 100,
        max_age_days: int = 7,
        deterministic_cleanup: bool = False,
    ):
        """
        Initialize cache.

        Args:
            cache_dir: Directory for cache files (default: ~/.cache/gilda)
            max_entries: Maximum number of cached terms
            max_size_mb: Maximum total disk space in MB
            max_age_days: Maximum age of cached entries in days
            deterministic_cleanup: If True, always cleanup when over limit (for tests).
                                   If False, use probabilistic cleanup (production).
        """
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "gilda")
        self.max_entries = max_entries
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_age_days = max_age_days
        self.deterministic_cleanup = deterministic_cleanup

        # Create cache directory if it doesn't exist
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(
                f"GildaCache initialized: dir={self.cache_dir}, "
                f"max_entries={max_entries}, max_size={max_size_mb}MB, "
                f"max_age={max_age_days}d"
            )
        except OSError as e:
            logger.warning(f"Failed to create cache directory {self.cache_dir}: {e}")

        # Run cleanup on init to enforce limits immediately
        self._cleanup()

    def _cache_key(self, term: str) -> str:
        """
        Generate cache filename from term using MD5 hash.

        Args:
            term: Term to hash

        Returns:
            MD5 hash string (32 characters)
        """
        return hashlib.md5(term.lower().encode()).hexdigest()

    def get(self, term: str, max_age_hours: int = 24) -> Optional[list[dict]]:
        """
        Get cached GILDA results if fresh enough.

        Args:
            term: Term to look up
            max_age_hours: Maximum age in hours (default: 24)

        Returns:
            Cached results or None if not found/expired/corrupted
        """
        cache_file = self.cache_dir / f"{self._cache_key(term)}.json"

        # Check if file exists
        if not cache_file.exists():
            logger.debug(f"Cache miss (not found): '{term}'")
            return None

        try:
            # Check age using file modification time
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - mtime

            if age > timedelta(hours=max_age_hours):
                logger.debug(
                    f"Cache miss (expired): '{term}' (age: {age.total_seconds() / 3600:.1f}h)"
                )
                return None

            # Load and return results
            with open(cache_file, "r") as f:
                data = json.load(f)
                results = data.get("results")

                if results is not None:
                    logger.debug(
                        f"Cache hit: '{term}' ({len(results)} results, "
                        f"age: {age.total_seconds() / 3600:.1f}h)"
                    )
                    return results
                else:
                    logger.warning(f"Cache file missing 'results' key: {cache_file}")
                    return None

        except (json.JSONDecodeError, OSError, KeyError) as e:
            # Corrupted cache file, ignore and continue
            logger.warning(f"Cache read error for '{term}': {e}")
            return None

    def set(self, term: str, results: list[dict]) -> None:
        """
        Cache GILDA results.

        Args:
            term: Term that was grounded
            results: GILDA grounding results
        """
        cache_file = self.cache_dir / f"{self._cache_key(term)}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "term": term,
                        "results": results,
                        "cached_at": datetime.now().isoformat(),
                    },
                    f,
                )
            logger.debug(f"Cache set: '{term}' ({len(results)} results)")

        except OSError as e:
            # Can't write cache, continue without caching
            logger.warning(f"Cache write error for '{term}': {e}")
            return

        # Cleanup strategy: deterministic (tests) vs probabilistic (production)
        if self.deterministic_cleanup:
            # Always cleanup when over limit (for tests)
            try:
                cache_files = list(self.cache_dir.glob("*.json"))
                if len(cache_files) > self.max_entries:
                    logger.debug("Triggering deterministic cache cleanup (over limit)")
                    self._cleanup()
            except OSError:
                pass  # Ignore errors during deterministic check
        else:
            # Trigger cleanup probabilistically (1% chance on each write)
            # This amortizes cleanup cost across many writes
            if random.random() < 0.01:
                logger.debug("Triggering probabilistic cache cleanup")
                self._cleanup()

    def _cleanup(self) -> None:
        """
        Clean cache based on multiple criteria (in order):
        1. Remove entries older than max_age_days
        2. Limit total number of entries (LRU eviction)
        3. Limit total disk space (LRU eviction)

        Uses file modification time for LRU ordering.
        Gracefully handles all errors to avoid breaking the cache.
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
        except OSError as e:
            logger.warning(f"Cache cleanup error (glob failed): {e}")
            return

        if not cache_files:
            logger.debug("Cache cleanup: no files to clean")
            return

        # Get file stats (mtime, size) for all cache files
        file_stats = []
        cutoff_time = datetime.now() - timedelta(days=self.max_age_days)

        for cache_file in cache_files:
            try:
                stat = cache_file.stat()
                file_stats.append(
                    {
                        "path": cache_file,
                        "mtime": datetime.fromtimestamp(stat.st_mtime),
                        "size": stat.st_size,
                    }
                )
            except OSError as e:
                logger.debug(f"Cache cleanup: failed to stat {cache_file}: {e}")
                continue

        # Sort by mtime (oldest first) for LRU eviction
        file_stats.sort(key=lambda x: x["mtime"])

        # Step 1: Remove old entries
        files_to_keep = []
        removed_by_age = 0

        for stat in file_stats:
            if stat["mtime"] < cutoff_time:
                try:
                    stat["path"].unlink()
                    removed_by_age += 1
                    logger.debug(
                        f"Cache cleanup: removed old file {stat['path'].name} "
                        f"(age: {(datetime.now() - stat['mtime']).days}d)"
                    )
                except OSError as e:
                    logger.debug(f"Cache cleanup: failed to remove {stat['path']}: {e}")
            else:
                files_to_keep.append(stat)

        if removed_by_age > 0:
            logger.info(f"Cache cleanup: removed {removed_by_age} old entries")

        # Step 2: Enforce max entries (remove oldest if over limit)
        removed_by_count = 0

        if len(files_to_keep) > self.max_entries:
            to_remove = files_to_keep[: len(files_to_keep) - self.max_entries]
            for stat in to_remove:
                try:
                    stat["path"].unlink()
                    removed_by_count += 1
                    logger.debug(
                        f"Cache cleanup: removed by count limit {stat['path'].name}"
                    )
                except OSError as e:
                    logger.debug(f"Cache cleanup: failed to remove {stat['path']}: {e}")

            files_to_keep = files_to_keep[-self.max_entries :]

            if removed_by_count > 0:
                logger.info(
                    f"Cache cleanup: removed {removed_by_count} entries (count limit)"
                )

        # Step 3: Enforce max size (remove oldest until under limit)
        current_size = sum(stat["size"] for stat in files_to_keep)
        removed_by_size = 0

        while current_size > self.max_size_bytes and files_to_keep:
            removed = files_to_keep.pop(0)
            try:
                removed["path"].unlink()
                current_size -= removed["size"]
                removed_by_size += 1
                logger.debug(
                    f"Cache cleanup: removed by size limit {removed['path'].name}"
                )
            except OSError as e:
                logger.debug(f"Cache cleanup: failed to remove {removed['path']}: {e}")

        if removed_by_size > 0:
            logger.info(
                f"Cache cleanup: removed {removed_by_size} entries "
                f"(size limit: {self.max_size_bytes / (1024 * 1024):.1f}MB)"
            )

        # Log final cache state
        total_removed = removed_by_age + removed_by_count + removed_by_size
        if total_removed > 0:
            logger.info(
                f"Cache cleanup complete: removed {total_removed} total entries, "
                f"{len(files_to_keep)} remaining, "
                f"{current_size / (1024 * 1024):.2f}MB used"
            )

    def clear(self) -> None:
        """
        Clear entire cache.

        Removes all cache files from the cache directory.
        Gracefully handles errors during deletion.
        """
        removed_count = 0
        error_count = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                removed_count += 1
            except OSError as e:
                error_count += 1
                logger.debug(f"Cache clear: failed to remove {cache_file}: {e}")

        logger.info(
            f"Cache cleared: removed {removed_count} files "
            f"({error_count} errors)" if error_count > 0 else f"Cache cleared: removed {removed_count} files"
        )
