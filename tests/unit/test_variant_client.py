"""
Unit tests for VariantClient.

Mocks all CoGEx function calls to test:
- All 6 public methods
- Helper methods
- P-value filtering
- Source filtering
- Data formatting
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from cogex_mcp.clients.variant_client import VariantClient


# Test fixtures

@pytest.fixture
def variant_client():
    """Create VariantClient instance for testing."""
    return VariantClient()


@pytest.fixture
def mock_variant_node():
    """Create mock variant Node for APOE rs7412."""
    node = Mock()
    node.data = {
        "id": "rs7412",
        "rsid": "rs7412",
        "chromosome": "19",
        "position": 45412079,
        "ref_allele": "C",
        "alt_allele": "T",
        "p_value": 2.3e-8,
        "odds_ratio": 3.9,
        "trait": "Alzheimer's disease",
        "study": "PMID:31799898",
        "source": "gwas_catalog",
    }
    node.db_ns = "dbsnp"
    node.db_id = "rs7412"
    return node


@pytest.fixture
def mock_variant_node_disgenet():
    """Create mock variant Node from DisGeNet."""
    node = Mock()
    node.data = {
        "id": "rs429358",
        "chromosome": "19",
        "position": 45411941,
        "ref_allele": "T",
        "alt_allele": "C",
        "p_value": 1.5e-10,
        "odds_ratio": 12.5,
        "trait": "Late-onset Alzheimer's disease",
        "study": "DisGeNet",
        "source": "disgenet",
    }
    node.db_ns = "dbsnp"
    node.db_id = "rs429358"
    return node


@pytest.fixture
def mock_gene_node():
    """Create mock gene Node for APOE."""
    node = Mock()
    node.data = {
        "id": "613",
        "name": "APOE",
        "description": "Apolipoprotein E",
    }
    node.db_ns = "hgnc"
    node.db_id = "613"
    return node


@pytest.fixture
def mock_disease_node():
    """Create mock disease Node for Alzheimer's."""
    node = Mock()
    node.data = {
        "id": "D000544",
        "name": "Alzheimer Disease",
        "description": "A degenerative disease of the brain",
        "p_value": 5.2e-9,
    }
    node.db_ns = "mesh"
    node.db_id = "D000544"
    return node


@pytest.fixture
def mock_phenotype_node():
    """Create mock phenotype Node for body mass index."""
    node = Mock()
    node.data = {
        "id": "0004340",
        "name": "body mass index",
        "trait": "body mass index",
        "description": "Measure of body fat based on height and weight",
        "p_value": 3.1e-12,
    }
    node.db_ns = "efo"
    node.db_id = "0004340"
    return node


# Test Class 1: TestGetGeneVariants

class TestGetGeneVariants:
    """Test get_gene_variants method."""

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_basic_query(self, mock_get_variants, variant_client, mock_variant_node):
        """Test basic variant query for gene."""
        mock_get_variants.return_value = [mock_variant_node]
        mock_client = Mock()

        result = variant_client.get_gene_variants("hgnc:613", client=mock_client)

        assert result["success"] is True
        assert result["total_variants"] == 1
        assert result["gene_id"] == "hgnc:613"
        assert len(result["variants"]) == 1
        assert result["variants"][0]["rsid"] == "rs7412"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_p_value_filtering(self, mock_get_variants, variant_client, mock_variant_node):
        """Test p-value max threshold filtering."""
        # Create variants with different p-values
        node1 = Mock()
        node1.data = {**mock_variant_node.data, "id": "rs1", "p_value": 1e-8}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {**mock_variant_node.data, "id": "rs2", "p_value": 1e-4}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        mock_get_variants.return_value = [node1, node2]

        result = variant_client.get_gene_variants("hgnc:613", max_p_value=1e-5, client=Mock())

        # Only rs1 should pass (1e-8 < 1e-5)
        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs1"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_p_value_range_filtering(self, mock_get_variants, variant_client):
        """Test p-value range filtering with min and max."""
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 1e-10, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-7, "source": "gwas_catalog"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        node3 = Mock()
        node3.data = {"id": "rs3", "p_value": 1e-4, "source": "gwas_catalog"}
        node3.db_ns = "dbsnp"
        node3.db_id = "rs3"

        mock_get_variants.return_value = [node1, node2, node3]

        result = variant_client.get_gene_variants(
            "hgnc:613",
            max_p_value=1e-5,
            min_p_value=1e-9,
            client=Mock(),
        )

        # Only rs2 should pass (1e-9 <= 1e-7 <= 1e-5)
        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs2"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_source_filtering(
        self,
        mock_get_variants,
        variant_client,
        mock_variant_node,
        mock_variant_node_disgenet,
    ):
        """Test filtering by data source."""
        mock_get_variants.return_value = [mock_variant_node, mock_variant_node_disgenet]

        result = variant_client.get_gene_variants("hgnc:613", source="gwas_catalog", client=Mock())

        # Only GWAS Catalog variant should be included
        assert result["total_variants"] == 1
        assert result["variants"][0]["source"] == "gwas_catalog"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_empty_results(self, mock_get_variants, variant_client):
        """Test handling of empty results."""
        mock_get_variants.return_value = []

        result = variant_client.get_gene_variants("hgnc:9999", client=Mock())

        assert result["success"] is True
        assert result["total_variants"] == 0
        assert result["variants"] == []


