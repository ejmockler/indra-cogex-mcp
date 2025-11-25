"""
Real-time cache monitoring.

Provides continuous monitoring of cache performance with:
- Real-time statistics collection
- Trend analysis
- Performance reporting
- Optimization recommendations
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from cogex_mcp.services.cache import CacheService

logger = logging.getLogger(__name__)


@dataclass
class CacheSnapshot:
    """Single point-in-time cache snapshot."""

    timestamp: float
    hits: int
    misses: int
    evictions: int
    size: int
    max_size: int
    hit_rate: float
    hit_rate_recent: float
    ttl_expirations: int
    memory_bytes: int
    capacity_utilization: float


class CacheMonitor:
    """
    Real-time cache monitoring with analytics.

    Collects metrics at regular intervals and provides:
    - Live statistics
    - Historical trend analysis
    - Performance insights
    - Optimization recommendations
    """

    def __init__(
        self,
        cache: CacheService,
        update_interval: int = 5,
    ):
        """
        Initialize cache monitor.

        Args:
            cache: CacheService instance to monitor
            update_interval: Seconds between metric collections
        """
        self.cache = cache
        self.update_interval = update_interval
        self.snapshots: List[CacheSnapshot] = []
        self.monitoring = False

    async def start_monitoring(
        self,
        duration: int = 300,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Monitor cache for specified duration.

        Args:
            duration: Monitoring duration in seconds
            verbose: Whether to print real-time updates

        Returns:
            Monitoring report with analysis
        """
        logger.info(f"Starting cache monitoring for {duration}s")
        self.monitoring = True
        start_time = time.time()

        try:
            while time.time() - start_time < duration and self.monitoring:
                # Collect snapshot
                snapshot = self._collect_snapshot()
                self.snapshots.append(snapshot)

                # Log current stats
                if verbose:
                    self._log_snapshot(snapshot)

                # Wait for next interval
                await asyncio.sleep(self.update_interval)

        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")

        finally:
            self.monitoring = False

        # Generate report
        report = self._generate_report()
        logger.info("Monitoring complete")

        return report

    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.monitoring = False

    def _collect_snapshot(self) -> CacheSnapshot:
        """Collect current cache metrics snapshot."""
        stats = self.cache.get_detailed_stats()

        return CacheSnapshot(
            timestamp=time.time(),
            hits=stats["hits"],
            misses=stats["misses"],
            evictions=stats["evictions"],
            size=stats["size"],
            max_size=stats["max_size"],
            hit_rate=stats["hit_rate"],
            hit_rate_recent=stats["hit_rate_recent"],
            ttl_expirations=stats["ttl_expirations"],
            memory_bytes=stats["total_memory_estimate"],
            capacity_utilization=stats["capacity_utilization"],
        )

    def _log_snapshot(self, snapshot: CacheSnapshot) -> None:
        """Log current snapshot to console."""
        timestamp = datetime.fromtimestamp(snapshot.timestamp).strftime("%H:%M:%S")

        logger.info(
            f"[{timestamp}] "
            f"Hit Rate: {snapshot.hit_rate_recent:.1f}% | "
            f"Size: {snapshot.size}/{snapshot.max_size} | "
            f"Hits: {snapshot.hits} | "
            f"Misses: {snapshot.misses} | "
            f"Evictions: {snapshot.evictions} | "
            f"Memory: {snapshot.memory_bytes/1024:.1f}KB"
        )

    def _generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive monitoring report.

        Returns:
            Report dictionary with analysis
        """
        if not self.snapshots:
            return {"error": "No snapshots collected"}

        duration = self.snapshots[-1].timestamp - self.snapshots[0].timestamp

        # Calculate trends
        trends = self._analyze_trends()

        # Generate recommendations
        recommendations = self._generate_recommendations()

        # Summary statistics
        summary = {
            "duration_seconds": duration,
            "snapshots_collected": len(self.snapshots),
            "final_stats": asdict(self.snapshots[-1]),
            "trends": trends,
            "recommendations": recommendations,
            "performance_summary": self._summarize_performance(),
        }

        return summary

    def _analyze_trends(self) -> Dict[str, Any]:
        """Analyze trends over monitoring period."""
        if len(self.snapshots) < 2:
            return {}

        first = self.snapshots[0]
        last = self.snapshots[-1]

        # Calculate deltas
        hit_rate_change = last.hit_rate_recent - first.hit_rate_recent
        size_change = last.size - first.size
        memory_change = last.memory_bytes - first.memory_bytes

        # Calculate rates
        total_hits = last.hits - first.hits
        total_misses = last.misses - first.misses
        total_evictions = last.evictions - first.evictions

        return {
            "hit_rate_change": hit_rate_change,
            "hit_rate_trend": "improving" if hit_rate_change > 5 else "stable" if abs(hit_rate_change) <= 5 else "declining",
            "size_change": size_change,
            "memory_change_kb": memory_change / 1024,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "total_evictions": total_evictions,
            "avg_hit_rate": sum(s.hit_rate_recent for s in self.snapshots) / len(self.snapshots),
            "peak_size": max(s.size for s in self.snapshots),
            "peak_memory_kb": max(s.memory_bytes for s in self.snapshots) / 1024,
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on trends."""
        if not self.snapshots:
            return []

        recommendations = []
        last = self.snapshots[-1]
        trends = self._analyze_trends()

        # Hit rate recommendations
        if last.hit_rate < 50:
            recommendations.append(
                "CRITICAL: Very low hit rate (<50%). "
                "Consider increasing cache size or TTL."
            )
        elif last.hit_rate < 70:
            recommendations.append(
                "WARNING: Moderate hit rate (<70%). "
                "Optimization may improve performance."
            )

        # Trend-based recommendations
        if trends.get("hit_rate_trend") == "declining":
            recommendations.append(
                "Hit rate is declining. "
                "Check for changing query patterns or insufficient cache size."
            )

        # Capacity recommendations
        if last.capacity_utilization > 95:
            recommendations.append(
                "Cache near capacity (>95%). "
                "Increase max_size to reduce evictions."
            )
        elif last.capacity_utilization > 80:
            recommendations.append(
                "Cache utilization high (>80%). "
                "Monitor for potential capacity issues."
            )

        # Eviction recommendations
        if trends.get("total_evictions", 0) > trends.get("total_hits", 1) * 0.2:
            recommendations.append(
                "High eviction rate (>20% of hits). "
                "Increasing cache size will improve hit rate."
            )

        # TTL recommendations
        ttl_ratio = last.ttl_expirations / max(last.evictions, 1)
        if ttl_ratio > 2:
            recommendations.append(
                "TTL expirations >> evictions. "
                "Consider increasing TTL for better cache utilization."
            )
        elif ttl_ratio < 0.5 and last.evictions > 0:
            recommendations.append(
                "Evictions >> TTL expirations. "
                "Consider decreasing TTL to free memory or increase cache size."
            )

        # Memory recommendations
        if last.memory_bytes > 100 * 1024 * 1024:  # > 100MB
            recommendations.append(
                f"High memory usage ({last.memory_bytes / (1024*1024):.1f}MB). "
                "Consider reducing cache size or TTL."
            )

        if not recommendations:
            recommendations.append("Cache performance appears optimal. No changes recommended.")

        return recommendations

    def _summarize_performance(self) -> Dict[str, Any]:
        """Summarize overall cache performance."""
        if not self.snapshots:
            return {}

        last = self.snapshots[-1]

        # Calculate overall performance score (0-100)
        score = 0

        # Hit rate contribution (50 points max)
        score += min(last.hit_rate * 0.5, 50)

        # Capacity utilization contribution (25 points max)
        # Optimal: 60-80% utilization
        util = last.capacity_utilization
        if 60 <= util <= 80:
            score += 25
        elif 50 <= util < 60 or 80 < util <= 90:
            score += 20
        elif util < 50 or util > 90:
            score += 10

        # Eviction rate contribution (25 points max)
        total_ops = last.hits + last.misses
        eviction_rate = last.evictions / max(total_ops, 1)
        if eviction_rate < 0.05:
            score += 25
        elif eviction_rate < 0.1:
            score += 20
        elif eviction_rate < 0.2:
            score += 15
        else:
            score += 5

        # Determine performance tier
        if score >= 90:
            tier = "Excellent"
        elif score >= 75:
            tier = "Good"
        elif score >= 60:
            tier = "Acceptable"
        elif score >= 40:
            tier = "Poor"
        else:
            tier = "Critical"

        return {
            "performance_score": round(score, 1),
            "performance_tier": tier,
            "hit_rate": last.hit_rate,
            "capacity_utilization": last.capacity_utilization,
            "eviction_rate_pct": eviction_rate * 100,
            "memory_usage_mb": last.memory_bytes / (1024 * 1024),
        }

    def export_snapshots(self, filepath: str) -> None:
        """
        Export snapshots to JSON file.

        Args:
            filepath: Output file path
        """
        import json

        data = {
            "monitoring_start": self.snapshots[0].timestamp if self.snapshots else None,
            "monitoring_end": self.snapshots[-1].timestamp if self.snapshots else None,
            "snapshots": [asdict(s) for s in self.snapshots],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(self.snapshots)} snapshots to {filepath}")


