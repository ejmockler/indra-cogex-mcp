"""
Unit tests for LiteratureClient.

Mocks all CoGEx function calls to test:
- All 4 public methods
- Helper methods
- Statement formatting
- Evidence formatting
- Publication formatting
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from cogex_mcp.clients.literature_client import LiteratureClient


# Test fixtures

@pytest.fixture
def literature_client():
    """Create LiteratureClient instance for testing."""
    return LiteratureClient()


@pytest.fixture
def mock_statement():
    """Create mock INDRA Statement for TP53 → MDM2 phosphorylation."""
    stmt = Mock()
    stmt.__class__.__name__ = "Phosphorylation"

    # Mock get_hash
    stmt.get_hash = Mock(return_value=-31347186125831290)

    # Mock agents
    subj = Mock()
    subj.name = "TP53"
    subj.db_refs = {"HGNC": "11998", "UP": "P04637"}

    obj = Mock()
    obj.name = "MDM2"
    obj.db_refs = {"HGNC": "6973", "UP": "Q00987"}

    stmt.agent_list = Mock(return_value=[subj, obj])

    # Mock evidence
    ev1 = Mock()
    ev1.source_api = "reach"
    ev1.pmid = "28746307"
    ev1.text = "TP53 phosphorylates MDM2 at serine 166."

    ev2 = Mock()
    ev2.source_api = "sparser"
    ev2.pmid = "28746307"
    ev2.text = "p53 was found to phosphorylate Mdm2."

    stmt.evidence = [ev1, ev2]
    stmt.belief = 0.95

    # Statement-specific attributes
    stmt.residue = "S"
    stmt.position = "166"

    return stmt


@pytest.fixture
def mock_evidence():
    """Create mock Evidence object."""
    ev = Mock()
    ev.text = "TP53 phosphorylates MDM2 at serine 166."
    ev.pmid = "28746307"
    ev.source_api = "reach"
    ev.annotations = {
        "pmid": "28746307",
        "source_api": "reach",
        "found_by": "Phosphorylation_syntax_1",
    }
    return ev


@pytest.fixture
def mock_statement_complex():
    """Create mock Statement with single agent (for edge cases)."""
    stmt = Mock()
    stmt.__class__.__name__ = "ActiveForm"
    stmt.get_hash = Mock(return_value=-12345678901234567)

    agent = Mock()
    agent.name = "MAPK1"
    agent.db_refs = {"HGNC": "6871"}

    stmt.agent_list = Mock(return_value=[agent])
    stmt.evidence = []
    stmt.belief = 0.8

    return stmt


# Test Class 1: TestGetPaperStatements

class TestGetPaperStatements:
    """Test get_paper_statements method."""

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    def test_basic_query(self, mock_get_stmts, literature_client, mock_statement):
        """Test basic statement retrieval for PMID."""
        mock_get_stmts.return_value = [(mock_statement, {})]

        result = literature_client.get_paper_statements(
            "28746307",
            include_evidence_text=False,
            client=Mock(),
        )

        assert result["success"] is True
        assert result["pmid"] == "28746307"
        assert result["total_statements"] == 1
        assert len(result["statements"]) == 1

        stmt = result["statements"][0]
        assert stmt["stmt_type"] == "Phosphorylation"
        assert stmt["subject"]["name"] == "TP53"
        assert stmt["object"]["name"] == "MDM2"

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_with_evidence_text(
        self,
        mock_get_evidence,
        mock_get_stmts,
        literature_client,
        mock_statement,
        mock_evidence,
    ):
        """Test statement retrieval with evidence text."""
        mock_get_stmts.return_value = [(mock_statement, {})]
        mock_get_evidence.return_value = [mock_evidence]

        result = literature_client.get_paper_statements(
            "28746307",
            include_evidence_text=True,
            max_evidence_per_statement=5,
            client=Mock(),
        )

        assert result["success"] is True
        assert len(result["statements"]) == 1

        stmt = result["statements"][0]
        assert "evidence" in stmt
        assert len(stmt["evidence"]) == 1
        assert stmt["evidence"][0]["text"] == "TP53 phosphorylates MDM2 at serine 166."

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_max_evidence_limit(
        self,
        mock_get_evidence,
        mock_get_stmts,
        literature_client,
        mock_statement,
    ):
        """Test max_evidence_per_statement limit."""
        mock_get_stmts.return_value = [(mock_statement, {})]

        # Create 10 evidence objects
        evidence_list = []
        for i in range(10):
            ev = Mock()
            ev.text = f"Evidence text {i}"
            ev.pmid = "28746307"
            ev.source_api = "reach"
            ev.annotations = {}
            evidence_list.append(ev)

        mock_get_evidence.return_value = evidence_list

        result = literature_client.get_paper_statements(
            "28746307",
            include_evidence_text=True,
            max_evidence_per_statement=3,
            client=Mock(),
        )

        stmt = result["statements"][0]
        # Should be limited to 3
        assert len(stmt["evidence"]) == 3

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    def test_multiple_statements(self, mock_get_stmts, literature_client):
        """Test paper with multiple statements."""
        stmt1 = Mock()
        stmt1.__class__.__name__ = "Phosphorylation"
        stmt1.get_hash = Mock(return_value=-111)
        stmt1.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt1.agent_list()[0].name = "TP53"
        stmt1.agent_list()[0].db_refs = {"HGNC": "11998"}
        stmt1.agent_list()[1].name = "MDM2"
        stmt1.agent_list()[1].db_refs = {"HGNC": "6973"}
        stmt1.evidence = []
        stmt1.belief = 0.9

        stmt2 = Mock()
        stmt2.__class__.__name__ = "Activation"
        stmt2.get_hash = Mock(return_value=-222)
        stmt2.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt2.agent_list()[0].name = "EGFR"
        stmt2.agent_list()[0].db_refs = {"HGNC": "3236"}
        stmt2.agent_list()[1].name = "MAPK1"
        stmt2.agent_list()[1].db_refs = {"HGNC": "6871"}
        stmt2.evidence = []
        stmt2.belief = 0.85

        mock_get_stmts.return_value = [(stmt1, {}), (stmt2, {})]

        result = literature_client.get_paper_statements(
            "12345678",
            include_evidence_text=False,
            client=Mock(),
        )

        assert result["total_statements"] == 2
        assert result["statements"][0]["stmt_type"] == "Phosphorylation"
        assert result["statements"][1]["stmt_type"] == "Activation"

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    def test_empty_results(self, mock_get_stmts, literature_client):
        """Test paper with no statements."""
        mock_get_stmts.return_value = []

        result = literature_client.get_paper_statements(
            "99999999",
            client=Mock(),
        )

        assert result["success"] is True
        assert result["total_statements"] == 0
        assert result["statements"] == []


# Test Class 2: TestGetStatementEvidence

class TestGetStatementEvidence:
    """Test get_statement_evidence method."""

    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_basic_query(self, mock_get_evidence, literature_client, mock_evidence):
        """Test basic evidence retrieval."""
        mock_get_evidence.return_value = [mock_evidence]

        result = literature_client.get_statement_evidence(
            "-31347186125831290",
            client=Mock(),
        )

        assert result["success"] is True
        assert result["statement_hash"] == "-31347186125831290"
        assert result["total_evidence"] == 1
        assert len(result["evidence"]) == 1

        ev = result["evidence"][0]
        assert ev["text"] == "TP53 phosphorylates MDM2 at serine 166."
        assert ev["pmid"] == "28746307"
        assert ev["source_api"] == "reach"

    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_without_text(self, mock_get_evidence, literature_client, mock_evidence):
        """Test evidence retrieval without text."""
        mock_get_evidence.return_value = [mock_evidence]

        result = literature_client.get_statement_evidence(
            "-31347186125831290",
            include_evidence_text=False,
            client=Mock(),
        )

        assert result["success"] is True
        ev = result["evidence"][0]
        assert ev["text"] is None
        assert ev["pmid"] == "28746307"

    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_multiple_evidence(self, mock_get_evidence, literature_client):
        """Test statement with multiple evidence entries."""
        evidence_list = []
        for i in range(5):
            ev = Mock()
            ev.text = f"Evidence {i}"
            ev.pmid = f"1234567{i}"
            ev.source_api = "reach"
            ev.annotations = {}
            evidence_list.append(ev)

        mock_get_evidence.return_value = evidence_list

        result = literature_client.get_statement_evidence(
            "-31347186125831290",
            client=Mock(),
        )

        assert result["total_evidence"] == 5
        assert len(result["evidence"]) == 5

    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_empty_evidence(self, mock_get_evidence, literature_client):
        """Test statement with no evidence."""
        mock_get_evidence.return_value = []

        result = literature_client.get_statement_evidence(
            "-12345",
            client=Mock(),
        )

        assert result["success"] is True
        assert result["total_evidence"] == 0
        assert result["evidence"] == []


# Test Class 3: TestSearchMeshLiterature

class TestSearchMeshLiterature:
    """Test search_mesh_literature method."""

    @patch("cogex_mcp.clients.literature_client.get_pmids_for_mesh")
    def test_single_term(self, mock_get_pmids, literature_client):
        """Test search with single MeSH term."""
        mock_get_pmids.return_value = ["28746307", "29123456"]

        result = literature_client.search_mesh_literature(
            ["autophagy"],
            client=Mock(),
        )

        assert result["success"] is True
        assert result["mesh_terms"] == ["autophagy"]
        assert result["total_publications"] == 2

        pmids = [pub["pmid"] for pub in result["publications"]]
        assert "28746307" in pmids
        assert "29123456" in pmids

    @patch("cogex_mcp.clients.literature_client.get_pmids_for_mesh")
    def test_multiple_terms(self, mock_get_pmids, literature_client):
        """Test search with multiple MeSH terms (union)."""
        def side_effect(term, client):
            if term == "autophagy":
                return ["111", "222", "333"]
            elif term == "cancer":
                return ["222", "333", "444"]
            return []

        mock_get_pmids.side_effect = side_effect

        result = literature_client.search_mesh_literature(
            ["autophagy", "cancer"],
            client=Mock(),
        )

        assert result["success"] is True
        # Should be union: 111, 222, 333, 444
        assert result["total_publications"] == 4

    @patch("cogex_mcp.clients.literature_client.get_pmids_for_mesh")
    def test_no_results(self, mock_get_pmids, literature_client):
        """Test search with no matching publications."""
        mock_get_pmids.return_value = []

        result = literature_client.search_mesh_literature(
            ["rare_term_xyz"],
            client=Mock(),
        )

        assert result["success"] is True
        assert result["total_publications"] == 0
        assert result["publications"] == []

    @patch("cogex_mcp.clients.literature_client.get_pmids_for_mesh")
    def test_publication_urls(self, mock_get_pmids, literature_client):
        """Test that publications have PubMed URLs."""
        mock_get_pmids.return_value = ["28746307"]

        result = literature_client.search_mesh_literature(
            ["autophagy"],
            client=Mock(),
        )

        pub = result["publications"][0]
        assert pub["url"] == "https://pubmed.ncbi.nlm.nih.gov/28746307/"


# Test Class 4: TestGetStatementsByHashes

class TestGetStatementsByHashes:
    """Test get_statements_by_hashes method."""

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_stmt_hashes")
    def test_batch_retrieval(self, mock_get_stmts, literature_client):
        """Test batch statement retrieval."""
        stmt1 = Mock()
        stmt1.__class__.__name__ = "Phosphorylation"
        stmt1.get_hash = Mock(return_value=-111)
        stmt1.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt1.agent_list()[0].name = "TP53"
        stmt1.agent_list()[0].db_refs = {"HGNC": "11998"}
        stmt1.agent_list()[1].name = "MDM2"
        stmt1.agent_list()[1].db_refs = {"HGNC": "6973"}
        stmt1.evidence = []
        stmt1.belief = 0.9

        stmt2 = Mock()
        stmt2.__class__.__name__ = "Activation"
        stmt2.get_hash = Mock(return_value=-222)
        stmt2.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt2.agent_list()[0].name = "EGFR"
        stmt2.agent_list()[0].db_refs = {"HGNC": "3236"}
        stmt2.agent_list()[1].name = "MAPK1"
        stmt2.agent_list()[1].db_refs = {"HGNC": "6871"}
        stmt2.evidence = []
        stmt2.belief = 0.85

        mock_get_stmts.return_value = [(stmt1, {}), (stmt2, {})]

        result = literature_client.get_statements_by_hashes(
            ["-111", "-222"],
            include_evidence_text=False,
            client=Mock(),
        )

        assert result["success"] is True
        assert result["total_statements"] == 2
        assert result["statements"][0]["stmt_type"] == "Phosphorylation"
        assert result["statements"][1]["stmt_type"] == "Activation"

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_stmt_hashes")
    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_with_evidence(
        self,
        mock_get_evidence,
        mock_get_stmts,
        literature_client,
        mock_statement,
        mock_evidence,
    ):
        """Test batch retrieval with evidence."""
        mock_get_stmts.return_value = [(mock_statement, {})]
        mock_get_evidence.return_value = [mock_evidence]

        result = literature_client.get_statements_by_hashes(
            ["-31347186125831290"],
            include_evidence_text=True,
            max_evidence_per_statement=5,
            client=Mock(),
        )

        assert result["total_statements"] == 1
        stmt = result["statements"][0]
        assert len(stmt["evidence"]) == 1

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_stmt_hashes")
    def test_empty_hashes(self, mock_get_stmts, literature_client):
        """Test with empty hash list."""
        mock_get_stmts.return_value = []

        result = literature_client.get_statements_by_hashes(
            [],
            client=Mock(),
        )

        assert result["success"] is True
        assert result["total_statements"] == 0

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_stmt_hashes")
    def test_partial_results(self, mock_get_stmts, literature_client):
        """Test when some hashes don't match."""
        stmt = Mock()
        stmt.__class__.__name__ = "Phosphorylation"
        stmt.get_hash = Mock(return_value=-111)
        stmt.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt.agent_list()[0].name = "TP53"
        stmt.agent_list()[0].db_refs = {"HGNC": "11998"}
        stmt.agent_list()[1].name = "MDM2"
        stmt.agent_list()[1].db_refs = {"HGNC": "6973"}
        stmt.evidence = []
        stmt.belief = 0.9

        # Only 1 of 3 hashes found
        mock_get_stmts.return_value = [(stmt, {})]

        result = literature_client.get_statements_by_hashes(
            ["-111", "-222", "-333"],
            client=Mock(),
        )

        # Should return what was found
        assert result["total_statements"] == 1