# Test Class 2: TestGetVariantGenes

class TestGetVariantGenes:
    """Test get_variant_genes method."""

    @patch("cogex_mcp.clients.variant_client.get_genes_for_variant")
    def test_basic_query(self, mock_get_genes, variant_client, mock_gene_node):
        """Test basic gene query for variant."""
        mock_get_genes.return_value = [mock_gene_node]

        result = variant_client.get_variant_genes("rs7412", client=Mock())

        assert result["success"] is True
        assert result["total_genes"] == 1
        assert result["variant_id"] == "rs7412"
        assert len(result["genes"]) == 1
        assert result["genes"][0]["name"] == "APOE"
        assert result["genes"][0]["curie"] == "hgnc:613"

    @patch("cogex_mcp.clients.variant_client.get_genes_for_variant")
    def test_multiple_genes(self, mock_get_genes, variant_client):
        """Test variant associated with multiple genes."""
        gene1 = Mock()
        gene1.data = {"id": "613", "name": "APOE"}
        gene1.db_ns = "hgnc"
        gene1.db_id = "613"

        gene2 = Mock()
        gene2.data = {"id": "620", "name": "APOC1"}
        gene2.db_ns = "hgnc"
        gene2.db_id = "620"

        mock_get_genes.return_value = [gene1, gene2]

        result = variant_client.get_variant_genes("rs12345", client=Mock())

        assert result["total_genes"] == 2
        gene_names = [g["name"] for g in result["genes"]]
        assert "APOE" in gene_names
        assert "APOC1" in gene_names

    @patch("cogex_mcp.clients.variant_client.get_genes_for_variant")
    def test_dbsnp_prefix_handling(self, mock_get_genes, variant_client, mock_gene_node):
        """Test handling of dbsnp: prefix in variant ID."""
        mock_get_genes.return_value = [mock_gene_node]

        result = variant_client.get_variant_genes("dbsnp:rs7412", client=Mock())

        assert result["success"] is True
        assert result["variant_id"] == "dbsnp:rs7412"


# Test Class 3: TestGetDiseaseVariants

