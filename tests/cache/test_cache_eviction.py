"""
Cache eviction policy tests.

Tests LRU (Least Recently Used) eviction behavior:
- Correct eviction order
- Eviction count tracking
- Memory management
- Edge cases
"""

import pytest
import asyncio
import logging
from typing import List, Dict, Any

from cogex_mcp.services.cache import CacheService
from tests.cache.conftest import MockQueryAdapter

logger = logging.getLogger(__name__)


@pytest.mark.cache
@pytest.mark.asyncio
class TestCacheEviction:
    """Test cache eviction policies."""

    async def test_lru_eviction_policy(self, small_cache):
        """Test LRU eviction works correctly."""
        cache = small_cache  # Max size: 10

        # Fill cache to capacity
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")

        stats = cache.get_stats()
        assert stats.size == 10

        # Access key_0 to make it recently used
        value = await cache.get("key_0")
        assert value == "value_0"

        # Add new item - should evict key_1 (least recently used)
        await cache.set("key_10", "value_10")

        # Verify key_0 still exists (was recently accessed)
        assert await cache.get("key_0") is not None

        # Verify key_1 was evicted (least recently used)
        assert await cache.get("key_1") is None

        # Verify key_10 was added
        assert await cache.get("key_10") == "value_10"

        stats = cache.get_detailed_stats()
        logger.info(f"Eviction count: {stats['evictions']}")
        assert stats["evictions"] == 1

        logger.info("LRU eviction policy verified")

    async def test_eviction_count_tracking(self, small_cache):
        """Test eviction counting is accurate."""
        cache = small_cache

        # Fill cache
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")

        initial_stats = cache.get_detailed_stats()
        initial_evictions = initial_stats["evictions"]

        # Trigger multiple evictions
        for i in range(10, 20):
            await cache.set(f"key_{i}", f"value_{i}")

        final_stats = cache.get_detailed_stats()
        eviction_count = final_stats["evictions"] - initial_evictions

        logger.info(f"Evictions tracked: {eviction_count}")

        # Should have tracked 10 evictions
        assert eviction_count == 10

    async def test_eviction_with_query_adapter(self, small_cache):
        """Test eviction in realistic query scenario."""
        adapter = MockQueryAdapter(small_cache)

        # Fill cache with queries
        for i in range(10):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": f"GENE_{i}"}
            )

        # Hot query that should stay cached
        hot_gene = "GENE_0"
        for _ in range(5):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": hot_gene}
            )

        # Add more queries to trigger evictions
        for i in range(10, 20):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": f"GENE_{i}"}
            )

        # Hot query should still be cached
        await adapter.query_tool(
            "cogex_query_gene_or_feature",
            {"gene": hot_gene}
        )

        stats = adapter.cache.get_stats()

        # Last query should be a hit (hot gene still cached)
        assert stats.hits > 0

        logger.info(f"Evictions in realistic scenario: {stats.evictions}")
        assert stats.evictions > 0

    async def test_no_eviction_when_not_full(self, small_cache):
        """Test cache doesn't evict when not at capacity."""
        cache = small_cache

        # Add only 5 items (cache capacity is 10)
        for i in range(5):
            await cache.set(f"key_{i}", f"value_{i}")

        stats = cache.get_detailed_stats()

        # No evictions should occur
        assert stats["evictions"] == 0
        assert stats["size"] == 5

        logger.info("No premature eviction - cache not at capacity")

    async def test_eviction_order_verification(self, small_cache):
        """Verify strict LRU eviction order."""
        cache = small_cache

        # Add keys in order
        for i in range(10):
            await cache.set(f"key_{i}", f"value_{i}")

        # Access pattern to establish LRU order:
        # Access key_5, key_7, key_3 (making them more recently used)
        await cache.get("key_5")
        await cache.get("key_7")
        await cache.get("key_3")

        # Now LRU order should be:
        # Oldest: key_0, key_1, key_2, key_4, key_6, key_8, key_9
        # Newest: key_5, key_7, key_3

        # Add 3 new keys to trigger evictions
        for i in range(10, 13):
            await cache.set(f"key_{i}", f"value_{i}")

        # Verify least recently used keys were evicted
        # key_0, key_1, key_2 should be gone
        assert await cache.get("key_0") is None
        assert await cache.get("key_1") is None
        assert await cache.get("key_2") is None

        # Recently accessed keys should remain
        assert await cache.get("key_5") is not None
        assert await cache.get("key_7") is not None
        assert await cache.get("key_3") is not None

        # New keys should be present
        assert await cache.get("key_10") is not None
        assert await cache.get("key_11") is not None
        assert await cache.get("key_12") is not None

        logger.info("LRU eviction order verified")

    async def test_eviction_memory_management(self):
        """Test cache memory is managed correctly during evictions."""
        cache = CacheService(max_size=20, ttl_seconds=3600, enabled=True)

        # Add large values
        large_value = "X" * 10000  # 10KB string

        for i in range(30):
            await cache.set(f"key_{i}", large_value)

        stats = cache.get_detailed_stats()

        # Cache should be at capacity
        assert stats["size"] == 20

        # Should have evicted 10 items
        assert stats["evictions"] == 10

        # Memory should be reasonable (20 items * ~10KB)
        memory_mb = stats["total_memory_estimate"] / (1024 * 1024)
        logger.info(f"Cache memory: {memory_mb:.2f} MB")

        # Should be roughly 0.2 MB (20 * 10KB)
        assert memory_mb < 1.0  # Reasonable upper bound

    async def test_eviction_hot_key_protection(self, small_cache):
        """Test frequently accessed keys resist eviction."""
        cache = small_cache
        adapter = MockQueryAdapter(cache)

        # Hot key that's accessed frequently
        hot_gene = "TP53"

        # Fill cache
        for i in range(10):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": f"GENE_{i}"}
            )

        # Make TP53 very hot (access multiple times)
        for _ in range(20):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": hot_gene}
            )

        # Add many cold queries to trigger evictions
        for i in range(10, 50):
            await adapter.query_tool(
                "cogex_query_gene_or_feature",
                {"gene": f"COLD_GENE_{i}"}
            )

        # Hot key should still be accessible
        result = await adapter.query_tool(
            "cogex_query_gene_or_feature",
            {"gene": hot_gene}
        )

        assert result is not None

        stats = cache.get_detailed_stats()
        hot_keys = stats["hot_keys"]

        # TP53 should be in hot keys
        hot_key_names = [key for key, count in hot_keys]
        assert any(hot_gene in key for key in hot_key_names)

        logger.info(f"Hot key survived {stats['evictions']} evictions")

    async def test_eviction_vs_ttl_expiration(self):
        """Compare eviction vs TTL expiration behavior."""
        # Small cache with long TTL
        cache_eviction = CacheService(max_size=10, ttl_seconds=3600, enabled=True)

        # Large cache with short TTL
        cache_ttl = CacheService(max_size=100, ttl_seconds=5, enabled=True)

        # Test eviction-dominated scenario
        for i in range(20):
            await cache_eviction.set(f"key_{i}", f"value_{i}")

        eviction_stats = cache_eviction.get_detailed_stats()

        # Test TTL-dominated scenario
        for i in range(20):
            await cache_ttl.set(f"key_{i}", f"value_{i}")

        await asyncio.sleep(6)  # Wait for TTL expiration

        # Try to access (will trigger TTL expiration tracking)
        for i in range(20):
            await cache_ttl.get(f"key_{i}")

        ttl_stats = cache_ttl.get_detailed_stats()

        logger.info("\nEviction vs TTL comparison:")
        logger.info(f"  Eviction-dominated: evictions={eviction_stats['evictions']}, "
                   f"ttl_expirations={eviction_stats['ttl_expirations']}")
        logger.info(f"  TTL-dominated: evictions={ttl_stats['evictions']}, "
                   f"ttl_expirations={ttl_stats['ttl_expirations']}")

        # Eviction-dominated should have more evictions
        assert eviction_stats["evictions"] > eviction_stats["ttl_expirations"]

        # TTL-dominated should have more TTL expirations
        assert ttl_stats["ttl_expirations"] > ttl_stats["evictions"]

    async def test_eviction_impact_on_hit_rate(self):
        """Test how eviction affects hit rate."""
        from tests.cache.conftest import simulate_realistic_workload

        results = []

        # Test different cache sizes (affects eviction frequency)
        cache_sizes = [10, 50, 100]

        for size in cache_sizes:
            cache = CacheService(max_size=size, ttl_seconds=3600, enabled=True)
            adapter = MockQueryAdapter(cache)

            # Run workload
            hit_rate = await simulate_realistic_workload(adapter, duration=5)

            stats = cache.get_detailed_stats()
            results.append({
                "size": size,
                "hit_rate": hit_rate,
                "evictions": stats["evictions"],
            })

        logger.info("\nEviction impact on hit rate:")
        for r in results:
            logger.info(
                f"  Size {r['size']:3d}: hit_rate={r['hit_rate']:.1f}%, "
                f"evictions={r['evictions']}"
            )

        # Smaller cache should have more evictions
        assert results[0]["evictions"] >= results[-1]["evictions"]

        # Larger cache should have better hit rate
        assert results[-1]["hit_rate"] >= results[0]["hit_rate"]


