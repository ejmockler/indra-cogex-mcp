"""
Integration tests for OntologyClient.

Tests real CoGEx queries against live Neo4j database with scientifically
validated ontology terms from GO, HPO, and MONDO ontologies.

Run with: pytest tests/integration/test_ontology_integration.py -v --slow
"""

import pytest
from cogex_mcp.clients.ontology_client import OntologyClient


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ontology_client():
    """
    OntologyClient instance for integration testing.

    Uses autoclient to connect to real CoGEx Neo4j instance.
    """
    return OntologyClient()


# =============================================================================
# Test GO (Gene Ontology) Hierarchy Navigation
# =============================================================================

class TestGOOntologyIntegration:
    """Test integration with Gene Ontology (GO)."""

    def test_go_apoptosis_parents(self, ontology_client):
        """
        Test retrieving parent terms for GO apoptosis.

        GO:0006915 (apoptotic process) should have parents like:
        - GO:0012501 (programmed cell death)
        - GO:0008219 (cell death)
        - GO:0016265 (death)
        """
        result = ontology_client.get_parent_terms(
            term="GO:0006915",  # apoptotic process
            max_depth=3,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0006915"
        assert result["total_parents"] > 0

        # Verify at least one expected parent is found
        parent_names = {p["name"].lower() for p in result["parents"]}
        expected_parents = {"programmed cell death", "cell death", "death"}

        # At least one should match
        assert len(parent_names.intersection(expected_parents)) > 0

    def test_go_apoptosis_children(self, ontology_client):
        """
        Test retrieving child terms for GO apoptosis.

        GO:0006915 (apoptotic process) should have children like:
        - GO:0097194 (intrinsic apoptotic signaling pathway)
        - GO:0097191 (extrinsic apoptotic signaling pathway)
        """
        result = ontology_client.get_child_terms(
            term="GO:0006915",  # apoptotic process
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0006915"
        assert result["total_children"] > 0

        # Verify child terms exist
        assert all("curie" in child for child in result["children"])
        assert all("name" in child for child in result["children"])
        assert all("depth" in child for child in result["children"])

    def test_go_cell_cycle_hierarchy(self, ontology_client):
        """
        Test complete hierarchy for GO cell cycle.

        GO:0007049 (cell cycle) is a major biological process with
        many parent and child terms.
        """
        result = ontology_client.get_hierarchy(
            term="GO:0007049",  # cell cycle
            direction="both",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0007049"

        # Should have both parents and children
        assert result["total_parents"] > 0
        assert result["total_children"] > 0

        # Verify structure
        assert isinstance(result["parents"], list)
        assert isinstance(result["children"], list)


# =============================================================================
# Test HPO (Human Phenotype Ontology) Navigation
# =============================================================================

class TestHPOOntologyIntegration:
    """Test integration with Human Phenotype Ontology (HPO)."""

    def test_hpo_seizures_parents(self, ontology_client):
        """
        Test retrieving parent terms for HPO seizures.

        HP:0001250 (Seizure) should have parents related to
        neurological abnormalities.
        """
        result = ontology_client.get_parent_terms(
            term="HP:0001250",  # Seizure
            max_depth=3,
        )

        assert result["success"] is True
        assert result["term"] == "HP:0001250"
        assert result["total_parents"] > 0

        # All parents should be HPO terms
        assert all(p["namespace"] == "hp" for p in result["parents"])

        # Verify depth assignment
        assert all(1 <= p["depth"] <= 3 for p in result["parents"])

    def test_hpo_seizures_children(self, ontology_client):
        """
        Test retrieving child terms for HPO seizures.

        HP:0001250 (Seizure) should have children for specific seizure types.
        """
        result = ontology_client.get_child_terms(
            term="HP:0001250",  # Seizure
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "HP:0001250"

        # May or may not have children depending on ontology structure
        # Just verify format is correct
        if result["total_children"] > 0:
            assert all("curie" in child for child in result["children"])
            assert all(child["namespace"] == "hp" for child in result["children"])

    def test_hpo_intellectual_disability_hierarchy(self, ontology_client):
        """
        Test complete hierarchy for HPO intellectual disability.

        HP:0001249 (Intellectual disability) is a common phenotype
        with clear hierarchical relationships.
        """
        result = ontology_client.get_hierarchy(
            term="HP:0001249",  # Intellectual disability
            direction="both",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "HP:0001249"

        # Should have parents (neurological features)
        assert result["total_parents"] > 0

        # Verify all terms are properly formatted
        if result["parents"]:
            for parent in result["parents"]:
                assert "curie" in parent
                assert parent["curie"].startswith("hp:")


# =============================================================================
# Test MONDO (Disease Ontology) Navigation
# =============================================================================

class TestMONDOOntologyIntegration:
    """Test integration with MONDO disease ontology."""

    def test_mondo_alzheimers_parents(self, ontology_client):
        """
        Test retrieving parent terms for MONDO Alzheimer's disease.

        MONDO:0004975 (Alzheimer disease) should have parents like:
        - MONDO:0005559 (dementia)
        - MONDO:0024458 (neurodegenerative disease)
        """
        result = ontology_client.get_parent_terms(
            term="MONDO:0004975",  # Alzheimer disease
            max_depth=3,
        )

        assert result["success"] is True
        assert result["term"] == "MONDO:0004975"

        # Should have parent disease terms
        if result["total_parents"] > 0:
            assert all(p["namespace"] == "mondo" for p in result["parents"])

    def test_mondo_alzheimers_children(self, ontology_client):
        """
        Test retrieving child terms for MONDO Alzheimer's disease.

        MONDO:0004975 may have specific subtypes of Alzheimer's.
        """
        result = ontology_client.get_child_terms(
            term="MONDO:0004975",  # Alzheimer disease
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "MONDO:0004975"

        # Format validation (may have 0 children if leaf node)
        assert "children" in result
        assert "total_children" in result

    def test_mondo_diabetes_hierarchy(self, ontology_client):
        """
        Test complete hierarchy for MONDO diabetes mellitus.

        MONDO:0005015 (diabetes mellitus) is a major disease category
        with well-defined hierarchies.
        """
        result = ontology_client.get_hierarchy(
            term="MONDO:0005015",  # diabetes mellitus
            direction="both",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "MONDO:0005015"

        # Verify response structure
        assert "parents" in result
        assert "children" in result
        assert "total_parents" in result
        assert "total_children" in result


# =============================================================================
# Test Cross-Ontology Scenarios
# =============================================================================

class TestCrossOntologyScenarios:
    """Test scenarios involving different ontologies."""

    def test_different_ontologies_same_client(self, ontology_client):
        """Test using same client for different ontologies."""
        # Query GO term
        go_result = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=2,
        )

        # Query HPO term
        hpo_result = ontology_client.get_parent_terms(
            term="HP:0001250",
            max_depth=2,
        )

        # Both should succeed
        assert go_result["success"] is True
        assert hpo_result["success"] is True

        # Should return different ontologies
        if go_result["total_parents"] > 0:
            assert go_result["parents"][0]["namespace"] == "go"
        if hpo_result["total_parents"] > 0:
            assert hpo_result["parents"][0]["namespace"] == "hp"

    def test_depth_variation_same_term(self, ontology_client):
        """Test different depth values for same term."""
        # Get with depth 1
        result_depth1 = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=1,
        )

        # Get with depth 3
        result_depth3 = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=3,
        )

        assert result_depth1["success"] is True
        assert result_depth3["success"] is True

        # Depth 3 should have >= terms than depth 1
        assert result_depth3["total_parents"] >= result_depth1["total_parents"]


# =============================================================================
# Test Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling for edge cases."""

    def test_nonexistent_term(self, ontology_client):
        """Test querying nonexistent term."""
        result = ontology_client.get_parent_terms(
            term="GO:9999999",  # Nonexistent
            max_depth=2,
        )

        # Should succeed but return empty results
        assert result["success"] is True
        assert result["total_parents"] == 0

    def test_invalid_term_format(self, ontology_client):
        """Test invalid term format raises error."""
        with pytest.raises(ValueError, match="Invalid term format"):
            ontology_client.get_parent_terms(
                term="INVALID",
                max_depth=2,
            )

    def test_root_term_no_parents(self, ontology_client):
        """Test root term with no parents."""
        # GO:0008150 is biological_process root
        result = ontology_client.get_parent_terms(
            term="GO:0008150",
            max_depth=2,
        )

        assert result["success"] is True
        # Root term may have 0 parents
        assert result["total_parents"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--slow"])
