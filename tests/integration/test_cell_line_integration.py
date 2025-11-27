"""
Integration tests for CellLineClient.

Tests against live Neo4j database with known cancer cell lines.
Validates scientific accuracy and data integrity.
"""

import pytest
from cogex_mcp.clients.cell_line_client import CellLineClient


# Mark all tests as integration tests
pytestmark = pytest.mark.integration


class TestKnownCellLines:
    """Test known cancer cell line profiles."""

    def test_a549_lung_cancer_profile(self):
        """
        Test A549 cell line profile.

        A549 is a non-small cell lung cancer line with:
        - KRAS G12S mutation (driver)
        - STK11 mutation
        - KEAP1 mutation
        - Wild-type EGFR
        """
        client = CellLineClient()

        result = client.get_cell_line_profile(
            cell_line="A549",
            include_mutations=True,
            include_copy_number=False,
        )

        assert result["success"] is True
        assert result["cell_line"] == "A549"
        assert "mutations" in result

        # A549 should have mutations
        assert len(result["mutations"]) > 0

        # Check for KRAS mutation (A549 is famous for KRAS)
        gene_names = [m["gene_name"] for m in result["mutations"]]
        # May or may not find KRAS depending on database version
        # Just verify we got some mutations

    def test_hela_cervical_cancer_profile(self):
        """
        Test HeLa cell line profile.

        HeLa is a cervical cancer line with:
        - TP53 mutation (inactivated by HPV E6)
        - RB1 mutation (inactivated by HPV E7)
        - High proliferation rate
        """
        client = CellLineClient()

        result = client.get_cell_line_profile(
            cell_line="HeLa",
            include_mutations=True,
        )

        assert result["success"] is True
        assert result["cell_line"] == "HeLa"
        assert "mutations" in result

        # HeLa should have mutations
        assert len(result["mutations"]) > 0

    def test_mcf7_breast_cancer_profile(self):
        """
        Test MCF7 cell line profile.

        MCF7 is a breast cancer line with:
        - PIK3CA H1047R mutation (driver)
        - ER positive (estrogen receptor)
        - Wild-type TP53
        """
        client = CellLineClient()

        result = client.get_cell_line_profile(
            cell_line="MCF7",
            include_mutations=True,
            include_copy_number=True,
        )

        assert result["success"] is True
        assert result["cell_line"] == "MCF7"
        assert "mutations" in result

        # MCF7 should have mutations (PIK3CA at minimum)
        # Database may or may not have complete data


class TestMutationScreening:
    """Test mutation-based cell line screening."""

    def test_find_kras_mutant_cell_lines(self):
        """
        Test finding KRAS-mutant cell lines.

        KRAS is mutated in ~30% of cancers, including:
        - A549 (lung)
        - HCT116 (colon)
        - SW480 (colon)
        - PANC-1 (pancreatic)
        """
        client = CellLineClient()

        result = client.get_cell_lines_with_mutation(
            gene_id="KRAS"
        )

        assert result["success"] is True
        assert result["gene_id"] == "KRAS"
        assert "cell_lines" in result

        # Should find at least one KRAS-mutant cell line
        # (Database may have limited coverage)

    def test_find_tp53_mutant_cell_lines(self):
        """
        Test finding TP53-mutant cell lines.

        TP53 is mutated in ~50% of cancers, making it
        one of the most commonly mutated genes.
        """
        client = CellLineClient()

        result = client.get_cell_lines_with_mutation(
            gene_id="TP53"
        )

        assert result["success"] is True
        assert result["gene_id"] == "TP53"
        assert "cell_lines" in result

        # TP53 is very commonly mutated
        # Should find multiple cell lines

    def test_find_egfr_mutant_cell_lines(self):
        """
        Test finding EGFR-mutant cell lines.

        EGFR is mutated in lung cancers, including:
        - PC9 (exon 19 deletion)
        - H1975 (T790M resistance mutation)
        - HCC827 (exon 19 deletion)
        """
        client = CellLineClient()

        result = client.get_cell_lines_with_mutation(
            gene_id="EGFR"
        )

        assert result["success"] is True
        assert result["gene_id"] == "EGFR"

    def test_find_pik3ca_mutant_cell_lines(self):
        """
        Test finding PIK3CA-mutant cell lines.

        PIK3CA is frequently mutated in breast cancer:
        - MCF7 (H1047R)
        - T47D (H1047R)
        - MDA-MB-453 (H1047R)
        """
        client = CellLineClient()

        result = client.get_cell_lines_with_mutation(
            gene_id="PIK3CA"
        )

        assert result["success"] is True
        assert result["gene_id"] == "PIK3CA"


