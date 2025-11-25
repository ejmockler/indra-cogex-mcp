"""
Cache performance and warmup tests.

Tests cache effectiveness, hit rates, and warmup strategies:
- Cache hit rate measurement
- Cache warmup performance
- Cache eviction behavior
- Cache TTL effectiveness

Cache configuration:
- Max cache size: 1000 entries
- TTL: 3600 seconds (1 hour)
"""

import asyncio
import logging
import time

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.performance
@pytest.mark.asyncio
class TestCacheWarmup:
    """Cache performance and warmup tests."""

    async def test_cache_hit_rate_cold_start(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test cache hit rate starting from cold cache.

        This establishes baseline cache behavior.
        """
        test_name = "cache_cold_start"
        query_count = 50

        logger.info(f"Starting {test_name} test with cold cache")

        # Use repeated queries to test caching
        genes = known_entities["genes"][:5]  # Use only 5 genes, repeat 10x each
        queries = genes * 10  # 50 total queries, 5 unique

        latencies = []
        cache_hits_expected = 0

        for i, gene in enumerate(queries):
            start = time.perf_counter()
            try:
                result = await performance_adapter.query(
                    "gene_to_features",
                    gene=gene,
                    include_expression=True,
                )
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

                # First occurrence of each gene is cache miss, rest are hits
                if i >= 5:
                    cache_hits_expected += 1

            except Exception as e:
                logger.error(f"Query {i+1} failed: {e}")
                latencies.append(60000.0)

        # Calculate cache performance metrics
        # First 5 queries are cache misses, should be slower
        # Remaining 45 queries are cache hits, should be faster
        cold_latencies = latencies[:5]
        warm_latencies = latencies[5:]

        avg_cold = sum(cold_latencies) / len(cold_latencies) if cold_latencies else 0
        avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0

        # Cache hit rate estimation (actual implementation would query cache stats)
        estimated_hit_rate = (len(warm_latencies) / len(latencies)) * 100

        summary = {
            "query_count": query_count,
            "unique_entities": len(genes),
            "expected_cache_hits": cache_hits_expected,
            "estimated_hit_rate_pct": estimated_hit_rate,
            "avg_cold_latency_ms": avg_cold,
            "avg_warm_latency_ms": avg_warm,
            "speedup_from_cache": avg_cold / avg_warm if avg_warm > 0 else 1.0,
        }

        logger.info(
            f"{test_name}: "
            f"hit_rate={estimated_hit_rate:.1f}%, "
            f"cold={avg_cold:.0f}ms, "
            f"warm={avg_warm:.0f}ms, "
            f"speedup={summary['speedup_from_cache']:.2f}x"
        )

        # Save to connection pool report (cache-specific report would be better)
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert avg_warm < avg_cold, "Cache should improve performance"
        assert summary["speedup_from_cache"] > 1.5, (
            f"Expected >1.5x speedup from cache, got {summary['speedup_from_cache']:.2f}x"
        )

    async def test_cache_warmup_strategy(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test cache warmup strategy effectiveness.

        Pre-populates cache with common entities and measures impact.
        """
        test_name = "cache_warmup_strategy"
        logger.info(f"Starting {test_name} test")

        # Phase 1: Warm up cache with common entities
        logger.info("Phase 1: Warming up cache...")
        warmup_entities = known_entities["genes"][:10]

        warmup_start = time.perf_counter()
        warmup_results = await asyncio.gather(*[
            performance_adapter.query("gene_to_features", gene=gene, include_expression=True)
            for gene in warmup_entities
        ], return_exceptions=True)
        warmup_time = (time.perf_counter() - warmup_start) * 1000

        warmup_errors = [r for r in warmup_results if isinstance(r, Exception)]

        logger.info(f"Warmup completed in {warmup_time:.0f}ms with {len(warmup_errors)} errors")

        # Phase 2: Test query performance with warm cache
        logger.info("Phase 2: Testing with warm cache...")
        test_queries = warmup_entities * 5  # 50 queries, all should hit cache

        test_start = time.perf_counter()
        test_results = await asyncio.gather(*[
            performance_adapter.query("gene_to_features", gene=gene, include_expression=True)
            for gene in test_queries
        ], return_exceptions=True)
        test_time = (time.perf_counter() - test_start) * 1000

        test_errors = [r for r in test_results if isinstance(r, Exception)]
        avg_query_time = test_time / len(test_queries)

        summary = {
            "warmup_entity_count": len(warmup_entities),
            "warmup_time_ms": warmup_time,
            "warmup_errors": len(warmup_errors),
            "test_query_count": len(test_queries),
            "test_time_ms": test_time,
            "test_errors": len(test_errors),
            "avg_query_time_ms": avg_query_time,
            "cache_hit_rate_pct": 100.0,  # All queries should hit cache
        }

        logger.info(
            f"{test_name}: "
            f"warmup_time={warmup_time:.0f}ms, "
            f"avg_query={avg_query_time:.0f}ms"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert avg_query_time < 500, (
            f"Expected fast queries with warm cache, got {avg_query_time:.0f}ms"
        )
        assert len(test_errors) == 0, f"Unexpected errors with warm cache: {len(test_errors)}"

    async def test_cache_eviction_behavior(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test cache eviction behavior when cache is full.

        This validates LRU eviction and cache size management.
        """
        test_name = "cache_eviction"
        cache_size = 1000  # Configured max cache size

        logger.info(f"Starting {test_name} test (max cache size: {cache_size})")

        # Phase 1: Fill cache to capacity
        logger.info("Phase 1: Filling cache to capacity...")

        # Generate unique queries to fill cache
        # Using gene queries with different parameters
        fill_queries = []
        for i in range(cache_size + 100):  # Exceed cache size
            gene = known_entities["genes"][i % len(known_entities["genes"])]
            # Vary parameters to create unique cache keys
            fill_queries.append((
                "gene_to_features",
                {
                    "gene": gene,
                    "include_expression": i % 2 == 0,
                    "include_go_terms": i % 3 == 0,
                }
            ))

        fill_start = time.perf_counter()
        fill_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in fill_queries
        ], return_exceptions=True)
        fill_time = (time.perf_counter() - fill_start) * 1000

        fill_errors = [r for r in fill_results if isinstance(r, Exception)]

        logger.info(
            f"Filled cache with {len(fill_queries)} queries in {fill_time:.0f}ms "
            f"({len(fill_errors)} errors)"
        )

        # Phase 2: Test eviction - query old entries
        logger.info("Phase 2: Testing evicted entries...")

        # First 100 queries should have been evicted
        evicted_queries = fill_queries[:100]

        eviction_start = time.perf_counter()
        eviction_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in evicted_queries
        ], return_exceptions=True)
        eviction_time = (time.perf_counter() - eviction_start) * 1000

        # These should be cache misses (slower)
        avg_evicted_time = eviction_time / len(evicted_queries)

        # Phase 3: Test recent entries
        logger.info("Phase 3: Testing recent entries...")

        # Last 100 queries should still be in cache
        recent_queries = fill_queries[-100:]

        recent_start = time.perf_counter()
        recent_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in recent_queries
        ], return_exceptions=True)
        recent_time = (time.perf_counter() - recent_start) * 1000

        # These should be cache hits (faster)
        avg_recent_time = recent_time / len(recent_queries)

        summary = {
            "cache_size": cache_size,
            "fill_query_count": len(fill_queries),
            "fill_time_ms": fill_time,
            "avg_evicted_query_ms": avg_evicted_time,
            "avg_recent_query_ms": avg_recent_time,
            "eviction_working": avg_recent_time < avg_evicted_time,
        }

        logger.info(
            f"{test_name}: "
            f"evicted={avg_evicted_time:.0f}ms, "
            f"recent={avg_recent_time:.0f}ms"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert avg_recent_time < avg_evicted_time, (
            "Recent (cached) queries should be faster than evicted queries"
        )

    async def test_cache_ttl_expiration(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test cache TTL expiration behavior.

        Note: This test is limited by practical testing time.
        Default TTL is 3600 seconds (1 hour), so we can't wait that long.
        This test validates the behavior but may not see actual expiration.
        """
        test_name = "cache_ttl"
        ttl_seconds = 3600  # Configured TTL

        logger.info(
            f"Starting {test_name} test (TTL: {ttl_seconds}s) - "
            f"Note: Not waiting for full TTL expiration"
        )

        # Query an entity
        gene = known_entities["genes"][0]

        # First query - cache miss
        start1 = time.perf_counter()
        result1 = await performance_adapter.query(
            "gene_to_features",
            gene=gene,
            include_expression=True,
        )
        latency1 = (time.perf_counter() - start1) * 1000

        # Immediate re-query - cache hit
        start2 = time.perf_counter()
        result2 = await performance_adapter.query(
            "gene_to_features",
            gene=gene,
            include_expression=True,
        )
        latency2 = (time.perf_counter() - start2) * 1000

        # Wait a short time
        await asyncio.sleep(5)

        # Query again - should still be cached
        start3 = time.perf_counter()
        result3 = await performance_adapter.query(
            "gene_to_features",
            gene=gene,
            include_expression=True,
        )
        latency3 = (time.perf_counter() - start3) * 1000

        summary = {
            "ttl_seconds": ttl_seconds,
            "first_query_ms": latency1,
            "immediate_requery_ms": latency2,
            "after_5s_query_ms": latency3,
            "cache_working": latency2 < latency1 and latency3 < latency1,
            "speedup_immediate": latency1 / latency2 if latency2 > 0 else 1.0,
            "speedup_after_5s": latency1 / latency3 if latency3 > 0 else 1.0,
        }

        logger.info(
            f"{test_name}: "
            f"first={latency1:.0f}ms, "
            f"immediate={latency2:.0f}ms, "
            f"after_5s={latency3:.0f}ms"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert latency2 < latency1, "Immediate re-query should be faster (cached)"
        assert latency3 < latency1, "Query after 5s should still be cached"

    async def test_cache_concurrent_access(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test cache behavior under concurrent access.

        This validates thread-safety and concurrent read performance.
        """
        test_name = "cache_concurrent_access"
        concurrent_count = 50

        logger.info(f"Starting {test_name} test with {concurrent_count} concurrent queries")

        # Use same entity for all queries - all should hit cache after first
        gene = known_entities["genes"][0]

        # Pre-populate cache
        await performance_adapter.query(
            "gene_to_features",
            gene=gene,
            include_expression=True,
        )

        # Execute concurrent queries (all should be cache hits)
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query("gene_to_features", gene=gene, include_expression=True)
            for _ in range(concurrent_count)
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000

        errors = [r for r in results if isinstance(r, Exception)]
        success_rate = ((concurrent_count - len(errors)) / concurrent_count) * 100
        avg_time = total_time / concurrent_count

        summary = {
            "concurrent_count": concurrent_count,
            "total_time_ms": total_time,
            "avg_time_per_query_ms": avg_time,
            "success_rate_pct": success_rate,
            "error_count": len(errors),
            "all_cache_hits": True,
        }

        logger.info(
            f"{test_name}: "
            f"total={total_time:.0f}ms, "
            f"avg={avg_time:.0f}ms, "
            f"success={success_rate:.1f}%"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert success_rate == 100.0, f"Expected 100% success, got {success_rate:.1f}%"
        assert avg_time < 100, (
            f"Cache access should be very fast (<100ms), got {avg_time:.0f}ms"
        )
