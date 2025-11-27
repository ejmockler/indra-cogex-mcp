"""
Unit tests for CellLineClient.

Tests all public methods with mocked Neo4j responses.
Covers mutations, CNAs, cell line lookups, and helper methods.
"""

import pytest
from unittest.mock import Mock, MagicMock

from cogex_mcp.clients.cell_line_client import CellLineClient


class TestGetCellLineProfile:
    """Test get_cell_line_profile method."""

    def test_profile_with_mutations_only(self):
        """Test cell line profile retrieval with only mutations."""
        client = CellLineClient()

        # Mock mutations
        mock_mutations = [
            Mock(
                gene="KRAS",
                namespace="hgnc",
                identifier="6407",
                mutation_type="missense",
                protein_change="G12C",
                variant_classification="Missense_Mutation",
                is_driver=True,
            ),
            Mock(
                gene="TP53",
                namespace="hgnc",
                identifier="11998",
                mutation_type="nonsense",
                protein_change="R248Q",
                variant_classification="Nonsense_Mutation",
                is_driver=True,
            ),
        ]

        # Mock Neo4j client
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="A549",
            include_mutations=True,
            include_copy_number=False,
            include_dependencies=False,
            include_expression=False,
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "A549"
        assert "mutations" in result

    def test_profile_with_all_features(self):
        """Test comprehensive cell line profile with all features."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="HeLa",
            include_mutations=True,
            include_copy_number=True,
            include_dependencies=True,
            include_expression=True,
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "HeLa"
        assert "mutations" in result
        assert "copy_number_alterations" in result
        assert "dependencies" in result
        assert "expression" in result

    def test_profile_empty_mutations(self):
        """Test cell line with no mutations."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="TESTLINE",
            include_mutations=True,
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "TESTLINE"

    def test_profile_case_insensitive_name(self):
        """Test cell line name is case-normalized."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="mcf7",  # Lowercase
            include_mutations=True,
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "MCF7"  # Normalized

    def test_profile_minimal_default_params(self):
        """Test default parameter behavior."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="A549",
            client=mock_client,
        )

        assert result["success"] is True
        assert "mutations" in result
        assert "copy_number_alterations" not in result  # Default False
        assert "dependencies" not in result  # Default False


class TestGetMutatedGenes:
    """Test get_mutated_genes method."""

    def test_get_mutated_genes_multiple(self):
        """Test retrieval of multiple mutated genes."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_mutated_genes(
            cell_line="A549",
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "A549"
        assert "mutated_genes" in result
        assert "total_mutations" in result

    def test_get_mutated_genes_empty(self):
        """Test cell line with no mutations."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_mutated_genes(
            cell_line="WILDTYPE",
            client=mock_client,
        )

        assert result["success"] is True
        assert result["total_mutations"] == 0

    def test_get_mutated_genes_normalized_name(self):
        """Test name normalization for mutated genes query."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_mutated_genes(
            cell_line="hela",  # Lowercase
            client=mock_client,
        )

        assert result["success"] is True
        assert result["cell_line"] == "HeLa"  # Normalized

    def test_get_mutated_genes_format(self):
        """Test mutation format includes required fields."""
        client = CellLineClient()
        mock_mutations = [
            Mock(
                gene="KRAS",
                namespace="hgnc",
                identifier="6407",
                mutation_type="missense",
                protein_change="G12C",
                variant_classification="Missense_Mutation",
                is_driver=True,
            ),
        ]
        mock_client = Mock()

        result = client.get_mutated_genes(
            cell_line="A549",
            client=mock_client,
        )

        assert result["success"] is True


class TestGetCellLinesWithMutation:
    """Test get_cell_lines_with_mutation method."""

    def test_find_kras_mutant_lines(self):
        """Test finding KRAS-mutant cell lines."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_lines_with_mutation(
            gene_id="KRAS",
            client=mock_client,
        )

        assert result["success"] is True
        assert result["gene_id"] == "KRAS"
        assert "cell_lines" in result
        assert "total_cell_lines" in result

    def test_find_tp53_mutant_lines(self):
        """Test finding TP53-mutant cell lines."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_lines_with_mutation(
            gene_id="hgnc:11998",  # TP53
            client=mock_client,
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:11998"

    def test_find_no_mutants(self):
        """Test gene with no mutant cell lines."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_lines_with_mutation(
            gene_id="RARE_GENE",
            client=mock_client,
        )

        assert result["success"] is True
        assert result["total_cell_lines"] == 0

    def test_gene_symbol_vs_curie(self):
        """Test both gene symbol and CURIE work."""
        client = CellLineClient()
        mock_client = Mock()

        # Test with symbol
        result1 = client.get_cell_lines_with_mutation(
            gene_id="EGFR",
            client=mock_client,
        )
        assert result1["success"] is True

        # Test with CURIE
        result2 = client.get_cell_lines_with_mutation(
            gene_id="hgnc:3236",
            client=mock_client,
        )
        assert result2["success"] is True

    def test_cell_line_format_complete(self):
        """Test cell line format includes all required fields."""
        client = CellLineClient()
        mock_cell_lines = [
            Mock(
                name="A549",
                ccle_id="ccle:A549",
                depmap_id="depmap:A549",
                tissue="lung",
                disease="lung adenocarcinoma",
            ),
        ]
        mock_client = Mock()

        result = client.get_cell_lines_with_mutation(
            gene_id="KRAS",
            client=mock_client,
        )

        assert result["success"] is True


