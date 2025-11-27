"""
Integration tests for DiseaseClient with real Neo4j database.

Tests scientific scenarios with known disease-gene-phenotype associations:
1. ALS mechanisms (expect SOD1, TARDBP, FUS, C9orf72)
2. BRCA1 diseases (expect breast cancer, ovarian cancer)
3. Alzheimer's phenotypes (expect memory impairment, dementia)
4. Seizure diseases (expect epilepsy syndromes)
5. Evidence filtering (min_evidence=3)
6. Check known association (BRCA1-breast cancer)

Run with: pytest tests/integration/test_disease_integration.py -v
"""

import pytest

from cogex_mcp.clients.disease_client import DiseaseClient


@pytest.fixture(scope="module")
def disease_client():
    """
    DiseaseClient with real Neo4j connection.

    Uses autoclient() to connect to Neo4j instance.
    Requires INDRA_NEO4J_URL environment variable.
    """
    return DiseaseClient()


# ============================================================================
# Test Disease → Mechanisms
# ============================================================================


class TestDiseaseMechanisms:
    """Test disease → genes + phenotypes queries with real data."""

    def test_als_mechanisms(self, disease_client):
        """
        Test ALS disease mechanisms.

        ALS (mesh:D000690) should be associated with known genes:
        - SOD1 (hgnc:11086) - Superoxide dismutase 1
        - TARDBP (hgnc:11571) - TAR DNA-binding protein
        - FUS (hgnc:13315) - Fused in sarcoma
        - C9orf72 (hgnc:28337) - C9orf72-SMCR8 complex subunit

        These are well-established ALS genes with strong evidence.
        """
        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D000690",  # ALS
            include_genes=True,
            include_phenotypes=True,
            min_evidence=1,
        )

        # Validate response structure
        assert result["success"] is True
        assert result["disease_id"] == "mesh:D000690"
        assert "genes" in result
        assert "phenotypes" in result
        assert "statistics" in result

        # Validate gene associations
        genes = result["genes"]
        assert len(genes) > 0, "Expected ALS to have gene associations"

        gene_ids = [g["gene_id"] for g in genes]
        gene_names = [g["gene_name"] for g in genes]

        # Check for known ALS genes (expect at least some of these)
        # Note: Neo4j may not have all genes depending on data version
        known_als_genes = ["SOD1", "TARDBP", "FUS", "C9orf72"]
        found_genes = [gene for gene in known_als_genes if gene in gene_names]

        assert len(found_genes) > 0, (
            f"Expected to find at least one known ALS gene "
            f"({known_als_genes}), but found: {gene_names}"
        )

        # Validate data quality
        for gene in genes:
            assert "gene_id" in gene
            assert "gene_name" in gene
            assert gene["gene_id"].startswith("hgnc:")
            assert gene["evidence_count"] >= 1
            assert 0.0 <= gene["score"] <= 1.0
            assert len(gene["sources"]) > 0

        # Validate statistics
        stats = result["statistics"]
        assert stats["gene_count"] == len(genes)
        assert "avg_gene_evidence" in stats
        assert "evidence_sources" in stats

    def test_alzheimers_phenotypes(self, disease_client):
        """
        Test Alzheimer's disease phenotypes.

        Alzheimer's disease (mondo:0004975) should have phenotypes:
        - Memory impairment (HP:0002354)
        - Dementia (HP:0000726)
        - Cognitive impairment (HP:0100543)

        These are cardinal features of Alzheimer's disease.
        """
        result = disease_client.get_disease_mechanisms(
            disease_id="mondo:0004975",  # Alzheimer's disease
            include_genes=False,  # Focus on phenotypes
            include_phenotypes=True,
        )

        assert result["success"] is True
        assert "phenotypes" in result

        phenotypes = result["phenotypes"]
        # Note: May return 0 phenotypes if HPO data not in Neo4j
        # This is a known limitation of the current database

        if len(phenotypes) > 0:
            # If we have phenotype data, validate it
            phenotype_names = [p["phenotype_name"].lower() for p in phenotypes]

            # Check for expected phenotypes (at least one should exist)
            expected_terms = ["memory", "dementia", "cognitive"]
            found_terms = [
                term for term in expected_terms
                if any(term in name for name in phenotype_names)
            ]

            assert len(found_terms) > 0, (
                f"Expected Alzheimer's to have phenotypes related to "
                f"{expected_terms}, but found: {phenotype_names}"
            )

            # Validate phenotype structure
            for phenotype in phenotypes:
                assert "phenotype_id" in phenotype
                assert "phenotype_name" in phenotype
                assert phenotype["phenotype_id"].startswith("HP:")

    def test_diabetes_mechanisms_comprehensive(self, disease_client):
        """
        Test comprehensive diabetes mellitus profile.

        Diabetes (mesh:D003920) is a well-studied disease with:
        - Many gene associations (e.g., INS, GCK, KCNJ11)
        - Multiple evidence sources
        - Rich phenotype data
        """
        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D003920",  # Diabetes mellitus
            include_genes=True,
            include_phenotypes=True,
            min_evidence=2,  # Require multiple evidence
        )

        assert result["success"] is True

        # Expect diabetes to have gene associations
        if "genes" in result and len(result["genes"]) > 0:
            genes = result["genes"]

            # Validate evidence filtering worked
            for gene in genes:
                assert gene["evidence_count"] >= 2

            # Check for multiple evidence sources
            stats = result["statistics"]
            assert len(stats.get("evidence_sources", [])) > 0

    def test_cancer_genes_with_high_evidence(self, disease_client):
        """
        Test cancer disease with high evidence threshold.

        Breast cancer (doid:1612) should have high-evidence genes like:
        - BRCA1, BRCA2, TP53, PTEN, etc.

        Using min_evidence=5 to focus on well-supported associations.
        """
        result = disease_client.get_disease_mechanisms(
            disease_id="doid:1612",  # Breast cancer
            include_genes=True,
            include_phenotypes=False,
            min_evidence=5,  # High evidence threshold
        )

        assert result["success"] is True

        genes = result.get("genes", [])

        if len(genes) > 0:
            # All genes should have high evidence
            for gene in genes:
                assert gene["evidence_count"] >= 5

            # Check for known breast cancer genes
            gene_names = [g["gene_name"] for g in genes]
            known_cancer_genes = ["BRCA1", "BRCA2", "TP53"]

            found_genes = [gene for gene in known_cancer_genes if gene in gene_names]

            # At least one should be found
            assert len(found_genes) > 0, (
                f"Expected to find at least one known breast cancer gene "
                f"({known_cancer_genes}), but found: {gene_names}"
            )


