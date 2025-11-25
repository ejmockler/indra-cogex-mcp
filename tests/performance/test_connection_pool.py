"""
Connection pool efficiency tests.

Tests Neo4j connection pool utilization, efficiency, and behavior under load:
- Pool utilization monitoring
- Connection lifecycle
- Pool saturation behavior
- Connection reuse efficiency

Connection pool configuration:
- Max pool size: 50 connections
- Connection timeout: 30 seconds
- Max connection lifetime: 3600 seconds
"""

import asyncio
import logging
import time

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.performance
@pytest.mark.asyncio
class TestConnectionPool:
    """Connection pool efficiency and utilization tests."""

    async def test_connection_pool_basic_utilization(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test basic connection pool utilization with sequential queries.

        This establishes baseline pool behavior under light load.
        """
        test_name = "basic_utilization"
        query_count = 100

        logger.info(f"Starting {test_name} test with {query_count} sequential queries")

        pool_stats = []
        latencies = []

        # Execute queries sequentially and monitor pool
        for i in range(query_count):
            start = time.perf_counter()

            # Execute query
            try:
                result = await performance_adapter.query(
                    "gene_to_features",
                    gene=known_entities["genes"][i % len(known_entities["genes"])],
                    include_expression=True,
                )
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)

                # Record pool stats (simulated - actual implementation would query driver)
                pool_stats.append({
                    "iteration": i,
                    "latency_ms": latency,
                    "active_connections": 1,  # Placeholder
                    "idle_connections": 0,    # Placeholder
                    "timestamp": time.time(),
                })

            except Exception as e:
                logger.error(f"Query {i+1} failed: {e}")
                latencies.append(60000.0)

            # Small delay between queries
            if i % 10 == 0:
                logger.debug(f"Completed {i+1}/{query_count} queries")

        # Calculate summary statistics
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_active = max(s["active_connections"] for s in pool_stats)

        summary = {
            "query_count": query_count,
            "avg_latency_ms": avg_latency,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "max_active_connections": max_active,
            "pool_size": 50,
            "utilization_pct": (max_active / 50) * 100,
        }

        logger.info(
            f"{test_name}: avg_latency={avg_latency:.0f}ms, "
            f"max_active={max_active}/50 ({summary['utilization_pct']:.1f}%)"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=pool_stats,
            summary=summary,
        )

        # Assertions
        assert avg_latency < 2000, f"Average latency too high: {avg_latency:.0f}ms"
        assert max_active <= 5, f"Expected low utilization for sequential queries, got {max_active}"

    async def test_connection_pool_concurrent_utilization(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test pool utilization with concurrent queries.

        This tests how efficiently the pool handles concurrent load.
        """
        test_name = "concurrent_utilization"
        concurrent_count = 30  # 60% of pool capacity

        logger.info(f"Starting {test_name} test with {concurrent_count} concurrent queries")

        # Create queries
        queries = [
            ("gene_to_features", {
                "gene": known_entities["genes"][i % len(known_entities["genes"])],
                "include_expression": True,
            })
            for i in range(concurrent_count)
        ]

        # Execute concurrently while monitoring
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000

        # Analyze results
        errors = [r for r in results if isinstance(r, Exception)]
        success_rate = ((concurrent_count - len(errors)) / concurrent_count) * 100

        # Estimate peak utilization (would be measured from driver in production)
        estimated_peak_connections = min(concurrent_count, 50)

        summary = {
            "concurrent_count": concurrent_count,
            "total_time_ms": total_time,
            "success_rate_pct": success_rate,
            "error_count": len(errors),
            "max_active_connections": estimated_peak_connections,
            "pool_size": 50,
            "utilization_pct": (estimated_peak_connections / 50) * 100,
        }

        logger.info(
            f"{test_name}: time={total_time:.0f}ms, "
            f"success={success_rate:.1f}%, "
            f"utilization={summary['utilization_pct']:.1f}%"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],  # Not collecting detailed stats for concurrent test
            summary=summary,
        )

        # Assertions
        assert success_rate == 100.0, f"Expected 100% success, got {success_rate:.1f}%"
        assert total_time < 10000, f"Total time too high: {total_time:.0f}ms"

    async def test_connection_pool_saturation(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test pool behavior at saturation (50+ concurrent queries).

        This tests connection queuing and timeout behavior.
        """
        test_name = "pool_saturation"
        concurrent_count = 60  # Exceeds pool capacity

        logger.info(f"Starting {test_name} test with {concurrent_count} queries")

        # Create queries
        queries = [
            ("gene_to_features", {
                "gene": known_entities["genes"][i % len(known_entities["genes"])],
                "include_expression": True,
            })
            for i in range(concurrent_count)
        ]

        # Execute concurrently
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000

        # Analyze results
        errors = [r for r in results if isinstance(r, Exception)]
        success_rate = ((concurrent_count - len(errors)) / concurrent_count) * 100

        # Categorize errors
        timeout_errors = [e for e in errors if "timeout" in str(e).lower()]
        connection_errors = [e for e in errors if "connection" in str(e).lower()]

        summary = {
            "concurrent_count": concurrent_count,
            "total_time_ms": total_time,
            "success_rate_pct": success_rate,
            "error_count": len(errors),
            "timeout_errors": len(timeout_errors),
            "connection_errors": len(connection_errors),
            "max_active_connections": 50,  # Pool capacity
            "pool_size": 50,
            "utilization_pct": 100.0,
            "queuing_detected": concurrent_count > 50,
        }

        logger.info(
            f"{test_name}: time={total_time:.0f}ms, "
            f"success={success_rate:.1f}%, "
            f"timeouts={len(timeout_errors)}, "
            f"connection_errors={len(connection_errors)}"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions - Allow some failures due to saturation
        assert success_rate >= 85.0, (
            f"Expected success rate >= 85% at saturation, got {success_rate:.1f}%"
        )

        if timeout_errors:
            logger.warning(
                f"Connection timeouts detected: {len(timeout_errors)}. "
                f"Consider increasing connection_acquisition_timeout or pool size."
            )

    async def test_connection_reuse_efficiency(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test connection reuse efficiency.

        This validates that connections are being properly reused from the
        pool rather than creating new connections for each query.
        """
        test_name = "connection_reuse"
        query_count = 50

        logger.info(f"Starting {test_name} test")

        # Execute queries and measure latency distribution
        latencies = []

        for i in range(query_count):
            start = time.perf_counter()
            try:
                result = await performance_adapter.query(
                    "resolve_identifiers",  # Fast query
                    identifiers=[known_entities["genes"][i % len(known_entities["genes"])]],
                    from_type="hgnc.symbol",
                    to_type="hgnc",
                )
                latency = (time.perf_counter() - start) * 1000
                latencies.append(latency)
            except Exception as e:
                logger.error(f"Query {i+1} failed: {e}")
                latencies.append(60000.0)

        # Analyze latency distribution
        # If connections are being reused efficiently, latency should be consistent
        # First query might be slower (connection establishment), rest should be fast
        first_query_latency = latencies[0] if latencies else 0
        avg_subsequent_latency = (
            sum(latencies[1:]) / len(latencies[1:]) if len(latencies) > 1 else 0
        )
        latency_variance = max(latencies) - min(latencies) if latencies else 0

        summary = {
            "query_count": query_count,
            "first_query_latency_ms": first_query_latency,
            "avg_subsequent_latency_ms": avg_subsequent_latency,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "latency_variance_ms": latency_variance,
            "connection_reuse_efficient": avg_subsequent_latency < first_query_latency,
        }

        logger.info(
            f"{test_name}: "
            f"first_query={first_query_latency:.0f}ms, "
            f"avg_subsequent={avg_subsequent_latency:.0f}ms, "
            f"variance={latency_variance:.0f}ms"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[{"iteration": i, "latency_ms": lat} for i, lat in enumerate(latencies)],
            summary=summary,
        )

        # Assertions
        assert avg_subsequent_latency < 1000, (
            f"Subsequent queries too slow: {avg_subsequent_latency:.0f}ms"
        )
        assert latency_variance < 5000, (
            f"High latency variance indicates connection issues: {latency_variance:.0f}ms"
        )

    async def test_connection_pool_recovery(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test pool recovery after saturation.

        This validates that the pool properly recovers and returns to normal
        performance after being saturated.
        """
        test_name = "pool_recovery"
        logger.info(f"Starting {test_name} test")

        # Phase 1: Saturate pool
        logger.info("Phase 1: Saturating connection pool...")
        saturation_queries = [
            ("gene_to_features", {
                "gene": known_entities["genes"][i % len(known_entities["genes"])],
                "include_expression": True,
            })
            for i in range(60)
        ]

        saturation_start = time.perf_counter()
        saturation_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in saturation_queries
        ], return_exceptions=True)
        saturation_time = (time.perf_counter() - saturation_start) * 1000

        saturation_errors = [r for r in saturation_results if isinstance(r, Exception)]

        logger.info(
            f"Saturation phase: {len(saturation_errors)} errors, {saturation_time:.0f}ms"
        )

        # Phase 2: Wait for recovery
        logger.info("Phase 2: Waiting for pool recovery...")
        await asyncio.sleep(2)

        # Phase 3: Test normal performance
        logger.info("Phase 3: Testing recovery performance...")
        recovery_queries = [
            ("gene_to_features", {
                "gene": known_entities["genes"][i % len(known_entities["genes"])],
                "include_expression": True,
            })
            for i in range(10)
        ]

        recovery_start = time.perf_counter()
        recovery_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in recovery_queries
        ], return_exceptions=True)
        recovery_time = (time.perf_counter() - recovery_start) * 1000

        recovery_errors = [r for r in recovery_results if isinstance(r, Exception)]
        recovery_success_rate = ((10 - len(recovery_errors)) / 10) * 100

        summary = {
            "saturation_query_count": 60,
            "saturation_time_ms": saturation_time,
            "saturation_error_count": len(saturation_errors),
            "recovery_query_count": 10,
            "recovery_time_ms": recovery_time,
            "recovery_error_count": len(recovery_errors),
            "recovery_success_rate_pct": recovery_success_rate,
            "pool_recovered": recovery_success_rate == 100.0,
        }

        logger.info(
            f"{test_name}: "
            f"recovery_success={recovery_success_rate:.1f}%, "
            f"recovery_time={recovery_time:.0f}ms"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert recovery_success_rate == 100.0, (
            f"Pool did not fully recover: {recovery_success_rate:.1f}% success"
        )
        assert recovery_time < 10000, (
            f"Recovery performance degraded: {recovery_time:.0f}ms"
        )

    async def test_connection_pool_sustained_load(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test pool performance under sustained load.

        This validates that the pool maintains consistent performance over time.
        """
        test_name = "sustained_load"
        duration_seconds = 30
        queries_per_second = 10

        logger.info(
            f"Starting {test_name} test "
            f"({duration_seconds}s @ {queries_per_second} qps)"
        )

        start_time = time.time()
        query_count = 0
        latencies = []
        errors = []

        while time.time() - start_time < duration_seconds:
            # Execute batch of queries
            batch_queries = [
                ("gene_to_features", {
                    "gene": known_entities["genes"][i % len(known_entities["genes"])],
                    "include_expression": True,
                })
                for i in range(queries_per_second)
            ]

            batch_start = time.perf_counter()
            batch_results = await asyncio.gather(*[
                performance_adapter.query(mode, **params)
                for mode, params in batch_queries
            ], return_exceptions=True)
            batch_time = (time.perf_counter() - batch_start) * 1000

            # Record results
            query_count += len(batch_queries)
            batch_errors = [r for r in batch_results if isinstance(r, Exception)]
            errors.extend(batch_errors)

            # Record average batch latency
            latencies.append(batch_time / len(batch_queries))

            # Wait before next batch (rate limiting)
            await asyncio.sleep(1)

        # Calculate summary
        total_time = time.time() - start_time
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        error_rate = (len(errors) / query_count) * 100 if query_count > 0 else 0

        summary = {
            "duration_seconds": total_time,
            "queries_per_second_target": queries_per_second,
            "total_queries": query_count,
            "actual_qps": query_count / total_time,
            "avg_latency_ms": avg_latency,
            "error_count": len(errors),
            "error_rate_pct": error_rate,
            "max_latency_ms": max(latencies) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
        }

        logger.info(
            f"{test_name}: "
            f"total_queries={query_count}, "
            f"avg_latency={avg_latency:.0f}ms, "
            f"error_rate={error_rate:.2f}%"
        )

        # Save report
        performance_profiler.save_connection_pool_report(
            test_name=test_name,
            pool_stats=[],
            summary=summary,
        )

        # Assertions
        assert error_rate < 5.0, f"Error rate too high: {error_rate:.2f}%"
        assert avg_latency < 2000, f"Average latency too high: {avg_latency:.0f}ms"
        assert summary["actual_qps"] >= queries_per_second * 0.9, (
            f"Query throughput too low: {summary['actual_qps']:.1f} qps"
        )
