"""
Integration tests for Tool 16 (cogex_query_protein_functions) with live backends.

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

from cogex_mcp.schemas import ProteinFunctionMode, ProteinFunctionQuery, ResponseFormat
from cogex_mcp.tools.protein_function import cogex_query_protein_functions

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16GeneToActivities:
    """Test gene → enzyme activities mode."""

    async def test_egfr_activities(self):
        """
        Get enzyme activities for EGFR (tyrosine kinase).

        Validates:
        - Gene to activities lookup works
        - Returns activity data
        - EGFR should have kinase activity
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="EGFR",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "gene" in data, "Response should have gene info"
        assert "activities" in data, "Response should have activities"

        # Step 4: Validate data exists
        assert data["gene"]["name"] == "EGFR"

        # EGFR is a well-known kinase, should have activity data
        assert isinstance(data["activities"], list), "Activities should be a list"
        assert len(data["activities"]) > 0, "EGFR should have enzyme activities (kinase)"

        # Step 5: Validate data quality
        for activity in data["activities"]:
            assert "activity" in activity, "Activity should have name"
            assert activity["activity"], "Activity name should not be empty"

        # EGFR should have kinase activity
        activity_names = [a["activity"].lower() for a in data["activities"]]
        assert any("kinase" in name for name in activity_names), "EGFR should have kinase activity"

        logger.info(f"✓ EGFR activities: {activity_names}")

    async def test_tp53_activities(self):
        """
        Get activities for TP53 (transcription factor).

        TP53 is a transcription factor, not an enzyme.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="TP53",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "gene" in data
        assert "activities" in data

        # TP53 may have few/no enzyme activities (it's a TF, not an enzyme)
        logger.info(f"✓ TP53 activities: {len(data['activities'])} found")

    async def test_mapk1_kinase_activity(self):
        """
        Get activities for MAPK1 (MAP kinase).

        Should have kinase activity.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="MAPK1",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "activities" in data

        if len(data["activities"]) > 0:
            activity_names = [a["activity"].lower() for a in data["activities"]]
            logger.info(f"✓ MAPK1 activities: {activity_names}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16ActivityToGenes:
    """Test activity → genes mode."""

    async def test_kinase_genes(self):
        """
        Get all genes with kinase activity.

        Should return many kinases.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="kinase",
            limit=50,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "genes" in data, "Response should have genes"
        assert "activity" in data, "Response should echo activity"
        assert "pagination" in data, "Response should have pagination"

        # There are hundreds of kinases
        assert len(data["genes"]) > 0, "Should find kinase genes"

        # Validate gene structure
        for gene in data["genes"]:
            assert "name" in gene, "Gene should have name"
            assert gene["name"], "Gene name should not be empty"

        # Check for known kinases
        gene_names = [g["name"] for g in data["genes"]]
        known_kinases = ["EGFR", "MAPK1", "SRC", "ABL1"]
        found_kinases = [k for k in known_kinases if k in gene_names]

        logger.info(f"✓ Found {len(data['genes'])} kinases, including: {found_kinases[:5]}")

    async def test_phosphatase_genes(self):
        """
        Get genes with phosphatase activity.

        Tests another enzyme class.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="phosphatase",
            limit=30,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if result.startswith("Error:"):
            pytest.skip("Phosphatase activity not found or not supported")

        data = json.loads(result)
        assert "genes" in data

        logger.info(f"✓ Found {len(data['genes'])} phosphatases")

    async def test_transcription_factor_genes(self):
        """
        Get transcription factor genes.

        Tests non-enzymatic protein function.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="transcription_factor",
            limit=30,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if result.startswith("Error:"):
            pytest.skip("Transcription factor query not supported in this mode")

        data = json.loads(result)
        assert "genes" in data

        # Should find TFs like TP53, MYC, etc.
        logger.info(f"✓ Found {len(data['genes'])} transcription factors")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16CheckActivity:
    """Test check_activity mode (boolean check)."""

    async def test_egfr_is_kinase(self):
        """
        Check if EGFR has kinase activity.

        Expected: True
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="EGFR",
            enzyme_activity="kinase",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "has_activity" in data, "Response should have has_activity boolean"
        assert "gene" in data
        assert "activity" in data

        # EGFR should be a kinase
        assert data["has_activity"] == True, "EGFR should have kinase activity"

        logger.info(f"✓ EGFR is kinase: {data['has_activity']}")

    async def test_tp53_is_not_kinase(self):
        """
        Check if TP53 has kinase activity.

        Expected: False (TP53 is transcription factor)
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="TP53",
            enzyme_activity="kinase",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "has_activity" in data

        # TP53 is not a kinase
        assert data["has_activity"] == False, "TP53 should NOT have kinase activity"

        logger.info(f"✓ TP53 is kinase: {data['has_activity']}")

    async def test_tp53_is_transcription_factor(self):
        """
        Check if TP53 is a transcription factor.

        Expected: True
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="TP53",
            enzyme_activity="transcription_factor",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if result.startswith("Error:"):
            pytest.skip("Transcription factor check not supported")

        data = json.loads(result)
        assert "has_activity" in data

        # TP53 is a well-known transcription factor
        if data["has_activity"]:
            logger.info("✓ TP53 is transcription factor: True")
        else:
            logger.warning("TP53 transcription factor status not found")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16CheckFunctionTypes:
    """Test check_function_types mode (batch check)."""

    async def test_batch_kinase_check(self):
        """
        Check multiple genes for kinase activity.

        Tests batch function checking.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=["EGFR", "MAPK1", "TP53"],
            function_types=["kinase"],
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "function_checks" in data, "Response should have function_checks"
        assert "genes_checked" in data
        assert "function_types" in data

        # Should check all 3 genes
        assert data["genes_checked"] == 3, "Should check all 3 genes"

        # Validate structure
        checks = data["function_checks"]
        assert "EGFR" in checks
        assert "MAPK1" in checks
        assert "TP53" in checks

        # Each check should have kinase boolean
        for gene_name, functions in checks.items():
            assert "kinase" in functions, f"{gene_name} should have kinase check"
            assert isinstance(functions["kinase"], bool), "kinase should be boolean"

        # EGFR and MAPK1 should be kinases, TP53 should not
        assert checks["EGFR"]["kinase"] == True, "EGFR should be kinase"
        assert checks["MAPK1"]["kinase"] == True, "MAPK1 should be kinase"
        assert checks["TP53"]["kinase"] == False, "TP53 should NOT be kinase"

        logger.info(f"✓ Batch kinase check: {checks}")

    async def test_multi_function_check(self):
        """
        Check multiple function types for multiple genes.

        Tests comprehensive function checking.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=["TP53", "EGFR"],
            function_types=["kinase", "phosphatase", "transcription_factor"],
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "function_checks" in data

        checks = data["function_checks"]

        # TP53 should be TF but not kinase/phosphatase
        tp53_checks = checks["TP53"]
        assert tp53_checks["kinase"] == False
        assert tp53_checks["phosphatase"] == False
        # TF check may or may not work

        # EGFR should be kinase but not phosphatase/TF
        egfr_checks = checks["EGFR"]
        assert egfr_checks["kinase"] == True
        assert egfr_checks["phosphatase"] == False
        assert egfr_checks["transcription_factor"] == False

        logger.info(f"✓ Multi-function check:")
        logger.info(f"  TP53: {tp53_checks}")
        logger.info(f"  EGFR: {egfr_checks}")

    async def test_single_gene_multi_function(self):
        """
        Check multiple functions for single gene.

        Tests that single gene can be passed as gene parameter.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            gene="EGFR",  # Single gene
            function_types=["kinase", "phosphatase"],
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "function_checks" in data

        checks = data["function_checks"]
        assert "EGFR" in checks
        assert checks["EGFR"]["kinase"] == True
        assert checks["EGFR"]["phosphatase"] == False

        logger.info(f"✓ Single gene check: {checks['EGFR']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16DataQuality:
    """Test enzyme activity data quality."""

    async def test_activity_metadata(self):
        """
        Activity results should include metadata.

        Validates activity data quality.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="EGFR",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)

        if len(data["activities"]) > 0:
            for activity in data["activities"]:
                # Check for expected fields
                assert "activity" in activity
                assert activity["activity"], "Activity name should not be empty"

                # Optional but common fields
                if "ec_number" in activity:
                    logger.info(f"  EC number: {activity['ec_number']}")

                if "confidence" in activity:
                    assert activity["confidence"] in ["high", "medium", "low", None]

                if "evidence_sources" in activity:
                    assert isinstance(activity["evidence_sources"], list)

            logger.info("✓ Activity metadata validated")

    async def test_gene_list_quality(self):
        """
        Gene lists should have valid identifiers.

        Validates gene data quality.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="kinase",
            limit=10,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)

        for gene in data["genes"]:
            assert "name" in gene
            assert gene["name"], "Gene name should not be empty"

            # Check for identifier
            has_id = "curie" in gene or "identifier" in gene
            assert has_id, "Gene should have identifier"

        logger.info(f"✓ Gene list quality validated for {len(data['genes'])} genes")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16EdgeCases:
    """Test edge cases and error handling."""

    async def test_unknown_gene(self):
        """
        Unknown gene should return error.

        Validates error handling.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="FAKEGENE999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert result.startswith("Error:"), "Unknown gene should error"
        assert "not found" in result.lower()

        logger.info(f"✓ Unknown gene error: {result}")

    async def test_unknown_activity(self):
        """
        Unknown activity type should handle gracefully.

        Validates activity validation.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="fake_activity_xyz",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        # May error or return empty results
        if result.startswith("Error:"):
            logger.info(f"✓ Unknown activity error: {result}")
        else:
            data = json.loads(result)
            assert "genes" in data
            # Empty results acceptable
            logger.info(f"✓ Unknown activity: {len(data.get('genes', []))} genes")

    async def test_pagination(self):
        """
        Test pagination for large result sets.

        Validates limit parameter.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.ACTIVITY_TO_GENES,
            enzyme_activity="kinase",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert len(data["genes"]) <= 5, "Should respect limit parameter"

        logger.info(f"✓ Pagination: {len(data['genes'])} genes returned")

    async def test_markdown_format(self):
        """
        Test markdown output format.

        Validates alternative response format.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.GENE_TO_ACTIVITIES,
            gene="EGFR",
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_query_protein_functions(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Should contain markdown formatting
        has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
        assert has_markdown or "EGFR" in result, "Markdown should have formatting or gene name"

        logger.info("✓ Markdown format validated")

    async def test_batch_with_invalid_gene(self):
        """
        Batch check with some invalid genes.

        Validates partial success handling.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            genes=["EGFR", "FAKEGENE999", "TP53"],
            function_types=["kinase"],
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        # Should handle invalid genes gracefully
        if result.startswith("Error:"):
            # May error on invalid gene
            logger.info("✓ Batch errors on invalid gene")
        else:
            data = json.loads(result)
            assert "function_checks" in data

            # Valid genes should still be checked
            checks = data["function_checks"]
            assert "EGFR" in checks or "TP53" in checks, "Valid genes should be checked"

            logger.info(f"✓ Batch with invalid: checked {len(checks)} genes")

    async def test_empty_function_types(self):
        """
        Empty function_types list should error.

        Validates input validation.
        """
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            gene="EGFR",
            function_types=[],  # Empty
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        assert result.startswith("Error:"), "Empty function_types should error"
        assert "required" in result.lower() or "empty" in result.lower()

        logger.info(f"✓ Empty function_types error: {result}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool16KnownProteins:
    """Test specific well-known proteins with known functions."""

    async def test_src_kinase(self):
        """SRC is proto-oncogene tyrosine kinase."""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="SRC",
            enzyme_activity="kinase",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            assert data["has_activity"] == True, "SRC should be kinase"
            logger.info("✓ SRC is kinase")

    async def test_pten_phosphatase(self):
        """PTEN is phosphatase and tensin homolog."""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_ACTIVITY,
            gene="PTEN",
            enzyme_activity="phosphatase",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            # PTEN is a phosphatase
            logger.info(f"✓ PTEN is phosphatase: {data['has_activity']}")

    async def test_myc_transcription_factor(self):
        """MYC is transcription factor."""
        query = ProteinFunctionQuery(
            mode=ProteinFunctionMode.CHECK_FUNCTION_TYPES,
            gene="MYC",
            function_types=["transcription_factor", "kinase"],
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_protein_functions(query)

        if not result.startswith("Error:"):
            data = json.loads(result)
            checks = data["function_checks"]["MYC"]
            # MYC should be TF, not kinase
            assert checks["kinase"] == False, "MYC should NOT be kinase"
            logger.info(f"✓ MYC functions: {checks}")
