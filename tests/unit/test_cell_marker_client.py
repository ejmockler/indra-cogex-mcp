"""
Unit tests for CellMarkerClient.

Tests all public methods and helper methods with mocked CoGEx responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from cogex_mcp.clients.cell_marker_client import CellMarkerClient


class TestGetCellTypeMarkers:
    """Test suite for get_cell_type_markers method."""

    @patch("cogex_mcp.clients.cell_marker_client.get_markers_for_cell_type")
    def test_get_markers_basic(self, mock_get_markers):
        """Test basic marker retrieval for a cell type."""
        # Mock CoGEx response
        mock_get_markers.return_value = [
            {
                "gene": "CD3D",
                "namespace": "hgnc",
                "identifier": "1673",
                "marker_type": "cell surface",
                "evidence": "experimental",
                "tissue": "blood",
                "species": "human",
            },
            {
                "gene": "CD4",
                "namespace": "hgnc",
                "identifier": "1678",
                "marker_type": "cell surface",
                "evidence": "experimental",
                "tissue": "blood",
                "species": "human",
            },
        ]

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_cell_type_markers(
            cell_type="T cell",
            species="human",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["cell_type"] == "T cell"
        assert result["species"] == "human"
        assert result["total_markers"] == 2
        assert len(result["markers"]) == 2

        # Verify first marker
        marker1 = result["markers"][0]
        assert marker1["gene"]["name"] == "CD3D"
        assert marker1["gene"]["curie"] == "hgnc:1673"
        assert marker1["marker_type"] == "cell surface"
        assert marker1["evidence"] == "experimental"

        # Verify mock was called correctly
        mock_get_markers.assert_called_once_with("T cell", client=mock_neo4j_client)

    @patch("cogex_mcp.clients.cell_marker_client.get_markers_for_cell_type")
    def test_get_markers_with_tissue_filter(self, mock_get_markers):
        """Test marker retrieval with tissue filter."""
        # Mock CoGEx response with multiple tissues
        mock_get_markers.return_value = [
            {
                "gene": "CD3D",
                "namespace": "hgnc",
                "identifier": "1673",
                "marker_type": "cell surface",
                "evidence": "experimental",
                "tissue": "blood",
                "species": "human",
            },
            {
                "gene": "CD3E",
                "namespace": "hgnc",
                "identifier": "1674",
                "marker_type": "cell surface",
                "evidence": "experimental",
                "tissue": "spleen",
                "species": "human",
            },
        ]

        # Execute with tissue filter
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_cell_type_markers(
            cell_type="T cell",
            species="human",
            tissue="blood",
            client=mock_neo4j_client,
        )

        # Verify filtering
        assert result["success"] is True
        assert result["total_markers"] == 1
        assert result["markers"][0]["gene"]["name"] == "CD3D"
        assert result["markers"][0]["tissue"] == "blood"

    @patch("cogex_mcp.clients.cell_marker_client.get_markers_for_cell_type")
    def test_get_markers_empty_result(self, mock_get_markers):
        """Test marker retrieval with no results."""
        # Mock empty response
        mock_get_markers.return_value = []

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_cell_type_markers(
            cell_type="Unknown Cell",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["total_markers"] == 0
        assert result["markers"] == []

    @patch("cogex_mcp.clients.cell_marker_client.get_markers_for_cell_type")
    def test_get_markers_normalizes_cell_type_name(self, mock_get_markers):
        """Test that cell type names are normalized."""
        mock_get_markers.return_value = []

        client = CellMarkerClient()
        mock_neo4j_client = Mock()

        # Test various name formats
        result = client.get_cell_type_markers(
            cell_type="t-cell",
            client=mock_neo4j_client,
        )

        # Verify normalization
        assert result["cell_type"] == "T cell"
        mock_get_markers.assert_called_with("T cell", client=mock_neo4j_client)

    @patch("cogex_mcp.clients.cell_marker_client.get_markers_for_cell_type")
    def test_get_markers_with_object_response(self, mock_get_markers):
        """Test handling of object-based CoGEx responses."""
        # Mock CoGEx returning objects instead of dicts
        mock_marker = Mock()
        mock_marker.gene = "CD3D"
        mock_marker.namespace = "hgnc"
        mock_marker.identifier = "1673"
        mock_marker.marker_type = "cell surface"
        mock_marker.evidence = "experimental"
        mock_marker.tissue = "blood"
        mock_marker.species = "human"

        mock_get_markers.return_value = [mock_marker]

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_cell_type_markers(
            cell_type="T cell",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["total_markers"] == 1
        assert result["markers"][0]["gene"]["name"] == "CD3D"


class TestGetMarkerCellTypes:
    """Test suite for get_marker_cell_types method."""

    @patch("cogex_mcp.clients.cell_marker_client.get_cell_types_for_marker")
    def test_get_cell_types_basic(self, mock_get_cell_types):
        """Test basic cell type retrieval for a marker."""
        # Mock CoGEx response
        mock_get_cell_types.return_value = [
            {
                "name": "T cell",
                "tissue": "blood",
                "species": "human",
                "marker_count": 15,
            },
            {
                "cell_type": "Thymocyte",
                "tissue": "thymus",
                "species": "human",
                "marker_count": 8,
            },
        ]

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_marker_cell_types(
            marker_gene="CD3D",
            species="human",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["marker_gene"] == "CD3D"
        assert result["species"] == "human"
        assert result["total_cell_types"] == 2
        assert len(result["cell_types"]) == 2

        # Verify first cell type
        ct1 = result["cell_types"][0]
        assert ct1["name"] == "T cell"
        assert ct1["tissue"] == "blood"
        assert ct1["species"] == "human"
        assert ct1["marker_count"] == 15

        # Verify mock was called correctly
        mock_get_cell_types.assert_called_once_with(("HGNC", "CD3D"), client=mock_neo4j_client)

    @patch("cogex_mcp.clients.cell_marker_client.get_cell_types_for_marker")
    def test_get_cell_types_with_curie(self, mock_get_cell_types):
        """Test cell type retrieval with gene CURIE."""
        mock_get_cell_types.return_value = [
            {
                "name": "T cell",
                "tissue": "blood",
                "species": "human",
                "marker_count": 15,
            },
        ]

        # Execute with CURIE
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_marker_cell_types(
            marker_gene="hgnc:1673",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["marker_gene"] == "hgnc:1673"

        # Verify mock was called with parsed CURIE
        mock_get_cell_types.assert_called_once_with(("HGNC", "1673"), client=mock_neo4j_client)

    @patch("cogex_mcp.clients.cell_marker_client.get_cell_types_for_marker")
    def test_get_cell_types_with_tissue_filter(self, mock_get_cell_types):
        """Test cell type retrieval with tissue filter."""
        # Mock CoGEx response with multiple tissues
        mock_get_cell_types.return_value = [
            {
                "name": "T cell",
                "tissue": "blood",
                "species": "human",
                "marker_count": 15,
            },
            {
                "name": "Thymocyte",
                "tissue": "thymus",
                "species": "human",
                "marker_count": 8,
            },
        ]

        # Execute with tissue filter
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_marker_cell_types(
            marker_gene="CD3D",
            tissue="blood",
            client=mock_neo4j_client,
        )

        # Verify filtering
        assert result["success"] is True
        assert result["total_cell_types"] == 1
        assert result["cell_types"][0]["name"] == "T cell"
        assert result["cell_types"][0]["tissue"] == "blood"

    @patch("cogex_mcp.clients.cell_marker_client.get_cell_types_for_marker")
    def test_get_cell_types_empty_result(self, mock_get_cell_types):
        """Test cell type retrieval with no results."""
        # Mock empty response
        mock_get_cell_types.return_value = []

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.get_marker_cell_types(
            marker_gene="UNKNOWN",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["total_cell_types"] == 0
        assert result["cell_types"] == []


class TestCheckMarkerStatus:
    """Test suite for check_marker_status method."""

    @patch("cogex_mcp.clients.cell_marker_client.is_marker_for_cell_type")
    def test_check_marker_positive(self, mock_is_marker):
        """Test checking marker status - positive result."""
        # Mock CoGEx response
        mock_is_marker.return_value = True

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.check_marker_status(
            cell_type="T cell",
            marker_gene="CD3D",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["is_marker"] is True
        assert result["cell_type"] == "T cell"
        assert result["marker_gene"] == "CD3D"
        assert result["gene_id"] == "hgnc:CD3D"

        # Verify mock was called correctly
        mock_is_marker.assert_called_once_with(
            ("HGNC", "CD3D"),
            "T cell",
            client=mock_neo4j_client,
        )

    @patch("cogex_mcp.clients.cell_marker_client.is_marker_for_cell_type")
    def test_check_marker_negative(self, mock_is_marker):
        """Test checking marker status - negative result."""
        # Mock CoGEx response
        mock_is_marker.return_value = False

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.check_marker_status(
            cell_type="B cell",
            marker_gene="CD3D",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["is_marker"] is False
        assert result["cell_type"] == "B cell"
        assert result["marker_gene"] == "CD3D"

    @patch("cogex_mcp.clients.cell_marker_client.is_marker_for_cell_type")
    def test_check_marker_with_curie(self, mock_is_marker):
        """Test checking marker status with gene CURIE."""
        # Mock CoGEx response
        mock_is_marker.return_value = True

        # Execute
        client = CellMarkerClient()
        mock_neo4j_client = Mock()
        result = client.check_marker_status(
            cell_type="T cell",
            marker_gene="hgnc:1673",
            client=mock_neo4j_client,
        )

        # Verify
        assert result["success"] is True
        assert result["is_marker"] is True
        assert result["gene_id"] == "hgnc:1673"

        # Verify mock was called with parsed CURIE
        mock_is_marker.assert_called_once_with(
            ("HGNC", "1673"),
            "T cell",
            client=mock_neo4j_client,
        )


class TestHelperMethods:
    """Test suite for helper methods."""

    def test_parse_cell_type_name(self):
        """Test cell type name normalization."""
        client = CellMarkerClient()

        # Test various formats
        assert client._parse_cell_type_name("t-cell") == "T cell"
        assert client._parse_cell_type_name("T Cell") == "T cell"
        assert client._parse_cell_type_name("b-cell") == "B cell"
        assert client._parse_cell_type_name("NK cell") == "NK cell"
        assert client._parse_cell_type_name("  Extra   Spaces  ") == "Extra Spaces"

    def test_parse_gene_id_with_curie(self):
        """Test parsing gene CURIE."""
        client = CellMarkerClient()

        # Test with CURIE
        namespace, identifier = client._parse_gene_id("hgnc:1673")
        assert namespace == "HGNC"
        assert identifier == "1673"

        # Test with lowercase namespace
        namespace, identifier = client._parse_gene_id("uniprot:P12345")
        assert namespace == "UNIPROT"
        assert identifier == "P12345"

    def test_parse_gene_id_without_curie(self):
        """Test parsing gene symbol."""
        client = CellMarkerClient()

        # Test without CURIE (assumes HGNC)
        namespace, identifier = client._parse_gene_id("CD3D")
        assert namespace == "HGNC"
        assert identifier == "CD3D"

    def test_format_marker_dict(self):
        """Test formatting marker dictionary."""
        client = CellMarkerClient()

        marker = {
            "gene": "CD3D",
            "namespace": "hgnc",
            "identifier": "1673",
            "marker_type": "cell surface",
            "evidence": "experimental",
            "tissue": "blood",
            "species": "human",
        }

        result = client._format_marker_dict(marker)

        assert result["gene"]["name"] == "CD3D"
        assert result["gene"]["curie"] == "hgnc:1673"
        assert result["gene"]["namespace"] == "hgnc"
        assert result["gene"]["identifier"] == "1673"
        assert result["marker_type"] == "cell surface"
        assert result["evidence"] == "experimental"
        assert result["tissue"] == "blood"
        assert result["species"] == "human"

    def test_format_marker_dict_with_object(self):
        """Test formatting marker from object."""
        client = CellMarkerClient()

        # Create mock object
        marker = Mock()
        marker.gene = "CD3D"
        marker.namespace = "hgnc"
        marker.identifier = "1673"
        marker.marker_type = "cell surface"
        marker.evidence = "experimental"
        marker.tissue = "blood"
        marker.species = "human"

        result = client._format_marker_dict(marker)

        assert result["gene"]["name"] == "CD3D"
        assert result["gene"]["curie"] == "hgnc:1673"

    def test_format_cell_type_dict(self):
        """Test formatting cell type dictionary."""
        client = CellMarkerClient()

        cell_type = {
            "name": "T cell",
            "tissue": "blood",
            "species": "human",
            "marker_count": 15,
        }

        result = client._format_cell_type_dict(cell_type)

        assert result["name"] == "T cell"
        assert result["tissue"] == "blood"
        assert result["species"] == "human"
        assert result["marker_count"] == 15

    def test_format_cell_type_dict_with_cell_type_field(self):
        """Test formatting cell type dict with 'cell_type' field instead of 'name'."""
        client = CellMarkerClient()

        cell_type = {
            "cell_type": "T cell",
            "tissue": "blood",
            "species": "human",
            "marker_count": 15,
        }

        result = client._format_cell_type_dict(cell_type)

        assert result["name"] == "T cell"

    def test_matches_tissue(self):
        """Test tissue filtering."""
        client = CellMarkerClient()

        # Test dict
        data_dict = {"tissue": "blood"}
        assert client._matches_tissue(data_dict, "blood") is True
        assert client._matches_tissue(data_dict, "Blood") is True  # Case insensitive
        assert client._matches_tissue(data_dict, "brain") is False

        # Test missing tissue
        data_no_tissue = {}
        assert client._matches_tissue(data_no_tissue, "blood") is False

        # Test object
        data_obj = Mock()
        data_obj.tissue = "blood"
        assert client._matches_tissue(data_obj, "blood") is True

    def test_matches_species(self):
        """Test species filtering."""
        client = CellMarkerClient()

        # Test dict
        data_dict = {"species": "human"}
        assert client._matches_species(data_dict, "human") is True
        assert client._matches_species(data_dict, "Human") is True  # Case insensitive
        assert client._matches_species(data_dict, "mouse") is False

        # Test missing species (defaults to human)
        data_no_species = {}
        assert client._matches_species(data_no_species, "human") is True
        assert client._matches_species(data_no_species, "mouse") is False
