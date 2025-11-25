# Phase 6: Evaluation, Testing & Performance Framework

**Version**: 2.0.0
**Date**: 2025-11-24
**Status**: Planning Complete - Ready for Implementation

---

## Overview

Comprehensive framework to validate, evaluate, and optimize the INDRA CoGEx MCP server with 16 production-ready tools.

**Goals**:
1. **Validation**: Ensure all 16 tools work correctly with live CoGEx backend
2. **Evaluation**: Create 10 complex, realistic questions to test LLM effectiveness
3. **Performance**: Profile, measure, and optimize query performance
4. **Monitoring**: Quantify cache effectiveness and connection health

---

## Component 1: Integration Testing Framework

**Purpose**: Validate all 16 tools against live CoGEx Neo4j backend

**Expert Persona**: Senior QA/Test Engineer with distributed systems expertise

### 1.1 Integration Test Suite (`tests/integration/`)

**File Structure**:
```
tests/integration/
├── __init__.py
├── conftest.py              # Shared fixtures, connection setup
├── test_tool01_gene.py      # Tool 1 integration tests
├── test_tool02_subnetwork.py
├── test_tool03_enrichment.py
├── test_tool04_drug.py
├── test_tool05_disease.py
├── test_tool06_pathway.py
├── test_tool07_cell_line.py
├── test_tool08_trials.py
├── test_tool09_literature.py
├── test_tool10_variants.py
├── test_tool11_identifier.py
├── test_tool12_relationship.py
├── test_tool13_ontology.py
├── test_tool14_cell_marker.py
├── test_tool15_kinase.py
├── test_tool16_protein.py
└── test_e2e_workflows.py    # Complex multi-tool workflows
```

**Test Categories per Tool**:
1. **Smoke Tests**: Basic connectivity, single valid query
2. **Happy Path**: All modes with known-good entities
3. **Edge Cases**: Empty results, invalid entities, malformed inputs
4. **Pagination**: Large result sets, offset/limit combinations
5. **Format Tests**: Markdown vs JSON output validation
6. **Error Handling**: Backend failures, timeout handling
7. **Performance**: Query latency benchmarks

**Example Test Structure**:
```python
# tests/integration/test_tool01_gene.py

import pytest
from cogex_mcp.schemas import GeneFeatureQuery, QueryMode, ResponseFormat

@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1Integration:
    """Integration tests for Tool 1: cogex_query_gene_or_feature"""

    async def test_gene_to_features_tp53_happy_path(self, mcp_client):
        """Test gene_to_features mode with TP53 (well-known gene)"""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            response_format=ResponseFormat.JSON,
        )

        result = await mcp_client.call_tool("cogex_query_gene_or_feature", query.model_dump())

        # Assertions
        assert result is not None
        assert "TP53" in result
        assert "expression" in result or "tissues" in result
        assert len(result) > 100  # Should have substantial data

    async def test_tissue_to_genes_brain_pagination(self, mcp_client):
        """Test tissue_to_genes with pagination"""
        query = GeneFeatureQuery(
            mode=QueryMode.TISSUE_TO_GENES,
            tissue="brain",
            limit=50,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result = await mcp_client.call_tool("cogex_query_gene_or_feature", query.model_dump())

        # Validate pagination
        assert "pagination" in result
        assert result["pagination"]["count"] <= 50
        assert result["pagination"]["has_more"] in [True, False]

    async def test_invalid_gene_error_handling(self, mcp_client):
        """Test error handling for non-existent gene"""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="FAKEGENE123456",
            response_format=ResponseFormat.JSON,
        )

        with pytest.raises(Exception) as exc:
            await mcp_client.call_tool("cogex_query_gene_or_feature", query.model_dump())

        # Should have actionable error message
        assert "not found" in str(exc.value).lower() or "resolve" in str(exc.value).lower()
```

