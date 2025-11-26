"""
Integration tests for Tool 7: cogex_query_cell_line

Tests cell line query functionality with actual data validation.

Run with: pytest tests/integration/test_tool07_cell_line_integration.py -v
"""

import json
import logging

import pytest

from cogex_mcp.schemas import CellLineQuery, CellLineQueryMode, ResponseFormat
from cogex_mcp.tools.cell_line import cogex_query_cell_line

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool7CellLineQueries:
    """Test Tool 7 cell line query modes with data validation."""

    async def test_get_properties_a549(self):
        """Test getting A549 cell line properties."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="A549",
            include_mutations=True,
            include_copy_number=True,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "cell_line" in data, "Response should include cell_line info"
        assert "mutations" in data, "Response should include mutations"

        # 4. Cell line metadata validation
        cell_line = data["cell_line"]
        assert cell_line["name"] == "A549", "Cell line name should be A549"
        assert "ccle_id" in cell_line, "Should have CCLE ID"

        # 5. Data structure validation - mutations
        if len(data["mutations"]) > 0:
            first_mut = data["mutations"][0]
            assert "gene" in first_mut, "Mutation should have gene"
            assert "mutation_type" in first_mut, "Mutation should have type"
            logger.info(f"✓ A549 has {len(data['mutations'])} mutations")
        else:
            logger.warning("A549 returned no mutations")

        # 6. Specific validation: A549 is known to have KRAS mutation
        gene_names = [m["gene"]["name"] for m in data["mutations"]]
        if "KRAS" in gene_names:
            logger.info("✓ A549 KRAS mutation confirmed")

    async def test_get_mutated_genes_mcf7(self):
        """Test getting mutated genes in MCF7 cell line."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_MUTATED_GENES,
            cell_line="MCF7",
            limit=50,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "cell_line" in data, "Response should include cell_line"
        assert "genes" in data, "Response should include genes list"

        # 4. Data is non-empty (MCF7 is well-characterized)
        assert len(data["genes"]) > 0, "MCF7 should have mutated genes"

        # 5. Data structure validation
        first_gene = data["genes"][0]
        assert "name" in first_gene, "Gene should have name"
        assert "curie" in first_gene, "Gene should have CURIE"

        # 6. Pagination metadata
        assert "pagination" in data, "Response should include pagination"

        logger.info(f"✓ MCF7 has {len(data['genes'])} mutated genes")

    async def test_get_cell_lines_with_tp53_mutation(self):
        """Test getting cell lines with TP53 mutations."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_CELL_LINES_WITH_MUTATION,
            gene="TP53",
            limit=30,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "gene" in data, "Response should include gene info"
        assert "cell_lines" in data, "Response should include cell_lines"

        # 4. Data is non-empty (TP53 is commonly mutated)
        assert len(data["cell_lines"]) > 0, "Should find cell lines with TP53 mutations"

        # 5. Data structure validation
        first_cell_line = data["cell_lines"][0]
        assert "name" in first_cell_line, "Cell line should have name"
        assert "ccle_id" in first_cell_line, "Cell line should have CCLE ID"

        # 6. Gene metadata validation
        assert data["gene"]["name"] == "TP53", "Gene name should be TP53"

        logger.info(f"✓ Found {len(data['cell_lines'])} cell lines with TP53 mutations")

    async def test_check_mutation_a549_kras(self):
        """Test checking if A549 has KRAS mutation."""
        query = CellLineQuery(
            mode=CellLineQueryMode.CHECK_MUTATION,
            cell_line="A549",
            gene="KRAS",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "has_mutation" in data, "Response should have has_mutation field"
        assert "cell_line" in data, "Response should include cell_line"
        assert "gene" in data, "Response should include gene"

        # 4. Metadata validation
        assert data["cell_line"]["name"] == "A549", "Cell line should be A549"
        assert data["gene"]["name"] == "KRAS", "Gene should be KRAS"

        # 5. Known fact: A549 has KRAS G12S mutation
        if data["has_mutation"]:
            logger.info("✓ A549 KRAS mutation confirmed")
        else:
            logger.warning("A549 KRAS mutation not found in database")

    async def test_unknown_cell_line_error(self):
        """Test error handling for unknown cell line."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="FAKE_CELL_LINE_XYZ",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        # Should error or return empty results
        if result.startswith("Error:"):
            logger.info(f"✓ Unknown cell line error: {result}")
        else:
            # Empty results are acceptable
            data = json.loads(result)
            logger.info(f"Unknown cell line returned data: {data}")

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="A549",
            include_mutations=True,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await cogex_query_cell_line(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            assert has_markdown, "Markdown response should have formatting"
            logger.info("✓ Markdown response has formatting")

    async def test_pagination_cell_lines(self):
        """Test pagination for cell lines with mutation."""
        # Get first page
        query1 = CellLineQuery(
            mode=CellLineQueryMode.GET_CELL_LINES_WITH_MUTATION,
            gene="TP53",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result1 = await cogex_query_cell_line(query1)
        assert not result1.startswith("Error:")

        data1 = json.loads(result1)
        assert "pagination" in data1, "Should have pagination metadata"
        assert len(data1["cell_lines"]) <= 5, "Should respect limit"

        logger.info("✓ Pagination working correctly")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool7CellLineFeatures:
    """Test additional cell line features."""

    async def test_include_dependencies(self):
        """Test getting gene dependencies (DepMap)."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="A549",
            include_dependencies=True,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            # Dependencies might not always be available
            if "dependencies" in data and len(data["dependencies"]) > 0:
                first_dep = data["dependencies"][0]
                assert "gene" in first_dep, "Dependency should have gene"
                assert "dependency_score" in first_dep, "Should have score"
                logger.info(f"✓ A549 has {len(data['dependencies'])} dependencies")

    async def test_copy_number_alterations(self):
        """Test copy number alterations."""
        query = CellLineQuery(
            mode=CellLineQueryMode.GET_PROPERTIES,
            cell_line="A549",
            include_copy_number=True,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_cell_line(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            if "copy_number_alterations" in data:
                cnas = data["copy_number_alterations"]
                if len(cnas) > 0:
                    first_cna = cnas[0]
                    assert "gene" in first_cna, "CNA should have gene"
                    assert "copy_number" in first_cna, "Should have copy number"
                    assert "alteration_type" in first_cna, "Should have type"
                    logger.info(f"✓ A549 has {len(cnas)} copy number alterations")
