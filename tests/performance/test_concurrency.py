"""
Concurrency tests for connection pool and circuit breaker validation.

Tests concurrent query handling at different scales:
- 10x concurrent: Within pool capacity (50 connections)
- 60x concurrent: Above pool capacity (tests queuing)
- 100x concurrent: Stress test (tests circuit breaker)

Performance targets:
- 10x concurrent: < 10000ms total, 100% success
- 60x concurrent: > 90% success rate
- 100x concurrent: Circuit breaker should activate gracefully
"""

import asyncio
import logging
import time

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.performance
@pytest.mark.asyncio
class TestConcurrency:
    """Concurrency tests for connection pool and fault tolerance."""

    def _create_diverse_queries(
        self, known_entities: dict, count: int
    ) -> list[tuple[str, dict]]:
        """
        Create diverse queries across all tools.

        Args:
            known_entities: Dictionary of known entities
            count: Number of queries to create

        Returns:
            List of (mode, params) tuples
        """
        queries = []

        # Tool 1: Gene queries
        for i in range(count // 4):
            queries.append((
                "gene_to_features",
                {
                    "gene": known_entities["genes"][i % len(known_entities["genes"])],
                    "include_expression": True,
                }
            ))

        # Tool 4: Drug queries
        for i in range(count // 4):
            queries.append((
                "drug_to_targets",
                {
                    "drug": known_entities["drugs"][i % len(known_entities["drugs"])],
                    "limit": 20,
                }
            ))

        # Tool 5: Disease queries
        for i in range(count // 4):
            queries.append((
                "disease_to_genes",
                {
                    "disease": known_entities["diseases"][i % len(known_entities["diseases"])],
                    "limit": 20,
                }
            ))

        # Tool 11: Identifier resolution (fast queries)
        for i in range(count - len(queries)):
            queries.append((
                "resolve_identifiers",
                {
                    "identifiers": [known_entities["genes"][i % len(known_entities["genes"])]],
                    "from_type": "hgnc.symbol",
                    "to_type": "hgnc",
                }
            ))

        return queries[:count]

    async def test_10x_concurrent_queries(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test 10 concurrent queries (within pool capacity).

        This should complete successfully without hitting pool limits.
        """
        test_name = "10x_concurrent"
        concurrent_count = 10

        logger.info(f"Starting {test_name} test with {concurrent_count} queries")

        # Create diverse queries
        queries = self._create_diverse_queries(known_entities, concurrent_count)

        # Execute concurrently
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000  # Convert to ms

        # Analyze results
        errors = [r for r in results if isinstance(r, Exception)]
        success_count = len(results) - len(errors)
        success_rate = (success_count / len(results)) * 100

        # Log results
        logger.info(
            f"{test_name}: completed in {total_time:.0f}ms, "
            f"success_rate={success_rate:.1f}% ({success_count}/{len(results)})"
        )

        if errors:
            logger.warning(f"{test_name}: Errors encountered:")
            for i, error in enumerate(errors[:5]):  # Log first 5 errors
                logger.warning(f"  {i+1}. {type(error).__name__}: {error}")

        # Save report
        performance_profiler.save_concurrency_report(
            test_name=test_name,
            concurrent_count=concurrent_count,
            total_time=total_time,
            success_rate=success_rate,
            errors=[str(e) for e in errors],
            additional_metrics={
                "avg_per_query_ms": total_time / concurrent_count,
            },
        )

        # Assertions
        assert success_rate == 100.0, (
            f"Expected 100% success rate, got {success_rate:.1f}%"
        )
        assert total_time < 10000, (
            f"Expected total time < 10000ms, got {total_time:.0f}ms"
        )

    async def test_60x_concurrent_queries_pool_saturation(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test 60 concurrent queries (above pool capacity of 50).

        This tests connection pool queuing behavior. Some queries will wait
        for available connections, but all should complete successfully.
        """
        test_name = "60x_pool_saturation"
        concurrent_count = 60

        logger.info(f"Starting {test_name} test with {concurrent_count} queries")

        # Create diverse queries
        queries = self._create_diverse_queries(known_entities, concurrent_count)

        # Execute concurrently
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000

        # Analyze results
        errors = [r for r in results if isinstance(r, Exception)]
        success_count = len(results) - len(errors)
        success_rate = (success_count / len(results)) * 100

        # Log results
        logger.info(
            f"{test_name}: completed in {total_time:.0f}ms, "
            f"success_rate={success_rate:.1f}% ({success_count}/{len(results)})"
        )

        if errors:
            logger.warning(f"{test_name}: Errors encountered:")
            for i, error in enumerate(errors[:5]):
                logger.warning(f"  {i+1}. {type(error).__name__}: {error}")

        # Categorize errors
        timeout_errors = [e for e in errors if "timeout" in str(e).lower()]
        circuit_breaker_errors = [
            e for e in errors if "circuit" in str(e).lower()
        ]
        connection_errors = [
            e for e in errors if "connection" in str(e).lower()
        ]

        # Save report
        performance_profiler.save_concurrency_report(
            test_name=test_name,
            concurrent_count=concurrent_count,
            total_time=total_time,
            success_rate=success_rate,
            errors=[str(e) for e in errors],
            additional_metrics={
                "avg_per_query_ms": total_time / concurrent_count,
                "timeout_errors": len(timeout_errors),
                "circuit_breaker_errors": len(circuit_breaker_errors),
                "connection_errors": len(connection_errors),
            },
        )

        # Assertions - Allow up to 10% failure due to pool saturation
        assert success_rate >= 90.0, (
            f"Expected success rate >= 90%, got {success_rate:.1f}%"
        )
        assert total_time < 30000, (
            f"Expected total time < 30000ms, got {total_time:.0f}ms"
        )

    async def test_100x_concurrent_queries_stress_test(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test 100 concurrent queries (stress test).

        This is designed to test circuit breaker activation and graceful
        degradation under extreme load.
        """
        test_name = "100x_stress_test"
        concurrent_count = 100

        logger.info(f"Starting {test_name} test with {concurrent_count} queries")

        # Create diverse queries
        queries = self._create_diverse_queries(known_entities, concurrent_count)

        # Execute concurrently
        start = time.perf_counter()
        results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        total_time = (time.perf_counter() - start) * 1000

        # Analyze results
        errors = [r for r in results if isinstance(r, Exception)]
        success_count = len(results) - len(errors)
        success_rate = (success_count / len(results)) * 100

        # Log results
        logger.info(
            f"{test_name}: completed in {total_time:.0f}ms, "
            f"success_rate={success_rate:.1f}% ({success_count}/{len(results)})"
        )

        if errors:
            logger.warning(f"{test_name}: Errors encountered:")
            for i, error in enumerate(errors[:10]):
                logger.warning(f"  {i+1}. {type(error).__name__}: {error}")

        # Categorize errors
        timeout_errors = [e for e in errors if "timeout" in str(e).lower()]
        circuit_breaker_errors = [
            e for e in errors if "circuit" in str(e).lower()
        ]
        connection_errors = [
            e for e in errors if "connection" in str(e).lower()
        ]

        # Save report
        performance_profiler.save_concurrency_report(
            test_name=test_name,
            concurrent_count=concurrent_count,
            total_time=total_time,
            success_rate=success_rate,
            errors=[str(e) for e in errors],
            additional_metrics={
                "avg_per_query_ms": total_time / concurrent_count,
                "timeout_errors": len(timeout_errors),
                "circuit_breaker_errors": len(circuit_breaker_errors),
                "connection_errors": len(connection_errors),
            },
        )

        # Assertions - More lenient for stress test
        assert success_rate >= 70.0, (
            f"Expected success rate >= 70% for stress test, got {success_rate:.1f}%"
        )

        # Log circuit breaker behavior
        if circuit_breaker_errors:
            logger.info(
                f"Circuit breaker activated {len(circuit_breaker_errors)} times - "
                f"this is expected under extreme load"
            )

    async def test_sequential_vs_concurrent_speedup(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Compare sequential vs concurrent execution to measure speedup.

        This validates that concurrent execution provides significant
        performance improvement.
        """
        test_name = "sequential_vs_concurrent"
        query_count = 10

        logger.info(f"Starting {test_name} comparison test")

        # Create queries
        queries = self._create_diverse_queries(known_entities, query_count)

        # Sequential execution
        logger.info("Running sequential execution...")
        sequential_start = time.perf_counter()
        sequential_results = []
        for mode, params in queries:
            try:
                result = await performance_adapter.query(mode, **params)
                sequential_results.append(result)
            except Exception as e:
                sequential_results.append(e)
        sequential_time = (time.perf_counter() - sequential_start) * 1000

        # Concurrent execution
        logger.info("Running concurrent execution...")
        concurrent_start = time.perf_counter()
        concurrent_results = await asyncio.gather(*[
            performance_adapter.query(mode, **params)
            for mode, params in queries
        ], return_exceptions=True)
        concurrent_time = (time.perf_counter() - concurrent_start) * 1000

        # Calculate speedup
        speedup = sequential_time / concurrent_time

        logger.info(
            f"{test_name}: "
            f"sequential={sequential_time:.0f}ms, "
            f"concurrent={concurrent_time:.0f}ms, "
            f"speedup={speedup:.2f}x"
        )

        # Save report
        performance_profiler.save_concurrency_report(
            test_name=test_name,
            concurrent_count=query_count,
            total_time=concurrent_time,
            success_rate=100.0,
            errors=[],
            additional_metrics={
                "sequential_time_ms": sequential_time,
                "concurrent_time_ms": concurrent_time,
                "speedup": speedup,
            },
        )

        # Assertions
        assert speedup > 2.0, (
            f"Expected speedup > 2x from concurrent execution, got {speedup:.2f}x"
        )

    async def test_gradual_load_ramp(
        self, performance_adapter, performance_profiler, known_entities
    ):
        """
        Test gradual load increase to find breaking point.

        Starts with 10 concurrent queries and increases by 10 until failure
        rate exceeds 10%.
        """
        test_name = "gradual_load_ramp"
        logger.info(f"Starting {test_name} test")

        results_by_load = {}
        max_load = 10

        for load in range(10, 101, 10):
            logger.info(f"Testing load: {load} concurrent queries")

            queries = self._create_diverse_queries(known_entities, load)

            start = time.perf_counter()
            results = await asyncio.gather(*[
                performance_adapter.query(mode, **params)
                for mode, params in queries
            ], return_exceptions=True)
            total_time = (time.perf_counter() - start) * 1000

            errors = [r for r in results if isinstance(r, Exception)]
            success_rate = ((load - len(errors)) / load) * 100

            results_by_load[load] = {
                "total_time_ms": total_time,
                "success_rate_pct": success_rate,
                "error_count": len(errors),
            }

            logger.info(
                f"Load {load}: time={total_time:.0f}ms, "
                f"success={success_rate:.1f}%"
            )

            # Track maximum successful load
            if success_rate >= 90.0:
                max_load = load
            else:
                logger.warning(f"Breaking point reached at {load} concurrent queries")
                break

            # Small delay between load levels
            await asyncio.sleep(1)

        # Save report
        performance_profiler.save_concurrency_report(
            test_name=test_name,
            concurrent_count=max_load,
            total_time=0,  # Not applicable
            success_rate=0,  # Not applicable
            errors=[],
            additional_metrics={
                "max_successful_load": max_load,
                "results_by_load": results_by_load,
            },
        )

        logger.info(f"{test_name}: Maximum successful load = {max_load} concurrent queries")

        # Assertion: Should handle at least 50 concurrent queries
        assert max_load >= 50, (
            f"Expected to handle at least 50 concurrent queries, "
            f"max successful load was {max_load}"
        )