**Fixtures** (`conftest.py`):
```python
@pytest.fixture(scope="session")
async def neo4j_connection():
    """Production Neo4j connection for integration tests"""
    from cogex_mcp.clients.neo4j_client import get_neo4j_client
    client = await get_neo4j_client()
    yield client
    await client.close()

@pytest.fixture(scope="session")
async def mcp_client(neo4j_connection):
    """MCP client with live backend"""
    from cogex_mcp.clients.adapter import get_adapter
    adapter = await get_adapter()
    yield adapter
    await adapter.close()

@pytest.fixture
def known_entities():
    """Known-good entities for testing"""
    return {
        "genes": ["TP53", "BRCA1", "EGFR", "MAPK1"],
        "drugs": ["imatinib", "aspirin", "pembrolizumab"],
        "diseases": ["diabetes", "alzheimer disease", "breast cancer"],
        "tissues": ["brain", "liver", "blood"],
        "pathways": ["p53 signaling", "MAPK signaling"],
    }
```

**Implementation Requirements**:
- Use `pytest-asyncio` for async tests
- Mark with `@pytest.mark.integration` for selective running
- Each tool: minimum 5 tests (smoke, happy, edge, pagination, error)
- Total: ~80-100 integration tests
- Expected runtime: 5-10 minutes against live backend

---

## Component 2: End-to-End Workflow Tests

**Purpose**: Test realistic multi-tool workflows that simulate actual LLM usage

**Expert Persona**: Senior Backend Engineer with workflow orchestration expertise

### 2.1 E2E Test Scenarios (`tests/integration/test_e2e_workflows.py`)

**Workflow Categories**:

**1. Drug Discovery Workflow**:
```python
async def test_drug_discovery_workflow(mcp_client, known_entities):
    """
    Workflow: Drug → Targets → Pathways → Related Genes → Enrichment

    Simulates: "What does imatinib target and what pathways are affected?"
    """
    # Step 1: Get drug targets (Tool 4)
    targets = await query_drug_profile("imatinib")
    assert len(targets) > 0

    # Step 2: Get pathways for top target (Tool 6)
    target_genes = [t.target.name for t in targets[:5]]
    pathways = await query_gene_pathways(target_genes[0])

    # Step 3: Find genes in shared pathways (Tool 6)
    shared = await find_shared_pathways(target_genes)

    # Step 4: Enrichment analysis (Tool 3)
    enrichment = await enrichment_analysis(target_genes, source="reactome")

    # Assertions
    assert "BCR" in target_genes or "ABL1" in target_genes  # Known targets
    assert len(enrichment) > 0
```

**2. Disease Mechanism Workflow**:
```python
async def test_disease_mechanism_workflow(mcp_client):
    """
    Workflow: Disease → Genes → Variants → Drugs → Trials

    Simulates: "What are the mechanisms and therapies for Alzheimer's?"
    """
    # Step 1: Disease mechanisms (Tool 5)
    mechanisms = await query_disease("alzheimer disease", include_genes=True, include_drugs=True)

    # Step 2: Get variants for top genes (Tool 10)
    genes = mechanisms.genes[:5]
    variants = await query_variants_for_gene(genes[0].gene.name)

    # Step 3: Check if known variant associated (Tool 12)
    apoe_check = await check_relationship("variant_association", "rs7412", "alzheimer disease")

    # Step 4: Clinical trials (Tool 8)
    trials = await query_trials_for_disease("alzheimer disease")

    # Assertions
    assert "APOE" in [g.gene.name for g in genes]  # Known gene
    assert apoe_check.exists == True  # rs7412 is known APOE variant
    assert len(trials) > 0
```

