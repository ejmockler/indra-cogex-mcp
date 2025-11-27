"""
Unit tests for DiseaseClient.

Tests all 4 methods with mocks for comprehensive coverage of:
- Disease mechanism queries (genes + phenotypes)
- Reverse lookups (gene→diseases, phenotype→diseases)
- Association checks
- Filtering and formatting logic

Run with: pytest tests/unit/test_disease_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from cogex_mcp.clients.disease_client import DiseaseClient


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def disease_client(mock_neo4j_client):
    """DiseaseClient instance with mocked Neo4j."""
    return DiseaseClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def als_genes_data():
    """Realistic ALS gene association data from DisGeNET."""
    return [
        {
            "gene_id": "hgnc:11086",
            "gene_name": "SOD1",
            "association_type": "genetic_variation",
            "evidence_count": 15,
            "score": 0.95,
            "sources": ["DisGeNET", "GWAS", "OMIM"],
        },
        {
            "gene_id": "hgnc:11571",
            "gene_name": "TARDBP",
            "association_type": "genetic_variation",
            "evidence_count": 8,
            "score": 0.87,
            "sources": ["DisGeNET", "GWAS"],
        },
        {
            "gene_id": "hgnc:13315",
            "gene_name": "FUS",
            "association_type": "genetic_variation",
            "evidence_count": 6,
            "score": 0.82,
            "sources": ["DisGeNET"],
        },
        {
            "gene_id": "hgnc:28337",
            "gene_name": "C9orf72",
            "association_type": "repeat_expansion",
            "evidence_count": 12,
            "score": 0.93,
            "sources": ["DisGeNET", "GWAS", "OMIM"],
        },
    ]


@pytest.fixture
def alzheimers_phenotypes_data():
    """Realistic Alzheimer's disease phenotype data from HPO."""
    return [
        {
            "phenotype_id": "HP:0002354",
            "phenotype_name": "Memory impairment",
            "frequency": "very_frequent",
            "evidence_count": 20,
        },
        {
            "phenotype_id": "HP:0000726",
            "phenotype_name": "Dementia",
            "frequency": "very_frequent",
            "evidence_count": 18,
        },
        {
            "phenotype_id": "HP:0100543",
            "phenotype_name": "Cognitive impairment",
            "frequency": "very_frequent",
            "evidence_count": 15,
        },
        {
            "phenotype_id": "HP:0002511",
            "phenotype_name": "Alzheimer disease",
            "frequency": "obligate",
            "evidence_count": 25,
        },
    ]


@pytest.fixture
def brca1_diseases_data():
    """Realistic BRCA1 disease association data."""
    return [
        {
            "disease_id": "doid:1612",
            "disease_name": "Breast cancer",
            "association_type": "genetic_variation",
            "evidence_count": 45,
            "score": 0.98,
            "sources": ["DisGeNET", "GWAS", "OMIM", "CTD"],
        },
        {
            "disease_id": "doid:2394",
            "disease_name": "Ovarian cancer",
            "association_type": "genetic_variation",
            "evidence_count": 32,
            "score": 0.96,
            "sources": ["DisGeNET", "GWAS", "OMIM"],
        },
        {
            "disease_id": "mondo:0011450",
            "disease_name": "Hereditary breast and ovarian cancer syndrome",
            "association_type": "genetic_variation",
            "evidence_count": 28,
            "score": 0.97,
            "sources": ["DisGeNET", "OMIM"],
        },
    ]


@pytest.fixture
def seizure_diseases_data():
    """Realistic diseases associated with seizures phenotype."""
    return [
        {
            "disease_id": "mondo:0005027",
            "disease_name": "Epilepsy",
            "association_type": "phenotype",
            "evidence_count": 50,
            "score": 0.99,
            "sources": ["HPO", "OMIM"],
        },
        {
            "disease_id": "doid:1826",
            "disease_name": "Epilepsy syndrome",
            "association_type": "phenotype",
            "evidence_count": 35,
            "score": 0.95,
            "sources": ["HPO"],
        },
        {
            "disease_id": "mondo:0015967",
            "disease_name": "Dravet syndrome",
            "association_type": "phenotype",
            "evidence_count": 20,
            "score": 0.92,
            "sources": ["HPO", "OMIM"],
        },
    ]


# ============================================================================
# Test Initialization
# ============================================================================


class TestDiseaseClientInit:
    """Test DiseaseClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        client = DiseaseClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses autoclient)."""
        client = DiseaseClient()
        assert client.client is None


# ============================================================================
# Test Helper Methods
# ============================================================================


