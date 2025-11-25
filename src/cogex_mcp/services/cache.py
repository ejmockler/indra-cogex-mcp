"""
Thread-safe LRU cache with TTL support.

Provides high-performance caching for frequently accessed entities like:
- Gene information
- Ontology terms
- Pathway data
- ID mappings
"""

import asyncio
import logging
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

from cogex_mcp.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheService:
    """
    Thread-safe LRU cache with TTL (Time-To-Live) support.

    Features:
    - Automatic expiration based on TTL
    - LRU eviction when full
    - Statistics tracking
    - Thread-safe operations
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        enabled: bool = True,
    ):
        """
        Initialize cache service.

        Args:
            max_size: Maximum number of cached items
            ttl_seconds: Time-to-live for cache entries in seconds
            enabled: Whether caching is enabled
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

        # Thread-safe TTL cache
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = CacheStats(max_size=max_size)
        self._last_stats_log = time.time()

        # Enhanced metrics tracking
        self._hit_rate_window = deque(maxlen=1000)  # Last 1000 operations
        self._key_access_count = Counter()  # Track hot keys
        self._ttl_expiration_count = 0
        self._key_sizes: dict[str, int] = {}  # Track key sizes
        self._value_sizes: dict[str, int] = {}  # Track value sizes

        logger.info(
            f"CacheService initialized: max_size={max_size}, ttl={ttl_seconds}s, enabled={enabled}"
        )

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.enabled:
            return None

        async with self._lock:
            try:
                value = self._cache[key]
                self._stats.hits += 1
                self._hit_rate_window.append(True)  # Hit
                self._key_access_count[key] += 1
                logger.debug(f"Cache HIT: {key}")
                return value
            except KeyError:
                self._stats.misses += 1
                self._hit_rate_window.append(False)  # Miss

                # Check if this was a TTL expiration
                if key in self._key_sizes:
                    self._ttl_expiration_count += 1
                    # Clean up size tracking for expired keys
                    del self._key_sizes[key]
                    if key in self._value_sizes:
                        del self._value_sizes[key]

                logger.debug(f"Cache MISS: {key}")
                return None

    async def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if not self.enabled:
            return

        async with self._lock:
            # Track evictions if cache is full
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._stats.evictions += 1

            self._cache[key] = value
            self._stats.size = len(self._cache)

            # Track key and value sizes
            self._key_sizes[key] = sys.getsizeof(key)
            self._value_sizes[key] = sys.getsizeof(value)

            logger.debug(f"Cache SET: {key}")

    async def delete(self, key: str) -> None:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete
        """
        if not self.enabled:
            return

        async with self._lock:
            try:
                del self._cache[key]
                self._stats.size = len(self._cache)
                logger.debug(f"Cache DELETE: {key}")
            except KeyError:
                pass

    async def clear(self) -> None:
        """Clear all cache entries."""
        if not self.enabled:
            return

        async with self._lock:
            self._cache.clear()
            self._stats.size = 0
            logger.info("Cache cleared")

    async def get_or_set(
        self,
        key: str,
        factory: callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Get value from cache, or compute and cache it if missing.

        Args:
            key: Cache key
            factory: Async function to compute value if not cached
            *args: Positional arguments for factory
            **kwargs: Keyword arguments for factory

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory(*args, **kwargs)
        else:
            value = factory(*args, **kwargs)

        # Cache it
        await self.set(key, value)

        return value

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats instance
        """
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            evictions=self._stats.evictions,
            size=len(self._cache),
            max_size=self.max_size,
        )

    def get_detailed_stats(self) -> dict[str, Any]:
        """
        Get enhanced statistics with detailed metrics.

        Returns:
            Dictionary containing comprehensive cache metrics
        """
        stats = self.get_stats()

        # Calculate detailed metrics
        detailed = {
            "hits": stats.hits,
            "misses": stats.misses,
            "evictions": stats.evictions,
            "size": stats.size,
            "max_size": stats.max_size,
            "hit_rate": stats.hit_rate * 100,  # Convert to percentage
            "hit_rate_recent": self._calculate_recent_hit_rate(),
            "hot_keys": self._key_access_count.most_common(10),
            "ttl_expirations": self._ttl_expiration_count,
            "avg_key_size": self._calculate_avg_key_size(),
            "avg_value_size": self._calculate_avg_value_size(),
            "total_memory_estimate": self._estimate_total_memory(),
            "capacity_utilization": (stats.size / stats.max_size * 100)
            if stats.max_size > 0
            else 0,
        }

        return detailed

    def _calculate_recent_hit_rate(self) -> float:
        """Calculate hit rate for last N operations."""
        if not self._hit_rate_window:
            return 0.0
        hits = sum(1 for x in self._hit_rate_window if x)
        return hits / len(self._hit_rate_window) * 100

    def _calculate_avg_key_size(self) -> float:
        """Calculate average key size in bytes."""
        if not self._key_sizes:
            return 0.0
        return sum(self._key_sizes.values()) / len(self._key_sizes)

    def _calculate_avg_value_size(self) -> float:
        """Calculate average value size in bytes."""
        if not self._value_sizes:
            return 0.0
        return sum(self._value_sizes.values()) / len(self._value_sizes)

    def _estimate_total_memory(self) -> int:
        """Estimate total memory usage in bytes."""
        key_memory = sum(self._key_sizes.values())
        value_memory = sum(self._value_sizes.values())
        return key_memory + value_memory

    def reset_stats(self) -> None:
        """Reset all statistics counters."""
        self._stats.hits = 0
        self._stats.misses = 0
        self._stats.evictions = 0
        self._ttl_expiration_count = 0
        self._hit_rate_window.clear()
        self._key_access_count.clear()
        logger.info("Cache statistics reset")

    async def log_stats_if_needed(self) -> None:
        """Log statistics if interval has passed."""
        if not settings.cache_stats_interval:
            return

        now = time.time()
        if now - self._last_stats_log >= settings.cache_stats_interval:
            stats = self.get_stats()
            logger.info(
                f"Cache stats: size={stats.size}/{stats.max_size}, "
                f"hit_rate={stats.hit_rate:.2%}, "
                f"hits={stats.hits}, misses={stats.misses}, evictions={stats.evictions}"
            )
            self._last_stats_log = now

    def make_key(self, prefix: str, *parts: Any) -> str:
        """
        Create cache key from components.

        Args:
            prefix: Key prefix (e.g., 'gene:', 'drug:')
            *parts: Key components

        Returns:
            Cache key string
        """
        # Convert all parts to strings and join
        key_parts = [str(part) for part in parts if part is not None]
        return f"{prefix}{'|'.join(key_parts)}"


# Global cache instance
_cache: CacheService | None = None


def get_cache() -> CacheService:
    """
    Get global cache service instance (singleton).

    Returns:
        CacheService instance
    """
    global _cache

    if _cache is None:
        _cache = CacheService(
            max_size=settings.cache_max_size,
            ttl_seconds=settings.cache_ttl_seconds,
            enabled=settings.cache_enabled,
        )

    return _cache