**3. Pathway Analysis Workflow**:
```python
async def test_pathway_analysis_workflow(mcp_client):
    """
    Workflow: Pathway → Genes → Subnetwork → Enrichment

    Simulates: "Analyze the p53 pathway network"
    """
    # Step 1: Get pathway genes (Tool 6)
    pathway_genes = await query_pathway_genes("p53 signaling")

    # Step 2: Extract subnetwork (Tool 2)
    subnetwork = await extract_subnetwork(pathway_genes[:10], mode="shared_upstream")

    # Step 3: Enrichment on regulators (Tool 3)
    regulators = [s.subject.name for s in subnetwork.statements]
    enrichment = await enrichment_analysis(list(set(regulators)), source="go")

    # Step 4: Check TP53 in pathway (Tool 12)
    tp53_check = await check_relationship("gene_in_pathway", "TP53", "p53 signaling")

    # Assertions
    assert "TP53" in pathway_genes
    assert tp53_check.exists == True
    assert len(subnetwork.statements) > 0
```

**4. Cell Line Analysis Workflow**:
```python
async def test_cell_line_analysis_workflow(mcp_client):
    """
    Workflow: Cell Line → Mutations → Drug Sensitivity → Pathways

    Simulates: "What are the druggable mutations in A549 cells?"
    """
    # Step 1: Get cell line mutations (Tool 7)
    mutations = await query_cell_line_mutations("A549")

    # Step 2: Check if mutation exists (Tool 12)
    kras_mut = await check_relationship("cell_line_mutation", "A549", "KRAS")

    # Step 3: Find drugs targeting mutated genes (Tool 4)
    mutated_genes = [m.gene.name for m in mutations[:5]]
    drugs = await query_drugs_for_targets(mutated_genes)

    # Step 4: Get pathways for mutated genes (Tool 6)
    pathways = await find_shared_pathways(mutated_genes)

    # Assertions
    assert kras_mut.exists == True  # A549 has KRAS mutation
    assert len(drugs) > 0
```

**5. Identifier Resolution Workflow**:
```python
async def test_identifier_workflow(mcp_client):
    """
    Workflow: Gene Symbols → HGNC IDs → UniProt IDs → Functions

    Simulates: "Convert gene list and get protein functions"
    """
    symbols = ["TP53", "BRCA1", "EGFR"]

    # Step 1: Symbol to HGNC (Tool 11)
    hgnc_ids = await resolve_identifiers(symbols, "hgnc.symbol", "hgnc")

    # Step 2: HGNC to UniProt (Tool 11)
    uniprot_ids = await resolve_identifiers(
        [m.target_ids[0] for m in hgnc_ids.mappings],
        "hgnc",
        "uniprot"
    )

    # Step 3: Get protein functions (Tool 16)
    functions = await query_protein_functions(symbols[0], mode="gene_to_activities")

    # Step 4: Check if kinase (Tool 16)
    kinase_check = await check_function_types(["EGFR"], ["kinase"])

    # Assertions
    assert len(hgnc_ids.mappings) == 3
    assert kinase_check["EGFR"]["kinase"] == True
```

**Implementation**:
- 10-15 E2E workflows
- Each workflow: 4-6 tool invocations
- Test realistic LLM usage patterns
- Validate data consistency across tools
- Expected runtime: 3-5 minutes

---

## Component 3: Evaluation Suite

**Purpose**: Create 10 complex questions to evaluate LLM effectiveness with MCP server

**Expert Persona**: ML Evaluation Engineer with biomedical domain expertise

### 3.1 Evaluation Framework (`evaluation/`)

**File Structure**:
```
evaluation/
├── questions.xml            # 10 evaluation questions
├── run_evaluation.py        # Evaluation runner
├── evaluate_responses.py    # Response validator
├── results/
│   ├── run_001_results.json
│   └── run_001_analysis.md
└── README.md
```

**Evaluation Questions** (`questions.xml`):

Following MCP evaluation best practices, each question must be:
- **Independent**: Not dependent on other questions
- **Read-only**: Non-destructive operations only
- **Complex**: Requiring 3-5+ tool calls
- **Realistic**: Based on actual biomedical research questions
- **Verifiable**: Single correct answer with string comparison
- **Stable**: Answer won't change over time

