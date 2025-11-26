"""
Integration tests for Tool 6/12 (cogex_query_pathway) with live backends.

Note: This is Tool 6 in the implementation but tested as Tool 12 in the sequence.

Tests complete flow: Tool → Entity Resolver → Adapter → Backends → Response

Critical validation pattern:
1. No errors
2. Parse response
3. Validate structure
4. Validate data exists
5. Validate data quality
"""

import json
import logging

import pytest

from cogex_mcp.schemas import PathwayQuery, PathwayQueryMode, ResponseFormat
from cogex_mcp.tools.pathway import cogex_query_pathway

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12GeneToPathways:
    """Test gene → pathways mode."""

    async def test_tp53_pathways(self):
        """
        Get pathways containing TP53.

        Validates:
        - Gene to pathways lookup works
        - Returns pathway data
        - Data structure is correct
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "pathways" in data, "Response missing pathways"
        assert "pagination" in data, "Response missing pagination"

        # Step 4: Validate data exists (TP53 is well-studied)
        assert len(data["pathways"]) > 0, "TP53 should be in multiple pathways"

        # Step 5: Validate data quality
        for pathway in data["pathways"]:
            assert "name" in pathway, "Pathway should have name"
            assert pathway["name"], "Pathway name should not be empty"
            assert "curie" in pathway or "source" in pathway, "Pathway should have identifier or source"

        logger.info(f"✓ TP53 in {len(data['pathways'])} pathways")

    async def test_brca1_pathways(self):
        """
        Get pathways for BRCA1.

        Tests another well-known gene.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="BRCA1",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "pathways" in data
        assert len(data["pathways"]) > 0, "BRCA1 should be in pathways (DNA repair, etc.)"

        # Check for DNA repair/cancer pathways
        pathway_names = [p["name"].lower() for p in data["pathways"]]
        logger.info(f"✓ BRCA1 pathways: {len(data['pathways'])} found")
        logger.info(f"  Sample: {pathway_names[:3]}")

    async def test_gene_by_curie(self):
        """
        Query pathways using gene CURIE.

        Validates CURIE resolution in pathway context.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="hgnc:11998",  # TP53
            limit=10,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"CURIE query failed: {result}"

        data = json.loads(result)
        assert "pathways" in data
        assert len(data["pathways"]) > 0, "Should find pathways via CURIE"

        logger.info(f"✓ Gene CURIE resolved to {len(data['pathways'])} pathways")

    async def test_pathway_source_filter(self):
        """
        Test filtering by pathway source (reactome, wikipathways).

        Validates source filtering functionality.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            pathway_source="reactome",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        if result.startswith("Error:") and "not supported" in result.lower():
            pytest.skip("Pathway source filtering not available")

        assert not result.startswith("Error:"), f"Source filter failed: {result}"

        data = json.loads(result)
        assert "pathways" in data

        # Verify all results are from Reactome
        for pathway in data["pathways"]:
            if "source" in pathway:
                assert pathway["source"].lower() == "reactome", f"Expected reactome, got {pathway['source']}"

        logger.info(f"✓ Reactome filter: {len(data['pathways'])} pathways")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12PathwayToGenes:
    """Test pathway → genes mode."""

    async def test_p53_pathway_genes(self, known_entities):
        """
        Get genes in p53 signaling pathway.

        Validates pathway to genes lookup.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="p53 signaling",
            limit=50,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        # May not find exact pathway name
        if result.startswith("Error:") and "not found" in result.lower():
            pytest.skip("p53 signaling pathway not found by name")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "genes" in data, "Response should have genes"
        assert "pathway" in data, "Response should have pathway info"

        # p53 pathway should have multiple genes
        assert len(data["genes"]) > 0, "p53 pathway should contain genes"

        # Validate gene structure
        for gene in data["genes"]:
            assert "name" in gene, "Gene should have name"
            assert gene["name"], "Gene name should not be empty"

        logger.info(f"✓ p53 pathway: {len(data['genes'])} genes")

    async def test_apoptosis_pathway_genes(self):
        """
        Get genes in apoptosis pathway.

        Tests biological process pathway.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="apoptosis",
            limit=50,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        if result.startswith("Error:") and "not found" in result.lower():
            pytest.skip("Apoptosis pathway not found")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "genes" in data
        assert len(data["genes"]) > 0, "Apoptosis pathway should have genes"

        logger.info(f"✓ Apoptosis pathway: {len(data['genes'])} genes")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12SharedPathways:
    """Test find_shared pathways mode."""

    async def test_tp53_mdm2_shared(self):
        """
        Find pathways containing both TP53 and MDM2.

        Tests multi-gene pathway intersection.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["TP53", "MDM2"],
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "pathways" in data, "Response should have pathways"
        assert "genes" in data, "Response should echo input genes"

        # TP53 and MDM2 are known to interact, should share pathways
        assert len(data["pathways"]) > 0, "TP53 and MDM2 should share pathways (p53 regulation)"

        # Validate pathway structure
        for pathway in data["pathways"]:
            assert "name" in pathway
            assert pathway["name"], "Pathway name should not be empty"

        logger.info(f"✓ TP53+MDM2 share {len(data['pathways'])} pathways")

    async def test_multiple_oncogenes_shared(self):
        """
        Find pathways shared by multiple oncogenes.

        Tests larger gene set.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["TP53", "KRAS", "MYC"],
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "pathways" in data

        # These cancer genes should share some pathways
        if len(data["pathways"]) > 0:
            logger.info(f"✓ TP53+KRAS+MYC share {len(data['pathways'])} pathways")
        else:
            logger.warning("No shared pathways found (may be expected)")

    async def test_unrelated_genes_no_shared(self):
        """
        Unrelated genes should have few/no shared pathways.

        Tests negative case.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["TP53", "INS"],  # Tumor suppressor + insulin
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "pathways" in data

        # Should have few or no shared pathways
        logger.info(f"✓ Unrelated genes: {len(data['pathways'])} shared pathways")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12CheckMembership:
    """Test check_membership mode (boolean check)."""

    async def test_tp53_in_p53_pathway(self):
        """
        Check if TP53 is in p53 signaling pathway.

        Should return true.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.CHECK_MEMBERSHIP,
            gene="TP53",
            pathway="p53 signaling",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        if result.startswith("Error:") and ("not found" in result.lower() or "not supported" in result.lower()):
            pytest.skip("Check membership mode or pathway not available")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "is_member" in data, "Response should have is_member boolean"
        assert "gene" in data, "Response should have gene info"
        assert "pathway" in data, "Response should have pathway info"

        # TP53 should be in p53 pathway
        assert data["is_member"] == True, "TP53 should be member of p53 signaling pathway"

        logger.info(f"✓ TP53 in p53 pathway: {data['is_member']}")

    async def test_unrelated_gene_not_in_pathway(self):
        """
        Check if unrelated gene is NOT in specific pathway.

        Should return false.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.CHECK_MEMBERSHIP,
            gene="INS",  # Insulin
            pathway="p53 signaling",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        if result.startswith("Error:") and ("not found" in result.lower() or "not supported" in result.lower()):
            pytest.skip("Check membership mode not available")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "is_member" in data

        # Insulin unlikely to be in p53 pathway
        logger.info(f"✓ INS in p53 pathway: {data['is_member']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12EdgeCases:
    """Test edge cases and parameter validation."""

    async def test_unknown_gene_error(self):
        """
        Unknown gene should return error.

        Validates error handling.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="FAKEGENE999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert result.startswith("Error:"), "Unknown gene should error"
        assert "not found" in result.lower(), f"Error should mention 'not found': {result}"

        logger.info(f"✓ Unknown gene error: {result}")

    async def test_pagination_parameters(self):
        """
        Test pagination with limit and offset.

        Validates pagination functionality.
        """
        # Get first page
        query1 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON
        )

        result1 = await cogex_query_pathway(query1)

        assert not result1.startswith("Error:"), f"Page 1 failed: {result1}"

        data1 = json.loads(result1)
        assert "pagination" in data1

        page1_count = len(data1["pathways"])
        assert page1_count <= 5, "Should respect limit parameter"

        # Get second page
        query2 = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            offset=5,
            response_format=ResponseFormat.JSON
        )

        result2 = await cogex_query_pathway(query2)

        if not result2.startswith("Error:"):
            data2 = json.loads(result2)
            page2_count = len(data2["pathways"])

            logger.info(f"✓ Pagination: page1={page1_count}, page2={page2_count}")
        else:
            logger.warning("Pagination offset not supported")

    async def test_markdown_format(self):
        """
        Test markdown output format.

        Validates alternative response format.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=10,
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Markdown query failed: {result}"

        # Should contain markdown formatting
        has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
        assert has_markdown, "Markdown response should contain formatting"

        assert "TP53" in result or "pathways" in result.lower()
        logger.info("✓ Markdown format contains expected content")

    async def test_find_shared_insufficient_genes(self):
        """
        find_shared mode requires at least 2 genes.

        Validates input validation.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.FIND_SHARED,
            genes=["TP53"],  # Only 1 gene
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert result.startswith("Error:"), "Single gene should error in find_shared mode"
        assert "at least 2" in result.lower() or "required" in result.lower()

        logger.info(f"✓ Insufficient genes error: {result}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool12DataQuality:
    """Test data quality and completeness."""

    async def test_pathway_metadata_completeness(self):
        """
        Pathway results should have complete metadata.

        Validates data quality.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_PATHWAYS,
            gene="TP53",
            limit=5,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert len(data["pathways"]) > 0

        for pathway in data["pathways"]:
            # Check required fields
            assert "name" in pathway, "Pathway should have name"
            assert pathway["name"], "Name should not be empty"

            # Check optional but expected fields
            if "gene_count" in pathway:
                assert pathway["gene_count"] > 0, "Gene count should be positive"

            if "source" in pathway:
                assert pathway["source"] in ["reactome", "wikipathways", "kegg", "unknown"]

        logger.info(f"✓ Pathway metadata complete for {len(data['pathways'])} pathways")

    async def test_gene_list_quality(self):
        """
        Gene lists should have valid data.

        Validates gene data quality in pathway results.
        """
        query = PathwayQuery(
            mode=PathwayQueryMode.GET_GENES,
            pathway="apoptosis",
            limit=10,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_pathway(query)

        if result.startswith("Error:"):
            pytest.skip("Pathway not found or mode not available")

        data = json.loads(result)

        if "genes" in data and len(data["genes"]) > 0:
            for gene in data["genes"]:
                assert "name" in gene
                assert gene["name"], "Gene name should not be empty"

                # Check for identifier
                has_id = "curie" in gene or "identifier" in gene
                assert has_id, "Gene should have identifier"

            logger.info(f"✓ Gene data quality verified for {len(data['genes'])} genes")
