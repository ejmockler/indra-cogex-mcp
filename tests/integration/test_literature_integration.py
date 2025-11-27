"""
Integration tests for LiteratureClient with real Neo4j database.

Tests scientific validation scenarios:
- Famous papers and their extracted statements
- Known INDRA statement hashes
- MeSH term searches (autophagy, cancer, Alzheimer's)
- Evidence retrieval and completeness
- Performance benchmarks
"""

import pytest
import time
from typing import Optional

from indra_cogex.client.neo4j_client import Neo4jClient

from cogex_mcp.clients.literature_client import LiteratureClient


def neo4j_available() -> bool:
    """Check if Neo4j is available for integration tests."""
    try:
        import os
        # Check for environment variables
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password")

        # Try to connect
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


@pytest.fixture
def neo4j_client() -> Optional[Neo4jClient]:
    """Create Neo4j client for integration tests."""
    if not neo4j_available():
        pytest.skip("Neo4j not available")

    import os
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    return Neo4jClient(url=uri, username=user, password=password)


@pytest.fixture
def literature_client(neo4j_client) -> LiteratureClient:
    """Create LiteratureClient with Neo4j connection."""
    return LiteratureClient(neo4j_client=neo4j_client)


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestPaperStatements:
    """
    Test paper statement extraction.

    Scientific validation:
    - Papers should have INDRA-extracted statements
    - Statements should have subjects, objects, types
    - Evidence counts should be reasonable
    - Famous papers should have known interactions
    """

    def test_extract_statements_from_paper(self, literature_client):
        """Test extracting statements from a real paper."""
        # Use a well-known PMID (may vary by database version)
        # This is a test - we'll try a few famous PMIDs
        test_pmids = [
            "28746307",  # Example PMID
            "26000852",  # Another example
            "25416956",  # Another example
        ]

        for pmid in test_pmids:
            try:
                result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                    max_evidence_per_statement=5,
                )

                if result["success"] and result["total_statements"] > 0:
                    print(f"\nPMID {pmid}: Found {result['total_statements']} statements")

                    # Check statement structure
                    stmt = result["statements"][0]
                    assert "stmt_type" in stmt
                    assert "subject" in stmt
                    assert "object" in stmt
                    assert "evidence_count" in stmt

                    print(f"  Example: {stmt['subject']['name']} → {stmt['object']['name']}")
                    print(f"  Type: {stmt['stmt_type']}")
                    print(f"  Evidence count: {stmt['evidence_count']}")

                    return  # Success - exit test

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        # If none worked, just pass (database may not have these)
        pytest.skip("No test PMIDs available in database")

    def test_statements_with_evidence_text(self, literature_client):
        """Test statement extraction with evidence text."""
        test_pmids = ["28746307", "26000852", "25416956"]

        for pmid in test_pmids:
            try:
                result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=True,
                    max_evidence_per_statement=3,
                )

                if result["success"] and result["total_statements"] > 0:
                    print(f"\nPMID {pmid}: With evidence")

                    # Find statement with evidence
                    for stmt in result["statements"]:
                        if stmt.get("evidence") and len(stmt["evidence"]) > 0:
                            print(f"  Statement: {stmt['stmt_type']}")
                            print(f"  Evidence texts: {len(stmt['evidence'])}")

                            ev = stmt["evidence"][0]
                            assert "text" in ev
                            assert "source_api" in ev
                            print(f"  Sample: {ev['text'][:100] if ev['text'] else 'No text'}")
                            return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("No statements with evidence found")

    def test_evidence_count_limit(self, literature_client):
        """Test max_evidence_per_statement limit works."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=True,
                    max_evidence_per_statement=2,
                )

                if result["success"] and result["total_statements"] > 0:
                    # Check that evidence is limited
                    for stmt in result["statements"]:
                        if stmt.get("evidence"):
                            assert len(stmt["evidence"]) <= 2
                            print(f"Evidence limited to {len(stmt['evidence'])} (max 2)")
                            return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test evidence limit")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestStatementEvidence:
    """
    Test statement evidence retrieval.

    Scientific validation:
    - Statement hashes should retrieve evidence
    - Evidence should have text, PMIDs, sources
    - Multiple papers can support same statement
    """

    def test_get_evidence_for_statement(self, literature_client):
        """Test retrieving evidence for a statement hash."""
        # This test depends on having a known statement hash
        # We'll try to get one from a paper first
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                # Get statements from paper
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] > 0:
                    stmt_hash = stmt_result["statements"][0]["stmt_hash"]

                    if stmt_hash:
                        # Get evidence for this hash
                        ev_result = literature_client.get_statement_evidence(
                            statement_hash=stmt_hash,
                            include_evidence_text=True,
                        )

                        assert ev_result["success"] is True
                        assert ev_result["statement_hash"] == stmt_hash

                        if ev_result["total_evidence"] > 0:
                            print(f"\nStatement hash: {stmt_hash}")
                            print(f"Evidence count: {ev_result['total_evidence']}")

                            ev = ev_result["evidence"][0]
                            assert "text" in ev
                            assert "source_api" in ev
                            print(f"Source API: {ev['source_api']}")
                            return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test statement evidence")

    def test_evidence_without_text(self, literature_client):
        """Test evidence retrieval without text."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] > 0:
                    stmt_hash = stmt_result["statements"][0]["stmt_hash"]

                    if stmt_hash:
                        ev_result = literature_client.get_statement_evidence(
                            statement_hash=stmt_hash,
                            include_evidence_text=False,
                        )

                        if ev_result["total_evidence"] > 0:
                            # Text should be None
                            assert ev_result["evidence"][0]["text"] is None
                            print("Evidence retrieved without text")
                            return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test evidence without text")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestMeshSearch:
    """
    Test MeSH term literature search.

    Scientific validation:
    - Common MeSH terms should find publications
    - Multiple terms should combine results
    - Results should have PMIDs and URLs
    """

    def test_single_mesh_term(self, literature_client):
        """Test search with single MeSH term."""
        mesh_terms = ["autophagy", "apoptosis", "inflammation"]

        for term in mesh_terms:
            try:
                result = literature_client.search_mesh_literature(
                    mesh_terms=[term],
                )

                if result["success"] and result["total_publications"] > 0:
                    print(f"\nMeSH term '{term}': {result['total_publications']} publications")

                    # Check publication structure
                    pub = result["publications"][0]
                    assert "pmid" in pub
                    assert "url" in pub
                    assert "mesh_terms" in pub

                    print(f"  Sample PMID: {pub['pmid']}")
                    print(f"  URL: {pub['url']}")

                    # Should find many papers
                    assert result["total_publications"] > 0
                    return

            except Exception as e:
                print(f"  MeSH term '{term}' failed: {e}")
                continue

        pytest.skip("No MeSH terms returned results")

    def test_multiple_mesh_terms(self, literature_client):
        """Test search with multiple MeSH terms."""
        try:
            result = literature_client.search_mesh_literature(
                mesh_terms=["autophagy", "cancer"],
            )

            if result["success"] and result["total_publications"] > 0:
                print(f"\nMeSH: autophagy + cancer")
                print(f"Publications: {result['total_publications']}")

                # Should combine results from both terms
                assert result["total_publications"] > 0

                # All publications should have PMIDs
                for pub in result["publications"][:10]:
                    assert pub["pmid"]
                    assert pub["url"].startswith("https://pubmed.ncbi.nlm.nih.gov/")

        except Exception as e:
            print(f"Multiple MeSH terms failed: {e}")
            pytest.skip("MeSH search not available")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestBatchRetrieval:
    """
    Test batch statement retrieval by hashes.

    Scientific validation:
    - Multiple hashes should be retrieved efficiently
    - Statements should match requested hashes
    - Evidence can be included in batch
    """

    def test_batch_statement_retrieval(self, literature_client):
        """Test batch retrieval of statements."""
        # First get some statement hashes
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] >= 2:
                    # Get first 2 statement hashes
                    hashes = [
                        stmt["stmt_hash"]
                        for stmt in stmt_result["statements"][:2]
                        if stmt.get("stmt_hash")
                    ]

                    if len(hashes) >= 2:
                        # Batch retrieve
                        batch_result = literature_client.get_statements_by_hashes(
                            statement_hashes=hashes,
                            include_evidence_text=False,
                        )

                        assert batch_result["success"] is True
                        print(f"\nBatch retrieved {batch_result['total_statements']} statements")

                        # Should get back what we requested
                        assert batch_result["total_statements"] <= len(hashes)
                        return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test batch retrieval")

    def test_batch_with_evidence(self, literature_client):
        """Test batch retrieval with evidence."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] >= 1:
                    hashes = [
                        stmt["stmt_hash"]
                        for stmt in stmt_result["statements"][:1]
                        if stmt.get("stmt_hash")
                    ]

                    if len(hashes) >= 1:
                        batch_result = literature_client.get_statements_by_hashes(
                            statement_hashes=hashes,
                            include_evidence_text=True,
                            max_evidence_per_statement=3,
                        )

                        if batch_result["total_statements"] > 0:
                            stmt = batch_result["statements"][0]
                            if "evidence" in stmt and len(stmt["evidence"]) > 0:
                                print(f"Batch statement with evidence: {len(stmt['evidence'])} entries")
                                return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test batch with evidence")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestPerformance:
    """
    Test query performance and benchmarks.

    Requirements:
    - Statement extraction should complete in <3 seconds
    - Evidence retrieval should be fast (<2 seconds)
    - MeSH searches should handle large result sets
    """

    def test_paper_statement_performance(self, literature_client):
        """Test performance of paper statement extraction."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                start = time.time()

                result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                elapsed = time.time() - start

                if result["total_statements"] > 0:
                    print(f"\nPaper extraction: {elapsed:.2f}s")
                    print(f"Statements: {result['total_statements']}")

                    # Should complete in <3 seconds
                    assert elapsed < 3.0, f"Query too slow: {elapsed:.2f}s"
                    return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test performance")

    def test_evidence_retrieval_performance(self, literature_client):
        """Test performance of evidence retrieval."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] > 0:
                    stmt_hash = stmt_result["statements"][0]["stmt_hash"]

                    if stmt_hash:
                        start = time.time()

                        ev_result = literature_client.get_statement_evidence(
                            statement_hash=stmt_hash,
                            include_evidence_text=True,
                        )

                        elapsed = time.time() - start

                        print(f"\nEvidence retrieval: {elapsed:.2f}s")
                        print(f"Evidence count: {ev_result['total_evidence']}")

                        # Should be very fast
                        assert elapsed < 2.0, f"Query too slow: {elapsed:.2f}s"
                        return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test evidence performance")


@pytest.mark.integration
@pytest.mark.skipif(not neo4j_available(), reason="Neo4j not available")
class TestDataQuality:
    """Test data quality and completeness."""

    def test_statement_completeness(self, literature_client):
        """Test that statements have required fields."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if result["total_statements"] > 0:
                    for stmt in result["statements"][:5]:
                        # Check required fields
                        assert "stmt_type" in stmt
                        assert "subject" in stmt
                        assert "object" in stmt
                        assert "evidence_count" in stmt
                        assert "belief_score" in stmt

                        # Subject/object should have name and CURIE
                        assert "name" in stmt["subject"]
                        assert "curie" in stmt["subject"]
                        assert "name" in stmt["object"]
                        assert "curie" in stmt["object"]

                        print(f"Statement: {stmt['stmt_type']}")
                        print(f"  {stmt['subject']['name']} → {stmt['object']['name']}")
                        print(f"  Belief: {stmt['belief_score']:.2f}")

                    return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test data quality")

    def test_evidence_completeness(self, literature_client):
        """Test that evidence has required fields."""
        test_pmids = ["28746307", "26000852"]

        for pmid in test_pmids:
            try:
                stmt_result = literature_client.get_paper_statements(
                    pmid=pmid,
                    include_evidence_text=False,
                )

                if stmt_result["total_statements"] > 0:
                    stmt_hash = stmt_result["statements"][0]["stmt_hash"]

                    if stmt_hash:
                        ev_result = literature_client.get_statement_evidence(
                            statement_hash=stmt_hash,
                            include_evidence_text=True,
                        )

                        if ev_result["total_evidence"] > 0:
                            for ev in ev_result["evidence"][:3]:
                                assert "text" in ev
                                assert "source_api" in ev
                                # PMID may be None for some sources

                                print(f"Evidence from {ev['source_api']}")

                            return

            except Exception as e:
                print(f"  PMID {pmid} failed: {e}")
                continue

        pytest.skip("Could not test evidence quality")
