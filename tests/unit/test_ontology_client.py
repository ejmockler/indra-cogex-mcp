"""
Unit tests for OntologyClient.

Tests all 3 public methods and helper functions with mocked CoGEx queries.
Achieves >90% code coverage without requiring real Neo4j connection.

Run with: pytest tests/unit/test_ontology_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    return MagicMock()


@pytest.fixture
def ontology_client(mock_neo4j_client):
    """OntologyClient instance with mocked Neo4j."""
    from cogex_mcp.clients.ontology_client import OntologyClient

    return OntologyClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def sample_parent_nodes():
    """
    Sample parent term nodes from CoGEx format.

    Simulates GO hierarchy:
    GO:0006915 (apoptotic process) → GO:0012501 (programmed cell death) → GO:0008219 (cell death)
    """
    nodes = []

    # Create mock nodes
    node1 = MagicMock()
    node1.db_ns = "GO"
    node1.db_id = "0012501"
    node1.name = "programmed cell death"
    node1.data = {"name": "programmed cell death"}
    nodes.append(node1)

    node2 = MagicMock()
    node2.db_ns = "GO"
    node2.db_id = "0008219"
    node2.name = "cell death"
    node2.data = {"name": "cell death"}
    nodes.append(node2)

    return nodes


@pytest.fixture
def sample_child_nodes():
    """
    Sample child term nodes from CoGEx format.

    Simulates GO hierarchy:
    GO:0008219 (cell death) → GO:0006915 (apoptotic process) → GO:0097194 (intrinsic apoptotic signaling)
    """
    nodes = []

    # Create mock nodes
    node1 = MagicMock()
    node1.db_ns = "GO"
    node1.db_id = "0006915"
    node1.name = "apoptotic process"
    node1.data = {"name": "apoptotic process"}
    nodes.append(node1)

    node2 = MagicMock()
    node2.db_ns = "GO"
    node2.db_id = "0097194"
    node2.name = "intrinsic apoptotic signaling pathway"
    node2.data = {"name": "intrinsic apoptotic signaling pathway"}
    nodes.append(node2)

    return nodes


# =============================================================================
# Test OntologyClient Initialization
# =============================================================================

class TestOntologyClientInit:
    """Test OntologyClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        from cogex_mcp.clients.ontology_client import OntologyClient

        client = OntologyClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses None)."""
        from cogex_mcp.clients.ontology_client import OntologyClient

        client = OntologyClient()
        assert client.client is None


# =============================================================================
# Test get_hierarchy Method
# =============================================================================

class TestGetHierarchy:
    """Test get_hierarchy method."""

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_get_hierarchy_parents_only(self, mock_get_parents, ontology_client, sample_parent_nodes):
        """Test getting parent hierarchy only."""
        mock_get_parents.return_value = sample_parent_nodes

        result = ontology_client.get_hierarchy(
            term="GO:0006915",  # apoptotic process
            direction="parents",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0006915"
        assert result["parents"] is not None
        assert result["children"] is None
        assert len(result["parents"]) == 2
        assert result["total_parents"] == 2
        assert result["total_children"] == 0

        # Verify parent structure
        assert result["parents"][0]["curie"] == "go:0012501"
        assert result["parents"][0]["name"] == "programmed cell death"
        assert result["parents"][0]["depth"] == 1

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_get_hierarchy_children_only(self, mock_get_children, ontology_client, sample_child_nodes):
        """Test getting child hierarchy only."""
        mock_get_children.return_value = sample_child_nodes

        result = ontology_client.get_hierarchy(
            term="GO:0008219",  # cell death
            direction="children",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0008219"
        assert result["parents"] is None
        assert result["children"] is not None
        assert len(result["children"]) == 2
        assert result["total_parents"] == 0
        assert result["total_children"] == 2

        # Verify child structure
        assert result["children"][0]["curie"] == "go:0006915"
        assert result["children"][0]["name"] == "apoptotic process"
        assert result["children"][0]["depth"] == 1

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_get_hierarchy_both_directions(
        self, mock_get_children, mock_get_parents, ontology_client,
        sample_parent_nodes, sample_child_nodes
    ):
        """Test getting both parent and child hierarchy."""
        mock_get_parents.return_value = sample_parent_nodes
        mock_get_children.return_value = sample_child_nodes

        result = ontology_client.get_hierarchy(
            term="GO:0006915",  # apoptotic process
            direction="both",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0006915"
        assert result["parents"] is not None
        assert result["children"] is not None
        assert result["total_parents"] == 2
        assert result["total_children"] == 2

    def test_get_hierarchy_invalid_direction(self, ontology_client):
        """Test error handling for invalid direction."""
        with pytest.raises(ValueError, match="Invalid direction"):
            ontology_client.get_hierarchy(
                term="GO:0006915",
                direction="sideways",  # Invalid
                max_depth=2,
            )

    def test_get_hierarchy_invalid_depth_too_low(self, ontology_client):
        """Test error handling for depth < 1."""
        with pytest.raises(ValueError, match="Invalid max_depth"):
            ontology_client.get_hierarchy(
                term="GO:0006915",
                direction="parents",
                max_depth=0,  # Too low
            )

    def test_get_hierarchy_invalid_depth_too_high(self, ontology_client):
        """Test error handling for depth > 5."""
        with pytest.raises(ValueError, match="Invalid max_depth"):
            ontology_client.get_hierarchy(
                term="GO:0006915",
                direction="parents",
                max_depth=10,  # Too high
            )

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_get_hierarchy_hpo_term(self, mock_get_parents, ontology_client):
        """Test with HPO (Human Phenotype Ontology) term."""
        mock_get_parents.return_value = []

        result = ontology_client.get_hierarchy(
            term="HP:0001250",  # Seizures
            direction="parents",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "HP:0001250"

        # Verify term was parsed correctly
        mock_get_parents.assert_called()
        call_args = mock_get_parents.call_args[0][0]
        assert call_args == ("HP", "0001250")


# =============================================================================
# Test get_parent_terms Method
# =============================================================================

class TestGetParentTerms:
    """Test get_parent_terms method."""

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_get_parent_terms_basic(self, mock_get_parents, ontology_client, sample_parent_nodes):
        """Test basic parent term retrieval."""
        mock_get_parents.return_value = sample_parent_nodes

        result = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0006915"
        assert len(result["parents"]) == 2
        assert result["total_parents"] == 2

        # Verify CoGEx query
        mock_get_parents.assert_called()
        call_args = mock_get_parents.call_args[0][0]
        assert call_args == ("GO", "0006915")

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_get_parent_terms_empty_result(self, mock_get_parents, ontology_client):
        """Test term with no parents (root term)."""
        mock_get_parents.return_value = []

        result = ontology_client.get_parent_terms(
            term="GO:0008150",  # biological_process (root)
            max_depth=2,
        )

        assert result["success"] is True
        assert len(result["parents"]) == 0
        assert result["total_parents"] == 0

    def test_get_parent_terms_invalid_depth(self, ontology_client):
        """Test error handling for invalid depth."""
        with pytest.raises(ValueError, match="Invalid max_depth"):
            ontology_client.get_parent_terms(
                term="GO:0006915",
                max_depth=0,
            )

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_get_parent_terms_single_depth(self, mock_get_parents, ontology_client, sample_parent_nodes):
        """Test single-level parent query."""
        # Only return first level parents
        mock_get_parents.return_value = [sample_parent_nodes[0]]

        result = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=1,
        )

        assert result["success"] is True
        assert len(result["parents"]) == 1
        assert result["parents"][0]["depth"] == 1


# =============================================================================
# Test get_child_terms Method
# =============================================================================

class TestGetChildTerms:
    """Test get_child_terms method."""

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_get_child_terms_basic(self, mock_get_children, ontology_client, sample_child_nodes):
        """Test basic child term retrieval."""
        mock_get_children.return_value = sample_child_nodes

        result = ontology_client.get_child_terms(
            term="GO:0008219",
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "GO:0008219"
        assert len(result["children"]) == 2
        assert result["total_children"] == 2

        # Verify CoGEx query
        mock_get_children.assert_called()
        call_args = mock_get_children.call_args[0][0]
        assert call_args == ("GO", "0008219")

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_get_child_terms_empty_result(self, mock_get_children, ontology_client):
        """Test term with no children (leaf term)."""
        mock_get_children.return_value = []

        result = ontology_client.get_child_terms(
            term="GO:0097194",  # Leaf term
            max_depth=2,
        )

        assert result["success"] is True
        assert len(result["children"]) == 0
        assert result["total_children"] == 0

    def test_get_child_terms_invalid_depth(self, ontology_client):
        """Test error handling for invalid depth."""
        with pytest.raises(ValueError, match="Invalid max_depth"):
            ontology_client.get_child_terms(
                term="GO:0008219",
                max_depth=6,
            )

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_get_child_terms_mondo_disease(self, mock_get_children, ontology_client):
        """Test with MONDO disease ontology term."""
        mock_get_children.return_value = []

        result = ontology_client.get_child_terms(
            term="MONDO:0004975",  # Alzheimer's disease
            max_depth=2,
        )

        assert result["success"] is True
        assert result["term"] == "MONDO:0004975"

        # Verify term was parsed correctly
        call_args = mock_get_children.call_args[0][0]
        assert call_args == ("MONDO", "0004975")


# =============================================================================
# Test Helper Methods
# =============================================================================

class TestHelperMethods:
    """Test internal helper methods."""

    def test_parse_term_id_go_term(self, ontology_client):
        """Test parsing GO term CURIE."""
        namespace, identifier = ontology_client._parse_term_id("GO:0006915")

        assert namespace == "GO"
        assert identifier == "0006915"

    def test_parse_term_id_hpo_term(self, ontology_client):
        """Test parsing HPO term CURIE."""
        namespace, identifier = ontology_client._parse_term_id("HP:0001250")

        assert namespace == "HP"
        assert identifier == "0001250"

    def test_parse_term_id_mondo_term(self, ontology_client):
        """Test parsing MONDO term CURIE."""
        namespace, identifier = ontology_client._parse_term_id("MONDO:0004975")

        assert namespace == "MONDO"
        assert identifier == "0004975"

    def test_parse_term_id_lowercase_namespace(self, ontology_client):
        """Test that lowercase namespaces are uppercased."""
        namespace, identifier = ontology_client._parse_term_id("go:0006915")

        assert namespace == "GO"
        assert identifier == "0006915"

    def test_parse_term_id_no_colon(self, ontology_client):
        """Test error handling for term without colon."""
        with pytest.raises(ValueError, match="Invalid term format"):
            ontology_client._parse_term_id("GO0006915")

    def test_parse_term_id_empty_namespace(self, ontology_client):
        """Test error handling for empty namespace."""
        with pytest.raises(ValueError, match="Empty namespace"):
            ontology_client._parse_term_id(":0006915")

    def test_parse_term_id_empty_identifier(self, ontology_client):
        """Test error handling for empty identifier."""
        with pytest.raises(ValueError, match="Empty identifier"):
            ontology_client._parse_term_id("GO:")

    def test_format_term_dict_basic(self, ontology_client):
        """Test formatting term node to dictionary."""
        node = MagicMock()
        node.db_ns = "GO"
        node.db_id = "0006915"
        node.name = "apoptotic process"
        node.data = {"name": "apoptotic process"}

        formatted = ontology_client._format_term_dict(node, depth=1)

        assert formatted["curie"] == "go:0006915"
        assert formatted["name"] == "apoptotic process"
        assert formatted["namespace"] == "go"
        assert formatted["identifier"] == "0006915"
        assert formatted["depth"] == 1
        assert formatted["relationship"] == "is_a"

    def test_format_term_dict_no_name_attribute(self, ontology_client):
        """Test formatting node without name attribute."""
        node = MagicMock()
        node.db_ns = "GO"
        node.db_id = "0006915"
        node.data = {"name": "apoptotic process"}
        delattr(node, "name")

        formatted = ontology_client._format_term_dict(node, depth=2)

        assert formatted["name"] == "apoptotic process"
        assert formatted["depth"] == 2

    def test_format_term_dict_no_name_fallback(self, ontology_client):
        """Test formatting node with no name uses curie as fallback."""
        node = MagicMock()
        node.db_ns = "GO"
        node.db_id = "0006915"
        node.data = {}
        delattr(node, "name")

        formatted = ontology_client._format_term_dict(node, depth=1)

        assert formatted["name"] == "GO:0006915"

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_traverse_hierarchy_parents(self, mock_get_parents, ontology_client, sample_parent_nodes):
        """Test hierarchical traversal for parents."""
        mock_get_parents.return_value = sample_parent_nodes

        from cogex_mcp.clients.ontology_client import OntologyClient
        from unittest.mock import MagicMock
        mock_client = MagicMock()

        result = ontology_client._traverse_hierarchy(
            term="GO:0006915",
            direction="parents",
            max_depth=2,
            client=mock_client,
        )

        assert len(result) > 0
        assert all(term["depth"] >= 1 for term in result)

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_traverse_hierarchy_children(self, mock_get_children, ontology_client, sample_child_nodes):
        """Test hierarchical traversal for children."""
        mock_get_children.return_value = sample_child_nodes

        from unittest.mock import MagicMock
        mock_client = MagicMock()

        result = ontology_client._traverse_hierarchy(
            term="GO:0008219",
            direction="children",
            max_depth=2,
            client=mock_client,
        )

        assert len(result) > 0
        assert all(term["depth"] >= 1 for term in result)

    def test_traverse_hierarchy_invalid_direction(self, ontology_client):
        """Test error handling for invalid direction in traversal."""
        from unittest.mock import MagicMock
        mock_client = MagicMock()

        with pytest.raises(ValueError, match="Invalid direction"):
            ontology_client._traverse_hierarchy(
                term="GO:0006915",
                direction="sideways",
                max_depth=2,
                client=mock_client,
            )


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_empty_parent_list(self, mock_get_parents, ontology_client):
        """Test handling empty parent list."""
        mock_get_parents.return_value = []

        result = ontology_client.get_parent_terms(term="GO:0008150")

        assert result["success"] is True
        assert result["parents"] == []
        assert result["total_parents"] == 0

    @patch("cogex_mcp.clients.ontology_client.get_ontology_child_terms")
    def test_empty_child_list(self, mock_get_children, ontology_client):
        """Test handling empty child list."""
        mock_get_children.return_value = []

        result = ontology_client.get_child_terms(term="GO:0097194")

        assert result["success"] is True
        assert result["children"] == []
        assert result["total_children"] == 0

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_max_depth_limit(self, mock_get_parents, ontology_client, sample_parent_nodes):
        """Test that max_depth is enforced."""
        mock_get_parents.return_value = sample_parent_nodes

        result = ontology_client.get_parent_terms(
            term="GO:0006915",
            max_depth=1,
        )

        assert result["success"] is True
        # Should only get depth 1 terms
        assert all(term["depth"] == 1 for term in result["parents"])

    @patch("cogex_mcp.clients.ontology_client.get_ontology_parent_terms")
    def test_query_error_handling(self, mock_get_parents, ontology_client):
        """Test graceful handling of query errors."""
        mock_get_parents.side_effect = Exception("Neo4j connection error")

        # Should not raise, but log warning
        from unittest.mock import MagicMock
        mock_client = MagicMock()

        result = ontology_client._traverse_hierarchy(
            term="GO:0006915",
            direction="parents",
            max_depth=1,
            client=mock_client,
        )

        # Should return empty list on error
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
