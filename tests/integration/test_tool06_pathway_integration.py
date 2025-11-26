"""
Integration tests for Tool 6: cogex_query_pathway

Tests pathway query functionality with actual data validation.

Run with: pytest tests/integration/test_tool06_pathway_integration.py -v
"""

import json
import logging

import pytest

from cogex_mcp.schemas import PathwayQuery, PathwayQueryMode, ResponseFormat
from cogex_mcp.tools.pathway import cogex_query_pathway

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool6PathwayQueries:
    """Test Tool 6 pathway query modes with data validation."""

    async def test_get_genes_p53_pathway(self):
        """Test getting genes in p53 signaling pathway."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="p53 signaling",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "pathway" in data, "Response should include pathway info"
        assert "genes" in data, "Response should include genes list"

        # 4. Data is non-empty (p53 pathway is well-known)
        assert len(data["genes"]) > 0, "p53 pathway should have genes"

        # 5. Data structure validation
        first_gene = data["genes"][0]
        assert "name" in first_gene, "Gene should have name"
        assert "curie" in first_gene, "Gene should have CURIE"

        # 6. Specific validation: TP53 should be in p53 pathway
        gene_names = [g["name"] for g in data["genes"]]
        assert "TP53" in gene_names, "TP53 should be in p53 signaling pathway"

        logger.info(f"✓ p53 pathway has {len(data['genes'])} genes")

    async def test_get_pathways_for_tp53(self):
        """Test getting pathways containing TP53."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=30,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "pathways" in data, "Response should include pathways list"

        # 4. Data is non-empty (TP53 is in many pathways)
        assert len(data["pathways"]) > 5, "TP53 should be in multiple pathways"

        # 5. Data structure validation
        first_pathway = data["pathways"][0]
        assert "name" in first_pathway, "Pathway should have name"
        assert "source" in first_pathway, "Pathway should have source"

        # 6. Pagination metadata exists
        assert "pagination" in data, "Response should include pagination"

        logger.info(f"✓ TP53 is in {len(data['pathways'])} pathways")

    async def test_find_shared_pathways_mapk_genes(self):
        """Test finding pathways shared by MAPK genes."""
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["MAPK1", "MAPK3", "MAP2K1"],
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "pathways" in data, "Response should include pathways"

        # 4. Data is non-empty (MAPK genes share pathways)
        assert len(data["pathways"]) > 0, "MAPK genes should share pathways"

        # 5. Verify MAPK pathway is in results
        pathway_names = [p["name"].lower() for p in data["pathways"]]
        has_mapk = any("mapk" in name or "erk" in name for name in pathway_names)
        assert has_mapk, "Should include MAPK/ERK signaling pathway"

        logger.info(f"✓ MAPK genes share {len(data['pathways'])} pathways")

    async def test_check_membership_tp53_in_p53_pathway(self):
        """Test checking if TP53 is in p53 pathway."""
        query = PathwayQuery(
            mode=PathwayQueryMode.CHECK_MEMBERSHIP,
            gene="TP53",
            pathway="p53 signaling",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "is_member" in data, "Response should have is_member field"

        # 4. Data validation: TP53 is definitely in p53 pathway
        assert data["is_member"] is True, "TP53 should be in p53 signaling pathway"

        # 5. Metadata exists
        assert "gene" in data, "Response should include gene info"
        assert "pathway" in data, "Response should include pathway info"

        logger.info("✓ TP53 membership in p53 pathway confirmed")

    async def test_unknown_pathway_error(self):
        """Test error handling for unknown pathway."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="fake_nonexistent_pathway_xyz",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # Should return error message
        assert result.startswith("Error:"), "Should return error for unknown pathway"
        assert "not found" in result.lower(), f"Error should mention 'not found': {result}"

        logger.info(f"✓ Unknown pathway error: {result}")

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=10,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await cogex_query_pathway(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            assert has_markdown, "Markdown response should have formatting"
            logger.info("✓ Markdown response has formatting")

    async def test_pagination_works(self):
        """Test pagination with limit and offset."""
        # Get first page
        query1 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result1 = await cogex_query_pathway(query1)
        assert not result1.startswith("Error:")

        data1 = json.loads(result1)
        assert len(data1["pathways"]) <= 5, "Should respect limit"

        # Get second page
        query2 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=5,
            response_format=ResponseFormat.JSON,
        )

        result2 = await cogex_query_pathway(query2)
        assert not result2.startswith("Error:")

        data2 = json.loads(result2)

        # Pages should have different results
        page1_names = {p["name"] for p in data1["pathways"]}
        page2_names = {p["name"] for p in data2["pathways"]}
        assert page1_names != page2_names, "Different pages should have different results"

        logger.info("✓ Pagination working correctly")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool6PathwayEdgeCases:
    """Edge cases and error handling for pathway queries."""

    async def test_gene_with_no_pathways(self):
        """Test gene that might not be in any pathways."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="FAKE_GENE_XYZ",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        # Should error or return empty results
        if not result.startswith("Error:"):
            data = json.loads(result)
            assert "pathways" in data
            # Empty results are OK for fake genes
            logger.info(f"Fake gene returned {len(data.get('pathways', []))} pathways")
        else:
            logger.info(f"✓ Fake gene error: {result}")

    async def test_pathway_source_filter(self):
        """Test filtering by pathway source."""
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            pathway_source="reactome",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_pathway(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            # Verify all pathways are from reactome
            for pathway in data["pathways"]:
                assert pathway["source"].lower() == "reactome", "Should only return Reactome pathways"
            logger.info(f"✓ Source filter working: {len(data['pathways'])} Reactome pathways")
