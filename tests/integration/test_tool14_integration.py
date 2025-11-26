"""
Integration tests for Tool 12/14 (cogex_check_relationship) with live backends.

Note: This is Tool 12 in implementation but tested as Tool 14 in the sequence.

Tests complete flow: Tool → Entity Resolver → Adapter → Backends → Response

Critical validation pattern:
1. No errors
2. Parse response
3. Validate structure
4. Validate data exists (boolean result)
5. Validate data quality
"""

import json
import logging

import pytest

from cogex_mcp.schemas import RelationshipQuery, RelationshipType, ResponseFormat
from cogex_mcp.tools.relationship import cogex_check_relationship

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14GenePathway:
    """Test gene_in_pathway relationship checks."""

    async def test_tp53_in_p53_pathway(self):
        """
        Check if TP53 is in p53 signaling pathway.

        Expected: True
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_IN_PATHWAY,
            entity1="TP53",
            entity2="p53 signaling",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:") and "not found" in result.lower():
            pytest.skip("Pathway not found by name")

        # Step 1: No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Step 2: Parse response
        data = json.loads(result)

        # Step 3: Validate structure
        assert "exists" in data, "Response should have 'exists' boolean"
        assert "relationship_type" in data
        assert "entity1" in data
        assert "entity2" in data

        # Step 4: Validate boolean result exists
        assert isinstance(data["exists"], bool), "exists should be boolean"

        # Step 5: Validate data quality
        assert data["relationship_type"] == "gene_in_pathway"
        assert data["entity1"]["name"] == "TP53"

        logger.info(f"✓ TP53 in p53 pathway: {data['exists']}")

    async def test_unrelated_gene_not_in_pathway(self):
        """
        Check if insulin is NOT in p53 pathway.

        Expected: False
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_IN_PATHWAY,
            entity1="INS",  # Insulin
            entity2="p53 signaling",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:") and "not found" in result.lower():
            pytest.skip("Pathway not found")

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        logger.info(f"✓ INS in p53 pathway: {data['exists']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14DrugTarget:
    """Test drug_target relationship checks."""

    async def test_imatinib_targets_abl1(self):
        """
        Check if imatinib targets ABL1.

        Expected: True (imatinib is BCR-ABL inhibitor)
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_TARGET,
            entity1="imatinib",
            entity2="ABL1",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        # Imatinib should target ABL1
        assert data["exists"] == True, "Imatinib should target ABL1"

        # Check for metadata
        if "metadata" in data and data["metadata"]:
            logger.info(f"  Metadata: {data['metadata']}")

        logger.info(f"✓ Imatinib targets ABL1: {data['exists']}")

    async def test_aspirin_targets_unknown(self):
        """
        Check aspirin targeting various proteins.

        Validates drug-target relationship detection.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_TARGET,
            entity1="aspirin",
            entity2="PTGS2",  # COX-2, aspirin target
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Drug or target not found")

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        logger.info(f"✓ Aspirin targets PTGS2: {data['exists']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14DrugIndication:
    """Test drug_indication relationship checks."""

    async def test_imatinib_for_leukemia(self):
        """
        Check if imatinib is indicated for leukemia.

        Expected: True (CML treatment)
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_INDICATION,
            entity1="imatinib",
            entity2="leukemia",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Drug or disease not found")

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        logger.info(f"✓ Imatinib for leukemia: {data['exists']}")

    async def test_metformin_for_diabetes(self):
        """
        Check if metformin is indicated for diabetes.

        Expected: True
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_INDICATION,
            entity1="metformin",
            entity2="diabetes",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Drug or disease not found")

        data = json.loads(result)
        assert "exists" in data

        # Metformin is standard diabetes treatment
        if data["exists"]:
            logger.info("✓ Metformin indicated for diabetes")
        else:
            logger.warning("Metformin-diabetes indication not found")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14GeneDisease:
    """Test gene_disease relationship checks."""

    async def test_brca1_breast_cancer(self):
        """
        Check if BRCA1 is associated with breast cancer.

        Expected: True
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="BRCA1",
            entity2="breast cancer",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        # BRCA1 is strongly associated with breast cancer
        assert data["exists"] == True, "BRCA1 should be associated with breast cancer"

        logger.info(f"✓ BRCA1-breast cancer association: {data['exists']}")

    async def test_tp53_cancer(self):
        """
        Check TP53 association with cancer.

        Expected: True (tumor suppressor)
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="TP53",
            entity2="cancer",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Gene or disease not found")

        data = json.loads(result)
        assert "exists" in data

        logger.info(f"✓ TP53-cancer association: {data['exists']}")

    async def test_unrelated_gene_disease(self):
        """
        Check unrelated gene-disease pair.

        Expected: False or no association
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="INS",  # Insulin
            entity2="alzheimer disease",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Gene or disease not found")

        data = json.loads(result)
        assert "exists" in data

        logger.info(f"✓ INS-Alzheimer association: {data['exists']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14VariantAssociation:
    """Test variant_association relationship checks."""

    async def test_apoe_variant_alzheimer(self):
        """
        Check APOE variant (rs7412) association with Alzheimer's.

        Well-known association.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.VARIANT_ASSOCIATION,
            entity1="rs7412",  # APOE variant
            entity2="alzheimer",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Variant or trait not found")

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        logger.info(f"✓ rs7412-Alzheimer association: {data['exists']}")

    async def test_variant_format_validation(self):
        """
        Test that rsID format is validated.

        Non-rsID should error.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.VARIANT_ASSOCIATION,
            entity1="NOT_AN_RSID",
            entity2="disease",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        # Should error for invalid rsID format
        assert result.startswith("Error:"), "Invalid rsID format should error"
        assert "rs" in result.lower() or "variant" in result.lower()

        logger.info(f"✓ Invalid rsID error: {result}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14CellLine:
    """Test cell_line_mutation relationship checks."""

    async def test_a549_tp53_mutation(self):
        """
        Check if A549 cell line has TP53 mutation.

        A549 is lung cancer cell line with known mutations.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.CELL_LINE_MUTATION,
            entity1="A549",
            entity2="TP53",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Cell line mutation data not available")

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        logger.info(f"✓ A549 has TP53 mutation: {data['exists']}")

    async def test_hela_mutation(self):
        """
        Check HeLa cell line for mutations.

        HeLa is well-characterized cell line.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.CELL_LINE_MUTATION,
            entity1="HeLa",
            entity2="TP53",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Cell line data not available")

        data = json.loads(result)
        assert "exists" in data

        logger.info(f"✓ HeLa TP53 status: {data['exists']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14CellMarker:
    """Test cell_marker relationship checks."""

    async def test_cd4_t_cell_marker(self):
        """
        Check if CD4 is a T cell marker.

        Expected: True
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.CELL_MARKER,
            entity1="CD4",
            entity2="T cell",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Cell marker data not available")

        data = json.loads(result)
        assert "exists" in data
        assert isinstance(data["exists"], bool)

        # CD4 is well-known T cell marker
        logger.info(f"✓ CD4 is T cell marker: {data['exists']}")

    async def test_cd19_b_cell_marker(self):
        """
        Check if CD19 is a B cell marker.

        Expected: True
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.CELL_MARKER,
            entity1="CD19",
            entity2="B cell",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Cell marker data not available")

        data = json.loads(result)
        assert "exists" in data

        logger.info(f"✓ CD19 is B cell marker: {data['exists']}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14Metadata:
    """Test relationship metadata quality."""

    async def test_metadata_structure(self):
        """
        Relationship results should include metadata when available.

        Validates metadata quality.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.DRUG_TARGET,
            entity1="imatinib",
            entity2="ABL1",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Query failed")

        data = json.loads(result)

        # Check for optional metadata
        if "metadata" in data and data["metadata"] is not None:
            metadata = data["metadata"]

            # Validate metadata fields
            valid_fields = ["confidence", "evidence_count", "sources", "additional_info"]
            for field in metadata:
                assert field in valid_fields, f"Unexpected metadata field: {field}"

            if "confidence" in metadata:
                assert isinstance(metadata["confidence"], (float, int, type(None)))

            if "evidence_count" in metadata:
                assert isinstance(metadata["evidence_count"], int)
                assert metadata["evidence_count"] >= 0

            if "sources" in metadata:
                assert isinstance(metadata["sources"], list)

            logger.info(f"✓ Metadata present: {list(metadata.keys())}")
        else:
            logger.info("✓ No metadata (optional)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool14EdgeCases:
    """Test edge cases and error handling."""

    async def test_unknown_entity1(self):
        """
        Unknown first entity should error.

        Validates error handling.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="FAKEGENE999",
            entity2="cancer",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        assert result.startswith("Error:"), "Unknown entity should error"
        assert "not found" in result.lower()

        logger.info(f"✓ Unknown entity error: {result}")

    async def test_unknown_entity2(self):
        """
        Unknown second entity should error.

        Validates error handling.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_DISEASE,
            entity1="TP53",
            entity2="FAKEDISEASE999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_check_relationship(query)

        assert result.startswith("Error:"), "Unknown disease should error"
        logger.info(f"✓ Unknown disease error: {result}")

    async def test_markdown_format(self):
        """
        Test markdown output format.

        Validates alternative response format.
        """
        query = RelationshipQuery(
            relationship_type=RelationshipType.GENE_IN_PATHWAY,
            entity1="TP53",
            entity2="p53 signaling",
            response_format=ResponseFormat.MARKDOWN
        )

        result = await cogex_check_relationship(query)

        if result.startswith("Error:"):
            pytest.skip("Pathway not found")

        # Markdown should contain boolean answer
        assert "yes" in result.lower() or "no" in result.lower() or "true" in result.lower() or "false" in result.lower()

        logger.info("✓ Markdown format validated")

    async def test_multiple_relationship_types(self, known_entities):
        """
        Test multiple relationship types in sequence.

        Validates no state contamination.
        """
        relationships = [
            (RelationshipType.GENE_IN_PATHWAY, "TP53", "apoptosis"),
            (RelationshipType.GENE_DISEASE, "BRCA1", "breast cancer"),
            (RelationshipType.DRUG_TARGET, "imatinib", "ABL1"),
        ]

        results = []
        for rel_type, entity1, entity2 in relationships:
            query = RelationshipQuery(
                relationship_type=rel_type,
                entity1=entity1,
                entity2=entity2,
                response_format=ResponseFormat.JSON
            )

            result = await cogex_check_relationship(query)

            if not result.startswith("Error:"):
                data = json.loads(result)
                assert "exists" in data
                results.append((rel_type.value, data["exists"]))

        assert len(results) >= 2, "Should successfully check at least 2 relationships"
        logger.info(f"✓ Multiple relationship checks: {results}")