class TestParsingMethods:
    """Test CURIE parsing helper methods."""

    def test_parse_disease_id_with_namespace(self, disease_client):
        """Test parsing disease CURIE with namespace."""
        namespace, identifier = disease_client._parse_disease_id("mesh:D000690")
        assert namespace == "MESH"
        assert identifier == "D000690"

    def test_parse_disease_id_case_insensitive(self, disease_client):
        """Test that namespace is uppercased."""
        namespace, identifier = disease_client._parse_disease_id("mondo:0004975")
        assert namespace == "MONDO"
        assert identifier == "0004975"

    def test_parse_disease_id_without_namespace(self, disease_client):
        """Test parsing disease without namespace (assumes MESH)."""
        namespace, identifier = disease_client._parse_disease_id("D000690")
        assert namespace == "MESH"
        assert identifier == "D000690"

    def test_parse_gene_id_with_namespace(self, disease_client):
        """Test parsing gene CURIE with namespace."""
        namespace, identifier = disease_client._parse_gene_id("hgnc:11998")
        assert namespace == "HGNC"
        assert identifier == "11998"

    def test_parse_gene_id_symbol(self, disease_client):
        """Test parsing bare gene symbol (assumes HGNC)."""
        namespace, identifier = disease_client._parse_gene_id("TP53")
        assert namespace == "HGNC"
        assert identifier == "TP53"

    def test_parse_phenotype_id_with_namespace(self, disease_client):
        """Test parsing HPO term CURIE."""
        namespace, identifier = disease_client._parse_phenotype_id("HP:0001250")
        assert namespace == "HP"
        assert identifier == "0001250"

    def test_parse_phenotype_id_without_namespace(self, disease_client):
        """Test parsing phenotype without namespace (assumes HP)."""
        namespace, identifier = disease_client._parse_phenotype_id("0001250")
        assert namespace == "HP"
        assert identifier == "0001250"


# ============================================================================
# Test Filtering and Formatting
# ============================================================================


class TestFilteringMethods:
    """Test gene association filtering methods."""

    def test_filter_genes_by_evidence_count(self, disease_client, als_genes_data):
        """Test filtering genes by minimum evidence count."""
        filtered = disease_client._filter_genes(
            als_genes_data,
            min_evidence=10,
        )

        # Only SOD1 (15) and C9orf72 (12) have ≥10 evidence
        assert len(filtered) == 2
        gene_names = [g["gene_name"] for g in filtered]
        assert "SOD1" in gene_names
        assert "C9orf72" in gene_names

    def test_filter_genes_by_evidence_sources(self, disease_client, als_genes_data):
        """Test filtering genes by evidence sources."""
        filtered = disease_client._filter_genes(
            als_genes_data,
            evidence_sources=["OMIM"],
        )

        # Only SOD1 and C9orf72 have OMIM evidence
        assert len(filtered) == 2
        for gene in filtered:
            assert "OMIM" in gene["sources"]

    def test_filter_genes_combined(self, disease_client, als_genes_data):
        """Test filtering genes with multiple criteria."""
        filtered = disease_client._filter_genes(
            als_genes_data,
            min_evidence=8,
            evidence_sources=["GWAS"],
        )

        # SOD1 (15, has GWAS) and TARDBP (8, has GWAS) and C9orf72 (12, has GWAS)
        assert len(filtered) == 3
        for gene in filtered:
            assert gene["evidence_count"] >= 8
            assert "GWAS" in gene["sources"]

    def test_filter_genes_no_filters(self, disease_client, als_genes_data):
        """Test that no filtering returns all genes."""
        filtered = disease_client._filter_genes(als_genes_data)
        assert len(filtered) == len(als_genes_data)