class TestGetDiseaseVariants:
    """Test get_disease_variants method."""

    @patch("cogex_mcp.clients.variant_client.get_variants_for_disease")
    def test_basic_query(self, mock_get_variants, variant_client, mock_variant_node):
        """Test basic variant query for disease."""
        mock_get_variants.return_value = [mock_variant_node]

        result = variant_client.get_disease_variants("mesh:D000544", client=Mock())

        assert result["success"] is True
        assert result["total_variants"] == 1
        assert result["disease_id"] == "mesh:D000544"
        assert result["variants"][0]["rsid"] == "rs7412"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_disease")
    def test_genome_wide_significance(self, mock_get_variants, variant_client):
        """Test filtering for genome-wide significance (5e-8)."""
        # Create variants at different significance levels
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 1e-10, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-6, "source": "gwas_catalog"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        mock_get_variants.return_value = [node1, node2]

        result = variant_client.get_disease_variants("mesh:D000544", max_p_value=5e-8, client=Mock())

        # Only rs1 should pass
        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs1"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_disease")
    def test_disgenet_filtering(self, mock_get_variants, variant_client):
        """Test filtering for DisGeNet source only."""
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 1e-8, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-8, "source": "disgenet"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        mock_get_variants.return_value = [node1, node2]

        result = variant_client.get_disease_variants("mesh:D000544", source="disgenet", client=Mock())

        assert result["total_variants"] == 1
        assert result["variants"][0]["source"] == "disgenet"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_disease")
    def test_combined_filtering(self, mock_get_variants, variant_client):
        """Test combined p-value and source filtering."""
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 1e-10, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-4, "source": "gwas_catalog"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        node3 = Mock()
        node3.data = {"id": "rs3", "p_value": 1e-9, "source": "disgenet"}
        node3.db_ns = "dbsnp"
        node3.db_id = "rs3"

        mock_get_variants.return_value = [node1, node2, node3]

        result = variant_client.get_disease_variants(
            "mesh:D000544",
            max_p_value=5e-8,
            source="gwas_catalog",
            client=Mock(),
        )

        # Only rs1 passes both filters
        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs1"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_disease")
    def test_mondo_disease_id(self, mock_get_variants, variant_client, mock_variant_node):
        """Test handling of MONDO disease identifiers."""
        mock_get_variants.return_value = [mock_variant_node]

        result = variant_client.get_disease_variants("mondo:0004975", client=Mock())

        assert result["success"] is True
        assert result["disease_id"] == "mondo:0004975"


# Test Class 4: TestGetVariantDiseases

class TestGetVariantDiseases:
    """Test get_variant_diseases method."""

    @patch("cogex_mcp.clients.variant_client.get_diseases_for_variant")
    def test_basic_query(self, mock_get_diseases, variant_client, mock_disease_node):
        """Test basic disease query for variant."""
        mock_get_diseases.return_value = [mock_disease_node]

        result = variant_client.get_variant_diseases("rs7412", client=Mock())

        assert result["success"] is True
        assert result["total_diseases"] == 1
        assert result["variant_id"] == "rs7412"
        assert result["diseases"][0]["name"] == "Alzheimer Disease"

    @patch("cogex_mcp.clients.variant_client.get_diseases_for_variant")
    def test_p_value_filtering(self, mock_get_diseases, variant_client):
        """Test p-value filtering for diseases."""
        disease1 = Mock()
        disease1.data = {"id": "D000544", "name": "Alzheimer Disease", "p_value": 1e-10}
        disease1.db_ns = "mesh"
        disease1.db_id = "D000544"

        disease2 = Mock()
        disease2.data = {"id": "D003920", "name": "Diabetes Mellitus", "p_value": 0.01}
        disease2.db_ns = "mesh"
        disease2.db_id = "D003920"

        mock_get_diseases.return_value = [disease1, disease2]

        result = variant_client.get_variant_diseases("rs7412", max_p_value=1e-5, client=Mock())

        # Only Alzheimer's should pass
        assert result["total_diseases"] == 1
        assert result["diseases"][0]["name"] == "Alzheimer Disease"

    @patch("cogex_mcp.clients.variant_client.get_diseases_for_variant")
    def test_multiple_diseases(self, mock_get_diseases, variant_client):
        """Test variant associated with multiple diseases."""
        disease1 = Mock()
        disease1.data = {"id": "D000544", "name": "Alzheimer Disease", "p_value": 1e-8}
        disease1.db_ns = "mesh"
        disease1.db_id = "D000544"

        disease2 = Mock()
        disease2.data = {"id": "D003704", "name": "Dementia", "p_value": 2e-7}
        disease2.db_ns = "mesh"
        disease2.db_id = "D003704"

        mock_get_diseases.return_value = [disease1, disease2]

        result = variant_client.get_variant_diseases("rs7412", max_p_value=1e-5, client=Mock())

        assert result["total_diseases"] == 2


# Test Class 5: TestGetVariantPhenotypes

