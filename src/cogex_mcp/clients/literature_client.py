"""
Direct CoGEx literature client.

Wraps INDRA CoGEx literature query functions to access PubMed publications,
INDRA statements, and evidence text. Provides access to the INDRA knowledge
extraction pipeline results.
"""

import logging
from typing import Any, Dict, List, Optional

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_stmts_for_paper,
    get_evidences_for_stmt_hash,
    get_evidences_for_mesh,
    get_pmids_for_mesh,
    get_stmts_for_stmt_hashes,
)

logger = logging.getLogger(__name__)


class LiteratureClient:
    """
    Direct literature query client using CoGEx library functions.

    Provides high-level interface to PubMed and INDRA data with:
    - PMID → INDRA statements extraction
    - Statement hash → evidence retrieval
    - MeSH term → publication search
    - Batch statement retrieval
    - Evidence text and source API tracking

    Example usage:
        >>> client = LiteratureClient()
        >>> result = client.get_paper_statements(
        ...     pmid="28746307",
        ...     include_evidence_text=True,
        ...     max_evidence_per_statement=5,
        ... )
        >>> print(f"Found {len(result['statements'])} statements")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize literature client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_paper_statements(
        self,
        pmid: str,
        include_evidence_text: bool = True,
        max_evidence_per_statement: int = 5,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get INDRA statements extracted from a paper.

        Queries the INDRA knowledge graph for all mechanistic statements
        extracted from the specified PubMed publication. Optionally includes
        evidence text snippets supporting each statement.

        Args:
            pmid: PubMed ID (e.g., "28746307")
            include_evidence_text: Include evidence text snippets (default: True)
            max_evidence_per_statement: Max evidence texts per statement (default: 5)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with statements and metadata:
                {
                    "success": True,
                    "pmid": "28746307",
                    "statements": [...],
                    "total_statements": N
                }

        Example:
            >>> result = client.get_paper_statements("28746307", max_evidence_per_statement=3)
            >>> for stmt in result["statements"]:
            ...     print(f"{stmt['stmt_type']}: {stmt['subject']['name']} → {stmt['object']['name']}")
        """
        logger.info(f"Getting statements for PMID {pmid}")

        # Query CoGEx for statements
        stmt_results = list(get_stmts_for_paper(pmid, client=client))

        logger.debug(f"Retrieved {len(stmt_results)} raw statements")

        # Convert to statement dicts
        statements = []
        for stmt_data in stmt_results:
            stmt_dict = self._format_statement_dict(stmt_data)

            # Add evidence if requested
            if include_evidence_text and stmt_dict.get("stmt_hash"):
                evidence_list = self._get_evidence_for_hash(
                    stmt_dict["stmt_hash"],
                    max_evidence=max_evidence_per_statement,
                    client=client,
                )
                stmt_dict["evidence"] = evidence_list
            else:
                stmt_dict["evidence"] = []

            statements.append(stmt_dict)

        logger.info(f"Formatted {len(statements)} statements for PMID {pmid}")

        return {
            "success": True,
            "pmid": pmid,
            "statements": statements,
            "total_statements": len(statements),
        }

    @autoclient()
    def get_statement_evidence(
        self,
        statement_hash: str,
        include_evidence_text: bool = True,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get evidence for a specific INDRA statement.

        Retrieves all evidence supporting an INDRA statement, including
        text snippets, PMIDs, source APIs, and annotations.

        Args:
            statement_hash: INDRA statement hash (e.g., "-31347186125831290")
            include_evidence_text: Include evidence text (default: True)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with evidence list:
                {
                    "success": True,
                    "statement_hash": "...",
                    "evidence": [...],
                    "total_evidence": N
                }

        Example:
            >>> result = client.get_statement_evidence("-31347186125831290")
            >>> for ev in result["evidence"]:
            ...     print(f"PMID {ev['pmid']}: {ev['text'][:100]}")
        """
        logger.info(f"Getting evidence for statement hash {statement_hash}")

        # Query CoGEx for evidence
        evidence_results = list(get_evidences_for_stmt_hash(statement_hash, client=client))

        logger.debug(f"Retrieved {len(evidence_results)} evidence entries")

        # Convert to evidence dicts
        evidence_list = []
        for ev_data in evidence_results:
            evidence_dict = self._format_evidence_dict(ev_data)

            # Optionally exclude text
            if not include_evidence_text:
                evidence_dict["text"] = None

            evidence_list.append(evidence_dict)

        logger.info(f"Formatted {len(evidence_list)} evidence entries")

        return {
            "success": True,
            "statement_hash": statement_hash,
            "evidence": evidence_list,
            "total_evidence": len(evidence_list),
        }

    @autoclient()
    def search_mesh_literature(
        self,
        mesh_terms: List[str],
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Search for publications by MeSH terms.

        Queries PubMed for publications annotated with the specified
        MeSH (Medical Subject Headings) terms. Useful for literature
        discovery and topic-based searches.

        Args:
            mesh_terms: List of MeSH terms (e.g., ["autophagy", "cancer"])
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with publications:
                {
                    "success": True,
                    "mesh_terms": ["autophagy", "cancer"],
                    "publications": [...],
                    "total_publications": N
                }

        Example:
            >>> result = client.search_mesh_literature(["autophagy", "cancer"])
            >>> for pub in result["publications"]:
            ...     print(f"{pub['pmid']}: {pub['title']}")
        """
        logger.info(f"Searching literature for MeSH terms: {mesh_terms}")

        # Query CoGEx for PMIDs
        all_pmids = set()
        for mesh_term in mesh_terms:
            pmids = list(get_pmids_for_mesh(mesh_term, client=client))
            all_pmids.update(pmids)
            logger.debug(f"MeSH term '{mesh_term}': {len(pmids)} PMIDs")

        logger.info(f"Found {len(all_pmids)} unique publications")

        # Convert PMIDs to publication dicts
        publications = []
        for pmid in sorted(all_pmids):
            pub_dict = self._format_publication_dict(pmid, mesh_terms)
            publications.append(pub_dict)

        return {
            "success": True,
            "mesh_terms": mesh_terms,
            "publications": publications,
            "total_publications": len(publications),
        }

    @autoclient()
    def get_statements_by_hashes(
        self,
        statement_hashes: List[str],
        include_evidence_text: bool = True,
        max_evidence_per_statement: int = 5,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Batch retrieve statements by hashes.

        Retrieves multiple INDRA statements by their hashes in a single
        query. Useful for reconstructing networks or following up on
        specific mechanistic relationships.

        Args:
            statement_hashes: List of statement hashes
            include_evidence_text: Include evidence text (default: True)
            max_evidence_per_statement: Max evidence per statement (default: 5)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with statements:
                {
                    "success": True,
                    "statements": [...],
                    "total_statements": N
                }

        Example:
            >>> hashes = ["-31347186125831290", "-42189012345678901"]
            >>> result = client.get_statements_by_hashes(hashes, max_evidence_per_statement=3)
            >>> print(f"Retrieved {result['total_statements']} statements")
        """
        logger.info(f"Batch retrieving {len(statement_hashes)} statements")

        # Query CoGEx for statements
        stmt_results = list(get_stmts_for_stmt_hashes(statement_hashes, client=client))

        logger.debug(f"Retrieved {len(stmt_results)} statements")

        # Convert to statement dicts
        statements = []
        for stmt_data in stmt_results:
            stmt_dict = self._format_statement_dict(stmt_data)

            # Add evidence if requested
            if include_evidence_text and stmt_dict.get("stmt_hash"):
                evidence_list = self._get_evidence_for_hash(
                    stmt_dict["stmt_hash"],
                    max_evidence=max_evidence_per_statement,
                    client=client,
                )
                stmt_dict["evidence"] = evidence_list
            else:
                stmt_dict["evidence"] = []

            statements.append(stmt_dict)

        logger.info(f"Formatted {len(statements)} statements")

        return {
            "success": True,
            "statements": statements,
            "total_statements": len(statements),
        }

    # Helper methods

    def _get_evidence_for_hash(
        self,
        stmt_hash: str,
        max_evidence: int,
        client: Neo4jClient,
    ) -> List[Dict[str, Any]]:
        """
        Get limited evidence for a statement hash.

        Args:
            stmt_hash: Statement hash
            max_evidence: Maximum evidence entries to return
            client: Neo4j client

        Returns:
            List of evidence dicts (limited to max_evidence)
        """
        evidence_results = list(get_evidences_for_stmt_hash(stmt_hash, client=client))

        # Limit evidence count
        limited_results = evidence_results[:max_evidence]

        evidence_list = []
        for ev_data in limited_results:
            evidence_dict = self._format_evidence_dict(ev_data)
            evidence_list.append(evidence_dict)

        return evidence_list

    def _format_statement_dict(self, stmt_data: Any) -> Dict[str, Any]:
        """
        Convert statement data to standardized dict.

        Args:
            stmt_data: Statement result from CoGEx (tuple or object)

        Returns:
            Statement dict with subject, object, evidence count, etc.

        Example:
            >>> stmt_dict = client._format_statement_dict(stmt_data)
            >>> print(stmt_dict["stmt_type"])
            Phosphorylation
        """
        # Handle different formats from CoGEx
        # Usually: (Statement object, source_counts)
        if isinstance(stmt_data, tuple):
            stmt = stmt_data[0]
            source_counts = stmt_data[1] if len(stmt_data) > 1 else {}
        else:
            stmt = stmt_data
            source_counts = {}

        # Get agents (subject and object)
        agents = [a for a in stmt.agent_list() if a is not None]

        if len(agents) < 2:
            # Handle statements with single agent
            subj = agents[0] if agents else None
            obj = None
        else:
            subj = agents[0]
            obj = agents[1]

        # Extract agent info
        def agent_to_dict(agent):
            if agent is None:
                return {
                    "name": "Unknown",
                    "curie": "unknown:unknown",
                    "namespace": "unknown",
                    "identifier": "unknown",
                }

            # Get primary identifier (prefer HGNC for genes)
            db_refs = agent.db_refs if hasattr(agent, 'db_refs') else {}
            if 'HGNC' in db_refs:
                namespace, identifier = 'hgnc', db_refs['HGNC']
            elif 'UP' in db_refs:
                namespace, identifier = 'uniprot', db_refs['UP']
            elif db_refs:
                # Take first available
                namespace, identifier = list(db_refs.items())[0]
            else:
                namespace, identifier = 'unknown', 'unknown'

            return {
                "name": agent.name if hasattr(agent, 'name') else identifier,
                "curie": f"{namespace.lower()}:{identifier}",
                "namespace": namespace.lower(),
                "identifier": identifier,
            }

        # Build statement dict
        stmt_dict = {
            "stmt_hash": str(stmt.get_hash(shallow=True)) if hasattr(stmt, 'get_hash') else None,
            "stmt_type": stmt.__class__.__name__,
            "subject": agent_to_dict(subj),
            "object": agent_to_dict(obj),
            "evidence_count": len(stmt.evidence) if hasattr(stmt, 'evidence') else 0,
            "belief_score": float(stmt.belief) if hasattr(stmt, 'belief') else 0.0,
        }

        # Add statement-specific fields
        if hasattr(stmt, 'residue') and stmt.residue:
            stmt_dict["residue"] = stmt.residue
        if hasattr(stmt, 'position') and stmt.position:
            stmt_dict["position"] = stmt.position

        # Extract evidence sources
        if hasattr(stmt, 'evidence'):
            sources = set()
            for ev in stmt.evidence:
                if hasattr(ev, 'source_api'):
                    sources.add(ev.source_api)
            stmt_dict["sources"] = sorted(list(sources))
        else:
            stmt_dict["sources"] = []

        return stmt_dict

    def _format_evidence_dict(self, evidence_data: Any) -> Dict[str, Any]:
        """
        Convert evidence data to standardized dict.

        Args:
            evidence_data: Evidence result from CoGEx (Evidence object)

        Returns:
            Evidence dict with text, PMID, source, annotations

        Example:
            >>> ev_dict = client._format_evidence_dict(evidence_data)
            >>> print(ev_dict["source_api"])
            reach
        """
        # Handle Evidence object
        if hasattr(evidence_data, 'text'):
            text = evidence_data.text
        else:
            text = str(evidence_data) if evidence_data else ""

        # Extract PMID
        pmid = None
        if hasattr(evidence_data, 'pmid'):
            pmid = evidence_data.pmid
        elif hasattr(evidence_data, 'annotations') and evidence_data.annotations:
            pmid = evidence_data.annotations.get('pmid')

        # Extract source API
        source_api = "unknown"
        if hasattr(evidence_data, 'source_api'):
            source_api = evidence_data.source_api
        elif hasattr(evidence_data, 'annotations') and evidence_data.annotations:
            source_api = evidence_data.annotations.get('source_api', 'unknown')

        # Extract annotations
        annotations = {}
        if hasattr(evidence_data, 'annotations') and evidence_data.annotations:
            annotations = evidence_data.annotations

        return {
            "text": text,
            "pmid": pmid,
            "source_api": source_api,
            "annotations": annotations if annotations else None,
        }

    def _format_publication_dict(
        self,
        pmid: str,
        mesh_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Convert PMID to publication dict.

        Args:
            pmid: PubMed ID
            mesh_terms: MeSH terms that led to this publication (optional)

        Returns:
            Publication dict with PMID, URL, and metadata

        Example:
            >>> pub_dict = client._format_publication_dict("28746307")
            >>> print(pub_dict["url"])
            https://pubmed.ncbi.nlm.nih.gov/28746307/
        """
        return {
            "pmid": str(pmid),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "mesh_terms": mesh_terms if mesh_terms else [],
        }