class TestFormattingMethods:
    """Test data formatting methods."""

    def test_format_genes(self, disease_client, als_genes_data):
        """Test formatting gene associations."""
        formatted = disease_client._format_genes(als_genes_data)

        assert len(formatted) == 4
        for gene in formatted:
            assert "gene_id" in gene
            assert "gene_name" in gene
            assert "association_type" in gene
            assert "evidence_count" in gene
            assert "score" in gene
            assert "sources" in gene

    def test_format_phenotypes(self, disease_client, alzheimers_phenotypes_data):
        """Test formatting phenotype associations."""
        formatted = disease_client._format_phenotypes(alzheimers_phenotypes_data)

        assert len(formatted) == 4
        for phenotype in formatted:
            assert "phenotype_id" in phenotype
            assert "phenotype_name" in phenotype
            assert "frequency" in phenotype
            assert "evidence_count" in phenotype

    def test_format_diseases(self, disease_client, brca1_diseases_data):
        """Test formatting disease list."""
        formatted = disease_client._format_diseases(brca1_diseases_data)

        assert len(formatted) == 3
        for disease in formatted:
            assert "disease_id" in disease
            assert "disease_name" in disease
            assert "association_type" in disease
            assert "evidence_count" in disease
            assert "score" in disease
            assert "sources" in disease

    def test_compute_statistics(self, disease_client, als_genes_data, alzheimers_phenotypes_data):
        """Test computing summary statistics."""
        result = {
            "genes": disease_client._format_genes(als_genes_data),
            "phenotypes": disease_client._format_phenotypes(alzheimers_phenotypes_data),
        }

        stats = disease_client._compute_statistics(result)

        assert stats["gene_count"] == 4
        assert stats["phenotype_count"] == 4
        assert "avg_gene_evidence" in stats
        assert stats["avg_gene_evidence"] > 0
        assert "evidence_sources" in stats
        assert "DisGeNET" in stats["evidence_sources"]


# ============================================================================
# Test Core Query Methods
# ============================================================================


class TestGetDiseaseMechanisms:
    """Test get_disease_mechanisms method."""

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_genes_for_disease")
    @patch("cogex_mcp.clients.disease_client.get_phenotypes_for_disease")
    def test_get_disease_mechanisms_full(
        self,
        mock_get_phenotypes,
        mock_get_genes,
        mock_neo4j_class,
        disease_client,
        als_genes_data,
        alzheimers_phenotypes_data,
    ):
        """Test getting full disease profile (genes + phenotypes)."""
        mock_get_genes.return_value = als_genes_data
        mock_get_phenotypes.return_value = alzheimers_phenotypes_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D000690",  # ALS
            include_genes=True,
            include_phenotypes=True,
        )

        assert result["success"] is True
        assert result["disease_id"] == "mesh:D000690"
        assert len(result["genes"]) == 4
        assert len(result["phenotypes"]) == 4
        assert "statistics" in result

        # Verify CoGEx functions were called
        mock_get_genes.assert_called_once()
        mock_get_phenotypes.assert_called_once()

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_genes_for_disease")
    def test_get_disease_mechanisms_genes_only(
        self,
        mock_get_genes,
        mock_neo4j_class,
        disease_client,
        als_genes_data,
    ):
        """Test getting genes only (no phenotypes)."""
        mock_get_genes.return_value = als_genes_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D000690",
            include_genes=True,
            include_phenotypes=False,
        )

        assert result["success"] is True
        assert len(result["genes"]) == 4
        assert "phenotypes" not in result

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_genes_for_disease")
    def test_get_disease_mechanisms_with_evidence_filter(
        self,
        mock_get_genes,
        mock_neo4j_class,
        disease_client,
        als_genes_data,
    ):
        """Test filtering genes by minimum evidence count."""
        mock_get_genes.return_value = als_genes_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D000690",
            include_genes=True,
            include_phenotypes=False,
            min_evidence=10,
        )

        # Only SOD1 and C9orf72 have ≥10 evidence
        assert len(result["genes"]) == 2


class TestFindDiseasesForGene:
    """Test find_diseases_for_gene method."""

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_gene")
    def test_find_diseases_for_gene_basic(
        self,
        mock_get_diseases,
        mock_neo4j_class,
        disease_client,
        brca1_diseases_data,
    ):
        """Test finding diseases for a gene (BRCA1)."""
        mock_get_diseases.return_value = brca1_diseases_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:1100",  # BRCA1
            limit=20,
        )

        assert result["success"] is True
        assert result["gene_id"] == "hgnc:1100"
        assert len(result["diseases"]) == 3
        assert result["total_diseases"] == 3

        # Verify expected diseases
        disease_names = [d["disease_name"] for d in result["diseases"]]
        assert "Breast cancer" in disease_names
        assert "Ovarian cancer" in disease_names

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_gene")
    def test_find_diseases_for_gene_with_limit(
        self,
        mock_get_diseases,
        mock_neo4j_class,
        disease_client,
        brca1_diseases_data,
    ):
        """Test limiting results."""
        mock_get_diseases.return_value = brca1_diseases_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:1100",
            limit=2,  # Limit to 2 diseases
        )

        assert len(result["diseases"]) == 2

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_gene")
    def test_find_diseases_for_gene_with_min_evidence(
        self,
        mock_get_diseases,
        mock_neo4j_class,
        disease_client,
        brca1_diseases_data,
    ):
        """Test filtering by minimum evidence count."""
        mock_get_diseases.return_value = brca1_diseases_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:1100",
            min_evidence=30,  # Only breast and ovarian cancer
        )

        assert len(result["diseases"]) == 2
        for disease in result["diseases"]:
            assert disease["evidence_count"] >= 30


