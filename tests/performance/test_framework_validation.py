"""
Framework validation test.

Quick test to verify the performance testing framework is working correctly.
"""

import logging

import pytest

from tests.performance.profiler import PerformanceProfiler

logger = logging.getLogger(__name__)


@pytest.mark.performance
class TestFrameworkValidation:
    """Validate performance testing framework setup."""

    def test_profiler_statistics_calculation(self):
        """Test profiler statistics calculation."""
        latencies = [100.0, 150.0, 120.0, 180.0, 110.0, 200.0, 130.0, 160.0, 140.0, 190.0]

        stats = PerformanceProfiler.calculate_statistics(latencies)

        assert "mean" in stats
        assert "median" in stats
        assert "p95" in stats
        assert "p99" in stats
        assert stats["mean"] > 0
        assert stats["min"] == 100.0
        assert stats["max"] == 200.0

        logger.info(f"Statistics calculated successfully: {stats}")

    def test_profiler_reports_directory(self):
        """Test reports directory creation."""
        profiler = PerformanceProfiler()

        assert profiler.reports_dir.exists()
        assert profiler.reports_dir.is_dir()

        logger.info(f"Reports directory exists: {profiler.reports_dir}")

    def test_profiler_save_latency_report(self):
        """Test latency report saving."""
        profiler = PerformanceProfiler()

        stats = {
            "mean": 1250.5,
            "median": 1200.0,
            "p95": 1800.0,
            "p99": 2100.0,
            "min": 950.0,
            "max": 2200.0,
            "stdev": 250.3,
        }

        profiler.save_latency_report("test_tool", "test_mode", stats)

        report_file = profiler.reports_dir / "latency_report.json"
        assert report_file.exists()

        logger.info("Latency report saved successfully")

    def test_profiler_save_concurrency_report(self):
        """Test concurrency report saving."""
        profiler = PerformanceProfiler()

        profiler.save_concurrency_report(
            test_name="test_concurrency",
            concurrent_count=10,
            total_time=5000.0,
            success_rate=100.0,
            errors=[],
        )

        report_file = profiler.reports_dir / "concurrency_report.json"
        assert report_file.exists()

        logger.info("Concurrency report saved successfully")

    def test_profiler_generate_recommendations(self):
        """Test recommendation generation."""
        profiler = PerformanceProfiler()

        recommendations = profiler.generate_recommendations()

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        logger.info(f"Generated {len(recommendations)} recommendations")

    def test_fixtures_available(
        self, performance_profiler, known_entities, performance_targets
    ):
        """Test that fixtures are available."""
        assert performance_profiler is not None
        assert known_entities is not None
        assert performance_targets is not None

        assert "genes" in known_entities
        assert len(known_entities["genes"]) > 0

        assert "complex_queries" in performance_targets

        logger.info("All fixtures available and valid")

    @pytest.mark.asyncio
    async def test_adapter_connection(self, performance_adapter):
        """Test adapter connection."""
        assert performance_adapter is not None

        status = performance_adapter.get_status()
        assert status["initialized"] is True

        logger.info(f"Adapter status: {status}")

        # Verify at least one backend is available
        assert (
            status["neo4j"]["available"] or status["rest"]["available"]
        ), "No backend available"

        logger.info("Adapter connection validated")