**Example Questions**:

```xml
<evaluation>
  <qa_pair>
    <question>
      The tumor suppressor gene TP53 is mutated in many cancers. Find the cell line
      in the CCLE database that has a TP53 mutation and also expresses the highest
      number of kinases. What is the DepMap ID of this cell line?
    </question>
    <answer>ACH-000001</answer>
    <tools_required>
      cogex_query_cell_line (get_cell_lines_with_mutation),
      cogex_query_protein_functions (check_function_types),
      cogex_query_gene_or_feature (tissue_to_genes)
    </tools_required>
    <complexity>high</complexity>
    <estimated_tool_calls>5-7</estimated_tool_calls>
  </qa_pair>

  <qa_pair>
    <question>
      Imatinib (Gleevec) is a targeted cancer therapy. Find all genes that imatinib
      targets, then identify which Reactome pathway is shared by the most targets.
      What is the Reactome ID (R-HSA-XXXXXX) of this pathway?
    </question>
    <answer>R-HSA-109582</answer>
    <tools_required>
      cogex_query_drug_or_effect (drug_to_profile),
      cogex_query_pathway (find_shared),
      cogex_check_relationship (gene_in_pathway)
    </tools_required>
    <complexity>high</complexity>
    <estimated_tool_calls>4-6</estimated_tool_calls>
  </qa_pair>

  <qa_pair>
    <question>
      Alzheimer's disease is associated with the APOE gene. Find the rsID of the
      variant in APOE with the lowest p-value in GWAS studies for Alzheimer's disease.
      Then check if this variant is also associated with cardiovascular disease using
      relationship validation. Answer format: "rsXXXXXXX,Yes" or "rsXXXXXXX,No"
    </question>
    <answer>rs7412,Yes</answer>
    <tools_required>
      cogex_query_variants (get_for_gene),
      cogex_query_disease_or_phenotype (disease_to_mechanisms),
      cogex_check_relationship (variant_association)
    </tools_required>
    <complexity>high</complexity>
    <estimated_tool_calls>5-8</estimated_tool_calls>
  </qa_pair>

  <!-- 7 more questions... -->
</evaluation>
```

**Question Categories**:
1. **Drug-Target-Pathway** (2 questions): Drug discovery pipelines
2. **Disease-Gene-Variant** (2 questions): Disease mechanism analysis
3. **Cell Line-Mutation-Drug** (2 questions): Cancer cell line analysis
4. **Ontology-Hierarchy** (1 question): Ontology navigation
5. **Enrichment-Pathway** (2 questions): Pathway enrichment analysis
6. **Multi-Tool-Integration** (1 question): Complex workflow requiring 8+ tools

**Evaluation Runner** (`run_evaluation.py`):
```python
"""
Run evaluation suite against MCP server.

Usage:
    python evaluation/run_evaluation.py --model claude-opus --output results/run_001.json
"""

import asyncio
from typing import List, Dict
import xml.etree.ElementTree as ET
from datetime import datetime
import json

class EvaluationRunner:
    def __init__(self, mcp_client, model_name: str):
        self.mcp_client = mcp_client
        self.model_name = model_name
        self.results = []

    async def run_question(self, question: str, expected_answer: str) -> Dict:
        """Run single question through LLM + MCP"""
        start_time = datetime.now()

        # Send question to LLM (Claude API)
        response = await self.ask_llm(question)

        # Extract answer from response
        answer = self.extract_answer(response)

        # Validate
        correct = self.validate_answer(answer, expected_answer)

        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "question": question,
            "expected": expected_answer,
            "actual": answer,
            "correct": correct,
            "elapsed_seconds": elapsed,
            "tool_calls": self.count_tool_calls(response),
            "llm_response": response,
        }

    async def run_all(self, questions_xml: str) -> Dict:
        """Run all questions and generate report"""
        tree = ET.parse(questions_xml)
        root = tree.getroot()

        for qa_pair in root.findall("qa_pair"):
            question = qa_pair.find("question").text.strip()
            answer = qa_pair.find("answer").text.strip()

            result = await self.run_question(question, answer)
            self.results.append(result)

        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate evaluation report"""
        total = len(self.results)
        correct = sum(1 for r in self.results if r["correct"])

        return {
            "model": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": correct / total if total > 0 else 0,
            "avg_time_per_question": sum(r["elapsed_seconds"] for r in self.results) / total,
            "avg_tool_calls": sum(r["tool_calls"] for r in self.results) / total,
            "results": self.results,
        }
```

