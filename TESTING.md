# Testing Guide

Complete testing framework with 203 tests across integration, performance, and cache effectiveness.

---

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Quick validation (5-7 minutes)
pytest tests/integration/ -v -k "smoke" -m "not slow"
pytest tests/performance/test_framework_validation.py -v
pytest tests/cache/test_cache_hit_rate.py::test_repeated_queries -v

# Full test suite (~2-3 hours)
pytest tests/ -v
```

---

## Test Coverage

| Component | Tests | Duration | Purpose |
|-----------|-------|----------|---------|
| **Integration** | 128 | 20-30 min | All 16 tools + E2E workflows |
| **Evaluation** | 10 questions | 60-90 min | Complex LLM workflows |
| **Performance** | 46 | 30-45 min | Latency, concurrency, pools |
| **Cache** | 29 | 5-10 min | Hit rates, TTL, eviction |
| **Total** | **203** | **~2-3 hours** | **Comprehensive** |

---

## Integration Tests

**Location**: `tests/integration/`
**Coverage**: All 16 tools, 6 E2E workflows
**Backend**: Production Neo4j + REST fallback

### Run Tests

```bash
# All integration tests
pytest tests/integration/ -v

# Specific tool
pytest tests/integration/test_tool01_gene_integration.py -v

# E2E workflows
pytest tests/integration/test_e2e_workflows.py -v

# Smoke tests only (fast)
pytest tests/integration/ -v -k "smoke"
```

### Test Structure

Each tool has 4 test types per mode:
1. **Smoke** - Basic functionality
2. **Happy path** - Known entities, validate structure
3. **Edge case** - Unknown entities, empty results
4. **Pagination** - Limit/offset functionality

**See**: `tests/integration/README.md` for details

---

## Evaluation Suite

**Location**: `evaluation/`
**Questions**: 10 complex biomedical scenarios
**Tool coverage**: 14/16 tools (87.5%)

### Run Evaluation

```bash
cd evaluation

# Full suite
python runner.py

# Single question
python runner.py --question q1

# Validate results
python validator.py results/evaluation_run_*.json
```

### Example Questions

**Q1: Drug-Target-Pathway** (Hard, 45-60s)
```
Imatinib targets → which Reactome pathway has most targets? →
extract regulatory subnetwork → report top 3 upstream regulators
```

**Q6: Identifier Resolution** (Medium, 30-45s)
```
HGNC IDs → gene symbols → UniProt → Ensembl →
find gene starting with 'T' → count tissues with gold expression
```

**See**: `evaluation/README.md` and `evaluation/questions.xml`

---

## Performance Tests

**Location**: `tests/performance/`
**Coverage**: Latency, concurrency, connection pools, cache
**Goal**: Benchmark and optimize

### Run Tests

```bash
# Full performance suite
python tests/performance/run_performance_tests.py --verbose

# Latency benchmarks only
pytest tests/performance/test_latency_benchmarks.py -v

# Concurrency tests
pytest tests/performance/test_concurrency.py -v

# View reports
ls -lh tests/performance/reports/
```

### Performance Targets

| Category | Target | Measure |
|----------|--------|---------|
| Simple queries (Tools 11-16) | <1000ms | p95 latency |
| Moderate queries (Tools 6-10) | <2000ms | p95 latency |
| Complex queries (Tools 1-5) | <5000ms | p95 latency |
| 10x concurrent | <10000ms | Total time |
| 60x concurrent | >90% | Success rate |
| Pool utilization | <50% | Normal load |

**See**: `tests/performance/README.md`

---

## Cache Effectiveness

**Location**: `tests/cache/`
**Coverage**: Hit rate, TTL, eviction, monitoring
**Goal**: Optimize cache configuration

### Run Tests

```bash
# All cache tests
pytest tests/cache/ -v

# Specific test suites
pytest tests/cache/test_cache_hit_rate.py -v
pytest tests/cache/test_cache_ttl.py -v
pytest tests/cache/test_cache_eviction.py -v

# Real-time monitoring
python tests/cache/dashboard/monitor.py --duration 60 --interval 5
```

### Cache Metrics

- **Hit rate**: 75-90% typical workloads
- **Speedup**: 10-15x for cached queries
- **Memory**: 50-200MB for 100-1000 entries
- **TTL**: 3600s (1 hour) default

**See**: `tests/cache/README.md`

---

## Configuration

### Environment Variables

```bash
# Production backend (.env.production)
NEO4J_URL=bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=newton-heroic-lily-sharp-malta-5377
USE_REST_FALLBACK=true

# Performance settings
NEO4J_MAX_CONNECTION_POOL_SIZE=50
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CHARACTER_LIMIT=25000
```

### Test Markers

```bash
# Run by marker
pytest -v -m integration   # Integration tests only
pytest -v -m performance   # Performance tests only
pytest -v -m cache         # Cache tests only
pytest -v -m "not slow"    # Exclude slow tests
pytest -v -m slow          # Only slow tests
```

---

## Troubleshooting

### Tests Fail to Connect

1. **Check Neo4j credentials**:
   ```bash
   cat .env.production | grep NEO4J
   ```

2. **Test connectivity**:
   ```bash
   nc -zv indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com 7687
   ```

3. **Enable REST fallback**:
   ```bash
   echo "USE_REST_FALLBACK=true" >> .env.production
   ```

### Slow Tests

- Use `pytest -v -m "not slow"` to skip long-running tests
- Reduce enrichment permutations (100 vs 1000)
- Use smaller limits for pagination tests
- Run specific test files instead of full suite

### Memory Issues

- Reduce connection pool size: `NEO4J_MAX_CONNECTION_POOL_SIZE=25`
- Decrease cache size: `CACHE_MAX_SIZE=500`
- Run tests sequentially: `pytest -v --tb=short`

---

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run smoke tests
        run: |
          pytest tests/integration/ -v -k "smoke" -m "not slow"

      - name: Run unit tests
        run: |
          pytest tests/ -v --cov=cogex_mcp
```

---

## Next Steps

1. **Run quick validation** to ensure everything works
2. **Review test reports** for performance insights
3. **Optimize based on recommendations** from performance tests
4. **Add to CI/CD** for automated testing
5. **Run evaluation suite** to test LLM integration

---

**Test Status**: ✅ All 203 tests implemented and ready
**Production Ready**: Yes, with comprehensive validation