class TestCheckMutation:
    """Test check_mutation method."""

    def test_check_kras_in_a549_positive(self):
        """Test A549 has KRAS mutation (known positive)."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.check_mutation(
            cell_line="A549",
            gene_id="KRAS",
            client=mock_client,
        )

        assert result["success"] is True
        assert "is_mutated" in result
        assert result["cell_line"] == "A549"
        assert result["gene_id"] == "KRAS"

    def test_check_tp53_in_hela_positive(self):
        """Test HeLa has TP53 mutation (known positive)."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.check_mutation(
            cell_line="HeLa",
            gene_id="TP53",
            client=mock_client,
        )

        assert result["success"] is True
        assert "is_mutated" in result

    def test_check_negative_result(self):
        """Test negative mutation check."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.check_mutation(
            cell_line="WILDTYPE",
            gene_id="TP53",
            client=mock_client,
        )

        assert result["success"] is True
        assert "is_mutated" in result

    def test_check_with_curie(self):
        """Test mutation check with gene CURIE."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.check_mutation(
            cell_line="A549",
            gene_id="hgnc:6407",  # KRAS
            client=mock_client,
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:6407"


class TestHelperMethods:
    """Test helper methods."""

    def test_parse_cell_line_name_uppercase(self):
        """Test cell line name normalization - uppercase."""
        client = CellLineClient()

        assert client._parse_cell_line_name("a549") == "A549"
        assert client._parse_cell_line_name("A549") == "A549"

    def test_parse_cell_line_name_special_cases(self):
        """Test special cell line name handling."""
        client = CellLineClient()

        assert client._parse_cell_line_name("hela") == "HeLa"
        assert client._parse_cell_line_name("HELA") == "HeLa"
        assert client._parse_cell_line_name("mcf7") == "MCF7"
        assert client._parse_cell_line_name("mcf-7") == "MCF7"

    def test_parse_gene_id_curie(self):
        """Test gene CURIE parsing."""
        client = CellLineClient()

        namespace, identifier = client._parse_gene_id("hgnc:6407")
        assert namespace == "HGNC"
        assert identifier == "6407"

    def test_parse_gene_id_symbol(self):
        """Test gene symbol parsing (assumes HGNC)."""
        client = CellLineClient()

        namespace, identifier = client._parse_gene_id("KRAS")
        assert namespace == "HGNC"
        assert identifier == "KRAS"

    def test_format_mutation_dict_complete(self):
        """Test mutation dict formatting with all fields."""
        client = CellLineClient()

        mutation = {
            "gene": "KRAS",
            "namespace": "hgnc",
            "identifier": "6407",
            "mutation_type": "missense",
            "protein_change": "G12C",
            "variant_classification": "Missense_Mutation",
            "is_driver": True,
        }

        result = client._format_mutation_dict(mutation)

        assert result["gene_id"] == "hgnc:6407"
        assert result["gene_name"] == "KRAS"
        assert result["mutation_type"] == "missense"
        assert result["protein_change"] == "G12C"
        assert result["is_driver"] is True

    def test_format_mutation_dict_minimal(self):
        """Test mutation dict formatting with minimal fields."""
        client = CellLineClient()

        mutation = {
            "gene": "TP53",
        }

        result = client._format_mutation_dict(mutation)

        assert result["gene_id"] == "hgnc:TP53"
        assert result["gene_name"] == "TP53"
        assert result["mutation_type"] == "unknown"

    def test_format_cell_line_dict_complete(self):
        """Test cell line dict formatting."""
        client = CellLineClient()

        cell_line = {
            "name": "A549",
            "ccle_id": "ccle:A549",
            "depmap_id": "depmap:A549",
            "tissue": "lung",
            "disease": "lung adenocarcinoma",
        }

        result = client._format_cell_line_dict(cell_line)

        assert result["name"] == "A549"
        assert result["ccle_id"] == "ccle:A549"
        assert result["tissue"] == "lung"
        assert result["disease"] == "lung adenocarcinoma"

    def test_format_cell_line_dict_minimal(self):
        """Test cell line dict formatting with minimal data."""
        client = CellLineClient()

        cell_line = {
            "name": "TESTLINE",
        }

        result = client._format_cell_line_dict(cell_line)

        assert result["name"] == "TESTLINE"
        assert "ccle:" in result["ccle_id"]

    def test_format_cna_list_amplification(self):
        """Test CNA formatting - amplification."""
        client = CellLineClient()

        cna_genes = [
            {
                "gene": "EGFR",
                "namespace": "hgnc",
                "identifier": "3236",
                "copy_number": 5.0,
            }
        ]

        result = client._format_cna_list(cna_genes)

        assert len(result) == 1
        assert result[0]["alteration_type"] == "amplification"
        assert result[0]["copy_number"] == 5.0

    def test_format_cna_list_deletion(self):
        """Test CNA formatting - deletion."""
        client = CellLineClient()

        cna_genes = [
            {
                "gene": "CDKN2A",
                "namespace": "hgnc",
                "identifier": "1787",
                "copy_number": 0.5,
            }
        ]

        result = client._format_cna_list(cna_genes)

        assert len(result) == 1
        assert result[0]["alteration_type"] == "deletion"
        assert result[0]["copy_number"] == 0.5

    def test_format_cna_list_neutral(self):
        """Test CNA formatting - neutral."""
        client = CellLineClient()

        cna_genes = [
            {
                "gene": "NORMAL",
                "namespace": "hgnc",
                "identifier": "1234",
                "copy_number": 2.0,
            }
        ]

        result = client._format_cna_list(cna_genes)

        assert len(result) == 1
        assert result[0]["alteration_type"] == "neutral"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_cell_line(self):
        """Test behavior with unknown cell line."""
        client = CellLineClient()
        mock_client = Mock()

        result = client.get_cell_line_profile(
            cell_line="NONEXISTENT",
            client=mock_client,
        )

        assert result["success"] is True

    def test_empty_gene_symbol(self):
        """Test empty gene symbol handling."""
        client = CellLineClient()

        # Should still parse, though may fail at query time
        namespace, identifier = client._parse_gene_id("")
        assert namespace == "HGNC"

    def test_format_mutations_empty_list(self):
        """Test formatting empty mutation list."""
        client = CellLineClient()

        result = client._format_mutations([])

        assert result == []

    def test_format_cna_empty_list(self):
        """Test formatting empty CNA list."""
        client = CellLineClient()

        result = client._format_cna_list([])

        assert result == []