---

## Component 4: Performance Profiling Framework

**Purpose**: Measure and optimize query performance across all 16 tools

**Expert Persona**: Performance Engineer with distributed systems profiling expertise

### 4.1 Performance Testing Suite (`tests/performance/`)

**File Structure**:
```
tests/performance/
├── __init__.py
├── conftest.py                 # Performance fixtures
├── test_query_latency.py       # Latency benchmarks
├── test_concurrency.py         # Concurrent query tests
├── test_cache_effectiveness.py # Cache hit rate analysis
├── test_connection_pool.py     # Connection pool efficiency
├── profiling/
│   ├── profile_tool01.py       # Per-tool profiling
│   ├── profile_tool02.py
│   └── ...
└── reports/
    ├── latency_report.json
    ├── cache_report.json
    └── performance_summary.md
```

**4.2 Latency Benchmarks** (`test_query_latency.py`):

```python
import pytest
import time
from typing import Dict, List
import statistics

@pytest.mark.performance
class TestQueryLatency:
    """Benchmark query latency for all 16 tools"""

    @pytest.mark.asyncio
    async def test_tool01_latency_profile(self, mcp_client, known_entities):
        """Profile Tool 1 latency across all modes"""
        latencies = {}

        modes = [
            ("gene_to_features", {"gene": "TP53"}),
            ("tissue_to_genes", {"tissue": "brain", "limit": 20}),
            ("go_to_genes", {"go_term": "GO:0006915", "limit": 20}),
        ]

        for mode_name, params in modes:
            times = []
            for _ in range(10):  # 10 runs per mode
                start = time.time()
                await mcp_client.query_gene_or_feature(mode=mode_name, **params)
                elapsed = time.time() - start
                times.append(elapsed)

            latencies[mode_name] = {
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "p95": statistics.quantiles(times, n=20)[18],  # 95th percentile
                "p99": statistics.quantiles(times, n=100)[98],  # 99th percentile
                "min": min(times),
                "max": max(times),
            }

        # Assertions
        for mode, stats in latencies.items():
            assert stats["p95"] < 2.0, f"{mode} p95 latency > 2s: {stats['p95']}"
            assert stats["mean"] < 1.0, f"{mode} mean latency > 1s: {stats['mean']}"

        return latencies

    async def benchmark_all_tools(self) -> Dict:
        """Benchmark all 16 tools and generate report"""
        results = {}

        # Run benchmarks for each tool
        # ...

        return {
            "timestamp": datetime.now().isoformat(),
            "tool_latencies": results,
            "summary": self.generate_latency_summary(results),
        }
```

**4.3 Concurrency Tests** (`test_concurrency.py`):