class TestGetVariantPhenotypes:
    """Test get_variant_phenotypes method."""

    @patch("cogex_mcp.clients.variant_client.get_phenotypes_for_variant_gwas")
    def test_basic_query(self, mock_get_phenotypes, variant_client, mock_phenotype_node):
        """Test basic phenotype query for variant."""
        mock_get_phenotypes.return_value = [mock_phenotype_node]

        result = variant_client.get_variant_phenotypes("rs9939609", client=Mock())

        assert result["success"] is True
        assert result["total_phenotypes"] == 1
        assert result["variant_id"] == "rs9939609"
        assert result["phenotypes"][0]["name"] == "body mass index"

    @patch("cogex_mcp.clients.variant_client.get_phenotypes_for_variant_gwas")
    def test_gwas_significance(self, mock_get_phenotypes, variant_client):
        """Test genome-wide significance threshold."""
        pheno1 = Mock()
        pheno1.data = {"id": "0004340", "name": "BMI", "p_value": 1e-15}
        pheno1.db_ns = "efo"
        pheno1.db_id = "0004340"

        pheno2 = Mock()
        pheno2.data = {"id": "0004465", "name": "height", "p_value": 1e-6}
        pheno2.db_ns = "efo"
        pheno2.db_id = "0004465"

        mock_get_phenotypes.return_value = [pheno1, pheno2]

        result = variant_client.get_variant_phenotypes("rs123", max_p_value=5e-8, client=Mock())

        # Only BMI passes genome-wide threshold
        assert result["total_phenotypes"] == 1
        assert result["phenotypes"][0]["name"] == "BMI"

    @patch("cogex_mcp.clients.variant_client.get_phenotypes_for_variant_gwas")
    def test_empty_phenotypes(self, mock_get_phenotypes, variant_client):
        """Test variant with no significant phenotypes."""
        mock_get_phenotypes.return_value = []

        result = variant_client.get_variant_phenotypes("rs99999", client=Mock())

        assert result["success"] is True
        assert result["total_phenotypes"] == 0
        assert result["phenotypes"] == []


# Test Class 6: TestGetPhenotypeVariants

class TestGetPhenotypeVariants:
    """Test get_phenotype_variants method."""

    @patch("cogex_mcp.clients.variant_client.get_variants_for_phenotype_gwas")
    def test_basic_query(self, mock_get_variants, variant_client, mock_variant_node):
        """Test basic variant query for phenotype."""
        mock_get_variants.return_value = [mock_variant_node]

        result = variant_client.get_phenotype_variants("body mass index", client=Mock())

        assert result["success"] is True
        assert result["total_variants"] == 1
        assert result["phenotype"] == "body mass index"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_phenotype_gwas")
    def test_phenotype_curie(self, mock_get_variants, variant_client, mock_variant_node):
        """Test phenotype specified as CURIE."""
        mock_get_variants.return_value = [mock_variant_node]

        result = variant_client.get_phenotype_variants("efo:0004340", client=Mock())

        assert result["success"] is True
        assert result["phenotype"] == "efo:0004340"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_phenotype_gwas")
    def test_gwas_filtering(self, mock_get_variants, variant_client):
        """Test genome-wide significance filtering."""
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 3e-15, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-6, "source": "gwas_catalog"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        mock_get_variants.return_value = [node1, node2]

        result = variant_client.get_phenotype_variants("height", max_p_value=5e-8, client=Mock())

        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs1"

    @patch("cogex_mcp.clients.variant_client.get_variants_for_phenotype_gwas")
    def test_p_value_range(self, mock_get_variants, variant_client):
        """Test p-value range filtering for phenotypes."""
        node1 = Mock()
        node1.data = {"id": "rs1", "p_value": 1e-50, "source": "gwas_catalog"}
        node1.db_ns = "dbsnp"
        node1.db_id = "rs1"

        node2 = Mock()
        node2.data = {"id": "rs2", "p_value": 1e-10, "source": "gwas_catalog"}
        node2.db_ns = "dbsnp"
        node2.db_id = "rs2"

        node3 = Mock()
        node3.data = {"id": "rs3", "p_value": 1e-7, "source": "gwas_catalog"}
        node3.db_ns = "dbsnp"
        node3.db_id = "rs3"

        mock_get_variants.return_value = [node1, node2, node3]

        result = variant_client.get_phenotype_variants(
            "type 2 diabetes",
            max_p_value=5e-8,
            min_p_value=1e-20,
            client=Mock(),
        )

        # Only rs2 passes (1e-20 <= 1e-10 <= 5e-8)
        assert result["total_variants"] == 1
        assert result["variants"][0]["rsid"] == "rs2"


# Test Class 7: TestHelperMethods

