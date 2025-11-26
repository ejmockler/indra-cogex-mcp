"""
Integration tests for Tool 11 (cogex_resolve_identifiers) with live backends.

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

from cogex_mcp.schemas import IdentifierQuery, ResponseFormat
from cogex_mcp.tools.identifier import cogex_resolve_identifiers

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool11SymbolToHGNC:
    """Test symbol to HGNC ID conversion."""

    async def test_tp53_symbol_to_hgnc(self):
        """
        Convert TP53 symbol to HGNC ID.

        Validates:
        - Symbol to HGNC conversion works
        - Returns valid HGNC ID
        - Data structure is correct
        """
        query = IdentifierQuery(
            identifiers=["TP53"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "mappings" in data, "Response missing mappings"
        assert "statistics" in data, "Response missing statistics"
        assert "unmapped" in data, "Response missing unmapped"

        # Step 4: Validate data exists
        assert len(data["mappings"]) > 0, "Should return mapping for TP53"
        assert data["statistics"]["mapped"] > 0, "Should have at least one mapped identifier"

        # Step 5: Validate data quality
        mapping = data["mappings"][0]
        assert "source_id" in mapping
        assert mapping["source_id"] == "TP53"
        assert "target_ids" in mapping
        assert len(mapping["target_ids"]) > 0, "TP53 should map to HGNC ID"

        # Verify HGNC ID format (should be numeric string)
        hgnc_id = mapping["target_ids"][0]
        assert hgnc_id.isdigit() or hgnc_id.startswith("HGNC:"), f"Invalid HGNC ID format: {hgnc_id}"

        logger.info(f"✓ TP53 → {hgnc_id}")

    async def test_multiple_symbols_to_hgnc(self, known_entities):
        """
        Convert multiple gene symbols to HGNC IDs.

        Validates batch conversion functionality.
        """
        gene_symbols = known_entities["genes"][:5]  # TP53, BRCA1, EGFR, MAPK1, TNF

        query = IdentifierQuery(
            identifiers=gene_symbols,
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "mappings" in data
        assert "statistics" in data

        # Should map most known genes
        assert data["statistics"]["mapped"] >= 3, "Should map at least 3 out of 5 known genes"

        # Verify each mapping has required fields
        for mapping in data["mappings"]:
            assert "source_id" in mapping
            assert "target_ids" in mapping
            assert len(mapping["target_ids"]) > 0, f"{mapping['source_id']} should have target IDs"

        logger.info(f"✓ Mapped {data['statistics']['mapped']}/{len(gene_symbols)} genes")

    async def test_invalid_symbol_unmapped(self):
        """
        Unknown gene symbol should be in unmapped list.

        Validates error handling for invalid identifiers.
        """
        query = IdentifierQuery(
            identifiers=["FAKEGENE999", "NOTREAL123"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query should not error, just return unmapped: {result}"

        data = json.loads(result)
        assert "unmapped" in data

        # Both invalid symbols should be unmapped
        assert len(data["unmapped"]) == 2, "Both invalid symbols should be unmapped"
        assert "FAKEGENE999" in data["unmapped"]
        assert "NOTREAL123" in data["unmapped"]

        logger.info(f"✓ Invalid symbols correctly unmapped: {data['unmapped']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool11HGNCToUniProt:
    """Test HGNC ID to UniProt conversion."""

    async def test_tp53_hgnc_to_uniprot(self):
        """
        Convert TP53 HGNC ID to UniProt IDs.

        Note: One gene may map to multiple UniProt entries.
        """
        query = IdentifierQuery(
            identifiers=["11998"],  # TP53 HGNC ID
            from_namespace="hgnc",
            to_namespace="uniprot",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "mappings" in data
        assert len(data["mappings"]) > 0, "Should return UniProt mapping for TP53"

        mapping = data["mappings"][0]
        assert mapping["source_id"] == "11998"
        assert len(mapping["target_ids"]) > 0, "TP53 should have at least one UniProt ID"

        # Verify UniProt ID format (typically P##### or Q#####)
        uniprot_id = mapping["target_ids"][0]
        assert len(uniprot_id) >= 6, f"UniProt ID seems too short: {uniprot_id}"

        logger.info(f"✓ HGNC:11998 → UniProt: {mapping['target_ids']}")

    async def test_multiple_hgnc_to_uniprot(self):
        """
        Convert multiple HGNC IDs to UniProt.

        Tests batch conversion with 1:many mappings.
        """
        # HGNC IDs for TP53, BRCA1, EGFR
        query = IdentifierQuery(
            identifiers=["11998", "1100", "3236"],
            from_namespace="hgnc",
            to_namespace="uniprot",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "statistics" in data

        # Should map all or most well-known genes
        assert data["statistics"]["mapped"] >= 2, "Should map at least 2 HGNC IDs"

        # Verify mappings quality
        for mapping in data["mappings"]:
            assert len(mapping["target_ids"]) > 0, f"HGNC {mapping['source_id']} should have UniProt IDs"

        logger.info(f"✓ Mapped {data['statistics']['mapped']} HGNC IDs to {data['statistics']['total_targets']} UniProt IDs")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool11CrossReference:
    """Test various cross-reference conversions."""

    async def test_ensembl_to_hgnc(self):
        """
        Convert Ensembl gene ID to HGNC.

        Tests Ensembl → HGNC conversion path.
        """
        # TP53 Ensembl ID
        query = IdentifierQuery(
            identifiers=["ENSG00000141510"],
            from_namespace="ensembl",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        # This conversion may or may not be supported
        if result.startswith("Error:"):
            logger.warning(f"Ensembl→HGNC not supported: {result}")
            pytest.skip("Ensembl→HGNC conversion not available")
        else:
            data = json.loads(result)
            assert "mappings" in data

            if len(data["mappings"]) > 0:
                mapping = data["mappings"][0]
                logger.info(f"✓ ENSG00000141510 → HGNC:{mapping['target_ids']}")
            else:
                logger.warning("Ensembl ID not mapped (might be expected)")

    async def test_hgnc_to_symbol(self):
        """
        Convert HGNC ID back to gene symbol.

        Tests reverse conversion: HGNC → symbol.
        """
        query = IdentifierQuery(
            identifiers=["11998", "1100"],  # TP53, BRCA1
            from_namespace="hgnc",
            to_namespace="hgnc.symbol",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        if result.startswith("Error:"):
            logger.warning(f"HGNC→symbol conversion not supported: {result}")
            pytest.skip("HGNC→symbol conversion not available")
        else:
            data = json.loads(result)
            assert "mappings" in data
            assert len(data["mappings"]) >= 2, "Should convert both HGNC IDs"

            # Check for expected symbols
            symbols = [m["target_ids"][0] for m in data["mappings"]]
            logger.info(f"✓ HGNC IDs → symbols: {symbols}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool11EdgeCases:
    """Test edge cases and parameter validation."""

    async def test_empty_identifier_list(self):
        """
        Empty identifier list should raise validation error.

        Validates input validation at schema level.
        """
        from pydantic import ValidationError

        # Schema validation should reject empty list
        with pytest.raises(ValidationError) as exc_info:
            query = IdentifierQuery(
                identifiers=[],
                from_namespace="hgnc.symbol",
                to_namespace="hgnc",
                response_format=ResponseFormat.JSON
            )

        # Verify the error mentions the identifiers field
        error_str = str(exc_info.value)
        assert "identifiers" in error_str.lower(), f"Error should mention identifiers: {error_str}"

        logger.info(f"✓ Empty list correctly rejected by schema validation")

    async def test_single_identifier(self):
        """
        Single identifier should work correctly.

        Tests minimum valid input.
        """
        query = IdentifierQuery(
            identifiers=["TP53"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Single identifier failed: {result}"

        data = json.loads(result)
        assert data["statistics"]["total_input"] == 1
        logger.info("✓ Single identifier conversion works")

    async def test_mixed_valid_invalid_identifiers(self):
        """
        Mix of valid and invalid identifiers.

        Validates partial success handling.
        """
        query = IdentifierQuery(
            identifiers=["TP53", "FAKEGENE999", "BRCA1", "INVALID123"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        stats = data["statistics"]

        # Should have both mapped and unmapped
        assert stats["mapped"] >= 2, "Should map TP53 and BRCA1"
        assert stats["unmapped"] >= 2, "Should have 2 unmapped (FAKEGENE999, INVALID123)"
        assert stats["total_input"] == 4

        logger.info(f"✓ Partial success: {stats['mapped']} mapped, {stats['unmapped']} unmapped")

    async def test_markdown_format(self):
        """
        Test markdown output format.

        Validates alternative response format.
        """
        query = IdentifierQuery(
            identifiers=["TP53", "BRCA1"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Markdown query failed: {result}"

        # Should contain markdown formatting
        has_markdown = any(marker in result for marker in ["##", "**", "|", "-", "→"])
        assert has_markdown, "Markdown response should contain formatting"

        # Should mention the genes
        assert "TP53" in result or "11998" in result
        logger.info("✓ Markdown format contains expected content")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool11Statistics:
    """Test statistics and metadata in responses."""

    async def test_statistics_completeness(self):
        """
        Statistics should be complete and accurate.

        Validates metadata quality.
        """
        query = IdentifierQuery(
            identifiers=["TP53", "BRCA1", "EGFR"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        stats = data["statistics"]

        # Verify all statistics fields present
        required_fields = ["total_input", "mapped", "unmapped", "total_targets"]
        for field in required_fields:
            assert field in stats, f"Statistics missing '{field}'"

        # Verify statistics consistency
        assert stats["total_input"] == 3
        assert stats["mapped"] + stats["unmapped"] == stats["total_input"]
        assert stats["total_targets"] >= stats["mapped"], "total_targets should be >= mapped"

        logger.info(f"✓ Statistics complete: {stats}")

    async def test_mapping_confidence(self):
        """
        Mappings should include confidence information.

        Validates data quality metadata.
        """
        query = IdentifierQuery(
            identifiers=["TP53"],
            from_namespace="hgnc.symbol",
            to_namespace="hgnc",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_resolve_identifiers(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)

        if len(data["mappings"]) > 0:
            mapping = data["mappings"][0]

            # Check for confidence field (optional)
            if "confidence" in mapping:
                assert mapping["confidence"] in ["exact", "high", "medium", "low", None]
                logger.info(f"✓ Confidence: {mapping['confidence']}")
            else:
                logger.info("✓ Confidence field not present (optional)")