```python
@pytest.mark.performance
class TestConcurrency:
    """Test concurrent query handling"""

    @pytest.mark.asyncio
    async def test_concurrent_queries_10x(self, mcp_client):
        """Test 10 concurrent queries"""
        queries = [
            ("cogex_query_gene_or_feature", {"gene": f"GENE{i}"})
            for i in range(10)
        ]

        start = time.time()
        results = await asyncio.gather(*[
            mcp_client.call_tool(tool, params)
            for tool, params in queries
        ])
        elapsed = time.time() - start

        # Should complete faster than sequential
        assert elapsed < 5.0, f"10 concurrent queries took {elapsed}s (expected < 5s)"

    @pytest.mark.asyncio
    async def test_connection_pool_saturation(self, mcp_client):
        """Test behavior under connection pool saturation"""
        # Send 60 concurrent queries (pool size = 50)
        queries = [
            ("cogex_query_gene_or_feature", {"gene": "TP53"})
            for _ in range(60)
        ]

        start = time.time()
        results = await asyncio.gather(*[
            mcp_client.call_tool(tool, params)
            for tool, params in queries
        ], return_exceptions=True)
        elapsed = time.time() - start

        # Should handle gracefully without errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors under load"
        assert elapsed < 30.0, f"60 queries took {elapsed}s"
```

---

## Component 5: Cache Effectiveness Analysis

**Purpose**: Quantify cache performance and identify optimization opportunities

**Expert Persona**: Systems Performance Engineer with caching expertise

### 5.1 Cache Analytics Framework (`tests/performance/test_cache_effectiveness.py`):

```python
@pytest.mark.performance
class TestCacheEffectiveness:
    """Analyze cache hit rates and effectiveness"""

    @pytest.mark.asyncio
    async def test_cache_hit_rate_entity_resolution(self, mcp_client):
        """Measure cache hit rate for entity resolution"""
        from cogex_mcp.services.cache import get_cache
        cache = get_cache()

        # Reset cache stats
        cache.reset_stats()

        # Query same entities multiple times
        entities = ["TP53", "BRCA1", "EGFR"] * 10  # 30 total, 3 unique

        for entity in entities:
            await mcp_client.resolve_gene(entity)

        stats = cache.get_stats()
        hit_rate = stats.hits / (stats.hits + stats.misses) if (stats.hits + stats.misses) > 0 else 0

        # Should have high hit rate (first 3 are misses, rest are hits)
        # Expected: 3 misses, 27 hits = 90% hit rate
        assert hit_rate >= 0.85, f"Cache hit rate too low: {hit_rate:.2%}"

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, mcp_client):
        """Test cache TTL and expiration"""
        from cogex_mcp.services.cache import get_cache
        import asyncio

        cache = get_cache()

        # Set item with short TTL (for testing)
        await cache.set("test_key", "test_value", ttl=2)

        # Immediate retrieval should hit
        result1 = await cache.get("test_key")
        assert result1 == "test_value"

        # Wait for TTL expiration
        await asyncio.sleep(3)

        # Should be expired
        result2 = await cache.get("test_key")
        assert result2 is None

    async def analyze_cache_patterns(self, duration_minutes: int = 10) -> Dict:
        """
        Analyze cache patterns over time

        Metrics:
        - Hit rate by tool
        - Hit rate by entity type
        - Memory usage
        - Eviction rate
        - Average TTL utilization
        """
        from cogex_mcp.services.cache import get_cache
        import time

        cache = get_cache()
        start_time = time.time()
        samples = []

        while time.time() - start_time < duration_minutes * 60:
            stats = cache.get_stats()
            samples.append({
                "timestamp": time.time(),
                "hits": stats.hits,
                "misses": stats.misses,
                "size": stats.size,
                "hit_rate": stats.hits / (stats.hits + stats.misses) if (stats.hits + stats.misses) > 0 else 0,
            })

            await asyncio.sleep(10)  # Sample every 10 seconds

        return {
            "duration_minutes": duration_minutes,
            "samples": samples,
            "avg_hit_rate": statistics.mean(s["hit_rate"] for s in samples),
            "peak_size": max(s["size"] for s in samples),
            "total_hits": samples[-1]["hits"],
            "total_misses": samples[-1]["misses"],
        }
```

**5.2 Cache Monitoring Dashboard** (`src/cogex_mcp/monitoring/cache_monitor.py`):

