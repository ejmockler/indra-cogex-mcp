"""
TTL (Time-To-Live) effectiveness tests.

Tests cache TTL behavior and optimization:
- TTL expiration correctness
- Optimal TTL determination
- TTL impact on hit rate
- Memory vs freshness tradeoff
"""

import asyncio
import logging

import pytest

from cogex_mcp.services.cache import CacheService
from tests.cache.conftest import MockQueryAdapter, simulate_realistic_workload

logger = logging.getLogger(__name__)


@pytest.mark.cache
@pytest.mark.asyncio
class TestCacheTTL:
    """Test cache TTL functionality and optimization."""

    async def test_ttl_expiration_behavior(self, short_ttl_cache):
        """Test TTL expiration works correctly."""
        cache = short_ttl_cache  # 5-second TTL
        adapter = MockQueryAdapter(cache)

        gene = "TP53"

        # First query - cache miss
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})
        stats1 = cache.get_stats()
        assert stats1.misses == 1

        # Immediate second query - cache hit
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})
        stats2 = cache.get_stats()
        assert stats2.hits == 1

        logger.info("Query cached successfully")

        # Wait for TTL expiration
        logger.info("Waiting for TTL expiration (5 seconds)...")
        await asyncio.sleep(6)

        # Third query - cache miss due to TTL
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})
        stats3 = cache.get_stats()

        # Should have 2 misses now (initial + after expiration)
        assert stats3.misses == 2

        # Track TTL expirations
        detailed = cache.get_detailed_stats()
        logger.info(f"TTL expirations: {detailed['ttl_expirations']}")
        assert detailed["ttl_expirations"] > 0

        logger.info("TTL expiration working correctly")

    async def test_ttl_no_premature_expiration(self, short_ttl_cache):
        """Test entries don't expire before TTL."""
        cache = short_ttl_cache
        adapter = MockQueryAdapter(cache)

        gene = "BRCA1"

        # Cache entry
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Query multiple times within TTL window
        for i in range(5):
            await asyncio.sleep(0.8)  # 0.8s * 5 = 4s < 5s TTL
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        stats = cache.get_stats()

        # Should have 1 miss (initial) and 5 hits (within TTL)
        assert stats.misses == 1
        assert stats.hits == 5

        logger.info("No premature expiration - TTL window respected")

    async def test_optimal_ttl_determination(self):
        """Determine optimal TTL through experimentation."""
        ttl_values = [60, 300, 600, 1800, 3600]  # 1min to 1hr
        results = []

        for ttl in ttl_values:
            cache = CacheService(max_size=100, ttl_seconds=ttl, enabled=True)
            adapter = MockQueryAdapter(cache)

            # Simulate realistic workload (10 seconds)
            hit_rate = await simulate_realistic_workload(adapter, duration=10)

            stats = cache.get_detailed_stats()
            results.append({
                "ttl": ttl,
                "hit_rate": hit_rate,
                "memory_usage": stats["total_memory_estimate"],
                "size": stats["size"],
                "ttl_expirations": stats["ttl_expirations"],
            })

            await cache.clear()

        # Log results
        logger.info("\nTTL optimization analysis:")
        logger.info(f"{'TTL (s)':<10} {'Hit Rate':<12} {'Size':<8} {'Expirations':<15} {'Memory (KB)'}")
        logger.info("-" * 70)

        for r in results:
            logger.info(
                f"{r['ttl']:<10} {r['hit_rate']:<11.1f}% {r['size']:<8} "
                f"{r['ttl_expirations']:<15} {r['memory_usage']/1024:<.1f}"
            )

        # Find optimal TTL (balance hit rate vs memory)
        # Prefer higher hit rate, but penalize excessive memory
        def score(r):
            return r["hit_rate"] - (r["memory_usage"] / 100000)  # Penalize large memory

        optimal = max(results, key=score)
        logger.info(f"\nOptimal TTL: {optimal['ttl']}s with {optimal['hit_rate']:.1f}% hit rate")

        # TTL should matter for hit rate
        hit_rates = [r["hit_rate"] for r in results]
        assert max(hit_rates) - min(hit_rates) > 0  # Some variation expected

    async def test_ttl_impact_on_memory_usage(self):
        """Test how TTL affects memory usage."""
        results = []

        # Test short vs long TTL
        ttl_configs = [
            ("short", 60),    # 1 minute
            ("medium", 600),  # 10 minutes
            ("long", 3600),   # 1 hour
        ]

        for name, ttl in ttl_configs:
            cache = CacheService(max_size=200, ttl_seconds=ttl, enabled=True)
            adapter = MockQueryAdapter(cache)

            # Fill cache with queries
            for i in range(50):
                await adapter.query_tool(
                    "cogex_query_gene_or_feature",
                    {"gene": f"GENE_{i}"}
                )

            stats = cache.get_detailed_stats()
            results.append({
                "ttl_name": name,
                "ttl_seconds": ttl,
                "memory_bytes": stats["total_memory_estimate"],
                "size": stats["size"],
            })

            await cache.clear()

        # Log results
        logger.info("\nTTL impact on memory:")
        for r in results:
            logger.info(
                f"  {r['ttl_name']:6s} ({r['ttl_seconds']:4d}s): "
                f"{r['memory_bytes']/1024:.1f} KB, size={r['size']}"
            )

    async def test_ttl_expiration_count_accuracy(self, short_ttl_cache):
        """Verify TTL expiration counting is accurate."""
        cache = short_ttl_cache
        adapter = MockQueryAdapter(cache)

        # Cache 3 different entries
        genes = ["TP53", "BRCA1", "EGFR"]
        for gene in genes:
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Wait for TTL expiration
        await asyncio.sleep(6)

        # Try to access all 3 (should all be expired)
        for gene in genes:
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        stats = cache.get_detailed_stats()

        logger.info(f"TTL expirations tracked: {stats['ttl_expirations']}")

        # Should have tracked 3 expirations
        assert stats["ttl_expirations"] == 3

    async def test_ttl_refresh_on_access(self):
        """Test if TTL is refreshed on access (it shouldn't be with TTLCache)."""
        cache = CacheService(max_size=100, ttl_seconds=5, enabled=True)
        adapter = MockQueryAdapter(cache)

        gene = "TP53"

        # Initial cache
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Access multiple times within TTL
        for _ in range(3):
            await asyncio.sleep(1.5)  # 4.5s total
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Wait a bit more (total > 5s from initial)
        await asyncio.sleep(1)

        # Should be expired (TTL not refreshed on access)
        await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        stats = cache.get_stats()

        # Should have 1 initial miss + 1 expiration miss
        assert stats.misses >= 2

        logger.info("Confirmed: TTL is NOT refreshed on access (expected behavior)")

    async def test_mixed_ttl_workload(self):
        """Test cache behavior with mixed access patterns and TTL."""
        cache = CacheService(max_size=100, ttl_seconds=10, enabled=True)
        adapter = MockQueryAdapter(cache)

        # Pattern: Some hot queries, some cold queries
        hot_gene = "TP53"
        cold_genes = [f"GENE_{i}" for i in range(20)]

        # Phase 1: Fill cache (0-5s)
        for gene in cold_genes:
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Phase 2: Hot queries (5-10s)
        for _ in range(20):
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": hot_gene})
            await asyncio.sleep(0.25)

        # Phase 3: Wait for some cold entries to expire (10-15s)
        await asyncio.sleep(6)

        # Phase 4: Try to access cold entries (should be expired)
        for gene in cold_genes[:5]:
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        stats = cache.get_detailed_stats()

        logger.info("\nMixed TTL workload results:")
        logger.info(f"  Total queries: {adapter.query_count}")
        logger.info(f"  Cache hits: {stats['hits']}")
        logger.info(f"  Cache misses: {stats['misses']}")
        logger.info(f"  TTL expirations: {stats['ttl_expirations']}")
        logger.info(f"  Hit rate: {stats['hit_rate']:.1f}%")

        # Should have some TTL expirations
        assert stats["ttl_expirations"] > 0

    async def test_ttl_vs_eviction(self, small_cache):
        """Compare TTL expirations vs LRU evictions."""
        cache = small_cache  # Max size: 10
        cache.ttl_seconds = 30  # Long TTL
        adapter = MockQueryAdapter(cache)

        # Fill cache to capacity
        for i in range(10):
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": f"GENE_{i}"})

        # Add more entries to trigger eviction
        for i in range(10, 20):
            await adapter.query_tool("cogex_query_gene_or_feature", {"gene": f"GENE_{i}"})

        stats = cache.get_detailed_stats()

        logger.info("\nTTL vs Eviction analysis:")
        logger.info(f"  Evictions: {stats['evictions']}")
        logger.info(f"  TTL expirations: {stats['ttl_expirations']}")

        # Should have evictions but no TTL expirations (TTL is long)
        assert stats["evictions"] > 0
        assert stats["ttl_expirations"] == 0

        logger.info("LRU eviction working correctly (before TTL expiration)")


