"""
Cache hit rate analysis tests.

Tests cache effectiveness with different query patterns:
- Repeated queries
- Mixed query patterns
- Tool-specific patterns
- Workload simulations
"""

import pytest
import asyncio
import logging
from typing import Dict, Any

from cogex_mcp.services.cache import CacheService
from tests.cache.conftest import simulate_realistic_workload

logger = logging.getLogger(__name__)


@pytest.mark.cache
@pytest.mark.asyncio
class TestCacheHitRate:
    """Test cache hit rate under various scenarios."""

    async def test_cache_hit_rate_with_repeated_queries(self, mock_query_adapter):
        """Test hit rate improves with repeated queries."""
        gene = "TP53"

        # Cold cache - all misses
        for i in range(10):
            await mock_query_adapter.query_tool(
                "cogex_query_gene_or_feature", {"gene": gene}
            )

        stats = mock_query_adapter.cache.get_detailed_stats()
        initial_hit_rate = stats["hit_rate_recent"]

        # Warm cache - should see hits
        for i in range(100):
            await mock_query_adapter.query_tool(
                "cogex_query_gene_or_feature", {"gene": gene}
            )

        stats = mock_query_adapter.cache.get_detailed_stats()
        final_hit_rate = stats["hit_rate_recent"]

        assert final_hit_rate > initial_hit_rate
        assert final_hit_rate > 80.0  # Should be high with repeated queries

        logger.info(
            f"Hit rate improved: {initial_hit_rate:.1f}% → {final_hit_rate:.1f}%"
        )
        logger.info(f"Cache savings: {mock_query_adapter.get_metrics()['cache_savings']:.1f}%")

    async def test_cache_effectiveness_across_tools(self, mock_query_adapter):
        """Test cache effectiveness for different tool types."""
        tool_tests = [
            ("cogex_query_gene_or_feature", {"gene": "TP53"}),
            ("cogex_query_pathway", {"pathway_id": "R-HSA-109581"}),
            ("cogex_query_drug_or_effect", {"drug": "imatinib"}),
        ]

        results = {}

        for tool_name, query in tool_tests:
            # Clear cache for clean test
            await mock_query_adapter.cache.clear()
            mock_query_adapter.cache.reset_stats()

            # Run 50 queries (same query repeated)
            for i in range(50):
                await mock_query_adapter.query_tool(tool_name, query)

            stats = mock_query_adapter.cache.get_detailed_stats()
            hit_rate = stats["hit_rate_recent"]

            results[tool_name] = {
                "hit_rate": hit_rate,
                "hits": stats["hits"],
                "misses": stats["misses"],
            }

            logger.info(f"{tool_name}: hit_rate={hit_rate:.1f}%")
            assert hit_rate > 90.0  # Should be very high for repeated queries

        # Log summary
        logger.info("\nCache effectiveness by tool:")
        for tool, metrics in results.items():
            logger.info(
                f"  {tool}: {metrics['hit_rate']:.1f}% "
                f"(hits={metrics['hits']}, misses={metrics['misses']})"
            )

    async def test_cache_hit_rate_with_mixed_queries(self, mock_query_adapter, known_entities):
        """Test hit rate with mixed query patterns."""
        # Mix of repeated and unique queries
        genes = known_entities["genes"]

        # Pattern: 70% repeated, 30% unique
        queries = []

        # Add 70 repeated queries (same 5 genes)
        for _ in range(14):  # 14 * 5 = 70
            for gene in genes[:5]:
                queries.append({"gene": gene})

        # Add 30 unique queries
        for i in range(30):
            queries.append({"gene": f"UNIQUE_GENE_{i}"})

        # Shuffle to simulate realistic pattern
        import random
        random.shuffle(queries)

        # Execute all queries
        for params in queries:
            await mock_query_adapter.query_tool("cogex_query_gene_or_feature", params)

        stats = mock_query_adapter.cache.get_detailed_stats()
        hit_rate = stats["hit_rate"]

        logger.info(f"Mixed query hit rate: {hit_rate:.1f}%")
        logger.info(f"Total queries: {len(queries)}")
        logger.info(f"Cache hits: {stats['hits']}, misses: {stats['misses']}")

        # With 70% repeated queries, hit rate should be > 60%
        # (first occurrence is miss, subsequent are hits)
        assert hit_rate > 60.0

    async def test_cache_hot_keys_tracking(self, mock_query_adapter, known_entities):
        """Test hot key tracking functionality."""
        genes = known_entities["genes"]

        # Create access pattern with clear hot keys
        # TP53: 50 queries, BRCA1: 30 queries, EGFR: 20 queries, others: 5 each
        access_pattern = (
            [{"gene": "TP53"}] * 50
            + [{"gene": "BRCA1"}] * 30
            + [{"gene": "EGFR"}] * 20
            + [{"gene": "MAPK1"}] * 5
            + [{"gene": "AKT1"}] * 5
        )

        # Execute queries
        for params in access_pattern:
            await mock_query_adapter.query_tool("cogex_query_gene_or_feature", params)

        stats = mock_query_adapter.cache.get_detailed_stats()
        hot_keys = stats["hot_keys"]

        logger.info("Hot keys (most frequently accessed):")
        for key, count in hot_keys[:5]:
            logger.info(f"  {key}: {count} accesses")

        # Verify hot keys are tracked correctly
        assert len(hot_keys) > 0

        # Top key should contain TP53
        top_key = hot_keys[0][0]
        assert "TP53" in top_key

    async def test_cache_hit_rate_realistic_workload(self, mock_query_adapter):
        """Test cache with realistic query workload simulation."""
        # Run realistic workload for 10 seconds
        hit_rate = await simulate_realistic_workload(mock_query_adapter, duration=10)

        stats = mock_query_adapter.cache.get_detailed_stats()
        metrics = mock_query_adapter.get_metrics()

        logger.info("\nRealistic workload results:")
        logger.info(f"  Duration: 10 seconds")
        logger.info(f"  Total queries: {metrics['total_queries']}")
        logger.info(f"  Backend calls: {metrics['backend_calls']}")
        logger.info(f"  Cache hit rate: {hit_rate:.1f}%")
        logger.info(f"  Cache savings: {metrics['cache_savings']:.1f}%")
        logger.info(f"  Cache size: {stats['size']}/{stats['max_size']}")

        # Realistic workload should achieve good hit rate (>70%)
        # due to 80/20 access pattern
        assert hit_rate > 70.0

    async def test_cache_performance_improvement(self, mock_query_adapter):
        """Measure performance improvement from caching."""
        import time

        gene = "TP53"

        # Measure cold query (cache miss)
        await mock_query_adapter.cache.clear()
        start = time.time()
        await mock_query_adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})
        cold_time = time.time() - start

        # Measure warm query (cache hit)
        start = time.time()
        await mock_query_adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})
        warm_time = time.time() - start

        speedup = cold_time / warm_time if warm_time > 0 else 1.0

        logger.info(f"\nCache performance:")
        logger.info(f"  Cold query: {cold_time*1000:.2f}ms")
        logger.info(f"  Warm query: {warm_time*1000:.2f}ms")
        logger.info(f"  Speedup: {speedup:.1f}x")

        # Cached query should be significantly faster
        assert warm_time < cold_time
        assert speedup > 2.0  # At least 2x faster

    async def test_cache_capacity_impact_on_hit_rate(self, known_entities):
        """Test how cache capacity affects hit rate."""
        from cogex_mcp.services.cache import CacheService
        from tests.cache.conftest import MockQueryAdapter

        results = []

        # Test different cache sizes
        cache_sizes = [10, 50, 100, 500]

        for size in cache_sizes:
            cache = CacheService(max_size=size, ttl_seconds=3600, enabled=True)
            adapter = MockQueryAdapter(cache)

            # Run workload
            hit_rate = await simulate_realistic_workload(adapter, duration=5)

            stats = cache.get_detailed_stats()
            results.append({
                "cache_size": size,
                "hit_rate": hit_rate,
                "evictions": stats["evictions"],
            })

            await cache.clear()

        # Log results
        logger.info("\nCache capacity vs hit rate:")
        for result in results:
            logger.info(
                f"  Size {result['cache_size']:3d}: "
                f"hit_rate={result['hit_rate']:.1f}%, "
                f"evictions={result['evictions']}"
            )

        # Larger cache should have higher hit rate
        assert results[-1]["hit_rate"] >= results[0]["hit_rate"]

    async def test_cache_hit_rate_measurement_accuracy(self, mock_query_adapter):
        """Verify hit rate calculation accuracy."""
        # Execute known pattern: 1 miss + 9 hits = 90% hit rate
        gene = "TP53"

        await mock_query_adapter.cache.clear()
        mock_query_adapter.cache.reset_stats()

        # First query: miss
        await mock_query_adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        # Next 9 queries: hits
        for _ in range(9):
            await mock_query_adapter.query_tool("cogex_query_gene_or_feature", {"gene": gene})

        stats = mock_query_adapter.cache.get_detailed_stats()

        # Verify exact counts
        assert stats["hits"] == 9
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 90.0  # Exactly 90%

        logger.info(f"Hit rate calculation verified: {stats['hit_rate']:.1f}%")
