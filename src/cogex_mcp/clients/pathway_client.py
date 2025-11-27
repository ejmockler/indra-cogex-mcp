"""
Direct CoGEx pathway client.

Wraps INDRA CoGEx pathway functions for pathway membership and shared pathway
queries. Provides methods to query genes in pathways, pathways containing genes,
and find pathways shared across multiple genes.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_genes_for_pathway,
    get_pathways_for_gene,
    get_shared_pathways_for_genes,
    is_gene_in_pathway,
)

logger = logging.getLogger(__name__)


class PathwayClient:
    """
    Direct pathway queries using CoGEx library functions.

    Provides high-level interface to pathway membership and shared pathway
    analysis with:
    - Gene → pathways mapping
    - Pathway → genes mapping
    - Shared pathway discovery across gene sets
    - Membership validation

    Example usage:
        >>> client = PathwayClient()
        >>> result = client.get_gene_pathways(
        ...     gene_id="hgnc:11998",  # TP53
        ...     pathway_source="reactome",
        ... )
        >>> print(f"Found {result['total_pathways']} pathways")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize pathway client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_gene_pathways(
        self,
        gene_id: str,
        pathway_source: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get pathways containing a specific gene.

        This method queries CoGEx for all pathways that include the specified
        gene. Results can be filtered by pathway source (Reactome, WikiPathways, etc.).

        Args:
            gene_id: Gene CURIE (e.g., "hgnc:11998" for TP53)
            pathway_source: Optional source filter ("reactome", "wikipathways", "go")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with pathways and metadata:
                {
                    "success": True,
                    "gene_id": "hgnc:11998",
                    "pathways": [...],
                    "total_pathways": 42
                }

        Example:
            >>> result = client.get_gene_pathways(
            ...     gene_id="hgnc:11998",  # TP53
            ...     pathway_source="reactome",
            ... )
            >>> for pathway in result["pathways"]:
            ...     print(f"{pathway['pathway_name']} ({pathway['namespace']})")
        """
        logger.info(f"Getting pathways for gene: {gene_id}")

        # Parse gene CURIE
        namespace, identifier = self._parse_gene_id(gene_id)

        # Query CoGEx
        pathways = get_pathways_for_gene(
            (namespace, identifier),
            client=client,
        )

        logger.debug(f"Retrieved {len(pathways)} pathways for {gene_id}")

        # Filter by source if specified
        if pathway_source:
            pathways = [
                p for p in pathways
                if p.get('namespace', '').lower() == pathway_source.lower()
            ]
            logger.debug(f"After source filter: {len(pathways)} pathways")

        # Format response
        return self._format_pathways_response(pathways, gene_id)

    @autoclient()
    def get_pathway_genes(
        self,
        pathway_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get genes in a specific pathway.

        This method queries CoGEx for all genes that are members of the
        specified pathway.

        Args:
            pathway_id: Pathway CURIE (e.g., "reactome:R-HSA-3700989")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with genes and metadata:
                {
                    "success": True,
                    "pathway_id": "reactome:R-HSA-3700989",
                    "genes": [...],
                    "total_genes": 157
                }

        Example:
            >>> result = client.get_pathway_genes(
            ...     pathway_id="reactome:R-HSA-3700989",  # TP53 pathway
            ... )
            >>> print(f"Found {result['total_genes']} genes in pathway")
        """
        logger.info(f"Getting genes for pathway: {pathway_id}")

        # Parse pathway CURIE
        namespace, identifier = self._parse_gene_id(pathway_id)

        # Query CoGEx
        genes = get_genes_for_pathway(
            (namespace, identifier),
            client=client,
        )

        logger.debug(f"Retrieved {len(genes)} genes for {pathway_id}")

        # Format response
        return self._format_genes_response(genes, pathway_id)

    @autoclient()
    def find_shared_pathways(
        self,
        gene_ids: List[str],
        min_genes_in_pathway: int = 2,
        pathway_source: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find pathways containing multiple genes from the input set.

        This method identifies pathways that include two or more genes from
        the provided gene list, useful for finding common biological processes.

        Args:
            gene_ids: List of gene CURIEs (e.g., ["hgnc:11998", "hgnc:6973"])
            min_genes_in_pathway: Minimum number of query genes required (default: 2)
            pathway_source: Optional source filter ("reactome", "wikipathways", "go")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with shared pathways and metadata:
                {
                    "success": True,
                    "query_genes": [...],
                    "shared_pathways": [...],
                    "total_shared": 15
                }

        Example:
            >>> result = client.find_shared_pathways(
            ...     gene_ids=["hgnc:11998", "hgnc:6973"],  # TP53, MDM2
            ...     min_genes_in_pathway=2,
            ... )
            >>> for pathway in result["shared_pathways"]:
            ...     print(f"{pathway['pathway_name']}: {pathway['gene_count']} genes")
        """
        logger.info(f"Finding shared pathways for {len(gene_ids)} genes")

        # Parse gene CURIEs
        gene_tuples = [self._parse_gene_id(gid) for gid in gene_ids]

        # Query CoGEx
        shared = get_shared_pathways_for_genes(
            gene_tuples,
            client=client,
        )

        logger.debug(f"Retrieved {len(shared)} shared pathways")

        # Filter by minimum gene count
        filtered = [
            p for p in shared
            if len(p.get("genes", [])) >= min_genes_in_pathway
        ]

        logger.debug(f"After min_genes filter: {len(filtered)} pathways")

        # Filter by source if specified
        if pathway_source:
            filtered = [
                p for p in filtered
                if p.get('namespace', '').lower() == pathway_source.lower()
            ]
            logger.debug(f"After source filter: {len(filtered)} pathways")

        # Format response
        return self._format_shared_response(filtered, gene_ids)

    @autoclient()
    def check_membership(
        self,
        gene_id: str,
        pathway_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Check if a gene is a member of a specific pathway.

        This method provides a boolean check for pathway membership,
        useful for validation and filtering.

        Args:
            gene_id: Gene CURIE (e.g., "hgnc:11998")
            pathway_id: Pathway CURIE (e.g., "reactome:R-HSA-3700989")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with membership status:
                {
                    "success": True,
                    "gene_id": "hgnc:11998",
                    "pathway_id": "reactome:R-HSA-3700989",
                    "is_member": True
                }

        Example:
            >>> result = client.check_membership(
            ...     gene_id="hgnc:11998",  # TP53
            ...     pathway_id="reactome:R-HSA-3700989",  # TP53 pathway
            ... )
            >>> print(f"TP53 in pathway: {result['is_member']}")
        """
        logger.info(f"Checking membership: {gene_id} in {pathway_id}")

        # Parse CURIEs
        gene_ns, gene_id_part = self._parse_gene_id(gene_id)
        pathway_ns, pathway_id_part = self._parse_gene_id(pathway_id)

        # Query CoGEx
        is_member = is_gene_in_pathway(
            gene=(gene_ns, gene_id_part),
            pathway=(pathway_ns, pathway_id_part),
            client=client,
        )

        logger.info(f"Membership check: {gene_id} in {pathway_id} = {is_member}")

        return {
            "success": True,
            "gene_id": gene_id,
            "pathway_id": pathway_id,
            "is_member": is_member,
        }

    # Helper methods

    def _parse_gene_id(self, curie: str) -> Tuple[str, str]:
        """
        Parse CURIE into (namespace, identifier) tuple.

        Args:
            curie: CURIE string (e.g., "hgnc:11998" or "TP53")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_gene_id("hgnc:11998")
            ("HGNC", "11998")
            >>> client._parse_gene_id("TP53")
            ("HGNC", "TP53")
        """
        if ":" in curie:
            namespace, identifier = curie.split(":", 1)
            return (namespace.upper(), identifier)
        else:
            # Assume HGNC gene symbol
            logger.debug(f"No namespace in '{curie}', assuming HGNC")
            return ("HGNC", curie)

    def _format_pathways_response(
        self,
        pathways: List[Dict[str, Any]],
        gene_id: str,
    ) -> Dict[str, Any]:
        """
        Format pathways list as MCP response.

        Args:
            pathways: List of pathway dicts from CoGEx
            gene_id: Original gene ID query

        Returns:
            Formatted response dict
        """
        formatted_pathways = []
        for p in pathways:
            formatted_pathways.append({
                "pathway_id": p.get("pathway_id", "unknown"),
                "pathway_name": p.get("pathway_name", "Unknown pathway"),
                "namespace": p.get("namespace", "unknown"),
                "gene_count": p.get("gene_count", 0),
            })

        result = {
            "success": True,
            "gene_id": gene_id,
            "pathways": formatted_pathways,
            "total_pathways": len(formatted_pathways),
        }

        logger.info(f"Formatted {len(formatted_pathways)} pathways for {gene_id}")
        return result

    def _format_genes_response(
        self,
        genes: List[Dict[str, Any]],
        pathway_id: str,
    ) -> Dict[str, Any]:
        """
        Format genes list as MCP response.

        Args:
            genes: List of gene dicts from CoGEx
            pathway_id: Original pathway ID query

        Returns:
            Formatted response dict
        """
        formatted_genes = []
        for g in genes:
            formatted_genes.append({
                "gene_id": g.get("gene_id", "unknown"),
                "gene_name": g.get("gene_name", "Unknown gene"),
            })

        result = {
            "success": True,
            "pathway_id": pathway_id,
            "genes": formatted_genes,
            "total_genes": len(formatted_genes),
        }

        logger.info(f"Formatted {len(formatted_genes)} genes for {pathway_id}")
        return result

    def _format_shared_response(
        self,
        shared: List[Dict[str, Any]],
        gene_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Format shared pathways list as MCP response.

        Args:
            shared: List of shared pathway dicts from CoGEx
            gene_ids: Original gene IDs query

        Returns:
            Formatted response dict
        """
        formatted_pathways = []
        for p in shared:
            genes_in_pathway = p.get("genes", [])

            formatted_pathways.append({
                "pathway_id": p.get("pathway_id", "unknown"),
                "pathway_name": p.get("pathway_name", "Unknown pathway"),
                "namespace": p.get("namespace", "unknown"),
                "genes_in_pathway": genes_in_pathway,
                "gene_count": len(genes_in_pathway),
            })

        result = {
            "success": True,
            "query_genes": gene_ids,
            "shared_pathways": formatted_pathways,
            "total_shared": len(formatted_pathways),
        }

        logger.info(f"Formatted {len(formatted_pathways)} shared pathways for {len(gene_ids)} genes")
        return result