class TestFindDiseasesForPhenotype:
    """Test find_diseases_for_phenotype method."""

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_phenotype")
    def test_find_diseases_for_phenotype_basic(
        self,
        mock_get_diseases,
        mock_neo4j_class,
        disease_client,
        seizure_diseases_data,
    ):
        """Test finding diseases for a phenotype (seizures)."""
        mock_get_diseases.return_value = seizure_diseases_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_phenotype(
            phenotype_id="HP:0001250",  # Seizures
            limit=20,
        )

        assert result["success"] is True
        assert result["phenotype_id"] == "HP:0001250"
        assert len(result["diseases"]) == 3
        assert result["total_diseases"] == 3

        # Verify expected epilepsy syndromes
        disease_names = [d["disease_name"] for d in result["diseases"]]
        assert "Epilepsy" in disease_names
        assert "Dravet syndrome" in disease_names

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_phenotype")
    def test_find_diseases_for_phenotype_with_limit(
        self,
        mock_get_diseases,
        mock_neo4j_class,
        disease_client,
        seizure_diseases_data,
    ):
        """Test limiting results."""
        mock_get_diseases.return_value = seizure_diseases_data
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_phenotype(
            phenotype_id="HP:0001250",
            limit=1,
        )

        assert len(result["diseases"]) == 1


class TestCheckGeneDiseaseAssociation:
    """Test check_gene_disease_association method."""

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.has_gene_disease_association")
    def test_check_association_exists(
        self,
        mock_has_association,
        mock_neo4j_class,
        disease_client,
    ):
        """Test checking known association (SOD1-ALS)."""
        mock_has_association.return_value = True
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.check_gene_disease_association(
            gene_id="hgnc:11086",  # SOD1
            disease_id="mesh:D000690",  # ALS
        )

        assert result["success"] is True
        assert result["has_association"] is True
        assert result["gene_id"] == "hgnc:11086"
        assert result["disease_id"] == "mesh:D000690"

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.has_gene_disease_association")
    def test_check_association_not_exists(
        self,
        mock_has_association,
        mock_neo4j_class,
        disease_client,
    ):
        """Test checking non-existent association."""
        mock_has_association.return_value = False
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.check_gene_disease_association(
            gene_id="hgnc:11998",  # TP53
            disease_id="mesh:D000690",  # ALS
        )

        assert result["success"] is True
        assert result["has_association"] is False


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_genes_for_disease")
    def test_empty_gene_results(self, mock_get_genes, mock_neo4j_class, disease_client):
        """Test handling empty gene results."""
        mock_get_genes.return_value = []
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.get_disease_mechanisms(
            disease_id="mesh:D999999",  # Non-existent disease
            include_genes=True,
            include_phenotypes=False,
        )

        assert result["success"] is True
        assert len(result["genes"]) == 0
        assert result["statistics"]["gene_count"] == 0

    @patch("indra_cogex.client.neo4j_client.Neo4jClient")
    @patch("cogex_mcp.clients.disease_client.get_diseases_for_gene")
    def test_empty_disease_results(self, mock_get_diseases, mock_neo4j_class, disease_client):
        """Test handling empty disease results."""
        mock_get_diseases.return_value = []
        mock_neo4j_class.return_value = MagicMock()

        result = disease_client.find_diseases_for_gene(
            gene_id="hgnc:99999",  # Non-existent gene
        )

        assert result["success"] is True
        assert len(result["diseases"]) == 0
        assert result["total_diseases"] == 0

    def test_filter_genes_removes_all(self, disease_client, als_genes_data):
        """Test filtering that removes all genes."""
        filtered = disease_client._filter_genes(
            als_genes_data,
            min_evidence=100,  # No genes have this much evidence
        )

        assert len(filtered) == 0

    def test_format_genes_empty_list(self, disease_client):
        """Test formatting empty gene list."""
        formatted = disease_client._format_genes([])
        assert formatted == []

    def test_compute_statistics_empty_result(self, disease_client):
        """Test computing statistics for empty result."""
        result = {}
        stats = disease_client._compute_statistics(result)

        # Should handle missing keys gracefully
        assert "gene_count" not in stats
        assert "phenotype_count" not in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=cogex_mcp.clients.disease_client", "--cov-report=term-missing"])