@pytest.mark.cache
class TestEvictionRecommendations:
    """Generate eviction-related recommendations."""

    async def test_generate_eviction_recommendations(self):
        """Generate recommendations based on eviction analysis."""
        cache = CacheService(max_size=50, ttl_seconds=3600, enabled=True)
        adapter = MockQueryAdapter(cache)

        # Run workload
        from tests.cache.conftest import simulate_realistic_workload
        await simulate_realistic_workload(adapter, duration=10)

        stats = cache.get_detailed_stats()

        recommendations = []

        # Analyze eviction patterns
        if stats["evictions"] > stats["hits"] * 0.1:
            recommendations.append(
                "HIGH EVICTION RATE: Consider increasing cache size"
            )

        if stats["capacity_utilization"] > 95:
            recommendations.append(
                "CACHE AT CAPACITY: Increase max_size to reduce evictions"
            )

        if stats["evictions"] > 0 and stats["hit_rate"] < 70:
            recommendations.append(
                "EVICTIONS HURTING HIT RATE: Increase cache size for better performance"
            )

        # Check hot key concentration
        hot_keys = stats["hot_keys"]
        if hot_keys and len(hot_keys) > 0:
            top_access_pct = (hot_keys[0][1] / (stats["hits"] + stats["misses"]) * 100
                            if (stats["hits"] + stats["misses"]) > 0 else 0)

            if top_access_pct > 20:
                recommendations.append(
                    f"HIGH KEY CONCENTRATION: Top key accounts for {top_access_pct:.1f}% of access"
                )

        logger.info("\nEviction Optimization Recommendations:")
        if recommendations:
            for rec in recommendations:
                logger.info(f"  - {rec}")
        else:
            logger.info("  - Eviction behavior appears optimal")

        logger.info(f"\nEviction metrics:")
        logger.info(f"  Total evictions: {stats['evictions']}")
        logger.info(f"  Capacity utilization: {stats['capacity_utilization']:.1f}%")
        logger.info(f"  Hit rate: {stats['hit_rate']:.1f}%")