class TestHelperMethods:
    """Test helper methods."""

    def test_parse_curie_basic(self, variant_client):
        """Test CURIE parsing with namespace."""
        namespace, identifier = variant_client._parse_curie("hgnc:613")

        assert namespace == "hgnc"
        assert identifier == "613"

    def test_parse_curie_gene_symbol(self, variant_client):
        """Test CURIE parsing without namespace (assumes HGNC)."""
        namespace, identifier = variant_client._parse_curie("APOE")

        assert namespace == "hgnc"
        assert identifier == "APOE"

    def test_parse_curie_mesh(self, variant_client):
        """Test CURIE parsing for MeSH."""
        namespace, identifier = variant_client._parse_curie("mesh:D000544")

        assert namespace == "mesh"
        assert identifier == "D000544"

    def test_parse_variant_id_rsid(self, variant_client):
        """Test variant ID parsing for rsID."""
        namespace, identifier = variant_client._parse_variant_id("rs7412")

        assert namespace == "dbsnp"
        assert identifier == "rs7412"

    def test_parse_variant_id_with_prefix(self, variant_client):
        """Test variant ID parsing with dbsnp: prefix."""
        namespace, identifier = variant_client._parse_variant_id("dbsnp:rs7412")

        assert namespace == "dbsnp"
        assert identifier == "rs7412"

    def test_filter_by_pvalue_max_only(self, variant_client):
        """Test p-value filtering with max threshold only."""
        variants = [
            {"rsid": "rs1", "p_value": 1e-10},
            {"rsid": "rs2", "p_value": 1e-6},
            {"rsid": "rs3", "p_value": 0.01},
        ]

        filtered = variant_client._filter_by_pvalue(variants, max_p=1e-5, min_p=None)

        assert len(filtered) == 2
        assert filtered[0]["rsid"] == "rs1"
        assert filtered[1]["rsid"] == "rs2"

    def test_filter_by_pvalue_range(self, variant_client):
        """Test p-value filtering with min and max."""
        variants = [
            {"rsid": "rs1", "p_value": 1e-50},
            {"rsid": "rs2", "p_value": 1e-10},
            {"rsid": "rs3", "p_value": 1e-6},
            {"rsid": "rs4", "p_value": 0.01},
        ]

        filtered = variant_client._filter_by_pvalue(
            variants,
            max_p=1e-5,
            min_p=1e-20,
        )

        # Should include rs2 and rs3
        assert len(filtered) == 2
        assert filtered[0]["rsid"] == "rs2"
        assert filtered[1]["rsid"] == "rs3"

    def test_filter_by_pvalue_no_pvalue(self, variant_client):
        """Test handling of variants without p_value."""
        variants = [
            {"rsid": "rs1"},  # No p_value, defaults to 1.0
            {"rsid": "rs2", "p_value": 1e-8},
        ]

        filtered = variant_client._filter_by_pvalue(variants, max_p=1e-5, min_p=None)

        # Only rs2 should pass
        assert len(filtered) == 1
        assert filtered[0]["rsid"] == "rs2"

    def test_filter_by_source_gwas(self, variant_client):
        """Test source filtering for GWAS Catalog."""
        variants = [
            {"rsid": "rs1", "source": "gwas_catalog"},
            {"rsid": "rs2", "source": "disgenet"},
            {"rsid": "rs3", "source": "gwas_catalog"},
        ]

        filtered = variant_client._filter_by_source(variants, source="gwas_catalog")

        assert len(filtered) == 2
        assert filtered[0]["rsid"] == "rs1"
        assert filtered[1]["rsid"] == "rs3"

    def test_filter_by_source_disgenet(self, variant_client):
        """Test source filtering for DisGeNet."""
        variants = [
            {"rsid": "rs1", "source": "gwas_catalog"},
            {"rsid": "rs2", "source": "disgenet"},
            {"rsid": "rs3", "source": "disgenet"},
        ]

        filtered = variant_client._filter_by_source(variants, source="disgenet")

        assert len(filtered) == 2
        assert filtered[0]["rsid"] == "rs2"
        assert filtered[1]["rsid"] == "rs3"

    def test_filter_by_source_case_insensitive(self, variant_client):
        """Test source filtering is case-insensitive."""
        variants = [
            {"rsid": "rs1", "source": "GWAS_Catalog"},
            {"rsid": "rs2", "source": "DisGeNet"},
        ]

        filtered = variant_client._filter_by_source(variants, source="gwas_catalog")

        assert len(filtered) == 1
        assert filtered[0]["rsid"] == "rs1"

    def test_filter_by_source_no_source(self, variant_client):
        """Test handling of variants without source field."""
        variants = [
            {"rsid": "rs1"},  # No source
            {"rsid": "rs2", "source": "gwas_catalog"},
        ]

        filtered = variant_client._filter_by_source(variants, source="gwas_catalog")

        # Only rs2 should match
        assert len(filtered) == 1
        assert filtered[0]["rsid"] == "rs2"

    def test_format_variant_dict(self, variant_client, mock_variant_node):
        """Test variant Node to dict conversion."""
        variant_dict = variant_client._format_variant_dict(mock_variant_node)

        assert variant_dict["rsid"] == "rs7412"
        assert variant_dict["curie"] == "dbsnp:rs7412"
        assert variant_dict["namespace"] == "dbsnp"
        assert variant_dict["chromosome"] == "19"
        assert variant_dict["position"] == 45412079
        assert variant_dict["ref_allele"] == "C"
        assert variant_dict["alt_allele"] == "T"
        assert variant_dict["p_value"] == 2.3e-8
        assert variant_dict["odds_ratio"] == 3.9
        assert variant_dict["trait"] == "Alzheimer's disease"

    def test_format_gene_dict(self, variant_client, mock_gene_node):
        """Test gene Node to dict conversion."""
        gene_dict = variant_client._format_gene_dict(mock_gene_node)

        assert gene_dict["name"] == "APOE"
        assert gene_dict["curie"] == "hgnc:613"
        assert gene_dict["namespace"] == "hgnc"
        assert gene_dict["identifier"] == "613"
        assert gene_dict["description"] == "Apolipoprotein E"

    def test_format_disease_dict(self, variant_client, mock_disease_node):
        """Test disease Node to dict conversion."""
        disease_dict = variant_client._format_disease_dict(mock_disease_node)

        assert disease_dict["name"] == "Alzheimer Disease"
        assert disease_dict["curie"] == "mesh:D000544"
        assert disease_dict["namespace"] == "mesh"
        assert disease_dict["identifier"] == "D000544"
        assert disease_dict["p_value"] == 5.2e-9

    def test_format_phenotype_dict(self, variant_client, mock_phenotype_node):
        """Test phenotype Node to dict conversion."""
        phenotype_dict = variant_client._format_phenotype_dict(mock_phenotype_node)

        assert phenotype_dict["name"] == "body mass index"
        assert phenotype_dict["curie"] == "efo:0004340"
        assert phenotype_dict["namespace"] == "efo"
        assert phenotype_dict["identifier"] == "0004340"
        assert phenotype_dict["p_value"] == 3.1e-12


