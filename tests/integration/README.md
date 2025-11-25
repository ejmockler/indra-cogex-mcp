# INDRA CoGEx MCP Integration Tests

Comprehensive integration testing framework for all 16 production tools against live CoGEx backend.

## Overview

- **Total Tests**: ~100+ integration tests
- **Coverage**: All 16 tools + 5 E2E workflows
- **Runtime**: 5-10 minutes against production CoGEx
- **Backend**: Uses live Neo4j connection from `.env.production`

## Test Organization

### Priority 1 Tools (Essential - Tools 1-5)
- **test_tool01_gene_integration.py** (20 tests)
  - Gene/Feature queries: 5 modes × 4 test types
  - Modes: gene_to_features, tissue_to_genes, go_to_genes, domain_to_genes, phenotype_to_genes

- **test_tool02_subnetwork_integration.py** (20 tests)
  - Subnetwork extraction: 5 modes × 4 test types
  - Modes: direct, mediated, shared_upstream, shared_downstream, source_to_targets

- **test_tool03_enrichment_integration.py** (16 tests)
  - Enrichment analysis: 4 types × 4 test types
  - Types: discrete, continuous, signed, metabolite

- **test_tool04_drug_integration.py** (8 tests)
  - Drug/Effect queries: 2 modes × 4 test types
  - Modes: drug_to_profile, side_effect_to_drugs

- **test_tool05_disease_integration.py** (12 tests)
  - Disease/Phenotype queries: 3 modes × 4 test types
  - Modes: disease_to_mechanisms, phenotype_to_diseases, check_phenotype

### Priority 2 Tools (Important - Tools 6-10)
- **test_tools06_10_integration.py** (~30 tests)
  - Tool 6: Pathway queries (4 modes)
  - Tool 7: Cell line queries (4 modes)
  - Tool 8: Clinical trials (3 modes)
  - Tool 9: Literature queries (4 modes)
  - Tool 10: Variant queries (6 modes)

### Priority 3 Tools (Supporting - Tools 11-16)
- **test_tools11_16_integration.py** (~25 tests)
  - Tool 11: Identifier resolution
  - Tool 12: Relationship checking (10 types)
  - Tool 13: Ontology hierarchy
  - Tool 14: Cell markers (3 modes)
  - Tool 15: Kinase queries
  - Tool 16: Protein functions (4 modes)

### End-to-End Workflows
- **test_e2e_workflows.py** (5 workflows + error handling)
  - **Workflow 1**: Drug Discovery (Drug → Targets → Pathways → Enrichment)
  - **Workflow 2**: Disease Mechanism (Disease → Genes → Variants → Drugs → Trials)
  - **Workflow 3**: Pathway Analysis (Pathway → Genes → Subnetwork → Enrichment)
  - **Workflow 4**: Cell Line Analysis (Cell Line → Mutations → Drug Sensitivity)
  - **Workflow 5**: Identifier Resolution (Symbols → HGNC → UniProt → Functions)

## Test Types

Each tool includes these test categories:

1. **Smoke Tests**: Basic connectivity, single query without error
2. **Happy Path Tests**: Known-good entities with rich data, validate structure
3. **Edge Case Tests**: Unknown entities, empty results, boundary conditions
4. **Pagination Tests**: Limit/offset functionality, large result sets

## Running Tests

### Run All Integration Tests
```bash
pytest tests/integration/ -v -m integration
```

### Run Specific Tool
```bash
pytest tests/integration/test_tool01_gene_integration.py -v
```

### Run E2E Workflows Only
```bash
pytest tests/integration/test_e2e_workflows.py -v
```

### Run Priority 1 Tools Only
```bash
pytest tests/integration/test_tool0[1-5]*.py -v
```

### Skip Slow Tests
```bash
pytest tests/integration/ -v -m "integration and not slow"
```

### Run with Coverage
```bash
pytest tests/integration/ -v --cov=cogex_mcp --cov-report=html
```

## Configuration

### Environment Setup
Integration tests require production credentials:

```bash
# .env.production
NEO4J_URL=bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=newton-heroic-lily-sharp-malta-5377
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
```

### Timeout Configuration
Some queries involve complex graph traversals (20-30s):

| Query Type | Timeout (seconds) |
|-----------|------------------|
| Simple lookup | 5 |
| Feature query | 15 |
| Subnetwork | 30 |
| Enrichment | 45 |
| Complex workflow | 60 |

Configured in `pytest.ini`:
```ini
timeout = 120
```

## Fixtures

### Session-Scoped Fixtures (conftest.py)

- **`integration_adapter`**: Production ClientAdapter with Neo4j connection
  - Reused across all tests in session
  - Automatic cleanup on session end
  - Includes circuit breaker and connection pooling

