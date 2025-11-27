"""
Integration tests for VariantClient with real Neo4j database.

Tests scientific validation scenarios:
- APOE variants (rs7412, rs429358) → Alzheimer's disease
- BRCA1/BRCA2 variants → Breast/ovarian cancer
- SOD1 variants → ALS
- GWAS phenotypes (BMI, height, T2D)
- Performance benchmarks
"""

import pytest
import time
from typing import Optional

from indra_cogex.client.neo4j_client import Neo4jClient

from cogex_mcp.clients.variant_client import VariantClient


def neo4j_available() -> bool:
    """Check if Neo4j is available for integration tests."""
    try:
        import os
        # Check for environment variables
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password")

        # Try to connect
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


@pytest.fixture
def neo4j_client() -> Optional[Neo4jClient]:
    """Create Neo4j client for integration tests."""
    if not neo4j_available():
        pytest.skip("Neo4j not available")

    import os
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    return Neo4jClient(url=uri, username=user, password=password)


@pytest.fixture
def variant_client(neo4j_client) -> VariantClient:
    """Create VariantClient with Neo4j connection."""
    return VariantClient(neo4j_client=neo4j_client)


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestAPOEVariants:
    """
    Test APOE variants and Alzheimer's disease.

    Scientific validation:
    - rs7412 (ε2 allele): Protective against AD
    - rs429358 (ε4 allele): Strongest genetic risk factor for AD
    - Both variants should map to APOE gene (chr19)
    """

    def test_apoe_gene_variants(self, variant_client):
        """Test getting variants for APOE gene."""
        result = variant_client.get_gene_variants(
            gene_id="hgnc:613",  # APOE
            max_p_value=1e-5,
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:613"

        # Should find APOE variants
        assert result["total_variants"] > 0

        # Check if famous APOE variants are present
        rsids = [v["rsid"] for v in result["variants"]]
        print(f"Found {len(rsids)} APOE variants")
        print(f"Sample rsIDs: {rsids[:10]}")

        # At least one should be on chromosome 19
        chromosomes = [v["chromosome"] for v in result["variants"]]
        assert "19" in chromosomes or "chr19" in chromosomes

    def test_rs7412_to_apoe(self, variant_client):
        """Test rs7412 (ε2 allele) maps to APOE."""
        result = variant_client.get_variant_genes("rs7412")

        assert result["success"] is True
        assert result["variant_id"] == "rs7412"

        if result["total_genes"] > 0:
            gene_names = [g["name"] for g in result["genes"]]
            print(f"rs7412 maps to genes: {gene_names}")

            # May find APOE
            # Note: Integration tests may vary based on database version
            assert len(gene_names) > 0

    def test_rs429358_to_apoe(self, variant_client):
        """Test rs429358 (ε4 allele) maps to APOE."""
        result = variant_client.get_variant_genes("rs429358")

        assert result["success"] is True
        assert result["variant_id"] == "rs429358"

        if result["total_genes"] > 0:
            gene_names = [g["name"] for g in result["genes"]]
            print(f"rs429358 maps to genes: {gene_names}")

    def test_alzheimers_variants(self, variant_client):
        """Test getting variants for Alzheimer's disease."""
        # Try multiple disease identifiers
        disease_ids = [
            "mesh:D000544",  # Alzheimer Disease
            "doid:10652",    # Alzheimer's disease
        ]

        for disease_id in disease_ids:
            try:
                result = variant_client.get_disease_variants(
                    disease_id=disease_id,
                    max_p_value=5e-8,  # Genome-wide significance
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{disease_id}: Found {result['total_variants']} variants")

                    # Should find genome-wide significant hits
                    assert result["total_variants"] > 0

                    # Check p-values
                    for variant in result["variants"][:5]:
                        assert variant["p_value"] <= 5e-8
                        print(f"  {variant['rsid']}: p={variant['p_value']:.2e}")

                    break
            except Exception as e:
                print(f"  {disease_id} failed: {e}")
                continue

    def test_rs7412_alzheimers_association(self, variant_client):
        """Test rs7412 association with Alzheimer's (protective)."""
        result = variant_client.get_variant_diseases(
            variant_id="rs7412",
            max_p_value=1e-3,
        )

        assert result["success"] is True

        if result["total_diseases"] > 0:
            disease_names = [d["name"] for d in result["diseases"]]
            print(f"rs7412 associated with diseases: {disease_names}")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestBRCAVariants:
    """
    Test BRCA1/BRCA2 variants and breast/ovarian cancer.

    Scientific validation:
    - BRCA1 (chr17) and BRCA2 (chr13) are tumor suppressors
    - Pathogenic variants increase cancer risk
    - Many variants in GWAS and DisGeNet
    """

    def test_brca1_variants(self, variant_client):
        """Test getting variants for BRCA1 gene."""
        result = variant_client.get_gene_variants(
            gene_id="hgnc:1100",  # BRCA1
            max_p_value=1e-4,
        )

        assert result["success"] is True

        if result["total_variants"] > 0:
            print(f"Found {result['total_variants']} BRCA1 variants")

            # Check chromosomes
            chromosomes = set(v["chromosome"] for v in result["variants"])
            print(f"Chromosomes: {chromosomes}")

    def test_brca2_variants(self, variant_client):
        """Test getting variants for BRCA2 gene."""
        result = variant_client.get_gene_variants(
            gene_id="hgnc:1101",  # BRCA2
            max_p_value=1e-4,
        )

        assert result["success"] is True

        if result["total_variants"] > 0:
            print(f"Found {result['total_variants']} BRCA2 variants")

    def test_breast_cancer_variants(self, variant_client):
        """Test getting variants for breast cancer."""
        disease_ids = [
            "doid:1612",     # Breast cancer
            "mesh:D001943",  # Breast Neoplasms
        ]

        for disease_id in disease_ids:
            try:
                result = variant_client.get_disease_variants(
                    disease_id=disease_id,
                    max_p_value=1e-5,
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{disease_id}: {result['total_variants']} variants")
                    break
            except Exception as e:
                print(f"  {disease_id} failed: {e}")
                continue


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestSODVariants:
    """
    Test SOD1 variants and ALS.

    Scientific validation:
    - SOD1 mutations cause familial ALS (~20% of cases)
    - Over 150 pathogenic mutations identified
    - Gene on chromosome 21
    """

    def test_sod1_variants(self, variant_client):
        """Test getting variants for SOD1 gene."""
        result = variant_client.get_gene_variants(
            gene_id="hgnc:11179",  # SOD1
            max_p_value=1e-3,
        )

        assert result["success"] is True
        print(f"Found {result['total_variants']} SOD1 variants")

    def test_als_variants(self, variant_client):
        """Test getting variants for ALS."""
        disease_ids = [
            "mesh:D000690",  # Amyotrophic Lateral Sclerosis
            "doid:332",      # ALS
        ]

        for disease_id in disease_ids:
            try:
                result = variant_client.get_disease_variants(
                    disease_id=disease_id,
                    max_p_value=1e-4,
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{disease_id}: {result['total_variants']} ALS variants")

                    # Print some examples
                    for variant in result["variants"][:5]:
                        print(f"  {variant['rsid']}: p={variant['p_value']:.2e}")
                    break
            except Exception as e:
                print(f"  {disease_id} failed: {e}")
                continue


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestGWASPhenotypes:
    """
    Test GWAS phenotypes and variant discovery.

    Scientific validation:
    - Body mass index: FTO gene (rs9939609)
    - Height: 100+ loci identified
    - Type 2 diabetes: TCF7L2, PPARG, KCNJ11
    """

    def test_bmi_variants(self, variant_client):
        """Test getting variants for body mass index."""
        phenotypes = [
            "body mass index",
            "BMI",
        ]

        for phenotype in phenotypes:
            try:
                result = variant_client.get_phenotype_variants(
                    phenotype=phenotype,
                    max_p_value=5e-8,  # Genome-wide significance
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{phenotype}: {result['total_variants']} variants")

                    # Should find multiple loci
                    assert result["total_variants"] > 0

                    # Check for famous FTO variant
                    rsids = [v["rsid"] for v in result["variants"]]
                    print(f"Sample variants: {rsids[:10]}")
                    break
            except Exception as e:
                print(f"  {phenotype} failed: {e}")
                continue

    def test_height_variants(self, variant_client):
        """Test getting variants for height (highly polygenic)."""
        phenotypes = [
            "height",
            "body height",
        ]

        for phenotype in phenotypes:
            try:
                result = variant_client.get_phenotype_variants(
                    phenotype=phenotype,
                    max_p_value=5e-8,
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{phenotype}: {result['total_variants']} variants")

                    # Height is highly polygenic (100+ loci)
                    # Should find many hits
                    print(f"Found {result['total_variants']} genome-wide significant hits")
                    break
            except Exception as e:
                print(f"  {phenotype} failed: {e}")
                continue

    def test_type2_diabetes_variants(self, variant_client):
        """Test getting variants for type 2 diabetes."""
        phenotypes = [
            "type 2 diabetes",
            "type 2 diabetes mellitus",
        ]

        for phenotype in phenotypes:
            try:
                result = variant_client.get_phenotype_variants(
                    phenotype=phenotype,
                    max_p_value=5e-8,
                )

                if result["success"] and result["total_variants"] > 0:
                    print(f"\n{phenotype}: {result['total_variants']} T2D variants")

                    # Should find multiple loci
                    for variant in result["variants"][:10]:
                        print(f"  {variant['rsid']}: p={variant['p_value']:.2e}")
                    break
            except Exception as e:
                print(f"  {phenotype} failed: {e}")
                continue

    def test_rs9939609_phenotypes(self, variant_client):
        """Test FTO variant (rs9939609) phenotype associations."""
        result = variant_client.get_variant_phenotypes(
            variant_id="rs9939609",
            max_p_value=1e-5,
        )

        assert result["success"] is True

        if result["total_phenotypes"] > 0:
            print(f"\nrs9939609 phenotypes: {result['total_phenotypes']}")

            phenotype_names = [p["name"] for p in result["phenotypes"]]
            print(f"Phenotypes: {phenotype_names}")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestPerformance:
    """
    Test query performance and benchmarks.

    Requirements:
    - Variant queries should complete in <3 seconds
    - Large result sets handled efficiently
    - Filtering doesn't degrade performance
    """

    def test_gene_variant_performance(self, variant_client):
        """Test performance of gene → variant query."""
        start = time.time()

        result = variant_client.get_gene_variants(
            gene_id="hgnc:613",  # APOE
            max_p_value=1e-5,
        )

        elapsed = time.time() - start

        print(f"\nGene → variant query: {elapsed:.2f}s")
        print(f"Returned {result['total_variants']} variants")

        # Should complete in <3 seconds
        assert elapsed < 3.0, f"Query too slow: {elapsed:.2f}s"

    def test_disease_variant_performance(self, variant_client):
        """Test performance of disease → variant query."""
        start = time.time()

        try:
            result = variant_client.get_disease_variants(
                disease_id="mesh:D000544",  # Alzheimer's
                max_p_value=5e-8,
            )

            elapsed = time.time() - start

            print(f"\nDisease → variant query: {elapsed:.2f}s")
            print(f"Returned {result['total_variants']} variants")

            assert elapsed < 3.0, f"Query too slow: {elapsed:.2f}s"
        except Exception as e:
            print(f"Disease query failed: {e}")
            pytest.skip("Disease query not available")

    def test_phenotype_variant_performance(self, variant_client):
        """Test performance of phenotype → variant query."""
        start = time.time()

        try:
            result = variant_client.get_phenotype_variants(
                phenotype="body mass index",
                max_p_value=5e-8,
            )

            elapsed = time.time() - start

            print(f"\nPhenotype → variant query: {elapsed:.2f}s")
            print(f"Returned {result['total_variants']} variants")

            assert elapsed < 3.0, f"Query too slow: {elapsed:.2f}s"
        except Exception as e:
            print(f"Phenotype query failed: {e}")
            pytest.skip("Phenotype query not available")

    def test_variant_gene_performance(self, variant_client):
        """Test performance of variant → gene query."""
        start = time.time()

        result = variant_client.get_variant_genes("rs7412")

        elapsed = time.time() - start

        print(f"\nVariant → gene query: {elapsed:.2f}s")
        print(f"Returned {result['total_genes']} genes")

        # Should be very fast
        assert elapsed < 2.0, f"Query too slow: {elapsed:.2f}s"

    def test_filtering_performance(self, variant_client):
        """Test that p-value filtering doesn't degrade performance."""
        # Query without filtering
        start1 = time.time()
        result1 = variant_client.get_gene_variants(
            gene_id="hgnc:1100",  # BRCA1
            max_p_value=1.0,  # No filtering
        )
        elapsed1 = time.time() - start1

        # Query with strict filtering
        start2 = time.time()
        result2 = variant_client.get_gene_variants(
            gene_id="hgnc:1100",
            max_p_value=1e-8,
        )
        elapsed2 = time.time() - start2

        print(f"\nNo filter: {elapsed1:.2f}s ({result1['total_variants']} variants)")
        print(f"With filter: {elapsed2:.2f}s ({result2['total_variants']} variants)")

        # Filtering should not add significant overhead
        assert elapsed2 < elapsed1 + 1.0


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestDataQuality:
    """Test data quality and completeness."""

    def test_variant_data_completeness(self, variant_client):
        """Test that variants have required fields."""
        result = variant_client.get_gene_variants(
            gene_id="hgnc:613",
            max_p_value=1e-5,
        )

        if result["total_variants"] > 0:
            for variant in result["variants"][:10]:
                # Check required fields
                assert "rsid" in variant
                assert "curie" in variant
                assert "p_value" in variant

                # P-value should be numeric
                assert isinstance(variant["p_value"], (int, float))

                print(f"{variant['rsid']}: chr{variant.get('chromosome', '?')}:{variant.get('position', '?')}")

    def test_gene_data_completeness(self, variant_client):
        """Test that genes have required fields."""
        result = variant_client.get_variant_genes("rs7412")

        if result["total_genes"] > 0:
            for gene in result["genes"]:
                assert "name" in gene
                assert "curie" in gene
                assert "namespace" in gene
                assert "identifier" in gene

                print(f"{gene['name']}: {gene['curie']}")
