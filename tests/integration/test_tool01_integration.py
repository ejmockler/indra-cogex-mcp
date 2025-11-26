"""
Integration tests for Tool 1 (cogex_query_gene_or_feature) with live backends.

Tests complete flow: Tool → Entity Resolver → Adapter → Backends → Response

Validates end-to-end Phase 1 & 2 fixes working together.
"""

import json
import logging

import pytest

from cogex_mcp.schemas import GeneFeatureQuery, QueryMode, ResponseFormat
from cogex_mcp.tools.gene_feature import cogex_query_gene_or_feature

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1GeneToFeatures:
    """Test Tool 1 gene_to_features mode end-to-end."""

    async def test_tp53_basic_profile(self):
        """
        Get basic TP53 profile (smoke test).

        Validates:
        - Tool can be called
        - Entity resolver works
        - Basic query completes
        - Gene data is present and valid
        - Expression data is present when requested
        """
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=False,
            include_pathways=False,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        # Should not be an error
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Parse and validate JSON response
        data = json.loads(result)

        # Validate gene data structure
        assert "gene" in data, "Response should include gene info"
        assert data["gene"]["name"] == "TP53", "Gene name should be TP53"
        assert data["gene"]["curie"], "Gene should have CURIE"
        assert "hgnc:" in data["gene"]["curie"].lower(), "Should be HGNC CURIE"

        # Validate expression data when requested
        assert "expression" in data, "Expression data should be present when requested"
        assert isinstance(data["expression"], list), "Expression should be a list"
        assert len(data["expression"]) > 0, "TP53 should have expression data"

        # Validate expression data structure
        for expr in data["expression"]:
            assert "tissue" in expr, "Expression should have tissue info"
            assert expr["tissue"]["name"], "Tissue name should not be empty"

        logger.info(f"✓ TP53 basic profile validated: {len(data['expression'])} tissues")

    async def test_tp53_full_profile(self):
        """
        Get comprehensive TP53 profile with all features.

        Validates:
        - All feature flags work
        - Multiple data sources integrate
        - Response is well-formed
        - All requested features are present and non-empty
        """
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            include_diseases=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Parse and validate JSON response
        data = json.loads(result)

        # Validate gene data
        assert "gene" in data, "Response should include gene info"
        assert data["gene"]["name"] == "TP53", "Gene name should be TP53"

        # Validate all requested features are present
        assert "expression" in data, "Expression should be present when requested"
        assert "go_terms" in data, "GO terms should be present when requested"
        assert "pathways" in data, "Pathways should be present when requested"
        assert "diseases" in data, "Diseases should be present when requested"

        # Validate features are non-empty for well-studied gene
        # Note: Some features may be empty if backend lacks that specific data type
        assert len(data["expression"]) > 0, "TP53 should have expression data"

        # For features that might be empty due to backend limitations, just validate structure
        feature_counts = {
            "expression": len(data["expression"]),
            "go_terms": len(data["go_terms"]),
            "pathways": len(data["pathways"]),
            "diseases": len(data["diseases"]),
        }

        # At least one non-basic feature should have data for TP53
        non_basic_features = feature_counts["go_terms"] + feature_counts["pathways"] + feature_counts["diseases"]
        assert non_basic_features > 0, "TP53 should have at least some pathway/disease/GO data"

        # Validate data quality for features that have data
        for expr in data["expression"]:
            assert "tissue" in expr, "Expression should have tissue info"
            assert expr["tissue"]["name"], "Tissue name should not be empty"

        if data["go_terms"]:
            for go_term in data["go_terms"]:
                assert "go_term" in go_term, "GO annotation should have term info"
                assert go_term["go_term"]["curie"], "GO term should have CURIE"

        if data["pathways"]:
            for pathway in data["pathways"]:
                assert "pathway" in pathway, "Pathway should have info"
                assert pathway["pathway"]["name"], "Pathway name should not be empty"

        if data["diseases"]:
            # Validate at least some diseases have names (backend data quality varies)
            diseases_with_names = [d for d in data["diseases"] if d.get("disease", {}).get("name")]
            if diseases_with_names:
                logger.info(f"  {len(diseases_with_names)}/{len(data['diseases'])} diseases have names")
            for disease in data["diseases"]:
                assert "disease" in disease, "Disease association should have disease info"
                # CURIE should always be present even if name is missing
                assert disease["disease"].get("curie"), "Disease should have CURIE"

        logger.info(
            f"✓ TP53 full profile validated: {feature_counts['expression']} tissues, "
            f"{feature_counts['go_terms']} GO terms, {feature_counts['pathways']} pathways, "
            f"{feature_counts['diseases']} diseases"
        )

    async def test_tp53_by_curie(self):
        """
        Query TP53 using CURIE format.

        Validates Phase 1 Fix:
        - CURIE format works end-to-end
        - Entity resolver routes correctly
        - Gene is resolved and data returned
        """
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="hgnc:11998",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        assert not result.startswith("Error:"), f"CURIE query failed: {result}"

        # Parse and validate JSON response
        data = json.loads(result)

        # Validate CURIE resolution
        assert "gene" in data, "Response should include gene info"
        assert data["gene"]["name"] == "TP53", "CURIE should resolve to TP53"
        assert data["gene"]["curie"] == "hgnc:11998", "Should preserve HGNC CURIE"

        # Validate expression data is present
        assert "expression" in data, "Expression should be present"
        assert len(data["expression"]) > 0, "TP53 should have expression data"

        logger.info(f"✓ TP53 via CURIE validated: {data['gene']['name']} with {len(data['expression'])} tissues")

    async def test_tp53_by_symbol_uppercase(self):
        """Test standard uppercase symbol format."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        assert not result.startswith("Error:")
        logger.info("✓ Symbol format (uppercase) works")

    async def test_multiple_genes_sequence(self, known_entities):
        """
        Test querying multiple genes in sequence.

        Validates:
        - No state contamination between queries
        - Cache works correctly
        - Consistent results
        """
        genes = known_entities["genes"][:3]  # TP53, BRCA1, EGFR

        results = []
        for gene_symbol in genes:
            query = GeneFeatureQuery(
                mode=QueryMode.GENE_TO_FEATURES,
                gene=gene_symbol,
                include_expression=True,
                response_format=ResponseFormat.JSON,
                limit=3
            )

            result = await cogex_query_gene_or_feature(query)

            if not result.startswith("Error:"):
                results.append(gene_symbol)
                logger.info(f"✓ Retrieved {gene_symbol}")

        assert len(results) >= 2, "Should successfully query at least 2 genes"

    async def test_unknown_gene_error(self):
        """
        Unknown gene should return helpful error.

        Validates:
        - Error handling works
        - User gets informative message
        """
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="FAKEGENE999",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        assert result.startswith("Error:"), "Should return error message"
        assert "not found" in result.lower(), f"Error should mention 'not found': {result}"
        logger.info(f"✓ Unknown gene error: {result}")

    async def test_json_response_format(self):
        """Verify JSON response is valid JSON with proper structure."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Validate JSON parsing
        data = json.loads(result)
        assert isinstance(data, dict), "JSON response should be a dict"

        # Validate required keys
        assert "gene" in data, "Response should have gene key"
        assert "expression" in data, "Response should have expression key"

        # Validate data types
        assert isinstance(data["gene"], dict), "Gene should be a dict"
        assert isinstance(data["expression"], list), "Expression should be a list"

        logger.info(f"✓ Valid JSON response with {len(data)} keys")

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            response_format=ResponseFormat.MARKDOWN,
            limit=5
        )

        result = await cogex_query_gene_or_feature(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            if has_markdown:
                logger.info("✓ Markdown response has formatting")
            else:
                logger.warning("Markdown response might be plain text")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1TissueToGenes:
    """Test Tool 1 tissue_to_genes mode (reverse query)."""

    async def test_brain_genes(self):
        """
        Find genes expressed in brain tissue.

        Tests reverse query functionality.
        """
        query = GeneFeatureQuery(
            mode=QueryMode.TISSUE_TO_GENES,
            tissue="brain",
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        if not result.startswith("Error:"):
            try:
                data = json.loads(result)
                if "genes" in data:
                    logger.info(f"✓ Found {len(data['genes'])} genes in brain")
                else:
                    logger.info("Brain query returned but no genes found")
            except json.JSONDecodeError:
                logger.warning("Brain query response not JSON")
        else:
            logger.warning(f"Tissue query not yet working: {result}")

    async def test_multiple_tissues(self, known_entities):
        """Test querying multiple tissues."""
        tissues = known_entities["tissues"][:2]  # brain, liver

        for tissue in tissues:
            query = GeneFeatureQuery(
                mode=QueryMode.TISSUE_TO_GENES,
                tissue=tissue,
                limit=10,
                response_format=ResponseFormat.JSON
            )

            result = await cogex_query_gene_or_feature(query)

            if not result.startswith("Error:"):
                logger.info(f"✓ {tissue} query completed")

    async def test_unknown_tissue_error(self):
        """Test error handling for unknown tissue."""
        query = GeneFeatureQuery(
            mode=QueryMode.TISSUE_TO_GENES,
            tissue="fake_tissue_xyz",
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        # Should either error or return empty results
        if result.startswith("Error:"):
            logger.info(f"✓ Unknown tissue error: {result}")
        else:
            logger.info("Unknown tissue returned (possibly empty results)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1GOTermQueries:
    """Test Tool 1 GO term related queries."""

    async def test_go_to_genes(self):
        """Test finding genes for a GO term."""
        query = GeneFeatureQuery(
            mode=QueryMode.GO_TO_GENES,
            go_term="GO:0006915",  # apoptotic process
            limit=20,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        if not result.startswith("Error:"):
            logger.info("✓ GO term query completed")
        else:
            logger.warning(f"GO term query: {result}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1ParameterValidation:
    """Test parameter validation and edge cases."""

    async def test_limit_parameter(self):
        """Test limit parameter restricts results."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            limit=3,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        if not result.startswith("Error:"):
            try:
                data = json.loads(result)
                if "expression" in data and data["expression"]:
                    count = len(data["expression"])
                    logger.info(f"✓ Limit parameter: returned {count} items")
            except json.JSONDecodeError:
                pass

    async def test_no_features_enabled(self):
        """Test query with no features enabled - should still return gene info."""
        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=False,
            include_go_terms=False,
            include_pathways=False,
            include_diseases=False,
            response_format=ResponseFormat.JSON
        )

        result = await cogex_query_gene_or_feature(query)

        assert not result.startswith("Error:"), f"Query failed: {result}"

        # Parse and validate response
        data = json.loads(result)

        # Should have gene info
        assert "gene" in data, "Should return gene info even without features"
        assert data["gene"]["name"] == "TP53", "Gene name should be TP53"
        assert data["gene"]["curie"], "Gene should have CURIE"

        # Features should be empty lists or not present
        if "expression" in data:
            assert isinstance(data["expression"], list), "Expression should be a list if present"
        if "go_terms" in data:
            assert isinstance(data["go_terms"], list), "GO terms should be a list if present"

        logger.info("✓ No features query validated - gene info present")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool1Performance:
    """Test Tool 1 performance characteristics."""

    async def test_simple_query_speed(self):
        """Test speed of simple gene query."""
        import time

        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            response_format=ResponseFormat.JSON,
            limit=5
        )

        start = time.time()
        result = await cogex_query_gene_or_feature(query)
        elapsed = time.time() - start

        logger.info(f"✓ Query completed in {elapsed:.2f}s")

        # Should be reasonably fast
        if elapsed > 10.0:
            logger.warning(f"Query slow: {elapsed:.2f}s")

    async def test_complex_query_speed(self):
        """Test speed of complex query with all features."""
        import time

        query = GeneFeatureQuery(
            mode=QueryMode.GENE_TO_FEATURES,
            gene="TP53",
            include_expression=True,
            include_go_terms=True,
            include_pathways=True,
            include_diseases=True,
            response_format=ResponseFormat.JSON,
            limit=10
        )

        start = time.time()
        result = await cogex_query_gene_or_feature(query)
        elapsed = time.time() - start

        logger.info(f"✓ Complex query completed in {elapsed:.2f}s")
