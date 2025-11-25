# Cache Effectiveness Analysis Framework

Comprehensive framework for analyzing, monitoring, and optimizing cache performance in the INDRA CoGEx MCP server.

## Overview

This framework provides:
- **Hit Rate Analysis**: Measure and optimize cache effectiveness across different query patterns
- **TTL Optimization**: Determine optimal Time-To-Live settings through experimentation
- **Eviction Analysis**: Validate LRU eviction policies and track memory management
- **Real-time Monitoring**: Live dashboard with performance metrics and trend analysis
- **Optimization Recommendations**: Automated suggestions based on cache behavior

## Quick Start

### Run All Cache Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all cache tests
pytest tests/cache/ -v -m cache

# Run specific test categories
pytest tests/cache/test_cache_hit_rate.py -v      # Hit rate tests
pytest tests/cache/test_cache_ttl.py -v           # TTL tests
pytest tests/cache/test_cache_eviction.py -v      # Eviction tests
```

### Real-time Monitoring

```bash
# Monitor cache for 60 seconds with 5-second intervals
python tests/cache/dashboard/monitor.py --duration 60 --interval 5

# Export monitoring data to JSON
python tests/cache/dashboard/monitor.py --duration 120 --output cache_metrics.json
```

## Test Structure

```
tests/cache/
├── __init__.py
├── conftest.py                 # Fixtures and test utilities
├── test_cache_hit_rate.py      # Hit rate analysis tests
├── test_cache_ttl.py           # TTL effectiveness tests
├── test_cache_eviction.py      # Eviction policy tests
└── dashboard/
    ├── __init__.py
    ├── monitor.py              # Real-time monitoring
    ├── visualizer.py           # Visualization utilities
    └── templates/
        └── dashboard.html      # HTML dashboard template
```

## Enhanced Cache Service

The cache service has been enhanced with detailed metrics tracking:

```python
from cogex_mcp.services.cache import get_cache

cache = get_cache()

# Get detailed statistics
stats = cache.get_detailed_stats()
print(f"Hit rate: {stats['hit_rate']:.1f}%")
print(f"Recent hit rate: {stats['hit_rate_recent']:.1f}%")
print(f"Hot keys: {stats['hot_keys'][:5]}")
print(f"Memory usage: {stats['total_memory_estimate']/1024:.1f} KB")
print(f"TTL expirations: {stats['ttl_expirations']}")
print(f"Evictions: {stats['evictions']}")
```

## Test Categories

### 1. Hit Rate Analysis (`test_cache_hit_rate.py`)

Tests cache effectiveness under various scenarios:

- **Repeated Queries**: Verify hit rate improves with query repetition
- **Tool-Specific Patterns**: Measure effectiveness per tool type
- **Mixed Workloads**: Test with realistic 80/20 access patterns
- **Hot Key Tracking**: Validate frequent access patterns
- **Performance Measurement**: Quantify speedup from caching

**Example Test:**
```python
async def test_cache_hit_rate_with_repeated_queries(mock_query_adapter):
    """Test hit rate improves with repeated queries."""
    gene = "TP53"

    # Execute 100 queries
    for i in range(100):
        await mock_query_adapter.query_tool(
            "cogex_query_gene_or_feature",
            {"gene": gene}
        )

    stats = mock_query_adapter.cache.get_detailed_stats()
    assert stats["hit_rate_recent"] > 80.0
```

### 2. TTL Effectiveness (`test_cache_ttl.py`)

Tests Time-To-Live behavior and optimization:

- **Expiration Correctness**: Verify TTL works as expected
- **Optimal TTL Determination**: Find best TTL through experimentation
- **Memory Impact**: Analyze TTL effects on memory usage
- **Workload Patterns**: Test with realistic query patterns

**Example Test:**
```python
async def test_ttl_expiration_behavior(short_ttl_cache):
    """Test TTL expiration works correctly."""
    cache = short_ttl_cache  # 5-second TTL

    # Cache entry
    await cache.set("key", "value")

    # Immediate access - cache hit
    assert await cache.get("key") == "value"

    # Wait for TTL expiration
    await asyncio.sleep(6)

    # Access after expiration - cache miss
    assert await cache.get("key") is None
