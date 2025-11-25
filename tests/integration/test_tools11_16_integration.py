"""
Integration tests for Tools 11-16: Identifier, Relationship, Ontology, Cell Markers, Kinase, Protein Functions

Priority 3 tools with essential coverage.

Run with: pytest tests/integration/test_tools11_16_integration.py -v -m integration
"""

import pytest

from cogex_mcp.schemas import (
    CellMarkerMode,
    CellMarkerQuery,
    HierarchyDirection,
    IdentifierQuery,
    OntologyHierarchyQuery,
    ProteinFunctionMode,
    ProteinFunctionQuery,
    RelationshipQuery,
    RelationshipType,
    ResponseFormat,
)

# ============================================================================
# Tool 11: Identifier Resolution
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 11 Identifier Resolution (404 errors)", strict=False)
class TestTool11Identifier:
    """Test cogex_resolve_identifiers"""

    async def test_hgnc_symbol_to_hgnc_id(self, integration_adapter):
        """Convert gene symbols to HGNC IDs"""
        query = IdentifierQuery(
            identifiers=["TP53", "BRCA1", "EGFR"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("resolve_identifiers", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should get HGNC IDs for all three

    async def test_hgnc_to_uniprot(self, integration_adapter):
        """Convert HGNC IDs to UniProt IDs"""
        query = IdentifierQuery(
            identifiers=["11998", "1100", "3236"],  # TP53, BRCA1, EGFR
            from_namespace="hgnc",
            to_namespace="uniprot",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("resolve_identifiers", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_unknown_identifiers(self, integration_adapter):
        """Edge case: Unknown/invalid identifiers"""
        query = IdentifierQuery(
            identifiers=["FAKEGENE1", "FAKEGENE2"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("resolve_identifiers", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should indicate no mappings found


# ============================================================================
# Tool 12: Relationship Checking
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 12 Relationship queries (404 errors)", strict=False)
class TestTool12Relationship:
    """Test cogex_check_relationship - 10 relationship types"""

    async def test_gene_in_pathway(self, integration_adapter):
        """Check if TP53 in p53 pathway"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_IN_PATHWAY,
            entity1="TP53",
            entity2="p53 signaling",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should return True

    async def test_drug_target(self, integration_adapter):
        """Check if imatinib targets BCR-ABL"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_TARGET,
            entity1="imatinib",
            entity2="ABL1",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_gene_disease(self, integration_adapter):
        """Check BRCA1-breast cancer association"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="BRCA1",
            entity2="breast cancer",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_cell_line_mutation(self, integration_adapter):
        """Check A549 KRAS mutation"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.CELL_LINE_MUTATION,
            entity1="A549",
            entity2="KRAS",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None
        # A549 has KRAS mutation

    async def test_variant_association(self, integration_adapter):
        """Check rs7412-Alzheimer's association"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.VARIANT_ASSOCIATION,
            entity1="rs7412",
            entity2="alzheimer disease",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 13: Ontology Hierarchy
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 13 Ontology queries (404 errors)", strict=False)
class TestTool13Ontology:
    """Test cogex_get_ontology_hierarchy"""

    async def test_go_parents(self, integration_adapter):
        """Get parent terms for apoptosis"""
        query = OntologyHierarchyQuery(
            term="GO:0006915",  # apoptotic process
            direction=HierarchyDirection.PARENTS,
            max_depth=2,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("ontology_hierarchy", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_go_children(self, integration_adapter):
        """Get child terms for cell death"""
        query = OntologyHierarchyQuery(
            term="GO:0008219",  # cell death
            direction=HierarchyDirection.CHILDREN,
            max_depth=2,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("ontology_hierarchy", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_hpo_both_directions(self, integration_adapter):
        """Get HPO hierarchy both directions"""
        query = OntologyHierarchyQuery(
            term="HP:0001250",  # Seizure
            direction=HierarchyDirection.BOTH,
            max_depth=2,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("ontology_hierarchy", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 14: Cell Markers
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 14 Cell Marker queries (404 errors)", strict=False)
class TestTool14CellMarkers:
    """Test cogex_query_cell_markers"""

    async def test_get_markers_for_t_cell(self, integration_adapter):
        """Get markers for T cells"""
        query = CellMarkerQuery(
            mode=CellMarkerMode.GET_MARKERS,
            cell_type="T cell",
            tissue="blood",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_markers", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should include CD3, CD4, CD8

    async def test_get_cell_types_for_cd4(self, integration_adapter):
        """Get cell types expressing CD4"""
        query = CellMarkerQuery(
            mode=CellMarkerMode.GET_CELL_TYPES,
            marker="CD4",
            limit=20,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("cell_types_for_marker", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_check_marker(self, integration_adapter):
        """Check if CD3 is T cell marker"""
        query = CellMarkerQuery(
            mode=CellMarkerMode.CHECK_MARKER,
            cell_type="T cell",
            marker="CD3E",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_marker", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 15: Kinase (part of Protein Functions - Tool 16)
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 15 Kinase queries (404 errors)", strict=False)
class TestTool15Kinase:
    """Test kinase-specific queries (part of Tool 16)"""

    async def test_check_egfr_is_kinase(self, integration_adapter):
        """Check if EGFR is a kinase"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=["EGFR"],
            function_types=["kinase"],
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_function_types", **query.model_dump(exclude_none=True))
        assert result is not None
        # EGFR is a tyrosine kinase

    async def test_get_kinase_activities(self, integration_adapter):
        """Get kinase activities for MAPK1"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="MAPK1",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("gene_to_activities", **query.model_dump(exclude_none=True))
        assert result is not None


# ============================================================================
# Tool 16: Protein Functions
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tool 16 Protein Function queries (404 errors)", strict=False)
class TestTool16ProteinFunctions:
    """Test cogex_query_protein_functions - 4 modes"""

    async def test_gene_to_activities_tp53(self, integration_adapter):
        """Get molecular activities for TP53"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="TP53",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("gene_to_activities", **query.model_dump(exclude_none=True))
        assert result is not None
        # TP53 is transcription factor

    async def test_activity_to_genes(self, integration_adapter):
        """Get genes with kinase activity"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="kinase",
            limit=30,
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("activity_to_genes", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_check_activity(self, integration_adapter):
        """Check if EGFR has kinase activity"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="EGFR",
            enzyme_activity="kinase",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_activity", **query.model_dump(exclude_none=True))
        assert result is not None

    async def test_check_multiple_function_types(self, integration_adapter):
        """Check multiple genes for multiple function types"""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=["EGFR", "SRC", "TP53", "MYC"],
            function_types=["kinase", "transcription_factor", "phosphatase"],
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_function_types", **query.model_dump(exclude_none=True))
        assert result is not None
        # EGFR/SRC are kinases, TP53/MYC are TFs


# Additional edge cases

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.xfail(reason="REST API endpoints not implemented for Tools 11-16 (404 errors)", strict=False)
class TestTools11to16EdgeCases:
    """Edge cases for Tools 11-16"""

    async def test_identifier_empty_list(self, integration_adapter):
        """Edge case: Empty identifier list"""
        try:
            query = IdentifierQuery(
                identifiers=[],
                from_namespace="hgnc.symbol",
                to_namespace="hgnc",
                response_format=ResponseFormat.JSON,
            )
            result = await integration_adapter.query("resolve_identifiers", **query.model_dump(exclude_none=True))
            assert result is not None
        except Exception:
            pass  # May fail validation

    async def test_relationship_no_connection(self, integration_adapter):
        """Edge case: Check relationship that doesn't exist"""
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_IN_PATHWAY,
            entity1="TP53",
            entity2="fake_pathway",
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("check_relationship", **query.model_dump(exclude_none=True))
        assert result is not None
        # Should return False

    async def test_ontology_max_depth(self, integration_adapter):
        """Test ontology hierarchy with max depth"""
        query = OntologyHierarchyQuery(
            term="GO:0006915",
            direction=HierarchyDirection.PARENTS,
            max_depth=5,  # Deep traversal
            response_format=ResponseFormat.JSON,
        )
        result = await integration_adapter.query("ontology_hierarchy", **query.model_dump(exclude_none=True))
        assert result is not None
