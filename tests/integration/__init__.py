"""
Integration tests for INDRA CoGEx MCP Server.

This package contains comprehensive integration tests for all 16 tools
and end-to-end workflow tests validating multi-tool usage patterns.

Test Organization:
- conftest.py: Fixtures and test configuration
- test_tool01_gene_integration.py: Tool 1 (Gene/Feature queries)
- test_tool02_subnetwork_integration.py: Tool 2 (Subnetwork extraction)
- test_tool03_enrichment_integration.py: Tool 3 (Enrichment analysis)
- test_tool04_drug_integration.py: Tool 4 (Drug/Effect queries)
- test_tool05_disease_integration.py: Tool 5 (Disease/Phenotype queries)
- test_tools06_10_integration.py: Tools 6-10 (Pathway, Cell Line, Trials, Literature, Variants)
- test_tools11_16_integration.py: Tools 11-16 (Identifier, Relationship, Ontology, Markers, Functions)
- test_e2e_workflows.py: End-to-end multi-tool workflows

Running Tests:
    # Run all integration tests
    pytest tests/integration/ -v -m integration

    # Run specific tool tests
    pytest tests/integration/test_tool01_gene_integration.py -v

    # Run E2E workflows only
    pytest tests/integration/test_e2e_workflows.py -v -m e2e

    # Skip integration tests (run unit tests only)
    pytest -m "not integration"

Requirements:
- Live connection to INDRA CoGEx Neo4j backend
- Production credentials in .env.production
- pytest-asyncio for async test support
- Recommended timeout: 120s per test (some queries are slow)

Note: Integration tests may take 5-10 minutes to complete due to
complex graph traversals and statistical computations.
"""

__version__ = "1.0.0"