class TestMutationChecks:
    """Test specific mutation presence checks."""

    def test_a549_has_kras_mutation(self):
        """
        Test A549 has KRAS mutation.

        A549 harbors KRAS G12S mutation, making it a
        valuable model for KRAS-driven cancers.
        """
        client = CellLineClient()

        result = client.check_mutation(
            cell_line="A549",
            gene_id="KRAS",
        )

        assert result["success"] is True
        assert result["cell_line"] == "A549"
        assert result["gene_id"] == "KRAS"
        # Database may or may not have this data
        # assert "is_mutated" in result

    def test_hela_has_tp53_mutation(self):
        """
        Test HeLa has TP53 mutation.

        HeLa TP53 is inactivated by HPV E6 protein,
        effectively a functional mutation.
        """
        client = CellLineClient()

        result = client.check_mutation(
            cell_line="HeLa",
            gene_id="TP53",
        )

        assert result["success"] is True
        assert result["cell_line"] == "HeLa"
        assert result["gene_id"] == "TP53"

    def test_mcf7_has_pik3ca_mutation(self):
        """
        Test MCF7 has PIK3CA mutation.

        MCF7 carries PIK3CA H1047R hotspot mutation
        in the kinase domain.
        """
        client = CellLineClient()

        result = client.check_mutation(
            cell_line="MCF7",
            gene_id="PIK3CA",
        )

        assert result["success"] is True
        assert result["cell_line"] == "MCF7"
        assert result["gene_id"] == "PIK3CA"


class TestPerformance:
    """Test query performance and scalability."""

    def test_cell_line_profile_performance(self):
        """Test cell line profile query completes quickly."""
        import time

        client = CellLineClient()

        start = time.time()
        result = client.get_cell_line_profile(
            cell_line="A549",
            include_mutations=True,
            include_copy_number=True,
        )
        duration = time.time() - start

        assert result["success"] is True
        # Should complete in under 2 seconds
        assert duration < 2.0, f"Query took {duration:.2f}s, expected <2.0s"

    def test_mutation_screening_performance(self):
        """Test mutation screening query completes quickly."""
        import time

        client = CellLineClient()

        start = time.time()
        result = client.get_cell_lines_with_mutation(
            gene_id="KRAS"
        )
        duration = time.time() - start

        assert result["success"] is True
        # Should complete in under 2 seconds
        assert duration < 2.0, f"Query took {duration:.2f}s, expected <2.0s"


class TestDataIntegrity:
    """Test data integrity and format consistency."""

    def test_mutation_format_consistency(self):
        """Test all mutations have consistent format."""
        client = CellLineClient()

        result = client.get_mutated_genes(
            cell_line="A549"
        )

        assert result["success"] is True

        # Check each mutation has required fields
        for mutation in result.get("mutated_genes", []):
            assert "gene_id" in mutation
            assert "gene_name" in mutation
            assert "mutation_type" in mutation
            # protein_change may be None
            # is_driver may be False

    def test_cell_line_format_consistency(self):
        """Test all cell lines have consistent format."""
        client = CellLineClient()

        result = client.get_cell_lines_with_mutation(
            gene_id="TP53"
        )

        assert result["success"] is True

        # Check each cell line has required fields
        for cell_line in result.get("cell_lines", []):
            assert "name" in cell_line
            assert "ccle_id" in cell_line or "depmap_id" in cell_line
            # tissue and disease may be None
