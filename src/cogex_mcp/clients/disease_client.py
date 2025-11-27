"""
Direct CoGEx disease client.

Wraps INDRA CoGEx disease-gene association and phenotype mapping functions.
Provides comprehensive disease profile queries with support for multiple
evidence sources (DisGeNET, GWAS, OMIM, etc.).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_genes_for_disease,
    get_diseases_for_gene,
    get_phenotypes_for_disease,
    get_diseases_for_phenotype,
    has_gene_disease_association,
)

logger = logging.getLogger(__name__)


class DiseaseClient:
    """
    Direct disease-gene associations and phenotype mappings using CoGEx library.

    Provides high-level interface to disease data with:
    - Gene-disease associations from multiple evidence sources
    - Phenotype-disease mappings (HPO)
    - Bidirectional queries (gene→diseases, phenotype→diseases)
    - Boolean association checks with evidence filtering

    Example usage:
        >>> client = DiseaseClient()
        >>> result = client.get_disease_mechanisms(
        ...     disease_id="mesh:D000690",  # ALS
        ...     include_genes=True,
        ...     include_phenotypes=True,
        ...     min_evidence=2,
        ... )
        >>> print(f"Found {len(result['genes'])} genes")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize disease client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_disease_mechanisms(
        self,
        disease_id: str,
        include_genes: bool = True,
        include_phenotypes: bool = True,
        min_evidence: int = 1,
        evidence_sources: Optional[List[str]] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get comprehensive molecular mechanisms for a disease.

        This method retrieves genes and phenotypes associated with a disease,
        with support for filtering by evidence count and source.

        Args:
            disease_id: Disease CURIE (e.g., "mesh:D000690", "doid:332", "mondo:0005015")
            include_genes: Include gene associations
            include_phenotypes: Include phenotype associations
            min_evidence: Minimum evidence count threshold (filters genes)
            evidence_sources: Filter by specific sources (e.g., ["DisGeNET", "GWAS"])
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with disease profile:
                {
                    "success": True,
                    "disease_id": str,
                    "genes": [...],
                    "phenotypes": [...],
                    "statistics": {...}
                }

        Example:
            >>> result = client.get_disease_mechanisms(
            ...     disease_id="mesh:D000690",  # ALS
            ...     min_evidence=2,
            ...     evidence_sources=["DisGeNET", "GWAS"],
            ... )
        """
        logger.info(f"Getting disease mechanisms for {disease_id}")

        # Parse disease ID to (namespace, identifier) tuple
        disease_tuple = self._parse_disease_id(disease_id)

        result = {
            "success": True,
            "disease_id": disease_id,
        }

        # Get gene associations
        if include_genes:
            logger.debug(f"Fetching gene associations for {disease_id}")
            genes_data = get_genes_for_disease(disease_tuple, client=client)

            # Filter by evidence count and sources
            filtered_genes = self._filter_genes(
                genes_data,
                min_evidence=min_evidence,
                evidence_sources=evidence_sources,
            )

            result["genes"] = self._format_genes(filtered_genes)
            logger.info(f"Found {len(result['genes'])} genes (after filtering)")

        # Get phenotype associations
        if include_phenotypes:
            logger.debug(f"Fetching phenotype associations for {disease_id}")
            phenotypes_data = get_phenotypes_for_disease(disease_tuple, client=client)
            result["phenotypes"] = self._format_phenotypes(phenotypes_data)
            logger.info(f"Found {len(result['phenotypes'])} phenotypes")

        # Compute statistics
        result["statistics"] = self._compute_statistics(result)

        return result

    @autoclient()
    def find_diseases_for_gene(
        self,
        gene_id: str,
        limit: int = 20,
        min_evidence: int = 1,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find diseases associated with a specific gene.

        This method retrieves all diseases linked to a gene through various
        evidence sources (DisGeNET, GWAS, OMIM, etc.).

        Args:
            gene_id: Gene CURIE or symbol (e.g., "hgnc:11998", "TP53")
            limit: Maximum number of diseases to return
            min_evidence: Minimum evidence count threshold
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with disease associations:
                {
                    "success": True,
                    "gene_id": str,
                    "diseases": [...],
                    "total_diseases": int
                }

        Example:
            >>> result = client.find_diseases_for_gene(
            ...     gene_id="hgnc:11998",  # TP53
            ...     limit=50,
            ...     min_evidence=3,
            ... )
        """
        logger.info(f"Finding diseases for gene {gene_id}")

        # Parse gene ID to (namespace, identifier) tuple
        gene_tuple = self._parse_gene_id(gene_id)

        # Query CoGEx for diseases
        diseases_data = get_diseases_for_gene(gene_tuple, client=client)

        # Filter by evidence count
        if min_evidence > 1:
            diseases_data = [
                d for d in diseases_data
                if d.get("evidence_count", 0) >= min_evidence
            ]

        # Limit results
        if len(diseases_data) > limit:
            logger.debug(f"Limiting from {len(diseases_data)} to {limit} diseases")
            diseases_data = diseases_data[:limit]

        # Format response
        diseases = self._format_diseases(diseases_data)

        logger.info(f"Found {len(diseases)} diseases for gene {gene_id}")

        return {
            "success": True,
            "gene_id": gene_id,
            "diseases": diseases,
            "total_diseases": len(diseases),
        }

    @autoclient()
    def find_diseases_for_phenotype(
        self,
        phenotype_id: str,
        limit: int = 20,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find diseases exhibiting a specific phenotype.

        This method retrieves diseases that present with a given HPO term,
        useful for differential diagnosis and phenotype-based discovery.

        Args:
            phenotype_id: HPO term CURIE or name (e.g., "HP:0001250", "seizures")
            limit: Maximum number of diseases to return
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with diseases:
                {
                    "success": True,
                    "phenotype_id": str,
                    "diseases": [...],
                    "total_diseases": int
                }

        Example:
            >>> result = client.find_diseases_for_phenotype(
            ...     phenotype_id="HP:0001250",  # Seizures
            ...     limit=30,
            ... )
        """
        logger.info(f"Finding diseases for phenotype {phenotype_id}")

        # Parse phenotype ID to (namespace, identifier) tuple
        phenotype_tuple = self._parse_phenotype_id(phenotype_id)

        # Query CoGEx for diseases
        diseases_data = get_diseases_for_phenotype(phenotype_tuple, client=client)

        # Limit results
        if len(diseases_data) > limit:
            logger.debug(f"Limiting from {len(diseases_data)} to {limit} diseases")
            diseases_data = diseases_data[:limit]

        # Format response
        diseases = self._format_diseases(diseases_data)

        logger.info(f"Found {len(diseases)} diseases for phenotype {phenotype_id}")

        return {
            "success": True,
            "phenotype_id": phenotype_id,
            "diseases": diseases,
            "total_diseases": len(diseases),
        }

    @autoclient()
    def check_gene_disease_association(
        self,
        gene_id: str,
        disease_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Boolean check: Is gene associated with disease?

        This method performs a simple existence check for gene-disease
        association in the knowledge graph.

        Args:
            gene_id: Gene CURIE or symbol
            disease_id: Disease CURIE
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with association status:
                {
                    "success": True,
                    "has_association": bool,
                    "gene_id": str,
                    "disease_id": str
                }

        Example:
            >>> result = client.check_gene_disease_association(
            ...     gene_id="hgnc:11086",  # SOD1
            ...     disease_id="mesh:D000690",  # ALS
            ... )
            >>> assert result["has_association"] is True
        """
        logger.info(f"Checking gene-disease association: {gene_id} - {disease_id}")

        # Parse identifiers
        gene_tuple = self._parse_gene_id(gene_id)
        disease_tuple = self._parse_disease_id(disease_id)

        # Check association
        has_association = has_gene_disease_association(
            gene_tuple,
            disease_tuple,
            client=client,
        )

        logger.info(f"Association exists: {has_association}")

        return {
            "success": True,
            "has_association": has_association,
            "gene_id": gene_id,
            "disease_id": disease_id,
        }

    # Helper methods

    def _parse_disease_id(self, disease_id: str) -> Tuple[str, str]:
        """
        Convert disease CURIE to (namespace, identifier) tuple.

        Args:
            disease_id: Disease CURIE (e.g., "mesh:D000690", "doid:332")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_disease_id("mesh:D000690")
            ("MESH", "D000690")
        """
        if ":" in disease_id:
            namespace, identifier = disease_id.split(":", 1)
            return (namespace.upper(), identifier)
        else:
            # Assume MESH if no namespace
            logger.debug(f"Assuming MESH namespace for disease: {disease_id}")
            return ("MESH", disease_id)

    def _parse_gene_id(self, gene_id: str) -> Tuple[str, str]:
        """
        Convert gene CURIE to (namespace, identifier) tuple.

        Args:
            gene_id: Gene CURIE or symbol (e.g., "hgnc:11998", "TP53")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_gene_id("hgnc:11998")
            ("HGNC", "11998")
            >>> client._parse_gene_id("TP53")
            ("HGNC", "TP53")
        """
        if ":" in gene_id:
            namespace, identifier = gene_id.split(":", 1)
            return (namespace.upper(), identifier)
        else:
            # Assume HGNC gene symbol
            logger.debug(f"Assuming HGNC namespace for gene: {gene_id}")
            return ("HGNC", gene_id)

    def _parse_phenotype_id(self, phenotype_id: str) -> Tuple[str, str]:
        """
        Convert phenotype CURIE to (namespace, identifier) tuple.

        Args:
            phenotype_id: HPO term CURIE (e.g., "HP:0001250")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_phenotype_id("HP:0001250")
            ("HP", "0001250")
        """
        if ":" in phenotype_id:
            namespace, identifier = phenotype_id.split(":", 1)
            return (namespace.upper(), identifier)
        else:
            # Assume HP if no namespace
            logger.debug(f"Assuming HP namespace for phenotype: {phenotype_id}")
            return ("HP", phenotype_id)

    def _filter_genes(
        self,
        genes_data: List[Dict[str, Any]],
        min_evidence: int = 1,
        evidence_sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filter gene associations by evidence count and sources.

        Args:
            genes_data: Raw gene data from CoGEx
            min_evidence: Minimum evidence count
            evidence_sources: Allowed evidence sources

        Returns:
            Filtered list of gene associations
        """
        filtered = genes_data

        # Filter by evidence count
        if min_evidence > 1:
            filtered = [
                g for g in filtered
                if g.get("evidence_count", 0) >= min_evidence
            ]
            logger.debug(f"After evidence filter: {len(filtered)} genes")

        # Filter by evidence sources
        if evidence_sources:
            filtered = [
                g for g in filtered
                if any(
                    source in g.get("sources", [])
                    for source in evidence_sources
                )
            ]
            logger.debug(f"After source filter: {len(filtered)} genes")

        return filtered

    def _format_genes(self, genes_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format gene associations to MCP-compatible format.

        Args:
            genes_data: Raw gene data from CoGEx

        Returns:
            Formatted list of gene associations
        """
        formatted = []
        for gene in genes_data:
            formatted.append({
                "gene_id": gene.get("gene_id", "unknown:unknown"),
                "gene_name": gene.get("gene_name", gene.get("gene_id", "Unknown")),
                "association_type": gene.get("association_type", "unknown"),
                "evidence_count": gene.get("evidence_count", 0),
                "score": gene.get("score", 0.0),
                "sources": gene.get("sources", []),
            })
        return formatted

    def _format_phenotypes(
        self,
        phenotypes_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Format phenotype associations to MCP-compatible format.

        Args:
            phenotypes_data: Raw phenotype data from CoGEx

        Returns:
            Formatted list of phenotype associations
        """
        formatted = []
        for phenotype in phenotypes_data:
            formatted.append({
                "phenotype_id": phenotype.get("phenotype_id", "unknown:unknown"),
                "phenotype_name": phenotype.get(
                    "phenotype_name",
                    phenotype.get("phenotype_id", "Unknown")
                ),
                "frequency": phenotype.get("frequency"),
                "evidence_count": phenotype.get("evidence_count", 0),
            })
        return formatted

    def _format_diseases(
        self,
        diseases_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Format disease list to MCP-compatible format.

        Args:
            diseases_data: Raw disease data from CoGEx

        Returns:
            Formatted list of diseases
        """
        formatted = []
        for disease in diseases_data:
            formatted.append({
                "disease_id": disease.get("disease_id", "unknown:unknown"),
                "disease_name": disease.get(
                    "disease_name",
                    disease.get("disease_id", "Unknown")
                ),
                "association_type": disease.get("association_type", "unknown"),
                "evidence_count": disease.get("evidence_count", 0),
                "score": disease.get("score", 0.0),
                "sources": disease.get("sources", []),
            })
        return formatted

    def _compute_statistics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute summary statistics from disease profile.

        Args:
            result: Disease profile result dict

        Returns:
            Dict with statistics
        """
        stats = {}

        if "genes" in result:
            stats["gene_count"] = len(result["genes"])
            if result["genes"]:
                stats["avg_gene_evidence"] = sum(
                    g["evidence_count"] for g in result["genes"]
                ) / len(result["genes"])
                # Count evidence sources
                all_sources = set()
                for gene in result["genes"]:
                    all_sources.update(gene.get("sources", []))
                stats["evidence_sources"] = sorted(list(all_sources))

        if "phenotypes" in result:
            stats["phenotype_count"] = len(result["phenotypes"])

        return stats
