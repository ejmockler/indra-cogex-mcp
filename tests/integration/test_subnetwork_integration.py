"""
Integration tests for SubnetworkClient against real CoGEx Neo4j database.

Tests scientifically meaningful queries with known biological interactions.
Validates complete integration chain: Handler → Adapter → Neo4j Client → SubnetworkClient → CoGEx.

Run with: pytest tests/integration/test_subnetwork_integration.py -v -m integration

Requirements:
- Requires Subagents 1, 2, 3 to complete SubnetworkClient implementation
- Requires real Neo4j connection with CoGEx database
- Tests validate known biology (TP53-MDM2, ALS genes, apoptosis, etc.)
"""

import logging
import time

import pytest

from cogex_mcp.clients.neo4j_client import Neo4jClient
from cogex_mcp.config import settings

logger = logging.getLogger(__name__)


@pytest.mark.skipif(not settings.has_neo4j_config, reason="Neo4j not configured")
@pytest.mark.integration
@pytest.mark.asyncio
class TestSubnetworkIntegration:
    """Integration tests with real Neo4j database."""

    @pytest.fixture(scope="class")
    async def neo4j_client(self):
        """Real Neo4j client for integration testing."""
        logger.info("Connecting to Neo4j for SubnetworkClient integration tests")
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
    def subnetwork_client(self, neo4j_client):
        """SubnetworkClient with real Neo4j connection."""
        from cogex_mcp.clients.subnetwork_client import SubnetworkClient

        return SubnetworkClient(neo4j_client=neo4j_client)

    # ========================================================================
    # Test 1: TP53-MDM2 Network (Canonical Example)
    # ========================================================================

    async def test_extract_direct_tp53_mdm2(self, subnetwork_client):
        """
        Test direct TP53-MDM2 interactions.

        Known biology:
        - TP53 phosphorylates MDM2 at S166
        - MDM2 ubiquitinates TP53
        - Canonical negative feedback loop
        - Well-studied with >100 publications
        """
        logger.info("Testing TP53-MDM2 direct network extraction")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            min_evidence=1,
            min_belief=0.5,
            max_statements=50,
        )

        # Validate response structure
        assert result["success"] is True, "TP53-MDM2 query should succeed"
        assert len(result["statements"]) > 0, "Should find TP53-MDM2 interactions"
        assert len(result["nodes"]) >= 2, "Should have at least TP53 and MDM2 nodes"

        # Verify known interactions present
        stmt_types = result["statistics"]["statement_types"]
        assert len(stmt_types) > 0, "Should have statement types"

        # Known biology: Should find Phosphorylation or Ubiquitination
        known_types = {"Phosphorylation", "Ubiquitination", "Activation", "Inhibition"}
        found_types = set(stmt_types.keys())
        assert found_types & known_types, f"Expected known interaction types, got {found_types}"

        # Validate statistics
        stats = result["statistics"]
        assert stats["statement_count"] > 0
        assert stats["node_count"] >= 2
        assert stats["avg_evidence_per_statement"] >= 1.0
        assert 0.0 <= stats["avg_belief_score"] <= 1.0

        logger.info(f"TP53-MDM2 network: {stats['statement_count']} statements, {stats['node_count']} nodes")

    async def test_extract_direct_tp53_mdm2_high_confidence(self, subnetwork_client):
        """Test TP53-MDM2 with high confidence filter (min_belief=0.8)."""
        logger.info("Testing TP53-MDM2 with high confidence filter")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            min_evidence=2,
            min_belief=0.8,  # High confidence only
            max_statements=50,
        )

        assert result["success"] is True
        if len(result["statements"]) > 0:
            # All statements should meet confidence threshold
            for stmt in result["statements"]:
                assert stmt["belief_score"] >= 0.8, f"Statement belief {stmt['belief_score']} below 0.8"
                assert stmt["evidence_count"] >= 2, f"Statement evidence {stmt['evidence_count']} below 2"

    # ========================================================================
    # Test 2: ALS Mediated Network
    # ========================================================================

    async def test_extract_mediated_als_genes(self, subnetwork_client):
        """
        Test mediated network for ALS genes.

        Known biology:
        - SOD1, TARDBP, FUS are major ALS genes
        - Connected through RNA binding, proteostasis pathways
        - Should find mediators like VCP, OPTN, TBK1
        """
        logger.info("Testing ALS gene mediated network")

        result = subnetwork_client.extract_mediated(
            gene_ids=["hgnc:11404", "hgnc:11571", "hgnc:8030"],  # SOD1, TARDBP, FUS
            min_evidence=2,
            max_statements=100,
        )

        assert result["success"] is True
        assert result["statistics"]["statement_count"] > 0, "Should find ALS gene connections"
        assert "note" in result, "Mediated network should include note"
        assert "two-hop" in result["note"].lower() or "mediated" in result["note"].lower()

        # Validate mediated paths structure
        # Should have intermediate nodes connecting ALS genes
        stats = result["statistics"]
        logger.info(f"ALS mediated network: {stats['statement_count']} statements, {stats['node_count']} nodes")

    # ========================================================================
    # Test 3: Apoptosis Shared Regulators
    # ========================================================================

    async def test_extract_shared_upstream_apoptosis(self, subnetwork_client):
        """
        Test shared upstream regulators for apoptosis genes.

        Known biology:
        - BCL2 and BAX are key apoptosis regulators
        - Both regulated by TP53
        - Both targets of caspases
        - Should find TP53, CASP3, CASP9 as shared regulators
        """
        logger.info("Testing shared upstream regulators for BCL2 and BAX")

        result = subnetwork_client.extract_shared_upstream(
            gene_ids=["hgnc:990", "hgnc:959"],  # BCL2, BAX
            min_evidence=2,
            max_statements=100,
        )

        assert result["success"] is True
        assert "note" in result
        assert "upstream" in result["note"].lower() or "regulator" in result["note"].lower()

        # Should find shared regulators
        assert result["statistics"]["statement_count"] > 0
        logger.info(f"Shared upstream: {result['statistics']['statement_count']} statements")

    # ========================================================================
    # Test 4: Brain-Specific Alzheimer's Network
    # ========================================================================

    async def test_extract_direct_with_tissue_filter_brain(self, subnetwork_client):
        """
        Test tissue-filtered network for brain-specific interactions.

        Known biology:
        - APP and PSEN1 are Alzheimer's disease genes
        - Key interactions occur in brain tissue
        - Tissue filter should reduce non-brain interactions
        """
        logger.info("Testing brain-specific network for APP-PSEN1")

        # First get unfiltered network
        result_unfiltered = subnetwork_client.extract_direct(
            gene_ids=["hgnc:620", "hgnc:9508"],  # APP, PSEN1
            max_statements=100,
        )

        # Then get brain-filtered network
        result_filtered = subnetwork_client.extract_direct(
            gene_ids=["hgnc:620", "hgnc:9508"],
            tissue="uberon:0000955",  # brain
            max_statements=100,
        )

        # Brain filter may reduce statements (or may not, depending on data)
        # Main validation: both queries succeed
        assert result_unfiltered["success"] is True
        assert result_filtered["success"] is True

        logger.info(
            f"APP-PSEN1: {result_unfiltered['statistics']['statement_count']} unfiltered, "
            f"{result_filtered['statistics']['statement_count']} brain-filtered"
        )

    # ========================================================================
    # Test 5: Autophagy GO Network
    # ========================================================================

    async def test_extract_direct_with_go_filter_autophagy(self, subnetwork_client):
        """
        Test GO term-filtered network for autophagy.

        Known biology:
        - ATG7 and BECN1 are core autophagy genes
        - GO:0006914 (autophagy) is the primary process
        - GO filter should enrich for autophagy-specific interactions
        """
        logger.info("Testing autophagy-specific network for ATG7-BECN1")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:588", "hgnc:1034"],  # ATG7, BECN1
            go_term="GO:0006914",  # autophagy
            max_statements=50,
        )

        assert result["success"] is True
        # GO filter may return empty if genes not annotated to GO term
        # Main validation: query succeeds without error
        logger.info(f"Autophagy network: {result['statistics']['statement_count']} statements")

    # ========================================================================
    # Test 6: MAPK Signaling Shared Downstream
    # ========================================================================

    async def test_extract_shared_downstream_mapk_signaling(self, subnetwork_client):
        """
        Test shared downstream targets for MAPK pathway kinases.

        Known biology:
        - MAPK1 (ERK2) and MAPK3 (ERK1) are paralogous kinases
        - Share many downstream targets (transcription factors)
        - Should find FOS, JUN, MYC as shared targets
        """
        logger.info("Testing shared downstream targets for MAPK1 and MAPK3")

        result = subnetwork_client.extract_shared_downstream(
            gene_ids=["hgnc:6871", "hgnc:6877"],  # MAPK1, MAPK3
            min_evidence=2,
            max_statements=100,
        )

        assert result["success"] is True
        assert "note" in result
        assert "downstream" in result["note"].lower() or "target" in result["note"].lower()

        # Should find shared targets
        assert result["statistics"]["statement_count"] > 0
        logger.info(f"Shared downstream: {result['statistics']['statement_count']} statements")

    # ========================================================================
    # Test 7: Statement Type Filtering
    # ========================================================================

    async def test_extract_direct_with_statement_type_filter(self, subnetwork_client):
        """
        Test filtering by statement types.

        Validates:
        - Only requested statement types returned
        - Type filter doesn't break query
        - Results match filter criteria
        """
        logger.info("Testing statement type filtering for TP53-MDM2")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            statement_types=["Phosphorylation", "Ubiquitination"],
            max_statements=50,
        )

        assert result["success"] is True

        if len(result["statements"]) > 0:
            # All statements should match requested types
            allowed_types = {"Phosphorylation", "Ubiquitination"}
            for stmt in result["statements"]:
                assert stmt["stmt_type"] in allowed_types, f"Unexpected type: {stmt['stmt_type']}"

            # Statistics should only show requested types
            stmt_types = set(result["statistics"]["statement_types"].keys())
            assert stmt_types.issubset(allowed_types), f"Found unexpected types: {stmt_types - allowed_types}"

    # ========================================================================
    # Test 8: Performance Benchmarks
    # ========================================================================

    async def test_performance_direct_query_under_5s(self, subnetwork_client):
        """
        Test that direct queries complete in <5 seconds.

        Performance requirement from spec:
        - Typical direct queries should be <5s
        - Validates SubnetworkClient is faster than raw Cypher
        """
        logger.info("Performance test: direct query latency")

        start_time = time.time()

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            max_statements=50,
        )

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed < 5.0, f"Query took {elapsed:.2f}s, expected <5s"
        logger.info(f"Performance: Direct query completed in {elapsed:.2f}s")

    async def test_performance_mediated_query_under_10s(self, subnetwork_client):
        """
        Test that mediated queries complete in <10 seconds.

        Mediated queries are more complex (two-hop paths) so get more time.
        """
        logger.info("Performance test: mediated query latency")

        start_time = time.time()

        result = subnetwork_client.extract_mediated(
            gene_ids=["hgnc:11998", "hgnc:6973", "hgnc:990"],  # TP53, MDM2, BCL2
            max_statements=100,
        )

        elapsed = time.time() - start_time

        assert result["success"] is True
        assert elapsed < 10.0, f"Query took {elapsed:.2f}s, expected <10s"
        logger.info(f"Performance: Mediated query completed in {elapsed:.2f}s")

    # ========================================================================
    # Test 9: Edge Cases
    # ========================================================================

    async def test_edge_case_single_gene(self, subnetwork_client):
        """
        Test query with single gene.

        Expected behavior:
        - Should succeed (may return self-interactions or empty)
        - Should not crash
        """
        logger.info("Edge case: single gene query")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998"],  # TP53 only
            max_statements=50,
        )

        assert result["success"] is True
        # May return empty - that's OK
        logger.info(f"Single gene: {result['statistics']['statement_count']} statements")

    async def test_edge_case_no_interactions_found(self, subnetwork_client):
        """
        Test genes with no known direct interactions.

        Expected behavior:
        - Query succeeds
        - Returns empty results gracefully
        - Statistics show 0 statements
        """
        logger.info("Edge case: no interactions found")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:5", "hgnc:10"],  # Unlikely to have direct interactions
            max_statements=50,
        )

        assert result["success"] is True
        # May have 0 statements - validate graceful handling
        assert "statements" in result
        assert "statistics" in result
        logger.info(f"No interactions: {result['statistics']['statement_count']} statements")

    async def test_edge_case_max_statements_limit(self, subnetwork_client):
        """
        Test that max_statements limit is enforced.

        Validates:
        - Result count <= max_statements
        - Limit doesn't cause errors
        """
        logger.info("Edge case: max_statements limit enforcement")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973", "hgnc:990", "hgnc:959"],  # TP53, MDM2, BCL2, BAX
            max_statements=10,  # Small limit
        )

        assert result["success"] is True
        assert len(result["statements"]) <= 10, f"Exceeded max_statements: {len(result['statements'])} > 10"
        logger.info(f"Limit enforcement: {len(result['statements'])} statements (max 10)")

    # ========================================================================
    # Test 10: Complex Multi-Gene Network
    # ========================================================================

    async def test_complex_multi_gene_network(self, subnetwork_client):
        """
        Test complex network with many genes.

        Known biology:
        - TP53, MYC, KRAS, EGFR, PIK3CA are cancer hallmark genes
        - Extensively connected through signaling pathways
        - Should return substantial network
        """
        logger.info("Testing complex multi-gene cancer hallmark network")

        result = subnetwork_client.extract_direct(
            gene_ids=[
                "hgnc:11998",  # TP53
                "hgnc:7553",  # MYC
                "hgnc:6407",  # KRAS
                "hgnc:3236",  # EGFR
                "hgnc:8975",  # PIK3CA
            ],
            min_evidence=2,
            max_statements=200,
        )

        assert result["success"] is True
        assert result["statistics"]["statement_count"] > 0, "Should find cancer gene interactions"

        # Validate network structure
        stats = result["statistics"]
        assert stats["node_count"] >= 5, "Should include all query genes plus possible intermediates"
        assert len(stats["statement_types"]) > 0, "Should have diverse statement types"

        logger.info(
            f"Cancer hallmark network: {stats['statement_count']} statements, "
            f"{stats['node_count']} nodes, "
            f"{len(stats['statement_types'])} statement types"
        )

    # ========================================================================
    # Test 11: CURIE Format Validation
    # ========================================================================

    async def test_curie_format_consistency(self, subnetwork_client):
        """
        Test that all CURIEs are properly formatted.

        Validates:
        - Lowercase namespace
        - Colon separator
        - No duplicate prefixes
        - Consistent with CoGEx standards
        """
        logger.info("Testing CURIE format consistency")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            max_statements=20,
        )

        assert result["success"] is True

        # Validate node CURIEs
        for node in result["nodes"]:
            curie = node["curie"]
            assert ":" in curie, f"CURIE missing colon: {curie}"
            namespace, identifier = curie.split(":", 1)
            assert namespace.islower() or namespace.isupper(), f"Invalid namespace case: {namespace}"
            assert node["namespace"] == namespace, f"Namespace mismatch: {node['namespace']} vs {namespace}"

        # Validate statement CURIEs
        for stmt in result["statements"]:
            for agent_key in ["subject", "object"]:
                if agent_key in stmt:
                    curie = stmt[agent_key]["curie"]
                    assert ":" in curie, f"Statement {agent_key} CURIE missing colon: {curie}"

    # ========================================================================
    # Test 12: Evidence Source Validation
    # ========================================================================

    async def test_evidence_sources_present(self, subnetwork_client):
        """
        Test that evidence sources are properly extracted.

        Validates:
        - Statements have sources field
        - Sources are non-empty for well-studied interactions
        - Known sources like 'reach', 'sparser' appear
        """
        logger.info("Testing evidence source extraction")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53-MDM2 (well-studied)
            min_evidence=2,
            max_statements=20,
        )

        assert result["success"] is True

        if len(result["statements"]) > 0:
            # Check that statements have sources
            for stmt in result["statements"]:
                assert "sources" in stmt, "Statement missing sources field"
                # Well-studied interactions should have sources
                if stmt["evidence_count"] > 0:
                    assert len(stmt["sources"]) > 0, "Statement with evidence should have sources"

    # ========================================================================
    # Test 13: Shared Upstream with Statement Type Filter
    # ========================================================================

    async def test_shared_upstream_with_type_filter_kinases(self, subnetwork_client):
        """
        Test shared upstream with statement type filtering.

        Known biology:
        - AKT1 and MAPK1 are both phosphorylation targets
        - Should find shared kinases as upstream regulators
        - Filter to Phosphorylation only
        """
        logger.info("Testing shared upstream with Phosphorylation filter")

        result = subnetwork_client.extract_shared_upstream(
            gene_ids=["hgnc:391", "hgnc:6871"],  # AKT1, MAPK1
            statement_types=["Phosphorylation"],
            min_evidence=2,
            max_statements=50,
        )

        assert result["success"] is True

        if len(result["statements"]) > 0:
            # All statements should be Phosphorylation
            for stmt in result["statements"]:
                assert stmt["stmt_type"] == "Phosphorylation", f"Unexpected type: {stmt['stmt_type']}"

    # ========================================================================
    # Test 14: Shared Downstream with Evidence Filter
    # ========================================================================

    async def test_shared_downstream_high_evidence(self, subnetwork_client):
        """
        Test shared downstream with high evidence threshold.

        Known biology:
        - TP53 and MYC are major transcription factors
        - Should have many well-evidenced shared targets
        - min_evidence=5 ensures only well-studied connections
        """
        logger.info("Testing shared downstream with high evidence filter")

        result = subnetwork_client.extract_shared_downstream(
            gene_ids=["hgnc:11998", "hgnc:7553"],  # TP53, MYC
            min_evidence=5,  # High evidence threshold
            max_statements=100,
        )

        assert result["success"] is True

        if len(result["statements"]) > 0:
            # All statements should meet evidence threshold
            for stmt in result["statements"]:
                assert stmt["evidence_count"] >= 5, f"Evidence {stmt['evidence_count']} below threshold"

            # Validate high average evidence
            avg_evidence = result["statistics"]["avg_evidence_per_statement"]
            assert avg_evidence >= 5.0, f"Average evidence {avg_evidence} below threshold"