```

### 3. Eviction Policy (`test_cache_eviction.py`)

Tests LRU eviction behavior:

- **LRU Order Verification**: Ensure least recently used items are evicted
- **Eviction Count Tracking**: Validate accurate tracking
- **Hot Key Protection**: Verify frequently accessed keys resist eviction
- **Memory Management**: Test memory is managed correctly

**Example Test:**
```python
async def test_lru_eviction_policy(small_cache):
    """Test LRU eviction works correctly."""
    cache = small_cache  # Max size: 10

    # Fill cache
    for i in range(10):
        await cache.set(f"key_{i}", f"value_{i}")

    # Access key_0 (make it recently used)
    await cache.get("key_0")

    # Add new item - should evict key_1 (least recently used)
    await cache.set("key_10", "value_10")

    # Verify
    assert await cache.get("key_0") is not None  # Still cached
    assert await cache.get("key_1") is None       # Evicted
```

## Real-time Monitoring

The monitoring framework provides continuous cache observation:

### Features

- **Live Metrics Collection**: Captures snapshots at regular intervals
- **Trend Analysis**: Identifies performance trends over time
- **Performance Scoring**: Rates cache performance (0-100)
- **Automated Recommendations**: Suggests optimizations
- **Export Capabilities**: Save metrics to JSON for analysis

### Usage

```python
from cogex_mcp.services.cache import get_cache
from tests.cache.dashboard.monitor import CacheMonitor

cache = get_cache()
monitor = CacheMonitor(cache, update_interval=5)

# Monitor for 5 minutes
report = await monitor.start_monitoring(duration=300, verbose=True)

print(f"Performance Score: {report['performance_summary']['performance_score']}/100")
print(f"Recommendations: {report['recommendations']}")
```

### Sample Output

```
[10:30:15] Hit Rate: 87.3% | Size: 45/100 | Hits: 234 | Misses: 32 | Memory: 128.5KB
[10:30:20] Hit Rate: 89.1% | Size: 47/100 | Hits: 267 | Misses: 35 | Memory: 132.1KB
[10:30:25] Hit Rate: 90.5% | Size: 48/100 | Hits: 301 | Misses: 37 | Memory: 134.8KB

======================================================================
CACHE PERFORMANCE SUMMARY
======================================================================

Performance Score: 87.5/100 (Good)
Hit Rate: 90.5%
Capacity Utilization: 48.0%
Memory Usage: 0.13 MB

Recommendations:
  - Cache performance appears optimal. No changes recommended.
```

## Dashboard Visualization

Generate HTML dashboards with interactive charts:

```python
from tests.cache.dashboard.visualizer import CacheVisualizer

# Generate HTML dashboard
html = CacheVisualizer.generate_html_dashboard(
    snapshots=monitor.snapshots,
    title="Cache Performance Dashboard"
)

# Save to file
with open("cache_dashboard.html", "w") as f:
    f.write(html)
```

The dashboard includes:
- Real-time metric cards (hit rate, size, memory, performance)
- Hit rate trend chart
- Cache size & memory usage chart
- Operations breakdown chart
- Optimization recommendations

## Optimization Recommendations

The framework generates actionable recommendations:

### Example Recommendations

**Low Hit Rate (<50%)**
```
CRITICAL: Very low hit rate (<50%).
Increase cache size or TTL immediately.
```

**High Eviction Rate**
```
High eviction rate (>20% of hits).
Increasing cache size will improve hit rate.
```

**TTL vs Eviction Imbalance**
```
TTL expirations >> evictions.
Consider increasing TTL for better cache utilization.
```

**Capacity Issues**
```
Cache near capacity (>95%).
Increase max_size to reduce evictions.
```

**Hot Key Concentration**
```
HIGH KEY CONCENTRATION: Top key is 35.2% of traffic.
Consider dedicated caching strategy for hot keys.
```

## Metrics Reference

### Core Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| `hit_rate` | Overall cache hit percentage | >70% |
| `hit_rate_recent` | Recent (last 1000 ops) hit rate | >70% |
| `size` | Current cache entries | 60-80% of max_size |
| `evictions` | Total evictions since start | Low relative to hits |
| `ttl_expirations` | TTL-based removals | Balanced with evictions |
| `hot_keys` | Most frequently accessed keys | Helps identify patterns |
| `total_memory_estimate` | Estimated memory usage | <100MB typical |
| `capacity_utilization` | Cache fullness (%) | 60-80% optimal |

### Performance Tiers

| Score | Tier | Meaning |
|-------|------|---------|
| 90-100 | Excellent | Optimal performance |
| 75-89 | Good | Well-configured |
| 60-74 | Acceptable | Minor optimization possible |
| 40-59 | Poor | Needs optimization |
| 0-39 | Critical | Immediate action required |

## Advanced Usage

### Custom Workload Simulation

```python
from tests.cache.conftest import simulate_realistic_workload

