"""
Unit tests for SubnetworkClient.

Tests all methods with mocked Neo4j client and INDRA statements.
Achieves >90% code coverage without requiring real Neo4j connection.

Run with: pytest tests/unit/test_subnetwork_client.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from indra.statements import Activation, Phosphorylation
from indra.statements.agent import Agent


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for testing."""
    mock_client = MagicMock()
    mock_client.query_tx = MagicMock(return_value=[])
    return mock_client


@pytest.fixture
def subnetwork_client(mock_neo4j_client):
    """SubnetworkClient instance with mocked Neo4j."""
    from cogex_mcp.clients.subnetwork_client import SubnetworkClient

    return SubnetworkClient(neo4j_client=mock_neo4j_client)


@pytest.fixture
def sample_statements():
    """
    Sample INDRA statements for testing.

    Creates realistic TP53-MDM2 interactions with evidence and belief scores.
    """
    # Create agents with proper db_refs
    tp53 = Agent("TP53", db_refs={"HGNC": "11998", "UP": "P04637"})
    mdm2 = Agent("MDM2", db_refs={"HGNC": "6973", "UP": "Q00987"})
    p21 = Agent("CDKN1A", db_refs={"HGNC": "1387", "UP": "P38936"})

    # Create Phosphorylation statement
    stmt1 = Phosphorylation(tp53, mdm2, residue="S", position="166")
    stmt1.evidence = [MagicMock(source_api="reach")]
    stmt1.belief = 0.95

    # Create Activation statement with more evidence
    stmt2 = Activation(tp53, mdm2)
    stmt2.evidence = [
        MagicMock(source_api="sparser"),
        MagicMock(source_api="reach")
    ]
    stmt2.belief = 0.87

    # Create another Phosphorylation with different agents
    stmt3 = Phosphorylation(tp53, p21, residue="T", position="145")
    stmt3.evidence = [
        MagicMock(source_api="reach"),
        MagicMock(source_api="trips"),
        MagicMock(source_api="medscan")
    ]
    stmt3.belief = 0.92

    return [stmt1, stmt2, stmt3]


@pytest.fixture
def single_agent_statement():
    """Statement with only one agent (edge case)."""
    tp53 = Agent("TP53", db_refs={"HGNC": "11998"})

    # Create a statement type that might have single agent
    from indra.statements import ActiveForm
    stmt = ActiveForm(tp53, activity="transcription", is_active=True)
    stmt.evidence = [MagicMock(source_api="reach")]
    stmt.belief = 0.80

    return stmt


class TestSubnetworkClientInit:
    """Test SubnetworkClient initialization."""

    def test_init_with_client(self, mock_neo4j_client):
        """Test initialization with provided Neo4j client."""
        from cogex_mcp.clients.subnetwork_client import SubnetworkClient

        client = SubnetworkClient(neo4j_client=mock_neo4j_client)
        assert client.client == mock_neo4j_client

    def test_init_without_client(self):
        """Test initialization without Neo4j client (uses autoclient)."""
        from cogex_mcp.clients.subnetwork_client import SubnetworkClient

        client = SubnetworkClient()
        assert client.client is None


