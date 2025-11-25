"""
Performance profiling utilities.

Provides statistical analysis, report generation, and optimization recommendations
for performance benchmarking.
"""

import json
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """
    Performance profiling utilities for latency analysis and optimization.
    """

    def __init__(self, reports_dir: Optional[Path] = None):
        """
        Initialize performance profiler.

        Args:
            reports_dir: Directory for performance reports (defaults to tests/performance/reports)
        """
        if reports_dir is None:
            reports_dir = Path(__file__).parent / "reports"
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calculate_statistics(latencies: List[float]) -> Dict[str, float]:
        """
        Calculate comprehensive latency statistics.

        Args:
            latencies: List of latency measurements in milliseconds

        Returns:
            Dictionary with mean, median, stdev, min, max, p50, p95, p99
        """
        if not latencies:
            return {
                "mean": 0.0,
                "median": 0.0,
                "stdev": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        stats = {
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "stdev": statistics.stdev(latencies) if n > 1 else 0.0,
            "min": min(latencies),
            "max": max(latencies),
            "p50": sorted_latencies[int(n * 0.50)],
            "p95": sorted_latencies[int(n * 0.95)],
            "p99": sorted_latencies[int(n * 0.99)] if n >= 100 else sorted_latencies[-1],
        }

        return stats

    def save_latency_report(
        self, tool_name: str, mode: str, stats: Dict[str, float]
    ) -> None:
        """
        Save latency report to JSON file.

        Args:
            tool_name: Name of the tool (e.g., "tool_01_gene_feature")
            mode: Query mode (e.g., "gene_to_features")
            stats: Statistics dictionary from calculate_statistics()
        """
        report_file = self.reports_dir / "latency_report.json"

        # Load existing report or create new
        if report_file.exists():
            with open(report_file, "r") as f:
                report = json.load(f)
        else:
            report = {
                "generated_at": datetime.now().isoformat(),
                "tools": {},
            }

        # Add/update tool results
        if tool_name not in report["tools"]:
            report["tools"][tool_name] = {}

        report["tools"][tool_name][mode] = {
            **stats,
            "timestamp": datetime.now().isoformat(),
        }

        # Update generation timestamp
        report["generated_at"] = datetime.now().isoformat()

        # Save report
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Saved latency report: {tool_name}/{mode}")

    def save_concurrency_report(
        self,
        test_name: str,
        concurrent_count: int,
        total_time: float,
        success_rate: float,
        errors: List[str],
        additional_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save concurrency test report.

        Args:
            test_name: Name of the test (e.g., "10x_concurrent")
            concurrent_count: Number of concurrent queries
            total_time: Total time in milliseconds
            success_rate: Success rate as percentage (0-100)
            errors: List of error messages
            additional_metrics: Optional additional metrics
        """
        report_file = self.reports_dir / "concurrency_report.json"

        # Load existing report or create new
        if report_file.exists():
            with open(report_file, "r") as f:
                report = json.load(f)
        else:
            report = {
                "generated_at": datetime.now().isoformat(),
                "tests": {},
            }

        # Add test results
        report["tests"][test_name] = {
            "concurrent_count": concurrent_count,
            "total_time_ms": total_time,
            "avg_time_per_query_ms": total_time / concurrent_count,
            "success_rate_pct": success_rate,
            "error_count": len(errors),
            "errors": errors[:10],  # Keep only first 10 errors
            "timestamp": datetime.now().isoformat(),
        }

        if additional_metrics:
            report["tests"][test_name].update(additional_metrics)

        # Update generation timestamp
        report["generated_at"] = datetime.now().isoformat()

        # Save report
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Saved concurrency report: {test_name}")

    def save_connection_pool_report(
        self,
        test_name: str,
        pool_stats: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> None:
        """
        Save connection pool efficiency report.

        Args:
            test_name: Name of the test
            pool_stats: List of pool statistics samples
            summary: Summary statistics
        """
        report_file = self.reports_dir / "connection_pool_report.json"

        # Load existing report or create new
        if report_file.exists():
            with open(report_file, "r") as f:
                report = json.load(f)
        else:
            report = {
                "generated_at": datetime.now().isoformat(),
                "tests": {},
            }

        # Add test results
        report["tests"][test_name] = {
            "pool_stats": pool_stats,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }

        # Update generation timestamp
        report["generated_at"] = datetime.now().isoformat()

        # Save report
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Saved connection pool report: {test_name}")

    def generate_recommendations(self) -> List[str]:
        """
        Generate optimization recommendations based on all reports.

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        # Analyze latency report
        latency_file = self.reports_dir / "latency_report.json"
        if latency_file.exists():
            with open(latency_file, "r") as f:
                latency_report = json.load(f)

            # Check for slow queries
            for tool_name, modes in latency_report.get("tools", {}).items():
                for mode, stats in modes.items():
                    if stats["p95"] > 5000:
                        recommendations.append(
                            f"⚠️ {tool_name}/{mode}: High p95 latency ({stats['p95']:.0f}ms). "
                            f"Consider query optimization or caching."
                        )
                    if stats["stdev"] > stats["mean"]:
                        recommendations.append(
                            f"⚠️ {tool_name}/{mode}: High variance (stdev={stats['stdev']:.0f}ms). "
                            f"Indicates inconsistent performance."
                        )

        # Analyze concurrency report
        concurrency_file = self.reports_dir / "concurrency_report.json"
        if concurrency_file.exists():
            with open(concurrency_file, "r") as f:
                concurrency_report = json.load(f)

            for test_name, results in concurrency_report.get("tests", {}).items():
                if results["success_rate_pct"] < 90:
                    recommendations.append(
                        f"⚠️ {test_name}: Low success rate ({results['success_rate_pct']:.1f}%). "
                        f"Circuit breaker may be triggering. Review connection pool size."
                    )
                if results["error_count"] > 0:
                    recommendations.append(
                        f"⚠️ {test_name}: {results['error_count']} errors detected. "
                        f"Review error logs for patterns."
                    )

        # Analyze connection pool report
        pool_file = self.reports_dir / "connection_pool_report.json"
        if pool_file.exists():
            with open(pool_file, "r") as f:
                pool_report = json.load(f)

            for test_name, results in pool_report.get("tests", {}).items():
                summary = results.get("summary", {})
                max_active = summary.get("max_active_connections", 0)
                pool_size = summary.get("pool_size", 50)

                if max_active >= pool_size * 0.9:
                    recommendations.append(
                        f"⚠️ {test_name}: Connection pool near capacity "
                        f"({max_active}/{pool_size}). Consider increasing pool size."
                    )
                elif max_active < pool_size * 0.3:
                    recommendations.append(
                        f"✓ {test_name}: Connection pool underutilized "
                        f"({max_active}/{pool_size}). Pool size is adequate."
                    )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "✓ All metrics within acceptable thresholds. No immediate optimizations needed."
            )
        else:
            recommendations.insert(
                0,
                f"📊 Found {len(recommendations)} optimization opportunities:"
            )

        # Add general best practices
        recommendations.extend([
            "",
            "💡 General Best Practices:",
            "  • Enable caching for frequently queried entities",
            "  • Monitor circuit breaker activation patterns",
            "  • Use pagination for large result sets",
            "  • Implement query result caching for read-heavy workloads",
            "  • Consider read replicas for Neo4j if query load is high",
        ])

        return recommendations

    def save_recommendations(self) -> None:
        """Generate and save optimization recommendations."""
        recommendations = self.generate_recommendations()

        report_file = self.reports_dir / "recommendations.json"
        report = {
            "generated_at": datetime.now().isoformat(),
            "recommendations": recommendations,
        }

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info("Saved optimization recommendations")

    def print_summary(self) -> None:
        """Print performance summary to console."""
        print("\n" + "=" * 80)
        print("PERFORMANCE PROFILING SUMMARY")
        print("=" * 80 + "\n")

        # Latency summary
        latency_file = self.reports_dir / "latency_report.json"
        if latency_file.exists():
            with open(latency_file, "r") as f:
                latency_report = json.load(f)

            print("📊 LATENCY BENCHMARKS")
            print("-" * 80)
            for tool_name, modes in latency_report.get("tools", {}).items():
                print(f"\n{tool_name}:")
                for mode, stats in modes.items():
                    print(
                        f"  {mode:30s} | "
                        f"mean: {stats['mean']:6.0f}ms | "
                        f"p95: {stats['p95']:6.0f}ms | "
                        f"p99: {stats['p99']:6.0f}ms"
                    )

        # Concurrency summary
        concurrency_file = self.reports_dir / "concurrency_report.json"
        if concurrency_file.exists():
            with open(concurrency_file, "r") as f:
                concurrency_report = json.load(f)

            print("\n\n⚡ CONCURRENCY TESTS")
            print("-" * 80)
            for test_name, results in concurrency_report.get("tests", {}).items():
                print(
                    f"{test_name:30s} | "
                    f"{results['concurrent_count']} queries | "
                    f"total: {results['total_time_ms']:6.0f}ms | "
                    f"success: {results['success_rate_pct']:5.1f}%"
                )

        # Connection pool summary
        pool_file = self.reports_dir / "connection_pool_report.json"
        if pool_file.exists():
            with open(pool_file, "r") as f:
                pool_report = json.load(f)

            print("\n\n🔌 CONNECTION POOL EFFICIENCY")
            print("-" * 80)
            for test_name, results in pool_report.get("tests", {}).items():
                summary = results.get("summary", {})
                print(
                    f"{test_name:30s} | "
                    f"max_active: {summary.get('max_active_connections', 0)}/{summary.get('pool_size', 50)} | "
                    f"avg_latency: {summary.get('avg_latency_ms', 0):6.0f}ms"
                )

        # Recommendations
        print("\n\n💡 OPTIMIZATION RECOMMENDATIONS")
        print("-" * 80)
        recommendations = self.generate_recommendations()
        for rec in recommendations:
            print(rec)

        print("\n" + "=" * 80 + "\n")
