# Performance Testing Framework

Comprehensive performance profiling framework for INDRA CoGEx MCP server with 16 production-ready tools.

## Overview

This framework provides:
- **Latency Benchmarks**: Measure p50, p95, p99 latencies for all 16 tools
- **Concurrency Tests**: Validate behavior under 10x, 60x, 100x concurrent load
- **Connection Pool Analysis**: Monitor pool utilization and efficiency
- **Cache Performance**: Measure hit rates and warmup effectiveness
- **Optimization Recommendations**: Automated performance analysis

## Test Structure

```
tests/performance/
├── __init__.py
├── conftest.py                    # Performance test fixtures
├── profiler.py                    # Profiling utilities
├── test_latency_benchmarks.py     # Latency tests for all 16 tools
├── test_concurrency.py            # Concurrent query tests
├── test_connection_pool.py        # Pool efficiency tests
├── test_cache_warmup.py           # Cache performance tests
├── reports/                       # Generated performance reports (JSON)
│   ├── latency_report.json
│   ├── concurrency_report.json
│   ├── connection_pool_report.json
│   └── recommendations.json
└── README.md                      # This file
```

## Performance Targets

### Latency Benchmarks

| Tool Category | Tools | p95 Target |
|--------------|-------|------------|
| Complex Queries | Tools 1-5 | < 5000ms |
| Moderate Queries | Tools 6-10 | < 2000ms |
| Simple Queries | Tools 11-16 | < 1000ms |

### Concurrency Targets

| Test | Target |
|------|--------|
| 10x concurrent | < 10000ms total, 100% success |
| 60x concurrent | > 90% success rate |
| 100x stress test | Circuit breaker activation |

### Connection Pool Targets

- Pool size: 50 connections
- Normal load utilization: < 50%
- Saturation handling: > 85% success at 60 concurrent
- Recovery time: < 2 seconds

## Running Tests

### Run All Performance Tests

```bash
# From project root
pytest tests/performance/ -v --log-cli-level=INFO
```

### Run Specific Test Categories

```bash
# Latency benchmarks only
pytest tests/performance/test_latency_benchmarks.py -v

# Concurrency tests only
pytest tests/performance/test_concurrency.py -v

# Connection pool tests only
pytest tests/performance/test_connection_pool.py -v

# Cache tests only
pytest tests/performance/test_cache_warmup.py -v
```

### Run Individual Tool Benchmarks

```bash
# Benchmark Tool 1 only
pytest tests/performance/test_latency_benchmarks.py::TestLatencyBenchmarks::test_tool01_gene_to_features -v

# Benchmark Tool 4 only
pytest tests/performance/test_latency_benchmarks.py::TestLatencyBenchmarks::test_tool04_drug_to_targets -v
```

### Generate Performance Reports

```bash
# Run all tests and generate reports
pytest tests/performance/ -v --log-cli-level=INFO

# View generated reports
ls -lh tests/performance/reports/

# Print summary
python -c "
from tests.performance.profiler import PerformanceProfiler
profiler = PerformanceProfiler()
profiler.print_summary()
"
```

## Configuration

### Environment Variables

Set these in `.env.production`:

```bash
# Neo4j Connection
NEO4J_URL=bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>

# Performance Settings
NEO4J_MAX_CONNECTION_POOL_SIZE=50
NEO4J_CONNECTION_TIMEOUT=30
NEO4J_MAX_CONNECTION_LIFETIME=3600

# Cache Configuration
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CACHE_TTL_SECONDS=3600
```

### Test Parameters

Modify test parameters in `conftest.py`:

```python
# Latency benchmark iterations
iterations = 10  # Number of runs per test

# Concurrency test scales
concurrent_10x = 10
concurrent_60x = 60
concurrent_100x = 100

# Connection pool monitoring
pool_size = 50
connection_timeout = 30
```

## Performance Reports

### Latency Report Format

```json
{
  "generated_at": "2025-11-24T22:00:00",
  "tools": {
    "tool_01_gene_feature": {
      "gene_to_features": {
        "mean": 1250.5,
        "median": 1200.0,
        "p95": 1800.0,
        "p99": 2100.0,
        "min": 950.0,
        "max": 2200.0,
        "stdev": 250.3
      }
    }
  }
}
```