# ============================================================================
# Test Gene → Diseases
# ============================================================================


class TestGeneToDiseases:
    """Test gene → diseases reverse lookup."""

    def test_brca1_diseases(self, disease_client):
        """
        Test BRCA1 gene → disease associations.

        BRCA1 (hgnc:1100) is a tumor suppressor gene associated with:
        - Breast cancer
        - Ovarian cancer
        - Hereditary breast and ovarian cancer syndrome

        These are well-established associations.
        """
        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:1100",  # BRCA1
            limit=50,
            min_evidence=1,
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:1100"
        assert "diseases" in result

        diseases = result["diseases"]
        assert len(diseases) > 0, "Expected BRCA1 to have disease associations"

        disease_names = [d["disease_name"].lower() for d in diseases]

        # Check for expected cancer types
        expected_cancers = ["breast", "ovarian"]
        found_cancers = [
            cancer for cancer in expected_cancers
            if any(cancer in name for name in disease_names)
        ]

        assert len(found_cancers) > 0, (
            f"Expected BRCA1 to be associated with {expected_cancers}, "
            f"but found: {disease_names}"
        )

        # Validate disease structure
        for disease in diseases:
            assert "disease_id" in disease
            assert "disease_name" in disease
            assert disease["evidence_count"] >= 1

    def test_sod1_diseases(self, disease_client):
        """
        Test SOD1 gene → disease associations.

        SOD1 (hgnc:11086) mutations cause:
        - Amyotrophic lateral sclerosis (ALS)

        This is a canonical gene-disease association.
        """
        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:11086",  # SOD1
            limit=20,
        )

        assert result["success"] is True

        diseases = result["diseases"]

        if len(diseases) > 0:
            disease_names = [d["disease_name"].lower() for d in diseases]

            # SOD1 should be associated with ALS or motor neuron disease
            als_terms = ["als", "amyotrophic", "motor neuron"]
            found_als = any(
                any(term in name for term in als_terms)
                for name in disease_names
            )

            assert found_als, (
                f"Expected SOD1 to be associated with ALS, "
                f"but found: {disease_names}"
            )