```python
"""
Real-time cache monitoring and analysis.

Usage:
    python -m cogex_mcp.monitoring.cache_monitor --duration 60
"""

class CacheMonitor:
    """Monitor cache performance in real-time"""

    def __init__(self):
        self.cache = get_cache()
        self.samples = []

    async def monitor(self, duration_seconds: int, interval_seconds: int = 5):
        """Monitor cache for specified duration"""
        start = time.time()

        while time.time() - start < duration_seconds:
            stats = self.cache.get_stats()
            self.samples.append({
                "timestamp": time.time(),
                "stats": stats,
            })

            # Print real-time stats
            print(f"\rHit Rate: {self.current_hit_rate():.1%} | "
                  f"Size: {stats.size}/{self.cache.max_size} | "
                  f"Hits: {stats.hits} | Misses: {stats.misses}", end="")

            await asyncio.sleep(interval_seconds)

        print()  # New line after monitoring
        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate monitoring report"""
        return {
            "duration_seconds": len(self.samples) * 5,
            "avg_hit_rate": statistics.mean(self.hit_rate_at(i) for i in range(len(self.samples))),
            "peak_size": max(s["stats"].size for s in self.samples),
            "recommendations": self.generate_recommendations(),
        }

    def generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []

        hit_rate = self.current_hit_rate()
        if hit_rate < 0.5:
            recommendations.append("Low hit rate - consider increasing cache size")

        peak_size = max(s["stats"].size for s in self.samples)
        if peak_size >= self.cache.max_size * 0.9:
            recommendations.append("Cache near capacity - consider increasing max_size")

        return recommendations
```

---

## Component 6: Implementation Agents

Deploy 4 specialized agents in parallel:

### Agent 1: Integration Test Engineer
**Task**: Implement comprehensive integration tests
**Files**: `tests/integration/` (all 16 tool test files + e2e)
**Expertise**: Python testing, pytest, async testing, backend validation

### Agent 2: Evaluation Framework Engineer
**Task**: Create evaluation suite with 10 complex questions
**Files**: `evaluation/` (questions.xml, run_evaluation.py, evaluate_responses.py)
**Expertise**: ML evaluation, biomedical knowledge, MCP evaluation best practices

### Agent 3: Performance Engineer
**Task**: Implement performance profiling framework
**Files**: `tests/performance/` (latency, concurrency, profiling tools)
**Expertise**: Performance testing, profiling, benchmarking, statistics

### Agent 4: Cache Analytics Engineer
**Task**: Implement cache effectiveness analysis
**Files**: `tests/performance/test_cache_effectiveness.py`, `src/cogex_mcp/monitoring/cache_monitor.py`
**Expertise**: Caching systems, metrics, monitoring, optimization

---

## Success Criteria

**Integration Tests**:
- ✅ 80-100 integration tests implemented
- ✅ All 16 tools validated against live backend
- ✅ 5-15 E2E workflow tests
- ✅ 90%+ test pass rate

**Evaluation**:
- ✅ 10 complex questions created
- ✅ Evaluation runner functional
- ✅ Baseline accuracy established

**Performance**:
- ✅ Latency benchmarks for all 16 tools
- ✅ Concurrency tests (10x, 50x, 100x)
- ✅ Performance report generated

**Cache**:
- ✅ Hit rate analysis implemented
- ✅ Real-time monitoring tool
- ✅ Optimization recommendations

---

## Timeline

**Total Estimated Time**: 6-8 hours (with 4 parallel agents)

**Agent 1** (Integration): 6-8 hours
**Agent 2** (Evaluation): 4-5 hours
**Agent 3** (Performance): 5-6 hours
**Agent 4** (Cache): 3-4 hours

**Parallel execution**: ~8 hours total

---

## Next Steps

1. Deploy 4 agents in parallel with tailored context
2. Agents implement their respective components
3. Run integration tests against live backend
4. Execute evaluation suite
5. Generate performance and cache reports
6. Create final optimization recommendations

Ready to deploy agents!