# Simulate realistic query patterns
hit_rate = await simulate_realistic_workload(
    adapter=mock_query_adapter,
    duration=60  # seconds
)

print(f"Achieved hit rate: {hit_rate:.1f}%")
```

### Capacity Planning

```python
# Test different cache sizes
cache_sizes = [50, 100, 200, 500]
results = []

for size in cache_sizes:
    cache = CacheService(max_size=size, ttl_seconds=3600)
    adapter = MockQueryAdapter(cache)

    # Run workload
    hit_rate = await simulate_realistic_workload(adapter, duration=30)

    results.append({
        "size": size,
        "hit_rate": hit_rate,
        "memory": cache.get_detailed_stats()["total_memory_estimate"]
    })

# Find optimal size
optimal = max(results, key=lambda x: x["hit_rate"])
print(f"Optimal cache size: {optimal['size']}")
```

### TTL Experimentation

```python
# Find optimal TTL
ttl_values = [300, 600, 1800, 3600, 7200]  # 5min to 2hr
results = []

for ttl in ttl_values:
    cache = CacheService(max_size=100, ttl_seconds=ttl)
    adapter = MockQueryAdapter(cache)

    hit_rate = await simulate_realistic_workload(adapter, duration=30)

    results.append({
        "ttl": ttl,
        "hit_rate": hit_rate,
    })

optimal_ttl = max(results, key=lambda x: x["hit_rate"])
print(f"Optimal TTL: {optimal_ttl['ttl']}s")
```

## Integration with Production

### Monitoring Production Cache

```python
from cogex_mcp.services.cache import get_cache
from tests.cache.dashboard.monitor import run_monitoring_session

# Get production cache instance
cache = get_cache()

# Run monitoring session
report = await run_monitoring_session(
    cache=cache,
    duration=3600,  # 1 hour
    interval=10      # 10-second snapshots
)

# Analyze and act on recommendations
for rec in report["recommendations"]:
    print(f"Action needed: {rec}")
```

### Exporting Metrics

```python
from tests.cache.dashboard.monitor import CacheMonitor

monitor = CacheMonitor(cache)
await monitor.start_monitoring(duration=300)

# Export to JSON for analysis
monitor.export_snapshots("metrics/cache_metrics_2024_11_24.json")
```

## Troubleshooting

### Low Hit Rate

1. Check if cache size is sufficient
2. Verify TTL isn't too short
3. Analyze query patterns for uniqueness
4. Review hot keys for concentration

### High Memory Usage

1. Reduce cache size
2. Decrease TTL
3. Check for large cached values
4. Monitor eviction patterns

### Frequent Evictions

1. Increase cache size
2. Analyze if TTL could be shorter
3. Review access patterns
4. Consider cache warming strategies

## Performance Benchmarks

Typical performance with default settings:

- **Hit Rate**: 75-90% for typical workloads
- **Speedup**: 5-10x for cached queries
- **Memory**: 50-200MB depending on size
- **Overhead**: <5ms per cache operation

## Contributing

When adding new cache tests:

1. Use `@pytest.mark.cache` decorator
2. Leverage fixtures from `conftest.py`
3. Include performance assertions
4. Add descriptive docstrings
5. Update this README with new features

## References

- [PHASE6_PLAN.md](../../PHASE6_PLAN.md) - Overall testing strategy
- [src/cogex_mcp/services/cache.py](../../src/cogex_mcp/services/cache.py) - Cache implementation
- [cachetools documentation](https://cachetools.readthedocs.io/) - Underlying cache library
