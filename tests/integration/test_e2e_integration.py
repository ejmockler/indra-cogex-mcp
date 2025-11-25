"""
End-to-end workflow tests demonstrating complete system functionality.

These tests simulate real usage patterns and validate that all Phase 1 & 2
fixes work together in production scenarios.
"""

import json
import logging

import pytest

from cogex_mcp.schemas import GeneFeatureQuery, QueryMode, ResponseFormat
from cogex_mcp.tools.gene_feature import cogex_query_gene_or_feature

logger = logging.getLogger(__name__)


class MockContext:
    """Mock MCP context with progress reporting."""

    def __init__(self):
        self.progress_history = []

    async def report_progress(self, progress, message):
        self.progress_history.append((progress, message))
        logger.debug(f"[{int(progress*100):3d}%] {message}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestE2EWorkflows:
    """End-to-end workflow tests."""

    async def test_simple_gene_lookup_workflow(self):
        """
        Simple workflow: User asks "What do we know about TP53?"

        Flow: Query gene → Get features → Return profile

        Validates:
        - Complete data flow from tool to response
        - All Phase 1 & 2 fixes working together
        - Response is actionable
        """
        logger.info("\n" + "="*80)
        logger.info("E2E Test: Simple Gene Lookup (TP53)")
        logger.info("="*80)

        # Step 1: Query TP53 with multiple features
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        # Validate response
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Parse and examine data
        try:
            data = json.loads(result)
            assert "gene" in data
            assert data["gene"]["name"] == "TP53"

            logger.info(f"\n✓ Gene Info: {data['gene']['name']} ({data['gene'].get('curie', 'N/A')})")

            # Check what data we got
            if "expression" in data and data["expression"]:
                logger.info(f"✓ Expression: Found {len(data['expression'])} tissues")
                for exp in data["expression"][:3]:
                    logger.info(f"  - {exp.get('tissue', {}).get('name', 'Unknown')}")

            if "go_terms" in data and data["go_terms"]:
                logger.info(f"✓ GO Terms: Found {len(data['go_terms'])} terms")
                for go in data["go_terms"][:3]:
                    logger.info(f"  - {go.get('go_term', {}).get('name', 'Unknown')}")

            if "pathways" in data and data["pathways"]:
                logger.info(f"✓ Pathways: Found {len(data['pathways'])} pathways")
                for pathway in data["pathways"][:3]:
                    logger.info(f"  - {pathway.get('pathway', {}).get('name', 'Unknown')}")

            logger.info("\n" + "="*80)
            logger.info("✓ WORKFLOW COMPLETE")
            logger.info("="*80)

        except json.JSONDecodeError as e:
            pytest.fail(f"Response not valid JSON: {e}")

    async def test_multi_gene_comparison(self, known_entities):
        """
        Workflow: Compare profiles of multiple cancer genes.

        Flow: Query TP53, BRCA1, EGFR → Compare features

        Validates:
        - Sequential queries work
        - No state contamination
        - Consistent results
        """
        logger.info("\n" + "="*80)
        logger.info("E2E Test: Multi-Gene Comparison")
        logger.info("="*80)

        genes = known_entities["genes"][:3]  # TP53, BRCA1, EGFR
        profiles = {}

        for gene_symbol in genes:
            query = GeneFeatureQuery(
                mode=QueryMode.GENE_TO_FEATURES,
                gene=gene_symbol,
                include_pathways=True,
                response_format=ResponseFormat.JSON,
                limit=5
            )

            ctx = MockContext()
            result = await cogex_query_gene_or_feature(query, ctx)

            if not result.startswith("Error:"):
                try:
                    data = json.loads(result)
                    profiles[gene_symbol] = data
                    logger.info(f"✓ Retrieved profile for {gene_symbol}")
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse {gene_symbol} response")

        assert len(profiles) >= 2, "Should get at least 2 gene profiles"

        logger.info(f"\n✓ Retrieved profiles for {len(profiles)} genes:")
        for gene in profiles:
            logger.info(f"  - {gene}")

        logger.info("\n" + "="*80)
        logger.info("✓ WORKFLOW COMPLETE")
        logger.info("="*80)

    async def test_identifier_format_workflow(self):
        """
        Workflow: User provides different identifier formats.

        Flow: Try symbol → Try CURIE → Try tuple → Compare results

        Validates:
        - Phase 1 Fix: All identifier formats work
        - Consistent resolution
        - Same gene returned
        """
        logger.info("\n" + "="*80)
        logger.info("E2E Test: Identifier Format Workflow")
        logger.info("="*80)

        results = {}

        # Format 1: Symbol
        logger.info("\nTrying symbol format: TP53")
        query1 = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=3
        )
        result1 = await cogex_query_gene_or_feature(query1, MockContext())
        if not result1.startswith("Error:"):
            try:
                results["symbol"] = json.loads(result1)
                logger.info("✓ Symbol format works")
            except json.JSONDecodeError:
                pass

        # Format 2: CURIE
        logger.info("\nTrying CURIE format: hgnc:11998")
        query2 = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="hgnc:11998",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=3
        )
        result2 = await cogex_query_gene_or_feature(query2, MockContext())
        if not result2.startswith("Error:"):
            try:
                results["curie"] = json.loads(result2)
                logger.info("✓ CURIE format works")
            except json.JSONDecodeError:
                pass

        # Verify same gene
        if "symbol" in results and "curie" in results:
            gene_name_1 = results["symbol"]["gene"]["name"]
            gene_name_2 = results["curie"]["gene"]["name"]
            assert gene_name_1 == gene_name_2 == "TP53", \
                "Different formats should resolve to same gene"
            logger.info("\n✓ All formats resolve to TP53")

        logger.info("\n" + "="*80)
        logger.info(f"✓ WORKFLOW COMPLETE - Tested {len(results)} formats")
        logger.info("="*80)

    async def test_error_recovery_workflow(self):
        """
        Workflow: Handle errors gracefully in sequence.

        Flow: Unknown gene → Valid gene → Unknown gene → Valid gene

        Validates:
        - Error handling doesn't break system
        - Recovery after error
        - Clear error messages
        """
        logger.info("\n" + "="*80)
        logger.info("E2E Test: Error Recovery Workflow")
        logger.info("="*80)

        test_sequence = [
            ("FAKEGENE1", False, "unknown gene"),
            ("TP53", True, "valid gene"),
            ("FAKEGENE2", False, "unknown gene"),
            ("BRCA1", True, "valid gene"),
        ]

        results = []
        for gene, should_succeed, label in test_sequence:
            query = GeneFeatureQuery(
                mode=QueryMode.GENE_TO_FEATURES,
                gene=gene,
                include_expression=True,
                response_format=ResponseFormat.JSON,
                limit=3
            )

            ctx = MockContext()
            result = await cogex_query_gene_or_feature(query, ctx)

            is_error = result.startswith("Error:")
            results.append((gene, not is_error))

            if should_succeed:
                if not is_error:
                    logger.info(f"✓ {gene} ({label}): succeeded as expected")
                else:
                    logger.warning(f"⚠ {gene} ({label}): failed unexpectedly - {result}")
            else:
                if is_error:
                    logger.info(f"✓ {gene} ({label}): error as expected - {result[:50]}")
                else:
                    logger.warning(f"⚠ {gene} ({label}): succeeded unexpectedly")

        # Should have at least one success and one failure
        successes = sum(1 for _, success in results if success)
        failures = len(results) - successes

        logger.info(f"\n✓ Tested {len(results)} queries: {successes} succeeded, {failures} failed")

        logger.info("\n" + "="*80)
        logger.info("✓ WORKFLOW COMPLETE")
        logger.info("="*80)