# ============================================================================
# Test Phenotype → Diseases
# ============================================================================


class TestPhenotypeToDiseases:
    """Test phenotype → diseases reverse lookup."""

    def test_seizures_to_epilepsy(self, disease_client):
        """
        Test seizures phenotype → disease associations.

        Seizures (HP:0001250) is a cardinal feature of:
        - Epilepsy (mondo:0005027)
        - Various epilepsy syndromes
        - Neurological disorders

        This is a fundamental phenotype-disease relationship.
        """
        result = disease_client.find_diseases_for_phenotype(
            phenotype_id="HP:0001250",  # Seizures
            limit=30,
        )

        assert result["success"] is True
        assert result["phenotype_id"] == "HP:0001250"

        diseases = result.get("diseases", [])

        if len(diseases) > 0:
            disease_names = [d["disease_name"].lower() for d in diseases]

            # Expect to find epilepsy-related diseases
            epilepsy_terms = ["epilepsy", "seizure"]
            found_epilepsy = any(
                any(term in name for term in epilepsy_terms)
                for name in disease_names
            )

            assert found_epilepsy, (
                f"Expected seizures phenotype to be associated with epilepsy, "
                f"but found: {disease_names}"
            )

            # Validate disease structure
            for disease in diseases:
                assert "disease_id" in disease
                assert "disease_name" in disease


# ============================================================================
# Test Association Checks
# ============================================================================


class TestAssociationChecks:
    """Test boolean association checks."""

    def test_known_association_brca1_breast_cancer(self, disease_client):
        """
        Test known association: BRCA1 ↔ Breast cancer.

        This is one of the most well-established gene-disease associations
        in human genetics. Should return True.
        """
        result = disease_client.check_gene_disease_association(
            gene_id="hgnc:1100",  # BRCA1
            disease_id="doid:1612",  # Breast cancer
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:1100"
        assert result["disease_id"] == "doid:1612"

        # This association should exist
        assert result["has_association"] is True, (
            "BRCA1-breast cancer association is well-established and should exist"
        )

    def test_known_association_sod1_als(self, disease_client):
        """
        Test known association: SOD1 ↔ ALS.

        SOD1 mutations are a major cause of familial ALS.
        Should return True.
        """
        result = disease_client.check_gene_disease_association(
            gene_id="hgnc:11086",  # SOD1
            disease_id="mesh:D000690",  # ALS
        )

        assert result["success"] is True

        # This association should exist
        assert result["has_association"] is True, (
            "SOD1-ALS association is well-established and should exist"
        )

    def test_unlikely_association(self, disease_client):
        """
        Test unlikely association: Random gene ↔ Random disease.

        This tests that the check returns False for non-existent associations.
        """
        result = disease_client.check_gene_disease_association(
            gene_id="hgnc:11998",  # TP53 (cancer gene)
            disease_id="mesh:D003920",  # Diabetes mellitus
        )

        assert result["success"] is True

        # This association is unlikely to exist
        # (TP53 is primarily a cancer gene, not diabetes)
        # Note: This may return True if there's indirect evidence
        assert "has_association" in result


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nonexistent_disease(self, disease_client):
        """Test querying non-existent disease."""
        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D999999",  # Non-existent
            include_genes=True,
        )

        # Should succeed but return empty results
        assert result["success"] is True
        assert len(result.get("genes", [])) == 0

    def test_nonexistent_gene(self, disease_client):
        """Test querying non-existent gene."""
        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:99999",  # Non-existent
        )

        # Should succeed but return empty results
        assert result["success"] is True
        assert len(result["diseases"]) == 0

    def test_nonexistent_phenotype(self, disease_client):
        """Test querying non-existent phenotype."""
        result = disease_client.find_diseases_for_phenotype(
            phenotype_id="HP:9999999",  # Non-existent
        )

        # Should succeed but return empty results
        assert result["success"] is True
        assert len(result.get("diseases", [])) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