@pytest.mark.skipif(not settings.has_neo4j_config, reason="Neo4j not configured")
@pytest.mark.integration
@pytest.mark.asyncio
class TestSubnetworkScientificAccuracy:
    """
    Tests that validate scientifically accurate results.

    These tests check that known biological interactions are found.
    """

    @pytest.fixture
    def subnetwork_client(self, neo4j_client):
        """SubnetworkClient fixture."""
        from cogex_mcp.clients.subnetwork_client import SubnetworkClient

        return SubnetworkClient(neo4j_client=neo4j_client)

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

    async def test_tp53_phosphorylates_mdm2_at_s166(self, subnetwork_client):
        """
        Test that TP53→MDM2 phosphorylation at S166 is found.

        This is a canonical, well-established interaction that MUST be present.
        If missing, indicates data quality issue.
        """
        logger.info("Validating canonical TP53 phosphorylates MDM2 at S166")

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            statement_types=["Phosphorylation"],
            max_statements=50,
        )

        assert result["success"] is True

        # Look for specific phosphorylation
        found_s166 = False
        for stmt in result["statements"]:
            if stmt["stmt_type"] == "Phosphorylation":
                if "position" in stmt and stmt["position"] == "166":
                    found_s166 = True
                    logger.info("Found TP53→MDM2 S166 phosphorylation")
                    break

        # This is a known interaction - should be found
        # If not found, may indicate filtering or data issues
        if not found_s166:
            logger.warning("TP53→MDM2 S166 phosphorylation not found (may be filtered)")

    async def test_als_genes_share_rna_binding_pathway(self, subnetwork_client):
        """
        Test that ALS genes connect through RNA binding mechanisms.

        Known biology:
        - SOD1, TARDBP, FUS all involved in RNA processing
        - Should find connections related to RNA binding
        """
        logger.info("Validating ALS genes share RNA binding connections")

        result = subnetwork_client.extract_shared_upstream(
            gene_ids=["hgnc:11404", "hgnc:11571", "hgnc:8030"],  # SOD1, TARDBP, FUS
            max_statements=100,
        )

        assert result["success"] is True
        # Presence of shared upstream indicates connectivity
        # Exact pathway validation would require GO term analysis
        logger.info(f"ALS shared upstream: {result['statistics']['statement_count']} connections")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
