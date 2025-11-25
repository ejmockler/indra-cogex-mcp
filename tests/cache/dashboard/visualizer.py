"""
Cache visualization utilities.

Generates visualizations for cache performance:
- Hit rate over time
- Memory usage trends
- Eviction patterns
- HTML dashboard
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheVisualizer:
    """
    Generate visualizations for cache metrics.

    Uses ASCII charts for terminal output and HTML/JSON for dashboards.
    """

    @staticmethod
    def generate_ascii_chart(
        data: List[float],
        title: str,
        width: int = 60,
        height: int = 10,
    ) -> str:
        """
        Generate ASCII line chart.

        Args:
            data: Data points to chart
            title: Chart title
            width: Chart width in characters
            height: Chart height in lines

        Returns:
            ASCII chart string
        """
        if not data:
            return f"{title}\nNo data available"

        # Normalize data to chart height
        min_val = min(data)
        max_val = max(data)
        value_range = max_val - min_val if max_val != min_val else 1

        # Create chart grid
        chart_lines = []

        # Add title
        chart_lines.append(f"\n{title}")
        chart_lines.append("=" * width)

        # Y-axis labels and chart
        for row in range(height, -1, -1):
            # Y-axis value
            y_val = min_val + (row / height) * value_range
            line = f"{y_val:6.1f} |"

            # Plot points
            for i, value in enumerate(data):
                col = int((i / len(data)) * (width - 10))
                if col < len(line) - 8:
                    continue

                # Determine if point should be plotted at this height
                normalized = (value - min_val) / value_range
                point_row = int(normalized * height)

                if point_row == row:
                    line += "*"
                else:
                    line += " "

            chart_lines.append(line)

        # X-axis
        chart_lines.append(" " * 8 + "-" * (width - 8))
        chart_lines.append(" " * 8 + "Time →")

        return "\n".join(chart_lines)

    @staticmethod
    def format_metrics_table(metrics: Dict[str, Any]) -> str:
        """
        Format metrics as ASCII table.

        Args:
            metrics: Metrics dictionary

        Returns:
            Formatted table string
        """
        lines = []
        lines.append("\n┌" + "─" * 48 + "┐")
        lines.append("│" + " " * 16 + "CACHE METRICS" + " " * 19 + "│")
        lines.append("├" + "─" * 48 + "┤")

        for key, value in metrics.items():
            # Format key (title case with spaces)
            formatted_key = key.replace("_", " ").title()

            # Format value
            if isinstance(value, float):
                formatted_value = f"{value:.2f}"
            elif isinstance(value, int):
                formatted_value = f"{value:,}"
            else:
                formatted_value = str(value)

            # Pad and add
            line = f"│ {formatted_key:<28} {formatted_value:>16} │"
            lines.append(line)

        lines.append("└" + "─" * 48 + "┘\n")

        return "\n".join(lines)

    @staticmethod
    def generate_dashboard_data(snapshots: List[Any]) -> Dict[str, Any]:
        """
        Generate data for dashboard visualization.

        Args:
            snapshots: List of CacheSnapshot objects

        Returns:
            Dashboard data dictionary
        """
        if not snapshots:
            return {}

        # Extract time series data
        timestamps = [datetime.fromtimestamp(s.timestamp).isoformat() for s in snapshots]
        hit_rates = [s.hit_rate_recent for s in snapshots]
        sizes = [s.size for s in snapshots]
        memory_usage = [s.memory_bytes / 1024 for s in snapshots]  # KB
        evictions = [s.evictions for s in snapshots]

        return {
            "timestamps": timestamps,
            "hit_rates": hit_rates,
            "sizes": sizes,
            "memory_usage_kb": memory_usage,
            "evictions": evictions,
            "summary": {
                "avg_hit_rate": sum(hit_rates) / len(hit_rates),
                "max_size": max(sizes),
                "max_memory_kb": max(memory_usage),
                "total_evictions": evictions[-1] if evictions else 0,
            },
        }

    @staticmethod
    def generate_html_dashboard(
        snapshots: List[Any],
        title: str = "Cache Performance Dashboard",
    ) -> str:
        """
        Generate HTML dashboard with charts.

        Args:
            snapshots: List of CacheSnapshot objects
            title: Dashboard title

        Returns:
            HTML string
        """
        dashboard_data = CacheVisualizer.generate_dashboard_data(snapshots)

        if not dashboard_data:
            return "<html><body><h1>No data available</h1></body></html>"

        # Generate HTML with Chart.js
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .metric-card .value {{
            font-size: 32px;
            font-weight: bold;
            margin: 0;
        }}
        .chart-container {{
            margin: 30px 0;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 8px;
        }}
        .chart-container h2 {{
            margin-top: 0;
            color: #555;
        }}
        canvas {{
            max-height: 300px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Average Hit Rate</h3>
                <p class="value">{dashboard_data['summary']['avg_hit_rate']:.1f}%</p>
            </div>
            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <h3>Peak Cache Size</h3>
                <p class="value">{dashboard_data['summary']['max_size']}</p>
            </div>
            <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                <h3>Peak Memory</h3>
                <p class="value">{dashboard_data['summary']['max_memory_kb']:.1f} KB</p>
            </div>
            <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <h3>Total Evictions</h3>
                <p class="value">{dashboard_data['summary']['total_evictions']}</p>
            </div>
        </div>

        <div class="chart-container">
            <h2>Hit Rate Over Time</h2>
            <canvas id="hitRateChart"></canvas>
        </div>

        <div class="chart-container">
            <h2>Cache Size & Memory Usage</h2>
            <canvas id="resourceChart"></canvas>
        </div>

        <div class="chart-container">
            <h2>Evictions</h2>
            <canvas id="evictionChart"></canvas>
        </div>
    </div>

    <script>
        const timestamps = {dashboard_data['timestamps']};
        const hitRates = {dashboard_data['hit_rates']};
        const sizes = {dashboard_data['sizes']};
        const memoryUsage = {dashboard_data['memory_usage_kb']};
        const evictions = {dashboard_data['evictions']};

        // Hit Rate Chart
        new Chart(document.getElementById('hitRateChart'), {{
            type: 'line',
            data: {{
                labels: timestamps,
                datasets: [{{
                    label: 'Hit Rate (%)',
                    data: hitRates,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.1,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Hit Rate (%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Time'
                        }}
                    }}
                }}
            }}
        }});

        // Resource Chart
        new Chart(document.getElementById('resourceChart'), {{
            type: 'line',
            data: {{
                labels: timestamps,
                datasets: [
                    {{
                        label: 'Cache Size',
                        data: sizes,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        yAxisID: 'y',
                    }},
                    {{
                        label: 'Memory (KB)',
                        data: memoryUsage,
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        yAxisID: 'y1',
                    }}
                ]
            }},
            options: {{
                responsive: true,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {{
                            display: true,
                            text: 'Cache Size'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {{
                            display: true,
                            text: 'Memory (KB)'
                        }},
                        grid: {{
                            drawOnChartArea: false,
                        }},
                    }}
                }}
            }}
        }});

        // Eviction Chart
        new Chart(document.getElementById('evictionChart'), {{
            type: 'line',
            data: {{
                labels: timestamps,
                datasets: [{{
                    label: 'Cumulative Evictions',
                    data: evictions,
                    borderColor: 'rgb(255, 159, 64)',
                    backgroundColor: 'rgba(255, 159, 64, 0.1)',
                    stepped: true,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Eviction Count'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

        return html

    @staticmethod
    def print_summary_report(
        report: Dict[str, Any],
        detailed: bool = False,
    ) -> None:
        """
        Print formatted summary report to console.

        Args:
            report: Monitoring report dictionary
            detailed: Whether to include detailed metrics
        """
        print("\n" + "=" * 70)
        print("CACHE PERFORMANCE SUMMARY")
        print("=" * 70)

        # Performance summary
        if "performance_summary" in report:
            perf = report["performance_summary"]
            print(f"\nPerformance Score: {perf['performance_score']}/100 ({perf['performance_tier']})")
            print(f"Hit Rate: {perf['hit_rate']:.1f}%")
            print(f"Capacity Utilization: {perf['capacity_utilization']:.1f}%")
            print(f"Eviction Rate: {perf['eviction_rate_pct']:.2f}%")
            print(f"Memory Usage: {perf['memory_usage_mb']:.2f} MB")

        # Trends
        if "trends" in report and detailed:
            trends = report["trends"]
            print("\nTrends:")
            print(f"  Hit Rate Trend: {trends.get('hit_rate_trend', 'unknown')}")
            print(f"  Average Hit Rate: {trends.get('avg_hit_rate', 0):.1f}%")
            print(f"  Total Hits: {trends.get('total_hits', 0):,}")
            print(f"  Total Misses: {trends.get('total_misses', 0):,}")
            print(f"  Total Evictions: {trends.get('total_evictions', 0):,}")
            print(f"  Peak Size: {trends.get('peak_size', 0)}")

        # Recommendations
        if "recommendations" in report:
            print("\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  - {rec}")

        print("\n" + "=" * 70 + "\n")


def generate_optimization_report(
    cache_stats: Dict[str, Any],
) -> List[str]:
    """
    Generate cache optimization recommendations.

    Args:
        cache_stats: Detailed cache statistics

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Hit rate analysis
    hit_rate = cache_stats.get("hit_rate", 0)
    if hit_rate < 50:
        recommendations.append(
            "CRITICAL: Low hit rate (<50%). "
            "Increase cache size or TTL immediately."
        )
    elif hit_rate < 70:
        recommendations.append(
            "WARNING: Moderate hit rate (<70%). "
            "Consider optimization."
        )

    # Memory analysis
    memory_mb = cache_stats.get("total_memory_estimate", 0) / (1024 * 1024)
    if memory_mb > 500:
        recommendations.append(
            f"HIGH MEMORY: Using {memory_mb:.1f}MB. "
            "Consider reducing cache size or TTL."
        )

    # Eviction vs TTL balance
    evictions = cache_stats.get("evictions", 0)
    ttl_expirations = cache_stats.get("ttl_expirations", 0)

    if evictions > ttl_expirations * 2:
        recommendations.append(
            "Evictions >> TTL expirations. "
            "Increase cache size or reduce TTL."
        )
    elif ttl_expirations > evictions * 2:
        recommendations.append(
            "TTL expirations >> evictions. "
            "Increase TTL for better utilization."
        )

    # Hot key analysis
    hot_keys = cache_stats.get("hot_keys", [])
    if hot_keys and len(hot_keys) > 0:
        top_key, top_count = hot_keys[0]
        total_ops = cache_stats.get("hits", 0) + cache_stats.get("misses", 0)

        if total_ops > 0:
            concentration = (top_count / total_ops) * 100
            if concentration > 30:
                recommendations.append(
                    f"HIGH KEY CONCENTRATION: Top key is {concentration:.1f}% of traffic. "
                    "Consider dedicated caching strategy for hot keys."
                )

    # Capacity utilization
    utilization = cache_stats.get("capacity_utilization", 0)
    if utilization > 95:
        recommendations.append(
            "Cache at capacity. Increase max_size to improve performance."
        )

    if not recommendations:
        recommendations.append("Cache configuration appears optimal.")

    return recommendations