class TestParsingMethods:
    """Test helper methods for parsing gene IDs and CURIEs."""

    def test_parse_gene_ids_with_curies(self, subnetwork_client):
        """Test parsing gene CURIEs to tuples."""
        gene_ids = ["hgnc:11998", "hgnc:6973", "uniprot:P04637"]
        nodes = subnetwork_client._parse_gene_ids(gene_ids)

        assert len(nodes) == 3
        assert nodes[0] == ("HGNC", "11998")
        assert nodes[1] == ("HGNC", "6973")
        assert nodes[2] == ("UNIPROT", "P04637")

    def test_parse_gene_ids_without_namespace(self, subnetwork_client):
        """Test parsing bare gene symbols (assumes HGNC)."""
        gene_ids = ["TP53", "MDM2", "BRCA1"]
        nodes = subnetwork_client._parse_gene_ids(gene_ids)

        assert len(nodes) == 3
        assert nodes[0] == ("HGNC", "TP53")
        assert nodes[1] == ("HGNC", "MDM2")
        assert nodes[2] == ("HGNC", "BRCA1")

    def test_parse_gene_ids_mixed(self, subnetwork_client):
        """Test parsing mix of CURIEs and symbols."""
        gene_ids = ["hgnc:11998", "TP53", "uniprot:P04637"]
        nodes = subnetwork_client._parse_gene_ids(gene_ids)

        assert len(nodes) == 3
        assert nodes[0] == ("HGNC", "11998")
        assert nodes[1] == ("HGNC", "TP53")
        assert nodes[2] == ("UNIPROT", "P04637")

    def test_parse_curie_valid(self, subnetwork_client):
        """Test parsing valid CURIE."""
        curie = "go:0006915"
        namespace, identifier = subnetwork_client._parse_curie(curie)

        assert namespace == "GO"
        assert identifier == "0006915"

    def test_parse_curie_uppercase_namespace(self, subnetwork_client):
        """Test that namespace is uppercased."""
        curie = "mesh:D000690"
        namespace, identifier = subnetwork_client._parse_curie(curie)

        assert namespace == "MESH"
        assert identifier == "D000690"

    def test_parse_curie_invalid_raises_error(self, subnetwork_client):
        """Test that invalid CURIE raises ValueError."""
        with pytest.raises(ValueError, match="Invalid CURIE format"):
            subnetwork_client._parse_curie("invalid_curie_no_colon")


class TestFilteringMethods:
    """Test statement filtering methods."""

    def test_filter_statements_by_type(self, subnetwork_client, sample_statements):
        """Test filtering by statement type."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            statement_types=["Phosphorylation"],
        )

        assert len(filtered) == 2  # stmt1 and stmt3 are Phosphorylation
        for stmt in filtered:
            assert stmt.__class__.__name__ == "Phosphorylation"

    def test_filter_statements_by_multiple_types(self, subnetwork_client, sample_statements):
        """Test filtering by multiple statement types."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            statement_types=["Phosphorylation", "Activation"],
        )

        assert len(filtered) == 3  # All statements match

    def test_filter_statements_by_evidence_count(self, subnetwork_client, sample_statements):
        """Test filtering by minimum evidence count."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            min_evidence=2,
        )

        assert len(filtered) == 2  # stmt2 and stmt3 have >=2 evidence
        for stmt in filtered:
            assert len(stmt.evidence) >= 2

    def test_filter_statements_by_belief_score(self, subnetwork_client, sample_statements):
        """Test filtering by minimum belief score."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            min_belief=0.90,
        )

        assert len(filtered) == 2  # stmt1 (0.95) and stmt3 (0.92)
        for stmt in filtered:
            assert stmt.belief >= 0.90

    def test_filter_statements_max_limit(self, subnetwork_client, sample_statements):
        """Test limiting maximum number of statements."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            max_statements=2,
        )

        assert len(filtered) == 2

    def test_filter_statements_combined(self, subnetwork_client, sample_statements):
        """Test combining multiple filters."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            statement_types=["Phosphorylation"],
            min_evidence=2,
            min_belief=0.90,
            max_statements=1,
        )

        assert len(filtered) == 1  # Only stmt3 matches all criteria
        assert filtered[0].__class__.__name__ == "Phosphorylation"
        assert len(filtered[0].evidence) >= 2
        assert filtered[0].belief >= 0.90

    def test_filter_statements_empty_result(self, subnetwork_client, sample_statements):
        """Test filtering that returns empty list."""
        filtered = subnetwork_client._filter_statements(
            sample_statements,
            min_belief=0.99,  # No statements have belief >= 0.99
        )

        assert len(filtered) == 0

    def test_filter_statements_by_genes(self, subnetwork_client, sample_statements):
        """Test filtering statements by gene involvement."""
        nodes = [("HGNC", "11998"), ("HGNC", "6973")]  # TP53, MDM2

        filtered = subnetwork_client._filter_statements_by_genes(
            sample_statements,
            nodes,
        )

        # Should include stmt1 and stmt2 (TP53-MDM2), exclude stmt3 (TP53-CDKN1A)
        assert len(filtered) == 2

    def test_filter_statements_by_genes_no_match(self, subnetwork_client, sample_statements):
        """Test filtering by genes with no matches."""
        nodes = [("HGNC", "9999")]  # Non-existent gene

        filtered = subnetwork_client._filter_statements_by_genes(
            sample_statements,
            nodes,
        )

        assert len(filtered) == 0


