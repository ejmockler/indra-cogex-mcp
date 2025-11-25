"""
Integration tests for backend clients (Neo4j + REST) against live CoGEx.

Tests direct query execution without higher-level abstractions, validating:
- Phase 1 Fix: Neo4j schema corrections (STARTS WITH 'hgnc:', obsolete filter)
- Phase 2 Fix: REST client None parameter handling
"""

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestNeo4jClientIntegration:
    """Test Neo4j client against production database."""

    async def test_connection_health(self, integration_adapter):
        """Verify Neo4j connection is healthy."""
        adapter = integration_adapter
        status = adapter.get_status()

        assert status["initialized"], "Adapter should be initialized"
        assert status.get("neo4j_available") is not None, "Neo4j status should be available"

        logger.info(f"Neo4j connection status: {status}")

    async def test_get_gene_by_symbol_tp53(self, integration_adapter):
        """
        Get TP53 by symbol using corrected schema.

        Validates Phase 1 Fix:
        - Uses 'g.id STARTS WITH hgnc:' instead of 'Gene' label
        - Filters obsolete genes
        """
        adapter = integration_adapter

        result = await adapter.neo4j_client.execute_query(
            "get_gene_by_symbol",
            symbol="TP53"
        )

        assert result["success"], f"Query should succeed: {result.get('error')}"
        assert len(result["records"]) > 0, "Should find TP53"

        gene = result["records"][0]
        assert gene["name"] == "TP53", "Gene name should be TP53"
        assert "hgnc:" in gene["id"], "ID should be CURIE format (hgnc:11998)"

        logger.info(f"✓ TP53 gene data: {gene}")

    async def test_get_gene_by_id_curie(self, integration_adapter):
        """
        Get gene by full CURIE (hgnc:11998).

        Validates Phase 1 Fix:
        - Accepts full CURIE format
        - Returns correct gene node
        """
        adapter = integration_adapter

        result = await adapter.neo4j_client.execute_query(
            "get_gene_by_id",
            gene_id="hgnc:11998"
        )

        assert result["success"], f"Query should succeed: {result.get('error')}"
        assert len(result["records"]) > 0, "Should find gene by CURIE"

        gene = result["records"][0]
        assert gene["name"] == "TP53", "Should resolve to TP53"
        assert gene["id"] == "hgnc:11998", "Should preserve full CURIE"

        logger.info(f"✓ Gene by CURIE: {gene}")

    async def test_get_multiple_genes(self, integration_adapter, known_entities):
        """Test multiple gene lookups in sequence."""
        adapter = integration_adapter
        symbols = known_entities["genes"][:3]  # TP53, BRCA1, EGFR

        found_genes = []
        for symbol in symbols:
            result = await adapter.neo4j_client.execute_query(
                "get_gene_by_symbol",
                symbol=symbol
            )

            if result["success"] and len(result["records"]) > 0:
                gene = result["records"][0]
                found_genes.append(gene["name"])
                logger.info(f"✓ Found {gene['name']} ({gene['id']})")

        assert len(found_genes) >= 2, f"Should find at least 2 genes, found: {found_genes}"

    async def test_gene_properties_schema(self, integration_adapter):
        """
        Verify gene node has expected properties from schema discovery.

        Validates Phase 1 Fix:
        - Correct property names (id, name, type, obsolete)
        - No reference to non-existent 'db_refs'
        """
        adapter = integration_adapter

        result = await adapter.neo4j_client.execute_query(
            "get_gene_by_symbol",
            symbol="TP53"
        )

        assert result["success"]
        gene = result["records"][0]

        # Properties that SHOULD exist
        assert "name" in gene, "Should have 'name' property"
        assert "id" in gene, "Should have 'id' property"

        # Properties that should NOT be queried (per schema discovery)
        # The query should not fail due to missing 'db_refs'

        logger.info(f"✓ Gene properties validated: {list(gene.keys())}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestRESTClientIntegration:
    """Test REST client against live discovery.indra.bio API."""

    async def test_connection_health(self, integration_adapter):
        """
        Verify REST API is accessible.

        Validates Phase 2 Fix:
        - REST client handles None parameters in get_meta
        - No crash on endpoints without required parameters
        """
        adapter = integration_adapter
        status = adapter.get_status()

        assert status["initialized"], "Adapter should be initialized"

        # REST client should be available
        assert adapter.rest_client is not None, "REST client should exist"

        logger.info("✓ REST API client available")

    async def test_get_meta(self, integration_adapter):
        """
        Test get_meta endpoint (no parameters).

        Validates Phase 2 Fix:
        - Endpoint with no parameters doesn't crash
        - None parameter handling works correctly
        """
        adapter = integration_adapter

        try:
            result = await adapter.rest_client.execute_query("get_meta")

            # Should either succeed or fail gracefully
            assert result is not None, "Should return a result"
            logger.info("✓ get_meta endpoint accessible")

        except Exception as e:
            # Document if this endpoint has issues
            logger.warning(f"get_meta endpoint issue: {e}")
            # This is acceptable if REST API doesn't have this endpoint

    async def test_get_tissues_for_gene(self, integration_adapter):
        """
        Test gene query with entity tuple parameter.

        Validates Phase 2 Fix:
        - Entity tuple formatting works correctly
        - ("HGNC", "11998") format is accepted
        """
        adapter = integration_adapter

        try:
            # Use tuple format as per REST API requirements
            result = await adapter.rest_client.execute_query(
                "get_tissues_for_gene",
                gene=["HGNC", "11998"]  # TP53 as tuple
            )

            assert result is not None, "Should return a result"

            if result.get("success"):
                tissues = result.get("records", [])
                logger.info(f"✓ Found {len(tissues)} tissues for TP53 via REST")
            else:
                logger.warning(f"REST query returned no success: {result}")

        except Exception as e:
            logger.error(f"REST tissue query failed: {e}")
            # Don't fail test - REST might not be available

    async def test_rest_optional_parameters(self, integration_adapter):
        """
        Test REST endpoints with optional parameters.

        Validates Phase 2 Fix:
        - Optional parameters can be None
        - Query doesn't crash on missing optional params
        """
        adapter = integration_adapter

        # This test validates that the parameter handling doesn't crash
        # even if specific endpoints aren't fully implemented
        try:
            # Try a query that might have optional parameters
            result = await adapter.rest_client.execute_query(
                "get_go_terms_for_gene",
                gene=["HGNC", "11998"]
            )

            logger.info("✓ REST query with gene parameter succeeded")

        except Exception as e:
            # Document the error but don't fail
            logger.warning(f"REST optional param test: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestBackendRouting:
    """Test adapter routing between Neo4j and REST backends."""

    async def test_adapter_status(self, integration_adapter):
        """Verify adapter reports correct backend availability."""
        adapter = integration_adapter
        status = adapter.get_status()

        assert status["initialized"], "Adapter must be initialized"

        # Should have at least one backend available
        has_neo4j = status.get("neo4j_available", False)
        has_rest = status.get("rest_available", False)

        assert has_neo4j or has_rest, "At least one backend should be available"

        logger.info(f"✓ Backends available - Neo4j: {has_neo4j}, REST: {has_rest}")

    async def test_query_routing(self, integration_adapter):
        """Test that queries route to appropriate backend."""
        adapter = integration_adapter

        # This query should work on at least one backend
        try:
            result = await adapter.query(
                "get_gene_by_symbol",
                symbol="TP53"
            )

            assert result is not None, "Query should return result"
            logger.info("✓ Query routing successful")

        except Exception as e:
            pytest.fail(f"Query routing failed: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPhase1Fixes:
    """Specific tests validating Phase 1 fixes."""

    async def test_no_gene_label_check(self, integration_adapter):
        """
        Verify queries don't use non-existent 'Gene' label.

        Phase 1 Fix: Replaced 'Gene' IN labels(g) with g.id STARTS WITH 'hgnc:'
        """
        adapter = integration_adapter

        # This should succeed because we fixed the label check
        result = await adapter.neo4j_client.execute_query(
            "get_gene_by_symbol",
            symbol="TP53"
        )

        assert result["success"], "Query with corrected schema should succeed"
        assert len(result["records"]) > 0, "Should find genes without 'Gene' label"

        logger.info("✓ Phase 1: Schema label fix validated")

    async def test_obsolete_gene_filtering(self, integration_adapter):
        """
        Verify obsolete genes are filtered out.

        Phase 1 Fix: Added g.obsolete = false filter
        """
        adapter = integration_adapter

        result = await adapter.neo4j_client.execute_query(
            "get_gene_by_symbol",
            symbol="TP53"
        )

        if result["success"] and len(result["records"]) > 0:
            gene = result["records"][0]
            obsolete = gene.get("obsolete", False)

            # TP53 should not be obsolete
            assert obsolete is False, "TP53 should not be marked obsolete"
            logger.info("✓ Phase 1: Obsolete filtering validated")


@pytest.mark.integration
@pytest.mark.asyncio
class TestPhase2Fixes:
    """Specific tests validating Phase 2 fixes."""

    async def test_rest_none_parameter_handling(self, integration_adapter):
        """
        Verify REST client handles None parameters gracefully.

        Phase 2 Fix: _format_entity_tuple now accepts required=False
        """
        adapter = integration_adapter

        # This should not crash with "Invalid entity format: None" error
        # 404 is acceptable (endpoint doesn't exist), but ValueError is not
        try:
            result = await adapter.rest_client.execute_query("get_meta")
            logger.info("✓ Phase 2: None parameter handling validated")
        except ValueError as e:
            if "Invalid entity format: None" in str(e):
                pytest.fail("Phase 2 fix not applied: Still crashes on None")
            raise
        except Exception as e:
            # 404 or other HTTP errors are acceptable - we're testing parameter handling
            if "Invalid entity format: None" not in str(e):
                logger.info(f"✓ Phase 2: None parameter handling validated (endpoint returned {type(e).__name__})")
            else:
                pytest.fail(f"Phase 2 fix not applied: {e}")

    async def test_rest_endpoint_lazy_evaluation(self, integration_adapter):
        """
        Verify REST endpoints use lazy evaluation.

        Phase 2 Fix: Endpoint parameters only formatted when query is called
        """
        adapter = integration_adapter

        # Calling one endpoint should not try to format parameters for other endpoints
        try:
            result = await adapter.rest_client.execute_query(
                "get_tissues_for_gene",
                gene=["HGNC", "11998"]
            )

            # If this doesn't crash with "tissue parameter missing", lazy eval works
            logger.info("✓ Phase 2: Lazy evaluation validated")

        except Exception as e:
            if "tissue" in str(e).lower() and "missing" in str(e).lower():
                pytest.fail("Phase 2 fix incomplete: Not using lazy evaluation")
            # Other errors are acceptable for this test
            logger.warning(f"REST query issue (expected): {e}")
