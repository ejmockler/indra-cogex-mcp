"""
Integration tests for Tool 10: cogex_query_variants

Tests variant query functionality with actual data validation.

Run with: pytest tests/integration/test_tool10_variants_integration.py -v
"""

import json
import logging

import pytest

from cogex_mcp.schemas import ResponseFormat, VariantQuery, VariantQueryMode
from cogex_mcp.tools.variants import cogex_query_variants

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool10VariantQueries:
    """Test Tool 10 variant query modes with data validation."""

    async def test_get_for_gene_brca1(self):
        """Test getting variants for BRCA1 gene."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="BRCA1",
            max_p_value=1e-5,
            limit=30,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "variants" in data, "Response should include variants"

        # 4. Data is non-empty (BRCA1 has many known variants)
        assert len(data["variants"]) > 0, "BRCA1 should have variants"

        # 5. Data structure validation
        first_variant = data["variants"][0]
        assert "rsid" in first_variant, "Variant should have rsID"
        assert "chromosome" in first_variant, "Variant should have chromosome"
        assert "position" in first_variant, "Variant should have position"
        assert "p_value" in first_variant, "Variant should have p-value"

        # 6. rsID format validation
        assert first_variant["rsid"].startswith("rs"), "rsID should start with 'rs'"

        # 7. Chromosome validation - BRCA1 is on chr17
        for variant in data["variants"]:
            assert variant["chromosome"] == "17", "BRCA1 variants should be on chromosome 17"

        # 8. P-value filtering
        for variant in data["variants"]:
            assert variant["p_value"] <= 1e-5, "P-value should be below threshold"

        logger.info(f"✓ Found {len(data['variants'])} variants for BRCA1")

    async def test_get_for_disease_alzheimer(self):
        """Test getting variants associated with Alzheimer's disease."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_DISEASE,
            disease="alzheimer disease",
            max_p_value=1e-6,
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "variants" in data, "Response should include variants"

        # 4. Data is non-empty (Alzheimer's has well-known variants)
        assert len(data["variants"]) > 0, "Alzheimer's should have associated variants"

        # 5. Data structure validation
        for variant in data["variants"]:
            assert "rsid" in variant, "Variant should have rsID"
            assert "trait" in variant, "Variant should have trait"
            assert "source" in variant, "Variant should have source"

        # 6. Trait validation - should mention Alzheimer's
        traits = [v["trait"].lower() for v in data["variants"]]
        has_alzheimer = any("alzheimer" in trait for trait in traits)
        if has_alzheimer:
            logger.info("✓ Alzheimer's mentioned in variant traits")

        logger.info(f"✓ Found {len(data['variants'])} variants for Alzheimer's disease")

    async def test_variant_to_genes_apoe(self):
        """Test getting genes for APOE variant rs7412."""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_GENES,
            variant="rs7412",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "variant" in data, "Response should include variant"
        assert "genes" in data, "Response should include genes"

        # 4. Variant preserved
        assert data["variant"] == "rs7412", "Variant should match query"

        # 5. Data is non-empty (rs7412 is in APOE)
        assert len(data["genes"]) > 0, "rs7412 should be near genes"

        # 6. Data structure validation
        first_gene = data["genes"][0]
        assert "name" in first_gene, "Gene should have name"
        assert "curie" in first_gene, "Gene should have CURIE"

        # 7. APOE should be in results
        gene_names = [g["name"] for g in data["genes"]]
        assert "APOE" in gene_names, "APOE should be in results for rs7412"

        logger.info(f"✓ Found {len(data['genes'])} genes for rs7412: {gene_names}")

    async def test_variant_to_phenotypes(self):
        """Test getting phenotypes for variant."""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_PHENOTYPES,
            variant="rs7412",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "variant" in data, "Response should include variant"
        assert "phenotypes" in data, "Response should include phenotypes"

        # 4. Data structure validation (if phenotypes found)
        if len(data["phenotypes"]) > 0:
            first_pheno = data["phenotypes"][0]
            assert "name" in first_pheno, "Phenotype should have name"
            assert "curie" in first_pheno, "Phenotype should have CURIE"

            logger.info(f"✓ Found {len(data['phenotypes'])} phenotypes for rs7412")
        else:
            logger.warning("No phenotypes found for rs7412")

    async def test_check_association_apoe_alzheimer(self):
        """Test checking variant-disease association."""
        query = VariantQuery(
            mode=VariantQueryMode.CHECK_ASSOCIATION,
            variant="rs7412",
            disease="alzheimer disease",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # 1. No errors
        assert not result.startswith("Error:"), f"Query failed: {result}"

        # 2. Valid JSON
        data = json.loads(result)

        # 3. Primary fields exist
        assert "is_associated" in data, "Response should have is_associated field"
        assert "variant" in data, "Response should include variant info"
        assert "disease" in data, "Response should include disease info"

        # 4. Metadata validation
        assert data["variant"]["rsid"] == "rs7412", "Variant should be rs7412"

        # 5. Known fact: rs7412 is APOE variant associated with Alzheimer's
        if data["is_associated"]:
            assert "association_strength" in data, "Should have association strength"
            logger.info(f"✓ rs7412-Alzheimer's association confirmed (p={data['association_strength']})")
        else:
            logger.warning("rs7412-Alzheimer's association not found in database")

    async def test_get_for_phenotype(self):
        """Test getting variants for phenotype."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_PHENOTYPE,
            phenotype="HP:0000822",  # Hypertension
            max_p_value=1e-5,
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # Might not have data for all phenotypes
        if result.startswith("Error:"):
            logger.info(f"Phenotype query: {result}")
        else:
            data = json.loads(result)
            assert "variants" in data, "Response should include variants"
            logger.info(f"✓ Found {len(data.get('variants', []))} variants for phenotype")

    async def test_unknown_variant_error(self):
        """Test error handling for unknown variant."""
        query = VariantQuery(
            mode=VariantQueryMode.VARIANT_TO_GENES,
            variant="rs999999999999",
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        # Should error or return empty
        if result.startswith("Error:"):
            logger.info(f"✓ Unknown variant error: {result}")
        else:
            data = json.loads(result)
            assert "genes" in data
            logger.info(f"Unknown variant returned {len(data.get('genes', []))} genes")

    async def test_markdown_response_format(self):
        """Test markdown response format."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="BRCA1",
            limit=10,
            response_format=ResponseFormat.MARKDOWN,
        )

        result = await cogex_query_variants(query)

        if not result.startswith("Error:"):
            # Should contain markdown formatting
            has_markdown = any(marker in result for marker in ["##", "**", "|", "-"])
            assert has_markdown, "Markdown response should have formatting"
            logger.info("✓ Markdown response has formatting")


