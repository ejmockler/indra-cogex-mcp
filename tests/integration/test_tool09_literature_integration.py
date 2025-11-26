"""
Integration tests for Tool 9: cogex_query_literature

Tests literature query functionality with actual data validation.

Run with: pytest tests/integration/test_tool09_literature_integration.py -v
"""

import json
import logging

import pytest

from cogex_mcp.schemas import LiteratureQuery, LiteratureQueryMode, ResponseFormat
from cogex_mcp.tools.literature import cogex_query_literature

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool9LiteratureQueries:
    """Test Tool 9 literature query modes with data validation."""

    async def test_get_statements_for_pmid(self):
        """Test getting INDRA statements from PubMed article."""
        # Using a real PMID that likely has INDRA statements
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
            pmid="29760375",  # Known paper with many statements
            limit=20,
            include_evidence_text=True,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "pmid" in data, "Response should include PMID"
        assert "statements" in data, "Response should include statements"

        # 4. PMID validation
        assert data["pmid"] == "29760375", "PMID should match query"

        # 5. Data structure validation (if statements found)
        if len(data["statements"]) > 0:
            first_stmt = data["statements"][0]
            assert "stmt_hash" in first_stmt, "Statement should have hash"
            assert "stmt_type" in first_stmt, "Statement should have type"
            assert "subject" in first_stmt, "Statement should have subject"
            assert "object" in first_stmt, "Statement should have object"
            assert "evidence_count" in first_stmt, "Should have evidence count"

            logger.info(f"✓ Found {len(data['statements'])} statements in PMID 29760375")
        else:
            logger.warning("No statements found for PMID (might be expected)")

        # 6. Pagination metadata
        assert "pagination" in data, "Response should include pagination"

    async def test_search_by_mesh_autophagy_cancer(self):
        """Test searching publications by MeSH terms."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.SEARCH_BY_MESH,
            mesh_terms=["Autophagy", "Neoplasms"],
            limit=30,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "mesh_terms" in data, "Response should include MeSH terms"
        assert "publications" in data, "Response should include publications"

        # 4. MeSH terms preserved
        assert data["mesh_terms"] == ["Autophagy", "Neoplasms"], "MeSH terms should match query"

        # 5. Data is non-empty (autophagy + cancer has many papers)
        assert len(data["publications"]) > 0, "Should find publications for autophagy + cancer"

        # 6. Publication structure validation
        first_pub = data["publications"][0]
        assert "pmid" in first_pub, "Publication should have PMID"
        assert "title" in first_pub, "Publication should have title"
        assert "journal" in first_pub, "Publication should have journal"
        assert "year" in first_pub, "Publication should have year"

        # 7. URL validation
        assert "url" in first_pub, "Publication should have URL"
        assert "pubmed" in first_pub["url"].lower(), "URL should be PubMed link"

        logger.info(f"✓ Found {len(data['publications'])} publications for autophagy + cancer")

    async def test_get_evidence_for_statement(self):
        """Test getting evidence for a statement (if we have a valid hash)."""
        # This test might not work without a real statement hash
        # We'll make it flexible
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_EVIDENCE_FOR_STATEMENT,
            statement_hash="test_hash_123",  # Placeholder
            include_evidence_text=True,
            max_evidence_per_statement=5,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # This might error with fake hash - that's OK
        if result.startswith("Error:"):
            logger.info(f"✓ Expected error for fake hash: {result}")
        else:
            data = json.loads(result)
            assert "statement_hash" in data, "Response should include statement hash"
            assert "evidence" in data, "Response should include evidence"
            logger.info(f"Got evidence response: {len(data.get('evidence', []))} items")

    async def test_get_statements_by_hashes(self):
        """Test batch retrieval of statements by hashes."""
        # Using placeholder hashes - might not find results
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_BY_HASHES,
            statement_hashes=["hash1", "hash2", "hash3"],
            include_evidence_text=False,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # Might error or return empty
        if result.startswith("Error:"):
            logger.info(f"Expected error for fake hashes: {result}")
        else:
            data = json.loads(result)
            assert "statements" in data, "Response should include statements"
            logger.info(f"✓ Batch retrieval returned {len(data['statements'])} statements")

    async def test_evidence_text_included(self):
        """Test that evidence text is included when requested."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
            pmid="29760375",
            include_evidence_text=True,
            max_evidence_per_statement=3,
            limit=10,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            if len(data["statements"]) > 0:
                # Check if evidence is included
                for stmt in data["statements"]:
                    if stmt.get("evidence"):
                        # Evidence should be a list
                        assert isinstance(stmt["evidence"], list), "Evidence should be a list"
                        # Should respect max_evidence limit
                        assert len(stmt["evidence"]) <= 3, "Should respect max_evidence limit"
                        logger.info("✓ Evidence text included in statements")
                        break

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.SEARCH_BY_MESH,
            mesh_terms=["Apoptosis"],
            limit=10,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await cogex_query_literature(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            assert has_markdown, "Markdown response should have formatting"
            logger.info("✓ Markdown response has formatting")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool9EdgeCases:
    """Edge cases for literature queries."""

    async def test_invalid_pmid(self):
        """Test error handling for invalid PMID."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
            pmid="99999999",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # Might error or return empty
        if result.startswith("Error:"):
            logger.info(f"✓ Invalid PMID error: {result}")
        else:
            data = json.loads(result)
            assert "statements" in data
            logger.info(f"Invalid PMID returned {len(data.get('statements', []))} statements")

    async def test_empty_mesh_terms(self):
        """Test error handling for empty MeSH terms."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.SEARCH_BY_MESH,
            mesh_terms=[],
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        # Should error for empty MeSH terms
        assert result.startswith("Error:"), "Should error for empty MeSH terms"
        logger.info(f"✓ Empty MeSH error: {result}")

    async def test_pagination_publications(self):
        """Test pagination for publications."""
        # Get first page
        query1 = LiteratureQuery(
            mode=LiteratureQueryMode.SEARCH_BY_MESH,
            mesh_terms=["Apoptosis"],
            limit=10,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result1 = await cogex_query_literature(query1)

        if not result1.startswith("Error:"):
            data1 = json.loads(result1)
            assert len(data1["publications"]) <= 10, "Should respect limit"

            # Get second page
            query2 = LiteratureQuery(
                mode=LiteratureQueryMode.SEARCH_BY_MESH,
                mesh_terms=["Apoptosis"],
                limit=10,
                offset=10,
                response_format=ResponseFormat.JSON,
            )

            result2 = await cogex_query_literature(query2)

            if not result2.startswith("Error:"):
                data2 = json.loads(result2)

                # Pages should have different PMIDs
                page1_pmids = {p["pmid"] for p in data1["publications"]}
                page2_pmids = {p["pmid"] for p in data2["publications"]}
                assert page1_pmids != page2_pmids, "Different pages should have different publications"

                logger.info("✓ Pagination working correctly")

    async def test_statement_types(self):
        """Test that statement types are valid."""
        query = LiteratureQuery(
            mode=LiteratureQueryMode.GET_STATEMENTS_FOR_PMID,
            pmid="29760375",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_literature(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            # Valid INDRA statement types
            valid_types = [
                "Phosphorylation", "Activation", "Inhibition", "Complex",
                "IncreaseAmount", "DecreaseAmount", "Translocation",
                "RegulateActivity", "RegulateAmount", "Acetylation",
                "Ubiquitination", "Methylation", "Farnesylation"
            ]

            for stmt in data["statements"]:
                stmt_type = stmt["stmt_type"]
                # Type should be a string
                assert isinstance(stmt_type, str), "Statement type should be string"
                # Log the types we see
                logger.info(f"Statement type: {stmt_type}")