### Concurrency Report Format

```json
{
  "generated_at": "2025-11-24T22:00:00",
  "tests": {
    "10x_concurrent": {
      "concurrent_count": 10,
      "total_time_ms": 3500.0,
      "avg_time_per_query_ms": 350.0,
      "success_rate_pct": 100.0,
      "error_count": 0
    }
  }
}
```

### Connection Pool Report Format

```json
{
  "generated_at": "2025-11-24T22:00:00",
  "tests": {
    "basic_utilization": {
      "summary": {
        "query_count": 100,
        "avg_latency_ms": 1200.0,
        "max_active_connections": 3,
        "pool_size": 50,
        "utilization_pct": 6.0
      }
    }
  }
}
```

## Optimization Recommendations

The profiler automatically generates optimization recommendations based on test results:

```python
from tests.performance.profiler import PerformanceProfiler

profiler = PerformanceProfiler()
profiler.save_recommendations()

# View recommendations
with open("tests/performance/reports/recommendations.json") as f:
    print(json.load(f))
```

Example recommendations:

```
⚠️ tool_01_gene_feature/gene_to_features: High p95 latency (5500ms). Consider query optimization or caching.
⚠️ 60x_pool_saturation: Low success rate (85%). Review connection pool size.
✓ basic_utilization: Connection pool underutilized (6%). Pool size is adequate.

💡 General Best Practices:
  • Enable caching for frequently queried entities
  • Monitor circuit breaker activation patterns
  • Use pagination for large result sets
  • Consider read replicas for Neo4j if query load is high
```

## Interpreting Results

### Latency Benchmarks

- **p50 (median)**: Typical query performance
- **p95**: 95% of queries complete within this time
- **p99**: 99% of queries complete within this time
- **High stdev**: Indicates inconsistent performance

### Concurrency Tests

- **Success rate**: Percentage of successful queries
- **Total time**: End-to-end time for all concurrent queries
- **Errors**: Circuit breaker, timeout, or connection errors

### Connection Pool

- **Utilization**: Percentage of pool in use
- **High utilization**: May need larger pool
- **Low utilization**: Pool size is adequate
- **Saturation**: Queries waiting for connections

## Troubleshooting

### High Latency

1. Check network latency to Neo4j
2. Review Cypher query complexity
3. Enable query profiling in Neo4j
4. Consider adding indexes

### Connection Pool Saturation

1. Increase `NEO4J_MAX_CONNECTION_POOL_SIZE`
2. Increase `NEO4J_CONNECTION_TIMEOUT`
3. Monitor connection lifecycle
4. Review circuit breaker thresholds

### Circuit Breaker Activation

1. Review failure threshold (default: 5)
2. Check recovery timeout (default: 60s)
3. Monitor backend health
4. Review error patterns

### Cache Misses

1. Increase `CACHE_MAX_SIZE`
2. Review cache eviction patterns
3. Adjust `CACHE_TTL_SECONDS`
4. Implement cache warmup strategy

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run performance tests
        env:
          NEO4J_URL: ${{ secrets.NEO4J_URL }}
          NEO4J_USER: ${{ secrets.NEO4J_USER }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
        run: |
          pytest tests/performance/ -v --log-cli-level=INFO
      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: performance-reports
          path: tests/performance/reports/
```

## Development

### Adding New Tests

1. Create test method in appropriate test file
2. Use `_benchmark_query()` helper for latency tests
3. Save results with `performance_profiler.save_*_report()`
4. Add assertions for performance targets

Example:

```python
async def test_new_tool_benchmark(
    self, performance_adapter, performance_profiler, known_entities
):
    """Benchmark new tool."""
    latencies = await self._benchmark_query(
        performance_adapter,
        "tool_name",
        "mode",
        {"param": "value"},
    )

    stats = PerformanceProfiler.calculate_statistics(latencies)
    performance_profiler.save_latency_report("tool_name", "mode", stats)

    assert stats["p95"] < 2000
```

## References

- [Neo4j Performance Tuning](https://neo4j.com/docs/operations-manual/current/performance/)
- [asyncio Best Practices](https://docs.python.org/3/library/asyncio.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