@pytest.mark.cache
class TestTTLRecommendations:
    """Generate TTL optimization recommendations."""

    async def test_generate_ttl_recommendations(self):
        """Generate recommendations based on TTL analysis."""
        recommendations = []

        # Test configuration
        cache = CacheService(max_size=100, ttl_seconds=300, enabled=True)
        adapter = MockQueryAdapter(cache)

        # Run workload
        await simulate_realistic_workload(adapter, duration=10)

        stats = cache.get_detailed_stats()

        # Analyze TTL effectiveness
        ttl_expirations = stats["ttl_expirations"]
        evictions = stats["evictions"]

        if ttl_expirations > evictions * 2:
            recommendations.append(
                "HIGH TTL EXPIRATIONS: Consider increasing TTL to reduce re-fetching"
            )

        if evictions > ttl_expirations * 2:
            recommendations.append(
                "HIGH EVICTIONS: Consider increasing cache size or reducing TTL"
            )

        if stats["capacity_utilization"] > 90:
            recommendations.append(
                "CACHE NEAR CAPACITY: Consider increasing max_size"
            )

        if stats["hit_rate"] < 50:
            recommendations.append(
                "LOW HIT RATE: Consider increasing both cache size and TTL"
            )

        logger.info("\nTTL Optimization Recommendations:")
        if recommendations:
            for rec in recommendations:
                logger.info(f"  - {rec}")
        else:
            logger.info("  - Cache TTL configuration appears optimal")

        logger.info("\nCurrent configuration:")
        logger.info(f"  TTL: {cache.ttl_seconds}s")
        logger.info(f"  Max size: {cache.max_size}")
        logger.info(f"  Hit rate: {stats['hit_rate']:.1f}%")
        logger.info(f"  Capacity utilization: {stats['capacity_utilization']:.1f}%")