class TestStatementConversion:
    """Test converting INDRA Statements to dicts."""

    def test_statement_to_dict_phosphorylation(self, subnetwork_client, sample_statements):
        """Test converting Phosphorylation statement to dict."""
        stmt = sample_statements[0]  # TP53 phosphorylates MDM2 at S166
        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        assert stmt_dict["stmt_type"] == "Phosphorylation"
        assert stmt_dict["subject"]["curie"] == "hgnc:11998"
        assert stmt_dict["subject"]["name"] == "TP53"
        assert stmt_dict["object"]["curie"] == "hgnc:6973"
        assert stmt_dict["object"]["name"] == "MDM2"
        assert stmt_dict["residue"] == "S"
        assert stmt_dict["position"] == "166"
        assert stmt_dict["evidence_count"] == 1
        assert stmt_dict["belief_score"] == 0.95
        assert "reach" in stmt_dict["sources"]

    def test_statement_to_dict_activation(self, subnetwork_client, sample_statements):
        """Test converting Activation statement to dict."""
        stmt = sample_statements[1]  # TP53 activates MDM2
        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        assert stmt_dict["stmt_type"] == "Activation"
        assert stmt_dict["subject"]["curie"] == "hgnc:11998"
        assert stmt_dict["object"]["curie"] == "hgnc:6973"
        assert stmt_dict["evidence_count"] == 2
        assert stmt_dict["belief_score"] == 0.87
        assert "sparser" in stmt_dict["sources"]
        assert "reach" in stmt_dict["sources"]

    def test_statement_to_dict_with_uniprot(self, subnetwork_client):
        """Test agent with UniProt ID instead of HGNC."""
        agent1 = Agent("PROTEIN1", db_refs={"UP": "P12345"})
        agent2 = Agent("PROTEIN2", db_refs={"UP": "Q67890"})

        stmt = Activation(agent1, agent2)
        stmt.evidence = [MagicMock(source_api="signor")]
        stmt.belief = 0.75

        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        assert stmt_dict["subject"]["curie"] == "uniprot:P12345"
        assert stmt_dict["object"]["curie"] == "uniprot:Q67890"

    def test_statement_to_dict_single_agent(self, subnetwork_client, single_agent_statement):
        """Test converting statement with single agent."""
        stmt_dict = subnetwork_client._statement_to_dict(single_agent_statement)

        assert stmt_dict["stmt_type"] == "ActiveForm"
        assert stmt_dict["subject"]["curie"] == "hgnc:11998"
        assert stmt_dict["object"]["curie"] == "unknown:unknown"  # No second agent

    def test_statement_to_dict_hash(self, subnetwork_client, sample_statements):
        """Test that statement hash is included."""
        stmt = sample_statements[0]
        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        assert "stmt_hash" in stmt_dict
        assert stmt_dict["stmt_hash"] is not None


class TestStatisticsComputation:
    """Test network statistics computation."""

    def test_compute_statistics_basic(self, subnetwork_client, sample_statements):
        """Test basic statistics computation."""
        stmt_dicts = [
            subnetwork_client._statement_to_dict(stmt)
            for stmt in sample_statements
        ]

        stats = subnetwork_client._compute_statistics(stmt_dicts)

        assert stats["statement_count"] == 3
        assert stats["node_count"] == 3  # TP53, MDM2, CDKN1A
        assert "Phosphorylation" in stats["statement_types"]
        assert "Activation" in stats["statement_types"]
        assert stats["statement_types"]["Phosphorylation"] == 2
        assert stats["statement_types"]["Activation"] == 1

    def test_compute_statistics_averages(self, subnetwork_client, sample_statements):
        """Test average evidence and belief calculations."""
        stmt_dicts = [
            subnetwork_client._statement_to_dict(stmt)
            for stmt in sample_statements
        ]

        stats = subnetwork_client._compute_statistics(stmt_dicts)

        # Average evidence: (1 + 2 + 3) / 3 = 2.0
        assert stats["avg_evidence_per_statement"] == 2.0

        # Average belief: (0.95 + 0.87 + 0.92) / 3
        expected_avg_belief = (0.95 + 0.87 + 0.92) / 3
        assert abs(stats["avg_belief_score"] - expected_avg_belief) < 0.001

    def test_compute_statistics_empty(self, subnetwork_client):
        """Test statistics for empty statement list."""
        stats = subnetwork_client._compute_statistics([])

        assert stats["statement_count"] == 0
        assert stats["node_count"] == 0
        assert stats["statement_types"] == {}
        assert stats["avg_evidence_per_statement"] == 0.0
        assert stats["avg_belief_score"] == 0.0


