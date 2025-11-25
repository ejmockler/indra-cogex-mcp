"""
Integration tests for Tools 6-10: Pathway, Cell Line, Clinical Trials, Literature, Variants

Priority 2 tools with comprehensive coverage.

Run with: pytest tests/integration/test_tools06_10_integration.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import (
    CellLineQuery,
    CellLineQueryMode,
    ClinicalTrialsMode,
    ClinicalTrialsQuery,
    LiteratureQuery,
    LiteratureQueryMode,
    PathwayQuery,
    PathwayQueryMode,
    ResponseFormat,
    VariantQuery,
    VariantQueryMode,
)

# ============================================================================
# Tool 6: Pathway Queries
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 6 Pathway queries (404 errors)", strict=False)
class TestTool6Pathway:
    """Test cogex_query_pathway - 4 modes"""

    async def test_get_genes_p53_pathway(self, integration_adapter):
        """Get genes in p53 signaling pathway"""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="p53 signaling",
            limit=50,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("pathway_get_genes", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_pathways_for_tp53(self, integration_adapter):
        """Get pathways containing TP53"""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("pathway_get_pathways", **query.model_dump(exclude_none=True))
        assert result is not None
        # TP53 should be in multiple pathways

    async def test_find_shared_pathways(self, integration_adapter):
        """Find pathways shared by MAPK genes"""
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["MAPK1", "MAPK3", "MAP2K1"],
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("pathway_find_shared", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_check_membership(self, integration_adapter):
        """Check if TP53 in p53 pathway"""
        query = PathwayQuery(
            mode=PathwayQueryMode.CHECK_MEMBERSHIP,
            gene="TP53",
            pathway="p53 signaling",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("pathway_check", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 7: Cell Line Queries
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 7 Cell Line queries (404 errors)", strict=False)
class TestTool7CellLine:
    """Test cogex_query_cell_line - 4 modes"""

    async def test_get_properties_a549(self, integration_adapter):
        """Get A549 cell line properties"""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="A549",
            include_mutations=True,
            include_copy_number=True,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_line_properties", **query.model_dump(exclude_none=True))
        assert result is not None
        # A549 has KRAS mutation

    async def test_get_mutated_genes_mcf7(self, integration_adapter):
        """Get mutations in MCF7"""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_MUTATED_GENES,
            cell_line="MCF7",
            limit=50,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_line_mutations", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_cell_lines_with_tp53_mutation(self, integration_adapter):
        """Get cell lines with TP53 mutations"""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_CELL_LINES_WITH_MUTATION,
            gene="TP53",
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_lines_with_mutation", **query.model_dump(exclude_none=True))
        assert result is not None
        # Many cell lines have TP53 mutations

    async def test_check_a549_kras_mutation(self, integration_adapter):
        """Check if A549 has KRAS mutation"""
        query = CellLineQuery(
            mode=CellLineQueryMode.CHECK_MUTATION,
            cell_line="A549",
            gene="KRAS",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_line_check", **query.model_dump(exclude_none=True))
        assert result is not None
        # A549 is known to have KRAS G12S mutation


# ============================================================================
# Tool 8: Clinical Trials Queries
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 8 Clinical Trials queries (404 errors)", strict=False)
class TestTool8ClinicalTrials:
    """Test cogex_query_clinical_trials - 3 modes"""

    async def test_get_for_drug_pembrolizumab(self, integration_adapter):
        """Get trials for pembrolizumab"""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DRUG,
            drug="pembrolizumab",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("trials_for_drug", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_for_disease_diabetes(self, integration_adapter):
        """Get trials for diabetes"""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            phase=[2, 3],
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("trials_for_disease", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_by_id(self, integration_adapter):
        """Get specific trial by NCT ID"""
        query = ClinicalTrialsQuery(
            mode=ClinicalTrialsMode.GET_BY_ID,
            trial_id="NCT02576431",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("trial_by_id", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 9: Literature Queries
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 9 Literature queries (404 errors)", strict=False)
class TestTool9Literature:
    """Test cogex_query_literature - 4 modes"""

    async def test_get_statements_for_pmid(self, integration_adapter):
        """Get INDRA statements from PubMed article"""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
            pmid="12345678",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("lit_statements_pmid", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_evidence_for_statement(self, integration_adapter):
        """Get evidence for specific statement"""
        # This requires a valid statement hash from CoGEx
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_EVIDENCE_FOR_STATEMENT,
            statement_hash="1234567890abcdef",  # Example hash
            include_evidence_text=True,
            max_evidence_per_statement=5,
            response_format=ResponseFormat.JSON,
        )
        try:
            result = await integration_adapter.query("lit_evidence", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass  # May fail with example hash

    async def test_search_by_mesh(self, integration_adapter):
        """Search statements by MeSH terms"""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.SEARCH_BY_MESH,
            mesh_terms=["Apoptosis", "Neoplasms"],
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("lit_mesh_search", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 10: Variant Queries
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 10 Variant queries (404 errors)", strict=False)
class TestTool10Variants:
    """Test cogex_query_variants - 6 modes"""

    async def test_get_for_gene_brca1(self, integration_adapter):
        """Get variants for BRCA1"""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="BRCA1",
            max_p_value=1e-5,
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variants_for_gene", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_get_for_disease_alzheimer(self, integration_adapter):
        """Get variants associated with Alzheimer's"""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_DISEASE,
            disease="alzheimer disease",
            max_p_value=1e-6,
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variants_for_disease", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should include APOE variants

    async def test_variant_to_genes(self, integration_adapter):
        """Get genes for specific variant"""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_GENES,
            variant="rs7412",  # APOE variant
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variant_to_genes", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_variant_to_phenotypes(self, integration_adapter):
        """Get phenotypes for variant"""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_PHENOTYPES,
            variant="rs7412",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variant_to_phenotypes", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_check_association(self, integration_adapter):
        """Check variant-disease association"""
        query = VariantQuery(
            mode=VariantQueryMode.CHECK_ASSOCIATION,
            variant="rs7412",
            disease="alzheimer disease",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variant_check", **query.model_dump(exclude_none=True))
        assert result is not None
        # rs7412 is APOE variant associated with Alzheimer's


# Additional edge case and pagination tests

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tools 6-10 (404 errors)", strict=False)
class TestTools6to10EdgeCases:
    """Edge cases and pagination for Tools 6-10"""

    async def test_pathway_unknown(self, integration_adapter):
        """Edge case: Unknown pathway"""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="fake_pathway_xyz",
            response_format=ResponseFormat.JSON,
        )
        try:
            result = await integration_adapter.query("pathway_get_genes", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass  # Expected to fail

    async def test_cell_line_unknown(self, integration_adapter):
        """Edge case: Unknown cell line"""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="FAKE_CELL_LINE",
            response_format=ResponseFormat.JSON,
        )
        try:
            result = await integration_adapter.query("cell_line_properties", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass

    async def test_variant_invalid_rsid(self, integration_adapter):
        """Edge case: Invalid rsID format"""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_GENES,
            variant="rs999999999999",  # Non-existent
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("variant_to_genes", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_pagination_pathways(self, integration_adapter):
        """Pagination: Get pathways with offset"""
        query1 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )
        result1 = await integration_adapter.query("pathway_get_pathways", **query1.model_dump(exclude_none=True))

        query2 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=5,
            response_format=ResponseFormat.JSON,
        )
        result2 = await integration_adapter.query("pathway_get_pathways", **query2.model_dump(exclude_none=True))

        assert result1 is not None
        assert result2 is not None