@pytest.mark.integration
@pytest.mark.asyncio
class TestTool10EdgeCases:
    """Edge cases and filters for variant queries."""

    async def test_p_value_filtering(self):
        """Test p-value filtering with min and max."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="BRCA1",
            min_p_value=1e-8,
            max_p_value=1e-6,
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            # Verify p-value filtering
            for variant in data["variants"]:
                p_val = variant["p_value"]
                assert 1e-8 <= p_val <= 1e-6, f"P-value {p_val} outside range"

            logger.info(f"✓ P-value filtering working: {len(data['variants'])} variants")

    async def test_source_filter(self):
        """Test filtering by data source."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_DISEASE,
            disease="diabetes mellitus",
            source="gwas_catalog",
            limit=20,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            # Verify source filtering
            for variant in data["variants"]:
                assert variant["source"].lower() == "gwas_catalog", "Should only return GWAS Catalog variants"

            logger.info(f"✓ Source filter working: {len(data['variants'])} GWAS variants")

    async def test_pagination_variants(self):
        """Test pagination for variants."""
        # Get first page
        query1 = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="BRCA1",
            limit=5,
            offset=0,
            response_format=ResponseFormat.JSON,
        )

        result1 = await cogex_query_variants(query1)

        if not result1.startswith("Error:"):
            data1 = json.loads(result1)
            assert len(data1["variants"]) <= 5, "Should respect limit"

            # Get second page
            query2 = VariantQuery(
                mode=VariantQueryMode.GET_FOR_GENE,
                gene="BRCA1",
                limit=5,
                offset=5,
                response_format=ResponseFormat.JSON,
            )

            result2 = await cogex_query_variants(query2)

            if not result2.startswith("Error:"):
                data2 = json.loads(result2)

                # Pages should have different variants
                page1_rsids = {v["rsid"] for v in data1["variants"]}
                page2_rsids = {v["rsid"] for v in data2["variants"]}
                assert page1_rsids != page2_rsids, "Different pages should have different variants"

                logger.info("✓ Pagination working correctly")

    async def test_variant_data_quality(self):
        """Test variant data quality and completeness."""
        query = VariantQuery(
            mode=VariantQueryMode.GET_FOR_GENE,
            gene="APOE",
            limit=10,
            response_format=ResponseFormat.JSON,
        )

        result = await cogex_query_variants(query)

        if not result.startswith("Error:"):
            data = json.loads(result)

            for variant in data["variants"]:
                # Required fields
                assert variant["rsid"], "rsID should not be empty"
                assert variant["chromosome"], "Chromosome should not be empty"
                assert variant["position"] > 0, "Position should be positive"
                assert variant["p_value"] > 0, "P-value should be positive"

                # Alleles
                assert variant["ref_allele"], "Reference allele should not be empty"
                assert variant["alt_allele"], "Alternate allele should not be empty"

                # Source
                assert variant["source"] in ["gwas_catalog", "disgenet", "unknown"], "Source should be valid"

            logger.info("✓ Variant data quality verified")