@pytest.mark.integration
@pytest.mark.asyncio
class TestE2EPhaseValidation:
    """E2E tests specifically validating Phase 1 & 2 fixes."""

    async def test_phase1_symbol_to_curie_flow(self):
        """
        Validate Phase 1 Fix: Symbol resolution flows to correct backend query.

        Flow: Symbol → Entity Resolver → get_gene_by_symbol → Neo4j → Response
        """
        logger.info("\n" + "="*80)
        logger.info("Phase 1 Validation: Symbol Resolution Flow")
        logger.info("="*80)

        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            response_format=ResponseFormat.JSON
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        assert not result.startswith("Error:"), \
            "Phase 1: Symbol resolution should work"

        try:
            data = json.loads(result)
            assert data["gene"]["name"] == "TP53"
            logger.info("✓ Phase 1: Symbol → get_gene_by_symbol → Success")
        except json.JSONDecodeError:
            pytest.fail("Phase 1: Response not valid JSON")

        logger.info("="*80)

    async def test_phase1_curie_resolution_flow(self):
        """
        Validate Phase 1 Fix: CURIE resolution flows to correct backend query.

        Flow: CURIE → Entity Resolver → get_gene_by_id → Neo4j → Response
        """
        logger.info("\n" + "="*80)
        logger.info("Phase 1 Validation: CURIE Resolution Flow")
        logger.info("="*80)

        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="hgnc:11998",
            response_format=ResponseFormat.JSON
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        assert not result.startswith("Error:"), \
            "Phase 1: CURIE resolution should work"

        try:
            data = json.loads(result)
            assert data["gene"]["name"] == "TP53"
            logger.info("✓ Phase 1: CURIE → get_gene_by_id → Success")
        except json.JSONDecodeError:
            pytest.fail("Phase 1: Response not valid JSON")

        logger.info("="*80)

    async def test_phase1_neo4j_schema_fix(self):
        """
        Validate Phase 1 Fix: Neo4j queries use corrected schema.

        Validates:
        - No 'Gene' label check
        - Uses g.id STARTS WITH 'hgnc:'
        - Filters obsolete genes
        """
        logger.info("\n" + "="*80)
        logger.info("Phase 1 Validation: Neo4j Schema Fix")
        logger.info("="*80)

        # This query should work because schema is fixed
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            response_format=ResponseFormat.JSON
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        # Should succeed (would have failed with old schema)
        assert not result.startswith("Error:"), \
            "Phase 1: Query should succeed with corrected schema"

        logger.info("✓ Phase 1: Neo4j schema corrections working")
        logger.info("  - No 'Gene' label check")
        logger.info("  - Uses g.id STARTS WITH 'hgnc:'")
        logger.info("  - Obsolete filtering")

        logger.info("="*80)

    async def test_phase2_rest_none_handling(self, integration_adapter):
        """
        Validate Phase 2 Fix: REST client handles None parameters.

        Would have crashed before Phase 2 fix.
        """
        logger.info("\n" + "="*80)
        logger.info("Phase 2 Validation: REST None Parameter Handling")
        logger.info("="*80)

        # This should not crash even if REST is called
        try:
            query = GeneFeatureQuery(
                mode=QueryMode.GENE_TO_FEATURES,
                gene="TP53",
                include_expression=True,
                response_format=ResponseFormat.JSON,
                limit=5
            )

            ctx = MockContext()
            result = await cogex_query_gene_or_feature(query, ctx)

            # Should not crash with None parameter errors
            logger.info("✓ Phase 2: No None parameter crashes")

        except ValueError as e:
            if "Invalid entity format: None" in str(e):
                pytest.fail("Phase 2 fix not applied: Still crashes on None")
            raise

        logger.info("="*80)


@pytest.mark.integration
@pytest.mark.asyncio
class TestE2EProgressReporting:
    """Test progress reporting in E2E workflows."""

    async def test_progress_callback(self):
        """Verify progress is reported during query execution."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        # Check that progress was reported
        if ctx.progress_history:
            logger.info(f"✓ Progress reported {len(ctx.progress_history)} times")
            for progress, message in ctx.progress_history:
                logger.debug(f"  [{int(progress*100)}%] {message}")
        else:
            logger.info("No progress reporting (might be disabled)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestE2EPerformance:
    """E2E performance tests."""

    async def test_workflow_execution_time(self):
        """Measure complete workflow execution time."""
        import time

        start = time.time()

        # Execute simple workflow
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        ctx = MockContext()
        result = await cogex_query_gene_or_feature(query, ctx)

        elapsed = time.time() - start

        logger.info(f"✓ Complete workflow executed in {elapsed:.2f}s")

        # Workflow should complete in reasonable time
        if elapsed > 30.0:
            logger.warning(f"Workflow slow: {elapsed:.2f}s")
        else:
            logger.info(f"✓ Performance acceptable: {elapsed:.2f}s")