# Edge case tests

class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_missing_node_attributes(self, mock_get_variants, variant_client):
        """Test handling of nodes with missing attributes."""
        node = Mock()
        node.data = {"id": "rs123", "p_value": 1e-6}  # Minimal data with p-value
        node.db_ns = "dbsnp"
        node.db_id = "rs123"

        mock_get_variants.return_value = [node]

        result = variant_client.get_gene_variants("hgnc:613", client=Mock())

        # Should still work with defaults for missing fields
        assert result["success"] is True
        assert len(result["variants"]) == 1
        assert result["variants"][0]["rsid"] == "rs123"
        assert result["variants"][0]["p_value"] == 1e-6
        # Missing fields get defaults
        assert result["variants"][0]["chromosome"] == "unknown"
        assert result["variants"][0]["position"] == 0

    @patch("cogex_mcp.clients.variant_client.get_variants_for_gene")
    def test_all_variants_filtered_out(self, mock_get_variants, variant_client):
        """Test when all variants are filtered out."""
        node = Mock()
        node.data = {"id": "rs1", "p_value": 0.5, "source": "gwas_catalog"}
        node.db_ns = "dbsnp"
        node.db_id = "rs1"

        mock_get_variants.return_value = [node]

        result = variant_client.get_gene_variants("hgnc:613", max_p_value=1e-5, client=Mock())

        # All filtered, but still success
        assert result["success"] is True
        assert result["total_variants"] == 0
        assert result["variants"] == []