async def run_monitoring_session(
    cache: CacheService,
    duration: int = 60,
    interval: int = 5,
) -> Dict[str, Any]:
    """
    Run a monitoring session and generate report.

    Args:
        cache: CacheService to monitor
        duration: Monitoring duration in seconds
        interval: Update interval in seconds

    Returns:
        Monitoring report
    """
    monitor = CacheMonitor(cache, update_interval=interval)

    try:
        report = await monitor.start_monitoring(duration=duration, verbose=True)
        return report

    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
        monitor.stop_monitoring()
        return monitor._generate_report()


if __name__ == "__main__":
    """CLI entry point for cache monitoring."""
    import argparse
    import sys
    from cogex_mcp.services.cache import get_cache

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="Monitor CoGEx cache performance")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Monitoring duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Export snapshots to JSON file"
    )

    args = parser.parse_args()

    # Get cache instance
    cache = get_cache()

    # Run monitoring
    async def main():
        monitor = CacheMonitor(cache, update_interval=args.interval)
        report = await monitor.start_monitoring(duration=args.duration, verbose=True)

        # Print summary
        print("\n" + "="*70)
        print("CACHE MONITORING REPORT")
        print("="*70)

        perf = report["performance_summary"]
        print(f"\nPerformance Score: {perf['performance_score']}/100 ({perf['performance_tier']})")
        print(f"Hit Rate: {perf['hit_rate']:.1f}%")
        print(f"Capacity Utilization: {perf['capacity_utilization']:.1f}%")
        print(f"Memory Usage: {perf['memory_usage_mb']:.2f}MB")

        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")

        # Export if requested
        if args.output:
            monitor.export_snapshots(args.output)
            print(f"\nSnapshots exported to: {args.output}")

    asyncio.run(main())