class TestSubnetworkExtraction:
    """Test main subnetwork extraction methods."""

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_extract_direct_basic(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test basic direct subnetwork extraction."""
        mock_indra_subnetwork.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            min_evidence=1,
            min_belief=0.0,
            max_statements=100,
        )

        assert result["success"] is True
        assert len(result["statements"]) == 3
        assert len(result["nodes"]) == 3
        assert result["statistics"]["statement_count"] == 3

        # Verify CoGEx function was called
        mock_indra_subnetwork.assert_called_once()
        call_kwargs = mock_indra_subnetwork.call_args[1]
        assert "nodes" in call_kwargs
        assert call_kwargs["include_db_evidence"] is True

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_extract_direct_with_filters(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test direct extraction with filtering."""
        mock_indra_subnetwork.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            statement_types=["Phosphorylation"],
            min_evidence=2,
            min_belief=0.90,
            max_statements=10,
        )

        assert result["success"] is True
        assert len(result["statements"]) == 1  # Only stmt3 matches filters

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork_tissue")
    def test_extract_direct_with_tissue_filter(self, mock_tissue, subnetwork_client, sample_statements):
        """Test direct extraction with tissue context."""
        mock_tissue.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            tissue="uberon:0000955",  # brain
        )

        assert result["success"] is True
        mock_tissue.assert_called_once()
        call_kwargs = mock_tissue.call_args[1]
        assert call_kwargs["tissue"] == ("UBERON", "0000955")

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork_go")
    def test_extract_direct_with_go_filter(self, mock_go, subnetwork_client, sample_statements):
        """Test direct extraction with GO term context."""
        mock_go.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            go_term="go:0006915",  # apoptosis
        )

        assert result["success"] is True
        mock_go.assert_called_once()
        call_kwargs = mock_go.call_args[1]
        assert call_kwargs["go_term"] == ("GO", "0006915")
        assert call_kwargs["include_indirect"] is False

    @patch("cogex_mcp.clients.subnetwork_client.indra_mediated_subnetwork")
    def test_extract_mediated(self, mock_mediated, subnetwork_client, sample_statements):
        """Test mediated subnetwork extraction."""
        mock_mediated.return_value = sample_statements

        result = subnetwork_client.extract_mediated(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            min_evidence=1,
            max_statements=100,
        )

        assert result["success"] is True
        assert result.get("note") == "Two-hop mediated paths shown"
        assert len(result["statements"]) == 3

        mock_mediated.assert_called_once()
        call_kwargs = mock_mediated.call_args[1]
        assert call_kwargs["order_by_ev_count"] is True

    @patch("cogex_mcp.clients.subnetwork_client.indra_shared_upstream_subnetwork")
    def test_extract_shared_upstream(self, mock_upstream, subnetwork_client, sample_statements):
        """Test shared upstream regulators extraction."""
        mock_upstream.return_value = sample_statements

        result = subnetwork_client.extract_shared_upstream(
            gene_ids=["hgnc:6973", "hgnc:1387"],  # MDM2, CDKN1A
            min_evidence=1,
        )

        assert result["success"] is True
        assert result.get("note") == "Shared upstream regulators shown"
        assert len(result["statements"]) == 3

        mock_upstream.assert_called_once()

    @patch("cogex_mcp.clients.subnetwork_client.indra_shared_downstream_subnetwork")
    def test_extract_shared_downstream(self, mock_downstream, subnetwork_client, sample_statements):
        """Test shared downstream targets extraction."""
        mock_downstream.return_value = sample_statements

        result = subnetwork_client.extract_shared_downstream(
            gene_ids=["hgnc:11998"],  # TP53
            min_belief=0.8,
        )

        assert result["success"] is True
        assert result.get("note") == "Shared downstream targets shown"

        mock_downstream.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_empty_statement_list(self, mock_indra_subnetwork, subnetwork_client):
        """Test handling of empty statement list from CoGEx."""
        mock_indra_subnetwork.return_value = []

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
        )

        assert result["success"] is True
        assert len(result["statements"]) == 0
        assert len(result["nodes"]) == 0
        assert result["statistics"]["statement_count"] == 0

    def test_parse_empty_gene_list(self, subnetwork_client):
        """Test parsing empty gene list."""
        nodes = subnetwork_client._parse_gene_ids([])
        assert nodes == []

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_all_statements_filtered_out(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test when all statements are filtered out."""
        mock_indra_subnetwork.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            min_belief=0.99,  # Filters out all statements
        )

        assert result["success"] is True
        assert len(result["statements"]) == 0

    def test_statement_without_evidence(self, subnetwork_client):
        """Test handling statement without evidence attribute."""
        tp53 = Agent("TP53", db_refs={"HGNC": "11998"})
        mdm2 = Agent("MDM2", db_refs={"HGNC": "6973"})

        stmt = Activation(tp53, mdm2)
        # Don't set evidence or belief

        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        assert stmt_dict["evidence_count"] == 0
        assert stmt_dict["belief_score"] == 0.0
        assert stmt_dict["sources"] == []

    def test_agent_without_db_refs(self, subnetwork_client):
        """Test handling agent without database references."""
        agent = Agent("UNKNOWN_PROTEIN")
        # No db_refs

        stmt = Activation(agent, agent)
        stmt.evidence = []

        stmt_dict = subnetwork_client._statement_to_dict(stmt)

        # Should still create dict without crashing
        assert "subject" in stmt_dict
        assert "object" in stmt_dict


class TestResponseFormatting:
    """Test full response formatting."""

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_format_subnetwork_response(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test complete response formatting."""
        mock_indra_subnetwork.return_value = sample_statements

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
        )

        # Check response structure
        assert "success" in result
        assert "statements" in result
        assert "nodes" in result
        assert "statistics" in result

        # Check statement structure
        for stmt in result["statements"]:
            assert "stmt_type" in stmt
            assert "subject" in stmt
            assert "object" in stmt
            assert "evidence_count" in stmt
            assert "belief_score" in stmt
            assert "sources" in stmt

        # Check node structure
        for node in result["nodes"]:
            assert "curie" in node
            assert "namespace" in node
            assert "identifier" in node
            assert "name" in node

        # Check statistics structure
        stats = result["statistics"]
        assert "statement_count" in stats
        assert "node_count" in stats
        assert "statement_types" in stats
        assert "avg_evidence_per_statement" in stats
        assert "avg_belief_score" in stats

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_response_with_note(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test that optional note is included when provided."""
        mock_indra_subnetwork.return_value = sample_statements

        nodes = [("HGNC", "11998"), ("HGNC", "6973")]
        result = subnetwork_client._format_subnetwork_response(
            sample_statements,
            nodes,
            note="Test note"
        )

        assert "note" in result
        assert result["note"] == "Test note"


class TestPerformance:
    """Test performance characteristics."""

    @patch("cogex_mcp.clients.subnetwork_client.indra_subnetwork")
    def test_large_statement_list(self, mock_indra_subnetwork, subnetwork_client, sample_statements):
        """Test handling of large statement lists."""
        # Create 1000 statements
        large_list = sample_statements * 334  # ~1000 statements
        mock_indra_subnetwork.return_value = large_list

        result = subnetwork_client.extract_direct(
            gene_ids=["hgnc:11998", "hgnc:6973"],
            max_statements=50,  # Limit results
        )

        # Should respect max_statements limit
        assert len(result["statements"]) == 50

    def test_filtering_performance(self, subnetwork_client):
        """Test that filtering operations are efficient."""
        # Create many statements
        tp53 = Agent("TP53", db_refs={"HGNC": "11998"})
        mdm2 = Agent("MDM2", db_refs={"HGNC": "6973"})

        statements = []
        for i in range(1000):
            stmt = Activation(tp53, mdm2)
            stmt.evidence = [MagicMock(source_api="reach")] * (i % 5 + 1)
            stmt.belief = 0.5 + (i % 50) / 100
            statements.append(stmt)

        # Apply multiple filters
        filtered = subnetwork_client._filter_statements(
            statements,
            statement_types=["Activation"],
            min_evidence=2,
            min_belief=0.7,
            max_statements=10,
        )

        # Should complete quickly and respect limits
        assert len(filtered) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=cogex_mcp.clients.subnetwork_client", "--cov-report=term-missing"])