# Test Class 5: TestHelperMethods

class TestHelperMethods:
    """Test helper methods."""

    def test_format_statement_dict_basic(self, literature_client, mock_statement):
        """Test statement formatting."""
        stmt_dict = literature_client._format_statement_dict((mock_statement, {}))

        assert stmt_dict["stmt_type"] == "Phosphorylation"
        assert stmt_dict["stmt_hash"] == "-31347186125831290"
        assert stmt_dict["subject"]["name"] == "TP53"
        assert stmt_dict["subject"]["curie"] == "hgnc:11998"
        assert stmt_dict["object"]["name"] == "MDM2"
        assert stmt_dict["object"]["curie"] == "hgnc:6973"
        assert stmt_dict["evidence_count"] == 2
        assert stmt_dict["belief_score"] == 0.95
        assert stmt_dict["residue"] == "S"
        assert stmt_dict["position"] == "166"

    def test_format_statement_dict_sources(self, literature_client, mock_statement):
        """Test source API extraction."""
        stmt_dict = literature_client._format_statement_dict((mock_statement, {}))

        assert "sources" in stmt_dict
        assert "reach" in stmt_dict["sources"]
        assert "sparser" in stmt_dict["sources"]

    def test_format_statement_dict_single_agent(
        self,
        literature_client,
        mock_statement_complex,
    ):
        """Test formatting statement with single agent."""
        stmt_dict = literature_client._format_statement_dict(
            (mock_statement_complex, {})
        )

        assert stmt_dict["stmt_type"] == "ActiveForm"
        assert stmt_dict["subject"]["name"] == "MAPK1"
        assert stmt_dict["object"]["name"] == "Unknown"

    def test_format_statement_dict_uniprot_priority(self, literature_client):
        """Test UniProt ID used when HGNC not available."""
        stmt = Mock()
        stmt.__class__.__name__ = "Phosphorylation"
        stmt.get_hash = Mock(return_value=-123)

        # Agent with only UniProt ID
        agent = Mock()
        agent.name = "PROTEIN"
        agent.db_refs = {"UP": "P12345"}

        stmt.agent_list = Mock(return_value=[agent, agent])
        stmt.evidence = []
        stmt.belief = 0.8

        stmt_dict = literature_client._format_statement_dict((stmt, {}))

        assert stmt_dict["subject"]["curie"] == "uniprot:P12345"

    def test_format_evidence_dict_basic(self, literature_client, mock_evidence):
        """Test evidence formatting."""
        ev_dict = literature_client._format_evidence_dict(mock_evidence)

        assert ev_dict["text"] == "TP53 phosphorylates MDM2 at serine 166."
        assert ev_dict["pmid"] == "28746307"
        assert ev_dict["source_api"] == "reach"
        assert ev_dict["annotations"] is not None

    def test_format_evidence_dict_minimal(self, literature_client):
        """Test evidence formatting with minimal data."""
        ev = Mock()
        ev.text = "Some text"
        ev.pmid = None
        ev.source_api = "unknown"
        ev.annotations = None

        ev_dict = literature_client._format_evidence_dict(ev)

        assert ev_dict["text"] == "Some text"
        assert ev_dict["pmid"] is None
        assert ev_dict["source_api"] == "unknown"

    def test_format_publication_dict(self, literature_client):
        """Test publication formatting."""
        pub_dict = literature_client._format_publication_dict(
            "28746307",
            ["autophagy", "cancer"],
        )

        assert pub_dict["pmid"] == "28746307"
        assert pub_dict["url"] == "https://pubmed.ncbi.nlm.nih.gov/28746307/"
        assert pub_dict["mesh_terms"] == ["autophagy", "cancer"]

    def test_format_publication_dict_no_mesh(self, literature_client):
        """Test publication formatting without MeSH terms."""
        pub_dict = literature_client._format_publication_dict("12345678")

        assert pub_dict["pmid"] == "12345678"
        assert pub_dict["mesh_terms"] == []


