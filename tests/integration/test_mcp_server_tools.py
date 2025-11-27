"""
MCP server handler matrix: exercises all tools through server.handle_call_tool(),
mirroring the production execution path (handlers → adapter → backend).
"""

import pytest

from tests.integration.utils import assert_json, assert_keys, assert_non_empty


@pytest.fixture(scope="session", autouse=True)
async def initialize_backend_session():
    """Start backend once for this module and clean up afterward."""
    from cogex_mcp.server import cleanup_backend, initialize_backend

    await initialize_backend()
    yield
    await cleanup_backend()


async def _call_tool(name: str, arguments: dict):
    """Invoke server.handle_call_tool and return parsed JSON payload."""
    from cogex_mcp.server import handle_call_tool

    result = await handle_call_tool(name=name, arguments=arguments)
    assert isinstance(result, list) and result, "handle_call_tool should return non-empty list"
    text = result[0].text
    data = assert_json(text)
    return data


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCPServerToolMatrix:
    """Smoke matrix hitting representative paths for all tools."""

    @pytest.mark.timeout(45)
    async def test_gene_to_features(self):
        data = await _call_tool(
            "query_gene_or_feature",
            {
                "mode": "gene_to_features",
                "gene": "TP53",
                "include_expression": True,
                "include_go_terms": True,
                "include_pathways": True,
                "response_format": "json",
                "limit": 5,
            },
        )
        assert_keys(data, ["gene"])
        assert_non_empty(data, "go_terms")
        assert_non_empty(data, "pathways")

    @pytest.mark.timeout(45)
    async def test_drug_to_profile(self):
        data = await _call_tool(
            "query_drug_or_effect",
            {
                "mode": "drug_to_profile",
                "drug": "imatinib",
                "include_targets": True,
                "include_indications": True,
                "response_format": "json",
                "limit": 5,
            },
        )
        assert_keys(data, ["drug"])
        assert_non_empty(data, "targets")
        assert_non_empty(data, "indications")

    @pytest.mark.timeout(45)
    async def test_resolver_symbol_to_hgnc(self):
        data = await _call_tool(
            "resolve_identifiers",
            {
                "identifiers": ["TP53"],
                "from_namespace": "hgnc.symbol",
                "to_namespace": "hgnc",
                "response_format": "json",
            },
        )
        assert_keys(data, ["mappings"])
        assert_non_empty(data, "mappings")

    @pytest.mark.timeout(45)
    async def test_pathway_get_genes(self):
        data = await _call_tool(
            "query_pathway",
            {
                "mode": "get_genes",
                "pathway": "MAPK signaling",
                "response_format": "json",
                "limit": 5,
            },
        )
        assert_non_empty(data, "genes")

    @pytest.mark.timeout(45)
    async def test_clinical_trials_for_drug(self):
        data = await _call_tool(
            "query_clinical_trials",
            {
                "mode": "get_for_drug",
                "drug": "pembrolizumab",
                "response_format": "json",
                "limit": 5,
            },
        )
        assert_non_empty(data, "trials")
        first = data["trials"][0]
        assert_keys(first, ["nct_id", "title", "status"])

    @pytest.mark.timeout(45)
    async def test_subnetwork_direct(self):
        data = await _call_tool(
            "extract_subnetwork",
            {
                "mode": "direct",
                "genes": ["TP53", "MDM2"],
                "max_statements": 50,
                "response_format": "json",
            },
        )
        assert_non_empty(data, "statements")

    @pytest.mark.timeout(45)
    async def test_literature_statements_for_pmid(self):
        data = await _call_tool(
            "query_literature",
            {
                "mode": "get_statements_for_pmid",
                "pmid": "29760375",
                "limit": 10,
                "response_format": "json",
            },
        )
        assert_non_empty(data, "statements")

    @pytest.mark.timeout(45)
    async def test_variants_for_gene(self):
        data = await _call_tool(
            "query_variants",
            {
                "mode": "get_variants_for_gene",
                "gene": "BRCA1",
                "limit": 5,
                "response_format": "json",
            },
        )
        assert_non_empty(data, "variants")

    @pytest.mark.timeout(45)
    async def test_ontology_hierarchy(self):
        data = await _call_tool(
            "get_ontology_hierarchy",
            {
                "ontology": "go",
                "term": "GO:0006915",
                "direction": "parents",
                "response_format": "json",
                "limit": 5,
            },
        )
        assert_non_empty(data, "terms")

    @pytest.mark.timeout(45)
    async def test_cell_markers(self):
        data = await _call_tool(
            "query_cell_markers",
            {
                "mode": "markers_for_cell_type",
                "cell_type": "T cell",
                "limit": 5,
                "response_format": "json",
            },
        )
        assert_non_empty(data, "markers")

    @pytest.mark.timeout(45)
    @pytest.mark.xfail(reason="Kinase enrichment backend may be unavailable; enable when service is ready", strict=False)
    async def test_kinase_enrichment(self):
        data = await _call_tool(
            "analyze_kinase_enrichment",
            {
                "phosphosites": ["TP53_S15", "TP53_S20", "MDM2_S166"],
                "response_format": "json",
            },
        )
        assert_non_empty(data, "results")

    @pytest.mark.timeout(45)
    @pytest.mark.xfail(reason="Protein function annotations may be absent; remove xfail once data is available", strict=False)
    async def test_protein_functions_gene_to_activities(self):
        data = await _call_tool(
            "query_protein_functions",
            {
                "mode": "gene_to_activities",
                "gene": "EGFR",
                "response_format": "json",
            },
        )
        assert_non_empty(data, "activities")
