"""
Direct CoGEx subnetwork client.

Wraps INDRA CoGEx subnetwork functions to extract mechanistic networks
from the knowledge graph. Converts INDRA Statement objects to MCP-compatible
dictionaries.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra.statements import Statement
from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.subnetwork import (
    indra_mediated_subnetwork,
    indra_shared_downstream_subnetwork,
    indra_shared_upstream_subnetwork,
    indra_subnetwork,
    indra_subnetwork_go,
    indra_subnetwork_tissue,
)

logger = logging.getLogger(__name__)


class SubnetworkClient:
    """
    Direct subnetwork extraction using CoGEx library functions.

    Provides high-level interface to INDRA mechanistic networks with:
    - Multiple subnetwork extraction modes (direct, mediated, shared)
    - Filtering by statement type, belief score, evidence count
    - Tissue and GO term context filtering
    - INDRA Statement → MCP dict conversion

    Example usage:
        >>> client = SubnetworkClient()
        >>> result = client.extract_direct(
        ...     gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
        ...     min_evidence=2,
        ...     min_belief=0.7,
        ... )
        >>> print(f"Found {result['statistics']['statement_count']} statements")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize subnetwork client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def extract_direct(
        self,
        gene_ids: List[str],
        statement_types: Optional[List[str]] = None,
        min_evidence: int = 1,
        min_belief: float = 0.0,
        max_statements: int = 100,
        tissue: Optional[str] = None,
        go_term: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Extract direct mechanistic edges between genes.

        This method queries the INDRA knowledge graph for direct
        regulatory relationships (phosphorylation, activation, etc.)
        between the specified genes.

        Args:
            gene_ids: List of gene CURIEs (e.g., ["hgnc:11998", "hgnc:6407"])
            statement_types: Filter by statement types (e.g., ["Phosphorylation", "Activation"])
            min_evidence: Minimum evidence count threshold
            min_belief: Minimum belief score threshold (0.0-1.0)
            max_statements: Maximum statements to return
            tissue: Optional tissue context filter (e.g., "uberon:0002037")
            go_term: Optional GO term context filter (e.g., "GO:0006915")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with statements, nodes, and statistics:
                {
                    "success": True,
                    "statements": [...],
                    "nodes": [...],
                    "statistics": {...}
                }

        Example:
            >>> result = client.extract_direct(
            ...     gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            ...     min_evidence=2,
            ...     min_belief=0.7,
            ... )
        """
        logger.info(f"Extracting direct subnetwork for {len(gene_ids)} genes")

        # Convert gene_ids to (namespace, identifier) tuples
        nodes = self._parse_gene_ids(gene_ids)

        # Route to appropriate CoGEx function based on filters
        if tissue:
            tissue_tuple = self._parse_curie(tissue)
            statements = indra_subnetwork_tissue(
                nodes=nodes,
                tissue=tissue_tuple,
                client=client,
            )
        elif go_term:
            go_tuple = self._parse_curie(go_term)
            statements = indra_subnetwork_go(
                go_term=go_tuple,
                client=client,
                include_indirect=False,
            )
            # Filter to only nodes in our gene list
            statements = self._filter_statements_by_genes(statements, nodes)
        else:
            statements = indra_subnetwork(
                nodes=nodes,
                client=client,
            )

        logger.debug(f"Retrieved {len(statements)} raw statements")

        # Apply filters
        filtered_statements = self._filter_statements(
            statements,
            statement_types=statement_types,
            min_evidence=min_evidence,
            min_belief=min_belief,
            max_statements=max_statements,
        )

        logger.info(f"After filtering: {len(filtered_statements)} statements")

        # Convert to MCP format
        return self._format_subnetwork_response(filtered_statements, nodes)

    @autoclient()
    def extract_mediated(
        self,
        gene_ids: List[str],
        statement_types: Optional[List[str]] = None,
        min_evidence: int = 1,
        min_belief: float = 0.0,
        max_statements: int = 100,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Extract two-hop mediated paths connecting genes through intermediates.

        This method finds indirect connections where genes interact through
        a common intermediate (A→X→B pattern). Useful for pathway discovery.

        Args:
            gene_ids: List of gene CURIEs
            statement_types: Filter by statement types
            min_evidence: Minimum evidence count
            min_belief: Minimum belief score
            max_statements: Maximum statements to return
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with mediated statements, nodes, and statistics

        Example:
            >>> result = client.extract_mediated(
            ...     gene_ids=["hgnc:11998", "hgnc:588"],  # TP53, BRCA1
            ...     min_evidence=2,
            ... )
            >>> # Returns paths like TP53 → MDM2 → BRCA1
        """
        logger.info(f"Extracting mediated subnetwork for {len(gene_ids)} genes")

        nodes = self._parse_gene_ids(gene_ids)

        statements = indra_mediated_subnetwork(
            nodes=nodes,
            client=client,
        )

        logger.debug(f"Retrieved {len(statements)} mediated statements")

        filtered_statements = self._filter_statements(
            statements,
            statement_types=statement_types,
            min_evidence=min_evidence,
            min_belief=min_belief,
            max_statements=max_statements,
        )

        logger.info(f"After filtering: {len(filtered_statements)} mediated statements")

        return self._format_subnetwork_response(
            filtered_statements,
            nodes,
            note="Two-hop mediated paths shown"
        )

    @autoclient()
    def extract_shared_upstream(
        self,
        gene_ids: List[str],
        statement_types: Optional[List[str]] = None,
        min_evidence: int = 1,
        min_belief: float = 0.0,
        max_statements: int = 100,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find shared upstream regulators of target genes.

        This method identifies proteins/genes that regulate multiple
        targets in your gene list (X→A and X→B pattern). Useful for
        finding master regulators.

        Args:
            gene_ids: List of gene CURIEs (targets)
            statement_types: Filter by statement types
            min_evidence: Minimum evidence count
            min_belief: Minimum belief score
            max_statements: Maximum statements to return
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with shared regulators and their connections

        Example:
            >>> result = client.extract_shared_upstream(
            ...     gene_ids=["hgnc:6407", "hgnc:6840"],  # MAP2K1, MAP2K2
            ...     min_evidence=3,
            ... )
            >>> # Finds kinases that phosphorylate both MAP2K1 and MAP2K2
        """
        logger.info(f"Finding shared upstream regulators for {len(gene_ids)} genes")

        nodes = self._parse_gene_ids(gene_ids)

        statements = indra_shared_upstream_subnetwork(
            nodes=nodes,
            client=client,
        )

        logger.debug(f"Retrieved {len(statements)} shared upstream statements")

        filtered_statements = self._filter_statements(
            statements,
            statement_types=statement_types,
            min_evidence=min_evidence,
            min_belief=min_belief,
            max_statements=max_statements,
        )

        logger.info(f"After filtering: {len(filtered_statements)} shared upstream statements")

        return self._format_subnetwork_response(
            filtered_statements,
            nodes,
            note="Shared upstream regulators shown"
        )

    @autoclient()
    def extract_shared_downstream(
        self,
        gene_ids: List[str],
        statement_types: Optional[List[str]] = None,
        min_evidence: int = 1,
        min_belief: float = 0.0,
        max_statements: int = 100,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find shared downstream targets of source genes.

        This method identifies proteins/genes that are regulated by multiple
        sources in your gene list (A→X and B→X pattern). Useful for
        finding convergent pathways.

        Args:
            gene_ids: List of gene CURIEs (sources)
            statement_types: Filter by statement types
            min_evidence: Minimum evidence count
            min_belief: Minimum belief score
            max_statements: Maximum statements to return
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with shared targets and their connections

        Example:
            >>> result = client.extract_shared_downstream(
            ...     gene_ids=["hgnc:3467", "hgnc:3468"],  # EGFR, ERBB2
            ...     min_evidence=3,
            ... )
            >>> # Finds proteins activated by both EGFR and ERBB2
        """
        logger.info(f"Finding shared downstream targets for {len(gene_ids)} genes")

        nodes = self._parse_gene_ids(gene_ids)

        statements = indra_shared_downstream_subnetwork(
            nodes=nodes,
            client=client,
        )

        logger.debug(f"Retrieved {len(statements)} shared downstream statements")

        filtered_statements = self._filter_statements(
            statements,
            statement_types=statement_types,
            min_evidence=min_evidence,
            min_belief=min_belief,
            max_statements=max_statements,
        )

        logger.info(f"After filtering: {len(filtered_statements)} shared downstream statements")

        return self._format_subnetwork_response(
            filtered_statements,
            nodes,
            note="Shared downstream targets shown"
        )

    # Helper methods

    def _parse_gene_ids(self, gene_ids: List[str]) -> List[Tuple[str, str]]:
        """
        Convert gene CURIEs to (namespace, identifier) tuples.

        Args:
            gene_ids: List of CURIEs (e.g., ["hgnc:11998", "hgnc:6407"])

        Returns:
            List of (namespace, identifier) tuples for CoGEx

        Example:
            >>> client._parse_gene_ids(["hgnc:11998", "TP53"])
            [("HGNC", "11998"), ("HGNC", "TP53")]
        """
        nodes = []
        for gene_id in gene_ids:
            if ":" in gene_id:
                namespace, identifier = gene_id.split(":", 1)
                nodes.append((namespace.upper(), identifier))
            else:
                # Assume HGNC gene symbol
                nodes.append(("HGNC", gene_id))
                logger.debug(f"Assuming HGNC namespace for gene: {gene_id}")
        return nodes

    def _parse_curie(self, curie: str) -> Tuple[str, str]:
        """
        Parse CURIE into (namespace, identifier) tuple.

        Args:
            curie: CURIE string (e.g., "GO:0006915")

        Returns:
            Tuple of (namespace, identifier)

        Raises:
            ValueError: If CURIE format is invalid
        """
        if ":" in curie:
            namespace, identifier = curie.split(":", 1)
            return (namespace.upper(), identifier)
        raise ValueError(f"Invalid CURIE format: {curie}")

    def _filter_statements(
        self,
        statements: List[Statement],
        statement_types: Optional[List[str]] = None,
        min_evidence: int = 1,
        min_belief: float = 0.0,
        max_statements: int = 100,
    ) -> List[Statement]:
        """
        Filter INDRA statements by type, evidence, and belief.

        Args:
            statements: List of INDRA Statement objects
            statement_types: Allowed statement types (None = all)
            min_evidence: Minimum evidence count
            min_belief: Minimum belief score
            max_statements: Maximum to return

        Returns:
            Filtered list of statements
        """
        filtered = statements

        # Filter by statement type
        if statement_types:
            filtered = [
                stmt for stmt in filtered
                if stmt.__class__.__name__ in statement_types
            ]
            logger.debug(f"After type filter: {len(filtered)} statements")

        # Filter by evidence count
        if min_evidence > 1:
            filtered = [
                stmt for stmt in filtered
                if len(stmt.evidence) >= min_evidence
            ]
            logger.debug(f"After evidence filter: {len(filtered)} statements")

        # Filter by belief score
        if min_belief > 0.0:
            filtered = [
                stmt for stmt in filtered
                if hasattr(stmt, 'belief') and stmt.belief >= min_belief
            ]
            logger.debug(f"After belief filter: {len(filtered)} statements")

        # Limit results
        if len(filtered) > max_statements:
            logger.debug(f"Limiting from {len(filtered)} to {max_statements} statements")
            filtered = filtered[:max_statements]

        return filtered

    def _filter_statements_by_genes(
        self,
        statements: List[Statement],
        nodes: List[Tuple[str, str]],
    ) -> List[Statement]:
        """
        Filter statements to only those involving specified genes.

        Args:
            statements: List of INDRA statements
            nodes: List of (namespace, identifier) tuples

        Returns:
            Filtered statements
        """
        node_ids = {f"{ns.lower()}:{id_}" for ns, id_ in nodes}

        filtered = []
        for stmt in statements:
            agents = [a for a in stmt.agent_list() if a is not None]
            agent_ids = set()
            for agent in agents:
                if hasattr(agent, 'db_refs'):
                    for db, db_id in agent.db_refs.items():
                        agent_ids.add(f"{db.lower()}:{db_id}")

            if agent_ids & node_ids:  # Intersection check
                filtered.append(stmt)

        logger.debug(f"Gene filter: {len(filtered)}/{len(statements)} statements match")
        return filtered

    def _format_subnetwork_response(
        self,
        statements: List[Statement],
        query_nodes: List[Tuple[str, str]],
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Convert INDRA statements to MCP-compatible format.

        Args:
            statements: Filtered INDRA Statement objects
            query_nodes: Original query genes
            note: Optional informational note

        Returns:
            Dict with statements, nodes, statistics, and metadata
        """
        # Convert statements to dicts
        stmt_dicts = []
        all_agents = set()

        for stmt in statements:
            stmt_dict = self._statement_to_dict(stmt)
            stmt_dicts.append(stmt_dict)

            # Collect all agents for node list
            all_agents.add(stmt_dict["subject"]["curie"])
            all_agents.add(stmt_dict["object"]["curie"])

        # Build node list
        nodes = []
        for agent_id in all_agents:
            if agent_id == "unknown:unknown":
                continue
            if ":" in agent_id:
                namespace, identifier = agent_id.split(":", 1)
                nodes.append({
                    "curie": agent_id,
                    "namespace": namespace,
                    "identifier": identifier,
                    "name": identifier,  # Simplified - could enhance with name lookup
                })

        # Compute statistics
        statistics = self._compute_statistics(stmt_dicts)

        result = {
            "success": True,
            "statements": stmt_dicts,
            "nodes": nodes,
            "statistics": statistics,
        }

        if note:
            result["note"] = note

        logger.info(
            f"Formatted response: {statistics['statement_count']} statements, "
            f"{statistics['node_count']} nodes"
        )

        return result

    def _statement_to_dict(self, stmt: Statement) -> Dict[str, Any]:
        """
        Convert INDRA Statement to MCP dict format.

        Args:
            stmt: INDRA Statement object

        Returns:
            Statement as dictionary with subject, object, evidence, etc.
        """
        # Get agents (subject and object)
        agents = [a for a in stmt.agent_list() if a is not None]

        if len(agents) < 2:
            # Handle statements with single agent (rare)
            subj = agents[0] if agents else None
            obj = None
        else:
            subj = agents[0]
            obj = agents[1]

        # Extract agent info
        def agent_to_dict(agent):
            if agent is None:
                return {
                    "curie": "unknown:unknown",
                    "namespace": "unknown",
                    "identifier": "unknown",
                    "name": "Unknown",
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
                "curie": f"{namespace.lower()}:{identifier}",
                "namespace": namespace.lower(),
                "identifier": identifier,
                "name": agent.name if hasattr(agent, 'name') else identifier,
            }

        stmt_dict = {
            "stmt_hash": stmt.get_hash(shallow=True) if hasattr(stmt, 'get_hash') else None,
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

    def _compute_statistics(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute network statistics from statement dicts.

        Args:
            statements: List of statement dictionaries

        Returns:
            Dict with statement counts, node counts, type distribution, etc.
        """
        if not statements:
            return {
                "statement_count": 0,
                "node_count": 0,
                "statement_types": {},
                "avg_evidence_per_statement": 0.0,
                "avg_belief_score": 0.0,
            }

        # Count nodes
        nodes = set()
        for stmt in statements:
            if stmt["subject"]["curie"] != "unknown:unknown":
                nodes.add(stmt["subject"]["curie"])
            if stmt["object"]["curie"] != "unknown:unknown":
                nodes.add(stmt["object"]["curie"])

        # Count statement types
        type_counts: Dict[str, int] = {}
        total_evidence = 0
        total_belief = 0.0

        for stmt in statements:
            stmt_type = stmt["stmt_type"]
            type_counts[stmt_type] = type_counts.get(stmt_type, 0) + 1
            total_evidence += stmt["evidence_count"]
            total_belief += stmt["belief_score"]

        return {
            "statement_count": len(statements),
            "node_count": len(nodes),
            "statement_types": type_counts,
            "avg_evidence_per_statement": total_evidence / len(statements) if statements else 0.0,
            "avg_belief_score": total_belief / len(statements) if statements else 0.0,
        }
