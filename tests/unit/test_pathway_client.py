"""
Unit tests for PathwayClient.

Tests all 4 methods with mocked CoGEx queries.
Achieves >90% code coverage without requiring real Neo4j connection.

Run with: pytest tests/unit/test_pathway_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    return MagicMock()


@pytest.fixture
def pathway_client(mock_neo4j_client):
    """PathwayClient instance with mocked Neo4j."""
    from cogex_mcp.clients.pathway_client import PathwayClient

    return PathwayClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def sample_pathways():
    """
    Sample pathway data from CoGEx format.

    Creates realistic pathway records:
    - p53 signaling (reactome)
    - Apoptosis (GO)
    - Cell cycle (WikiPathways)
    """
    return [
        {
            "pathway_id": "reactome:R-HSA-5633007",
            "pathway_name": "p53 signaling pathway",
            "namespace": "reactome",
            "gene_count": 123,
        },
        {
            "pathway_id": "go:0006915",
            "pathway_name": "apoptotic process",
            "namespace": "go",
            "gene_count": 456,
        },
        {
            "pathway_id": "wikipathways:WP179",
            "pathway_name": "Cell Cycle",
            "namespace": "wikipathways",
            "gene_count": 89,
        },
    ]


@pytest.fixture
def sample_genes():
    """
    Sample gene data from CoGEx format.

    Creates realistic gene records:
    - TP53, MDM2, CDKN1A (p53 pathway genes)
    """
    return [
        {
            "gene_id": "hgnc:11998",
            "gene_name": "TP53",
        },
        {
            "gene_id": "hgnc:6973",
            "gene_name": "MDM2",
        },
        {
            "gene_id": "hgnc:1387",
            "gene_name": "CDKN1A",
        },
    ]


# =============================================================================
# Test PathwayClient Initialization
# =============================================================================

class TestPathwayClientInit:
    """Test PathwayClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        from cogex_mcp.clients.pathway_client import PathwayClient

        client = PathwayClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses None)."""
        from cogex_mcp.clients.pathway_client import PathwayClient

        client = PathwayClient()
        assert client.client is None


# =============================================================================
# Test get_gene_pathways Method
# =============================================================================

class TestGetGenePathways:
    """Test get_gene_pathways method."""

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_get_gene_pathways_basic(self, mock_get_pathways, pathway_client, sample_pathways):
        """Test basic gene to pathways query."""
        mock_get_pathways.return_value = sample_pathways

        result = pathway_client.get_gene_pathways(
            gene_id="hgnc:11998",  # TP53
        )

        assert result["success"] is True
        assert len(result["pathways"]) == 3
        assert result["total_pathways"] == 3
        assert result["gene_id"] == "hgnc:11998"

        # Verify CoGEx query called correctly
        mock_get_pathways.assert_called_once()
        call_args = mock_get_pathways.call_args
        assert call_args[0][0] == ("HGNC", "11998")

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_get_gene_pathways_with_source_filter(self, mock_get_pathways, pathway_client, sample_pathways):
        """Test filtering by pathway source (e.g., reactome)."""
        mock_get_pathways.return_value = sample_pathways

        result = pathway_client.get_gene_pathways(
            gene_id="hgnc:11998",
            pathway_source="reactome",
        )

        assert result["success"] is True
        assert len(result["pathways"]) == 1  # Only reactome
        assert result["pathways"][0]["namespace"] == "reactome"

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_get_gene_pathways_empty_result(self, mock_get_pathways, pathway_client):
        """Test gene with no pathways found."""
        mock_get_pathways.return_value = []

        result = pathway_client.get_gene_pathways(
            gene_id="hgnc:99999",  # Non-existent gene
        )

        assert result["success"] is True
        assert len(result["pathways"]) == 0
        assert result["total_pathways"] == 0

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_get_gene_pathways_gene_symbol(self, mock_get_pathways, pathway_client, sample_pathways):
        """Test using gene symbol instead of CURIE."""
        mock_get_pathways.return_value = sample_pathways

        result = pathway_client.get_gene_pathways(
            gene_id="TP53",  # Bare symbol
        )

        assert result["success"] is True
        assert len(result["pathways"]) == 3

        # Should assume HGNC namespace
        call_args = mock_get_pathways.call_args
        assert call_args[0][0] == ("HGNC", "TP53")


# =============================================================================
# Test get_pathway_genes Method
# =============================================================================

class TestGetPathwayGenes:
    """Test get_pathway_genes method."""

    @patch("cogex_mcp.clients.pathway_client.get_genes_for_pathway")
    def test_get_pathway_genes_basic(self, mock_get_genes, pathway_client, sample_genes):
        """Test basic pathway to genes query."""
        mock_get_genes.return_value = sample_genes

        result = pathway_client.get_pathway_genes(
            pathway_id="reactome:R-HSA-5633007",  # p53 pathway
        )

        assert result["success"] is True
        assert len(result["genes"]) == 3
        assert result["total_genes"] == 3
        assert result["pathway_id"] == "reactome:R-HSA-5633007"

        # Verify gene names
        gene_names = {g["gene_name"] for g in result["genes"]}
        assert "TP53" in gene_names
        assert "MDM2" in gene_names

        # Verify CoGEx query
        mock_get_genes.assert_called_once()
        call_args = mock_get_genes.call_args
        assert call_args[0][0] == ("REACTOME", "R-HSA-5633007")

    @patch("cogex_mcp.clients.pathway_client.get_genes_for_pathway")
    def test_get_pathway_genes_empty_result(self, mock_get_genes, pathway_client):
        """Test pathway with no genes found."""
        mock_get_genes.return_value = []

        result = pathway_client.get_pathway_genes(
            pathway_id="reactome:R-HSA-UNKNOWN",
        )

        assert result["success"] is True
        assert len(result["genes"]) == 0
        assert result["total_genes"] == 0

    @patch("cogex_mcp.clients.pathway_client.get_genes_for_pathway")
    def test_get_pathway_genes_go_term(self, mock_get_genes, pathway_client, sample_genes):
        """Test using GO term as pathway."""
        mock_get_genes.return_value = sample_genes

        result = pathway_client.get_pathway_genes(
            pathway_id="go:0006915",  # apoptosis
        )

        assert result["success"] is True
        assert len(result["genes"]) == 3

        # Should parse GO namespace correctly
        call_args = mock_get_genes.call_args
        assert call_args[0][0] == ("GO", "0006915")


# =============================================================================
# Test find_shared_pathways Method
# =============================================================================

class TestFindSharedPathways:
    """Test find_shared_pathways method."""

    @patch("cogex_mcp.clients.pathway_client.get_shared_pathways_for_genes")
    def test_find_shared_pathways_basic(self, mock_get_shared, pathway_client, sample_pathways):
        """Test finding pathways shared by multiple genes."""
        # Add genes list to pathway data
        shared_pathways = [
            {**p, "genes": ["hgnc:11998", "hgnc:6973"]} for p in sample_pathways[:2]
        ]
        mock_get_shared.return_value = shared_pathways

        result = pathway_client.find_shared_pathways(
            gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
        )

        assert result["success"] is True
        assert len(result["shared_pathways"]) == 2
        assert result["total_shared"] == 2
        assert result["query_genes"] == ["hgnc:11998", "hgnc:6973"]

        # Verify CoGEx query
        mock_get_shared.assert_called_once()
        call_args = mock_get_shared.call_args
        assert call_args[0][0] == [("HGNC", "11998"), ("HGNC", "6973")]

    @patch("cogex_mcp.clients.pathway_client.get_shared_pathways_for_genes")
    def test_find_shared_pathways_with_min_genes(self, mock_get_shared, pathway_client, sample_pathways):
        """Test filtering by minimum gene count."""
        shared_pathways = [
            {**sample_pathways[0], "genes": ["hgnc:11998", "hgnc:6973", "hgnc:990"]},  # 3 genes
            {**sample_pathways[1], "genes": ["hgnc:11998"]},  # 1 gene
        ]
        mock_get_shared.return_value = shared_pathways

        result = pathway_client.find_shared_pathways(
            gene_ids=["hgnc:11998", "hgnc:6973", "hgnc:990"],
            min_genes_in_pathway=2,
        )

        assert result["success"] is True
        assert len(result["shared_pathways"]) == 1  # Only pathway with >=2 genes
        assert result["shared_pathways"][0]["gene_count"] == 3

    @patch("cogex_mcp.clients.pathway_client.get_shared_pathways_for_genes")
    def test_find_shared_pathways_with_source(self, mock_get_shared, pathway_client, sample_pathways):
        """Test filtering shared pathways by source."""
        shared_pathways = [
            {**p, "genes": ["hgnc:11998", "hgnc:6973"]} for p in sample_pathways
        ]
        mock_get_shared.return_value = shared_pathways

        result = pathway_client.find_shared_pathways(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            pathway_source="reactome",
        )

        assert result["success"] is True
        assert len(result["shared_pathways"]) == 1  # Only reactome
        assert result["shared_pathways"][0]["namespace"] == "reactome"

    @patch("cogex_mcp.clients.pathway_client.get_shared_pathways_for_genes")
    def test_find_shared_pathways_no_overlap(self, mock_get_shared, pathway_client):
        """Test genes with no shared pathways."""
        mock_get_shared.return_value = []

        result = pathway_client.find_shared_pathways(
            gene_ids=["hgnc:11998", "hgnc:99999"],
        )

        assert result["success"] is True
        assert len(result["shared_pathways"]) == 0
        assert result["total_shared"] == 0


# =============================================================================
# Test check_membership Method
# =============================================================================

class TestCheckMembership:
    """Test check_membership method."""

    @patch("cogex_mcp.clients.pathway_client.is_gene_in_pathway")
    def test_check_membership_true(self, mock_is_in_pathway, pathway_client):
        """Test checking gene membership - positive case."""
        mock_is_in_pathway.return_value = True

        result = pathway_client.check_membership(
            gene_id="hgnc:11998",  # TP53
            pathway_id="reactome:R-HSA-5633007",  # p53 signaling
        )

        assert result["success"] is True
        assert result["is_member"] is True
        assert result["gene_id"] == "hgnc:11998"
        assert result["pathway_id"] == "reactome:R-HSA-5633007"

        # Verify CoGEx query
        mock_is_in_pathway.assert_called_once()
        call_kwargs = mock_is_in_pathway.call_args[1]
        assert call_kwargs["gene"] == ("HGNC", "11998")
        assert call_kwargs["pathway"] == ("REACTOME", "R-HSA-5633007")

    @patch("cogex_mcp.clients.pathway_client.is_gene_in_pathway")
    def test_check_membership_false(self, mock_is_in_pathway, pathway_client):
        """Test checking gene membership - negative case."""
        mock_is_in_pathway.return_value = False

        result = pathway_client.check_membership(
            gene_id="hgnc:11998",  # TP53
            pathway_id="wikipathways:WP999",  # Unrelated pathway
        )

        assert result["success"] is True
        assert result["is_member"] is False

    @patch("cogex_mcp.clients.pathway_client.is_gene_in_pathway")
    def test_check_membership_gene_symbol(self, mock_is_in_pathway, pathway_client):
        """Test using gene symbol instead of CURIE."""
        mock_is_in_pathway.return_value = True

        result = pathway_client.check_membership(
            gene_id="TP53",  # Bare symbol
            pathway_id="reactome:R-HSA-5633007",
        )

        assert result["success"] is True
        assert result["is_member"] is True

        # Should assume HGNC namespace
        call_kwargs = mock_is_in_pathway.call_args[1]
        assert call_kwargs["gene"] == ("HGNC", "TP53")


# =============================================================================
# Test Helper Methods
# =============================================================================

class TestHelperMethods:
    """Test internal helper methods."""

    def test_parse_gene_id_with_curie(self, pathway_client):
        """Test parsing CURIE format."""
        namespace, identifier = pathway_client._parse_gene_id("hgnc:11998")

        assert namespace == "HGNC"
        assert identifier == "11998"

    def test_parse_gene_id_with_go_term(self, pathway_client):
        """Test parsing GO term CURIE."""
        namespace, identifier = pathway_client._parse_gene_id("go:0006915")

        assert namespace == "GO"
        assert identifier == "0006915"

    def test_parse_gene_id_bare_symbol(self, pathway_client):
        """Test parsing bare gene symbol (assumes HGNC)."""
        namespace, identifier = pathway_client._parse_gene_id("TP53")

        assert namespace == "HGNC"
        assert identifier == "TP53"

    def test_format_pathways_response(self, pathway_client, sample_pathways):
        """Test formatting pathway response."""
        result = pathway_client._format_pathways_response(
            sample_pathways,
            gene_id="hgnc:11998",
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:11998"
        assert len(result["pathways"]) == 3
        assert result["total_pathways"] == 3

        # Verify pathway structure
        for pathway in result["pathways"]:
            assert "pathway_id" in pathway
            assert "pathway_name" in pathway
            assert "namespace" in pathway
            assert "gene_count" in pathway

    def test_format_genes_response(self, pathway_client, sample_genes):
        """Test formatting genes response."""
        result = pathway_client._format_genes_response(
            sample_genes,
            pathway_id="reactome:R-HSA-5633007",
        )

        assert result["success"] is True
        assert result["pathway_id"] == "reactome:R-HSA-5633007"
        assert len(result["genes"]) == 3
        assert result["total_genes"] == 3

    def test_format_shared_response(self, pathway_client, sample_pathways):
        """Test formatting shared pathways response."""
        shared = [
            {**p, "genes": ["hgnc:11998", "hgnc:6973"]} for p in sample_pathways
        ]

        result = pathway_client._format_shared_response(
            shared,
            gene_ids=["hgnc:11998", "hgnc:6973"],
        )

        assert result["success"] is True
        assert result["query_genes"] == ["hgnc:11998", "hgnc:6973"]
        assert len(result["shared_pathways"]) == 3
        assert result["total_shared"] == 3

        # Verify pathway structure
        for pathway in result["shared_pathways"]:
            assert "genes_in_pathway" in pathway
            assert "gene_count" in pathway


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_empty_pathway_list(self, mock_get_pathways, pathway_client):
        """Test handling empty pathway list."""
        mock_get_pathways.return_value = []

        result = pathway_client.get_gene_pathways(gene_id="hgnc:99999")

        assert result["success"] is True
        assert result["pathways"] == []
        assert result["total_pathways"] == 0

    @patch("cogex_mcp.clients.pathway_client.get_genes_for_pathway")
    def test_empty_gene_list(self, mock_get_genes, pathway_client):
        """Test handling empty gene list."""
        mock_get_genes.return_value = []

        result = pathway_client.get_pathway_genes(pathway_id="reactome:R-HSA-UNKNOWN")

        assert result["success"] is True
        assert result["genes"] == []
        assert result["total_genes"] == 0

    @patch("cogex_mcp.clients.pathway_client.get_shared_pathways_for_genes")
    def test_single_gene_shared(self, mock_get_shared, pathway_client):
        """Test shared pathways with single gene."""
        mock_get_shared.return_value = []

        result = pathway_client.find_shared_pathways(gene_ids=["hgnc:11998"])

        assert result["success"] is True
        assert result["shared_pathways"] == []

    @patch("cogex_mcp.clients.pathway_client.get_pathways_for_gene")
    def test_source_filter_case_insensitive(self, mock_get_pathways, pathway_client, sample_pathways):
        """Test that source filter is case-insensitive."""
        mock_get_pathways.return_value = sample_pathways

        result = pathway_client.get_gene_pathways(
            gene_id="hgnc:11998",
            pathway_source="REACTOME",  # Uppercase
        )

        assert result["success"] is True
        assert len(result["pathways"]) == 1
        assert result["pathways"][0]["namespace"] == "reactome"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