- **`known_entities`**: Known-good test entities
  - Genes: TP53, BRCA1, EGFR, MAPK1, etc.
  - Drugs: imatinib, aspirin, pembrolizumab
  - Diseases: diabetes, alzheimer disease, breast cancer
  - Cell lines: A549, MCF7, HeLa
  - Variants: rs7412 (APOE), rs429358, rs1042522

- **`timeout_configs`**: Recommended timeouts by query type

## Test Examples

### Example: Smoke Test
```python
async def test_smoke_tp53(self, integration_adapter):
    """Smoke test: TP53 basic query returns without error"""
    query = GeneFeatureQuery(
        mode=QueryMode.GENE_TO_FEATURES,
        gene="TP53",
        response_format=ResponseFormat.JSON,
    )

    result = await integration_adapter.query(
        "gene_to_features",
        **query.model_dump(exclude_none=True)
    )
    assert result is not None
```

### Example: Happy Path Test
```python
async def test_happy_path_imatinib_full_profile(self, integration_adapter):
    """Happy path: Imatinib with full profile"""
    query = DrugEffectQuery(
        mode=DrugQueryMode.DRUG_TO_PROFILE,
        drug="imatinib",
        include_targets=True,
        include_indications=True,
        include_side_effects=True,
        response_format=ResponseFormat.JSON,
    )

    result = await integration_adapter.query(
        "drug_to_profile",
        **query.model_dump(exclude_none=True)
    )

    assert result is not None
    assert isinstance(result, dict)
    assert len(str(result)) > 500  # Should have rich data
```

### Example: E2E Workflow
```python
async def test_complete_drug_discovery_workflow(self, integration_adapter):
    """Drug Discovery: Drug → Targets → Pathways → Enrichment"""

    # Step 1: Get drug targets
    drug_result = await integration_adapter.query(...)

    # Step 2: Get pathways for targets
    pathway_result = await integration_adapter.query(...)

    # Step 3: Find shared pathways
    shared_result = await integration_adapter.query(...)

    # Step 4: Enrichment analysis
    enrichment_result = await integration_adapter.query(...)

    # All steps should succeed
    assert all([drug_result, pathway_result, shared_result, enrichment_result])
```

## Expected Results

### Success Criteria
- ✅ 80-100 integration tests implemented
- ✅ All 16 tools validated against live backend
- ✅ 5 E2E workflow tests
- ✅ 90%+ test pass rate
- ✅ <10 minute total runtime

### Known Limitations

1. **Query Performance**:
   - Complex subnetwork queries: 20-30s
   - Enrichment with 1000 permutations: 30-45s
   - Large pathway gene sets: 10-15s

2. **Backend Availability**:
   - Tests require live CoGEx connection
   - Circuit breaker protects against cascading failures
   - Automatic fallback to REST if Neo4j unavailable

3. **Data Variability**:
   - Some entities may have incomplete data
   - Edge case tests handle empty results gracefully
   - Unknown entities should return informative errors

## Troubleshooting

### Connection Failures
```bash
# Check Neo4j connectivity
pytest tests/integration/conftest.py::test_integration_adapter -v
```

### Timeout Issues
```bash
# Increase timeout for slow queries
pytest tests/integration/ -v --timeout=300
```

### Debug Mode
```bash
# Run with verbose logging
pytest tests/integration/ -v -s --log-cli-level=DEBUG
```

### Test One Tool in Isolation
```bash
# Test Tool 1 only
pytest tests/integration/test_tool01_gene_integration.py::TestTool1GeneToFeatures::test_smoke_tp53 -v -s
```

## Development Guidelines

### Adding New Tests

1. **Follow naming convention**: `test_<mode>_<entity>_<type>`
2. **Use known entities** from `known_entities` fixture
3. **Include all test types**: smoke, happy path, edge case, pagination
4. **Mark appropriately**: `@pytest.mark.integration`, `@pytest.mark.asyncio`
5. **Add docstrings**: Explain what the test validates

### Test Template
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_<mode>_<entity>_<type>(self, integration_adapter):
    """Test description: what this validates"""

    # Arrange: Create query
    query = ToolQuery(
        mode=...,
        entity=...,
        response_format=ResponseFormat.JSON,
    )

    # Act: Execute query
    result = await integration_adapter.query(
        "tool_name",
        **query.model_dump(exclude_none=True)
    )

    # Assert: Validate result
    assert result is not None
    assert isinstance(result, dict)
    # Additional assertions...
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -e ".[test]"
      - run: pytest tests/integration/ -v -m integration
        env:
          NEO4J_URL: ${{ secrets.NEO4J_URL }}
          NEO4J_USER: ${{ secrets.NEO4J_USER }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
```

## Contact & Support

- **Issues**: Report test failures with full traceback
- **Questions**: Consult PHASE6_PLAN.md for implementation details
- **Contributions**: Follow test guidelines above

---

**Last Updated**: 2025-11-24
**Test Framework Version**: 1.0.0
**Required pytest-asyncio**: >=0.21.0