# Edge case tests

class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    def test_statement_without_hash(self, mock_get_stmts, literature_client):
        """Test statement without get_hash method."""
        stmt = Mock()
        stmt.__class__.__name__ = "Regulation"
        # No get_hash method
        if hasattr(stmt, 'get_hash'):
            delattr(stmt, 'get_hash')
        stmt.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt.agent_list()[0].name = "A"
        stmt.agent_list()[0].db_refs = {}
        stmt.agent_list()[1].name = "B"
        stmt.agent_list()[1].db_refs = {}
        stmt.evidence = []
        stmt.belief = 0.5

        mock_get_stmts.return_value = [(stmt, {})]

        result = literature_client.get_paper_statements(
            "12345678",
            include_evidence_text=False,
            client=Mock(),
        )

        # Should handle gracefully
        assert result["success"] is True
        assert result["statements"][0]["stmt_hash"] is None

    @patch("cogex_mcp.clients.literature_client.get_stmts_for_paper")
    def test_statement_without_belief(self, mock_get_stmts, literature_client):
        """Test statement without belief score."""
        stmt = Mock()
        stmt.__class__.__name__ = "Complex"
        stmt.get_hash = Mock(return_value=-999)
        stmt.agent_list = Mock(return_value=[Mock(), Mock()])
        stmt.agent_list()[0].name = "A"
        stmt.agent_list()[0].db_refs = {}
        stmt.agent_list()[1].name = "B"
        stmt.agent_list()[1].db_refs = {}
        stmt.evidence = []
        # No belief attribute

        mock_get_stmts.return_value = [(stmt, {})]

        result = literature_client.get_paper_statements(
            "12345678",
            include_evidence_text=False,
            client=Mock(),
        )

        assert result["statements"][0]["belief_score"] == 0.0

    @patch("cogex_mcp.clients.literature_client.get_evidences_for_stmt_hash")
    def test_evidence_without_annotations(self, mock_get_evidence, literature_client):
        """Test evidence without annotations."""
        ev = Mock()
        ev.text = "Evidence text"
        ev.pmid = "12345678"
        ev.source_api = "trips"
        # No annotations

        mock_get_evidence.return_value = [ev]

        result = literature_client.get_statement_evidence(
            "-123",
            client=Mock(),
        )

        # Should handle gracefully
        assert result["success"] is True
        assert result["evidence"][0]["annotations"] is None

    @patch("cogex_mcp.clients.literature_client.get_pmids_for_mesh")
    def test_duplicate_pmids_removed(self, mock_get_pmids, literature_client):
        """Test that duplicate PMIDs are removed in MeSH search."""
        def side_effect(term, client):
            # Both terms return some overlapping PMIDs
            return ["111", "222", "333"]

        mock_get_pmids.side_effect = side_effect

        result = literature_client.search_mesh_literature(
            ["term1", "term2"],
            client=Mock(),
        )

        # Should deduplicate
        assert result["total_publications"] == 3
        pmids = [pub["pmid"] for pub in result["publications"]]
        assert len(pmids) == len(set(pmids))  # No duplicates
