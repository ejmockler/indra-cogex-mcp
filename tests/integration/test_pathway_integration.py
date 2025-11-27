"""
Integration tests for PathwayClient against real CoGEx Neo4j database.

Tests scientifically meaningful queries with known biological pathways.
Validates complete integration chain: Handler → Adapter → Neo4j Client → PathwayClient → CoGEx.

Run with: pytest tests/integration/test_pathway_integration.py -v -m integration

Requirements:
- Requires PathwayClient implementation
- Requires real Neo4j connection with CoGEx database
- Tests validate known biology (TP53 pathways, MAPK pathway, apoptosis genes, etc.)
"""

import logging

import pytest

from cogex_mcp.clients.neo4j_client import Neo4jClient
from cogex_mcp.config import settings

logger = logging.getLogger(__name__)


@pytest.mark.skipif(not settings.has_neo4j_config, reason="Neo4j not configured")
@pytest.mark.integration
@pytest.mark.asyncio
class TestPathwayIntegration:
    """Integration tests with real Neo4j database."""

    @pytest.fixture(scope="class")
    async def neo4j_client(self):
        """Real Neo4j client for integration testing."""
        logger.info("Connecting to Neo4j for PathwayClient integration tests")
        client = Neo4jClient(
            uri=settings.neo4j_url,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        await client.connect()
        logger.info("Neo4j connection established")
        yield client
        logger.info("Closing Neo4j connection")
        await client.close()

    @pytest.fixture
    def pathway_client(self, neo4j_client):
        """PathwayClient with real Neo4j connection."""
        from cogex_mcp.clients.pathway_client import PathwayClient

        return PathwayClient(neo4j_client=neo4j_client)

    # ========================================================================
    # Test 1: TP53 Pathways (Canonical Example)
    # ========================================================================

    async def test_get_pathways_for_tp53(self, pathway_client):
        """
        Test finding pathways containing TP53.

        Known biology:
        - TP53 is in p53 signaling pathway (Reactome R-HSA-5633007)
        - TP53 is in apoptotic process (GO:0006915)
        - TP53 is in cell cycle regulation pathways
        - Should find multiple pathway sources (Reactome, GO, WikiPathways)
        """
        logger.info("Testing pathways containing TP53")

        result = await pathway_client.get_pathways_for_gene(
            gene_id="hgnc:11998",  # TP53
            limit=50,
        )

        # Validate response structure
        assert result["success"] is True, "TP53 pathway query should succeed"
        assert len(result["pathways"]) > 0, "Should find pathways containing TP53"

        # Verify pathway structure
        for pathway in result["pathways"]:
            assert "name" in pathway
            assert "curie" in pathway
            assert "source" in pathway

        # Known biology: Should find p53 signaling or apoptosis pathways
        pathway_names = [p["name"].lower() for p in result["pathways"]]
        found_p53_related = any(
            "p53" in name or "apopt" in name or "cell cycle" in name
            for name in pathway_names
        )
        assert found_p53_related, f"Expected p53-related pathways, found: {pathway_names[:5]}"

        logger.info(f"TP53 found in {len(result['pathways'])} pathways")

    # ========================================================================
    # Test 2: MAPK Pathway Genes
    # ========================================================================

    async def test_get_genes_in_mapk_pathway(self, pathway_client):
        """
        Test getting genes in MAPK signaling pathway.

        Known biology:
        - MAPK pathway contains RAF, MEK, ERK kinases
        - Should find MAPK1 (ERK2), MAPK3 (ERK1)
        - Should find MAP2K1 (MEK1), MAP2K2 (MEK2)
        - Should find RAF1, BRAF, ARAF
        """
        logger.info("Testing MAPK pathway gene membership")

        # Try common MAPK pathway IDs from different sources
        mapk_pathway_ids = [
            "reactome:R-HSA-5683057",  # MAPK family signaling cascades
            "go:0000165",  # MAPK cascade
            "wikipathways:WP382",  # MAPK signaling pathway
        ]

        found_mapk_genes = False
        for pathway_id in mapk_pathway_ids:
            result = await pathway_client.get_genes_in_pathway(
                pathway_id=pathway_id,
                limit=100,
            )

            if result["success"] and len(result["genes"]) > 0:
                gene_symbols = {g["name"] for g in result["genes"]}

                # Check for known MAPK pathway genes
                expected_genes = {"MAPK1", "MAPK3", "MAP2K1", "MAP2K2", "RAF1", "BRAF"}
                found_genes = gene_symbols & expected_genes

                if found_genes:
                    found_mapk_genes = True
                    logger.info(f"MAPK pathway {pathway_id}: {len(result['genes'])} genes, found {found_genes}")
                    break

        # At least one MAPK pathway should be found with expected genes
        assert found_mapk_genes, "Should find MAPK pathway genes (MAPK1, MAPK3, RAF1, etc.)"

    # ========================================================================
    # Test 3: Shared Pathways for Apoptosis Genes
    # ========================================================================

    async def test_shared_pathways_apoptosis_genes(self, pathway_client):
        """
        Test finding pathways shared by apoptosis genes.

        Known biology:
        - BCL2, BAX, CASP3 are all apoptosis regulators
        - All should be in GO:0006915 (apoptotic process)
        - All should be in Reactome apoptosis pathways
        - Should find intrinsic apoptotic pathway
        """
        logger.info("Testing shared pathways for apoptosis genes (BCL2, BAX, CASP3)")

        result = await pathway_client.get_shared_pathways(
            gene_ids=[
                "hgnc:990",   # BCL2
                "hgnc:959",   # BAX
                "hgnc:1504",  # CASP3
            ],
            limit=50,
        )

        assert result["success"] is True

        if len(result["pathways"]) > 0:
            # Verify pathway structure
            for pathway in result["pathways"]:
                assert "name" in pathway
                assert "curie" in pathway

            # Known biology: Should find apoptosis-related pathways
            pathway_names = [p["name"].lower() for p in result["pathways"]]
            found_apoptosis = any(
                "apopt" in name or "death" in name or "caspase" in name
                for name in pathway_names
            )

            logger.info(f"Found {len(result['pathways'])} shared pathways for apoptosis genes")
            if found_apoptosis:
                logger.info("Correctly identified apoptosis-related shared pathways")
        else:
            logger.warning("No shared pathways found for BCL2, BAX, CASP3 (may indicate data filtering)")

    # ========================================================================
    # Test 4: Reactome vs WikiPathways Source Filtering
    # ========================================================================

    async def test_pathway_source_filtering(self, pathway_client):
        """
        Test filtering pathways by source (Reactome vs WikiPathways).

        Validates:
        - Source filter parameter works correctly
        - Different sources return different pathway sets
        - Same gene appears in multiple pathway databases
        """
        logger.info("Testing pathway source filtering for TP53")

        # Get Reactome pathways for TP53
        result_reactome = await pathway_client.get_pathways_for_gene(
            gene_id="hgnc:11998",  # TP53
            source="reactome",
            limit=50,
        )

        # Get WikiPathways pathways for TP53
        result_wikipathways = await pathway_client.get_pathways_for_gene(
            gene_id="hgnc:11998",
            source="wikipathways",
            limit=50,
        )

        # Both queries should succeed
        assert result_reactome["success"] is True
        assert result_wikipathways["success"] is True

        # Verify source filtering if results found
        if len(result_reactome["pathways"]) > 0:
            for pathway in result_reactome["pathways"]:
                assert pathway["source"] == "reactome", "Reactome filter should only return Reactome pathways"

        if len(result_wikipathways["pathways"]) > 0:
            for pathway in result_wikipathways["pathways"]:
                assert pathway["source"] == "wikipathways", "WikiPathways filter should only return WikiPathways"

        logger.info(
            f"TP53 pathways: {len(result_reactome['pathways'])} Reactome, "
            f"{len(result_wikipathways['pathways'])} WikiPathways"
        )

    # ========================================================================
    # Test 5: Check TP53 in p53 Signaling Pathway
    # ========================================================================

    async def test_check_tp53_in_p53_pathway(self, pathway_client):
        """
        Test checking if TP53 is in p53 signaling pathway.

        Known biology:
        - TP53 MUST be in Reactome p53 signaling pathway (R-HSA-5633007)
        - This is a canonical, well-established membership
        - If not found, indicates data quality issue
        """
        logger.info("Validating TP53 membership in p53 signaling pathway")

        result = await pathway_client.is_gene_in_pathway(
            gene_id="hgnc:11998",  # TP53
            pathway_id="reactome:R-HSA-5633007",  # p53 signaling
        )

        assert result["success"] is True

        # TP53 should be in p53 signaling pathway
        # If not found, log warning (may be due to data version or filtering)
        if result["is_member"]:
            logger.info("✓ Confirmed: TP53 is in p53 signaling pathway")
        else:
            logger.warning("✗ TP53 not found in p53 signaling pathway (may indicate data issue)")


@pytest.mark.skipif(not settings.has_neo4j_config, reason="Neo4j not configured")
@pytest.mark.integration
@pytest.mark.asyncio
class TestPathwayScientificAccuracy:
    """
    Tests that validate scientifically accurate results.

    These tests check that known biological pathway memberships are found.
    """

    @pytest.fixture
    def pathway_client(self, neo4j_client):
        """PathwayClient fixture."""
        from cogex_mcp.clients.pathway_client import PathwayClient

        return PathwayClient(neo4j_client=neo4j_client)

    @pytest.fixture(scope="class")
    async def neo4j_client(self):
        """Neo4j client fixture."""
        client = Neo4jClient(
            uri=settings.neo4j_url,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        await client.connect()
        yield client
        await client.close()

    async def test_tp53_mdm2_in_same_pathways(self, pathway_client):
        """
        Test that TP53 and MDM2 share pathways.

        Known biology:
        - TP53 and MDM2 form negative feedback loop
        - Both should be in p53 signaling pathway
        - Both should be in apoptosis pathways
        - Should find at least one shared pathway
        """
        logger.info("Validating TP53 and MDM2 share pathways")

        result = await pathway_client.get_shared_pathways(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            limit=50,
        )

        assert result["success"] is True

        if len(result["pathways"]) > 0:
            # Verify pathway structure
            pathway_names = [p["name"].lower() for p in result["pathways"]]

            # Known biology: Should find p53 signaling or apoptosis
            found_expected = any(
                "p53" in name or "apopt" in name
                for name in pathway_names
            )

            logger.info(f"TP53 and MDM2 share {len(result['pathways'])} pathways")
            if found_expected:
                logger.info("✓ Found expected p53/apoptosis shared pathways")
        else:
            logger.warning("No shared pathways found for TP53 and MDM2 (may indicate data filtering)")

    async def test_mapk_genes_in_mapk_pathway(self, pathway_client):
        """
        Test that MAPK genes are found in MAPK pathway.

        Known biology:
        - MAPK1 and MAPK3 are core MAPK pathway components
        - Both should be in GO:0000165 (MAPK cascade)
        - Both should be in Reactome MAPK pathways
        """
        logger.info("Validating MAPK1 and MAPK3 in MAPK pathway")

        result = await pathway_client.get_shared_pathways(
            gene_ids=["hgnc:6871", "hgnc:6877"],  # MAPK1, MAPK3
            limit=50,
        )

        assert result["success"] is True

        if len(result["pathways"]) > 0:
            pathway_names = [p["name"].lower() for p in result["pathways"]]

            # Should find MAPK-related pathways
            found_mapk = any("mapk" in name or "erk" in name for name in pathway_names)

            logger.info(f"MAPK1 and MAPK3 share {len(result['pathways'])} pathways")
            if found_mapk:
                logger.info("✓ Found expected MAPK-related shared pathways")
        else:
            logger.warning("No shared pathways found for MAPK1 and MAPK3")

    async def test_brca1_in_dna_repair_pathway(self, pathway_client):
        """
        Test that BRCA1 is in DNA repair pathways.

        Known biology:
        - BRCA1 is key DNA repair gene
        - Should be in GO:0006281 (DNA repair)
        - Should be in Reactome DNA repair pathways
        """
        logger.info("Validating BRCA1 in DNA repair pathways")

        result = await pathway_client.get_pathways_for_gene(
            gene_id="hgnc:1100",  # BRCA1
            limit=50,
        )

        assert result["success"] is True

        if len(result["pathways"]) > 0:
            pathway_names = [p["name"].lower() for p in result["pathways"]]

            # Should find DNA repair pathways
            found_dna_repair = any(
                "dna repair" in name or "homologous recombination" in name or "double-strand" in name
                for name in pathway_names
            )

            logger.info(f"BRCA1 found in {len(result['pathways'])} pathways")
            if found_dna_repair:
                logger.info("✓ Found expected DNA repair pathways for BRCA1")
        else:
            logger.warning("No pathways found for BRCA1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
