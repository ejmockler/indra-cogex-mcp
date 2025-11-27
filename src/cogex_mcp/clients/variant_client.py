"""
Direct CoGEx variant client.

Wraps INDRA CoGEx variant query functions to access GWAS Catalog and DisGeNet
data. Provides bidirectional queries between variants, genes, diseases, and
phenotypes with p-value filtering.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_variants_for_gene,
    get_genes_for_variant,
    get_variants_for_disease,
    get_diseases_for_variant,
    get_phenotypes_for_variant_gwas,
    get_variants_for_phenotype_gwas,
)

logger = logging.getLogger(__name__)


class VariantClient:
    """
    Direct variant query client using CoGEx library functions.

    Provides high-level interface to genetic variant data with:
    - Variant-gene associations (bidirectional)
    - Variant-disease associations (bidirectional)
    - Variant-phenotype GWAS mappings (bidirectional)
    - P-value filtering for statistical significance
    - Source filtering (GWAS Catalog vs DisGeNet)

    Example usage:
        >>> client = VariantClient()
        >>> result = client.get_gene_variants(
        ...     gene_id="hgnc:613",  # APOE
        ...     max_p_value=1e-8,
        ... )
        >>> print(f"Found {result['total_variants']} variants")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize variant client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_gene_variants(
        self,
        gene_id: str,
        max_p_value: float = 1e-5,
        min_p_value: Optional[float] = None,
        source: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get genetic variants in/near a gene.

        Queries GWAS Catalog and DisGeNet for variants associated with
        the specified gene. Returns rsIDs with p-values, odds ratios,
        and study information.

        Args:
            gene_id: Gene CURIE (e.g., "hgnc:613" for APOE)
            max_p_value: Maximum p-value threshold (default: 1e-5)
            min_p_value: Minimum p-value threshold (optional)
            source: Filter by source ("gwas_catalog" or "disgenet")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with variants and metadata:
                {
                    "success": True,
                    "variants": [...],
                    "total_variants": N,
                    "gene_id": "hgnc:613"
                }

        Example:
            >>> result = client.get_gene_variants("hgnc:613", max_p_value=1e-8)
            >>> for variant in result["variants"]:
            ...     print(f"{variant['rsid']}: p={variant['p_value']}")
        """
        logger.info(f"Getting variants for gene {gene_id}")

        # Parse gene ID to tuple format
        gene_tuple = self._parse_curie(gene_id)

        # Query CoGEx
        variant_nodes = list(get_variants_for_gene(gene_tuple, client=client))

        logger.debug(f"Retrieved {len(variant_nodes)} raw variants")

        # Convert to dicts and filter
        variants = []
        for node in variant_nodes:
            variant_dict = self._format_variant_dict(node)
            variants.append(variant_dict)

        # Apply p-value filtering
        filtered_variants = self._filter_by_pvalue(variants, max_p_value, min_p_value)

        # Apply source filtering if specified
        if source:
            filtered_variants = self._filter_by_source(filtered_variants, source)

        logger.info(f"After filtering: {len(filtered_variants)} variants")

        return {
            "success": True,
            "variants": filtered_variants,
            "total_variants": len(filtered_variants),
            "gene_id": gene_id,
        }

    @autoclient()
    def get_variant_genes(
        self,
        variant_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get genes near a variant.

        Finds genes that are associated with the specified variant
        (typically within a genomic window). Useful for mapping rsIDs
        to candidate genes.

        Args:
            variant_id: Variant rsID (e.g., "rs7412")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with genes and metadata:
                {
                    "success": True,
                    "genes": [...],
                    "total_genes": N,
                    "variant_id": "rs7412"
                }

        Example:
            >>> result = client.get_variant_genes("rs7412")
            >>> for gene in result["genes"]:
            ...     print(f"{gene['name']}: {gene['curie']}")
        """
        logger.info(f"Getting genes for variant {variant_id}")

        # Parse variant ID (rsID format)
        variant_tuple = self._parse_variant_id(variant_id)

        # Query CoGEx
        gene_nodes = list(get_genes_for_variant(variant_tuple, client=client))

        logger.debug(f"Retrieved {len(gene_nodes)} genes")

        # Convert to dicts
        genes = []
        for node in gene_nodes:
            gene_dict = self._format_gene_dict(node)
            genes.append(gene_dict)

        logger.info(f"Found {len(genes)} genes for variant {variant_id}")

        return {
            "success": True,
            "genes": genes,
            "total_genes": len(genes),
            "variant_id": variant_id,
        }

    @autoclient()
    def get_disease_variants(
        self,
        disease_id: str,
        max_p_value: float = 1e-5,
        min_p_value: Optional[float] = None,
        source: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get variants associated with disease.

        Queries GWAS Catalog and DisGeNet for variants associated with
        the specified disease. Returns genome-wide significant hits.

        Args:
            disease_id: Disease CURIE (e.g., "mesh:D000544" for Alzheimer's)
            max_p_value: Maximum p-value threshold (default: 1e-5)
            min_p_value: Minimum p-value threshold (optional)
            source: Filter by source ("gwas_catalog" or "disgenet")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with variants and metadata:
                {
                    "success": True,
                    "variants": [...],
                    "total_variants": N,
                    "disease_id": "mesh:D000544"
                }

        Example:
            >>> result = client.get_disease_variants("mesh:D000544", max_p_value=5e-8)
            >>> print(f"Found {result['total_variants']} significant variants")
        """
        logger.info(f"Getting variants for disease {disease_id}")

        # Parse disease ID
        disease_tuple = self._parse_curie(disease_id)

        # Query CoGEx
        variant_nodes = list(get_variants_for_disease(disease_tuple, client=client))

        logger.debug(f"Retrieved {len(variant_nodes)} raw variants")

        # Convert to dicts
        variants = []
        for node in variant_nodes:
            variant_dict = self._format_variant_dict(node)
            variants.append(variant_dict)

        # Apply p-value filtering
        filtered_variants = self._filter_by_pvalue(variants, max_p_value, min_p_value)

        # Apply source filtering if specified
        if source:
            filtered_variants = self._filter_by_source(filtered_variants, source)

        logger.info(f"After filtering: {len(filtered_variants)} variants")

        return {
            "success": True,
            "variants": filtered_variants,
            "total_variants": len(filtered_variants),
            "disease_id": disease_id,
        }

    @autoclient()
    def get_variant_diseases(
        self,
        variant_id: str,
        max_p_value: float = 1e-5,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get diseases associated with variant.

        Finds diseases linked to the specified variant in GWAS studies
        and DisGeNet. Useful for understanding clinical significance.

        Args:
            variant_id: Variant rsID (e.g., "rs7412")
            max_p_value: Maximum p-value threshold (default: 1e-5)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with diseases and metadata:
                {
                    "success": True,
                    "diseases": [...],
                    "total_diseases": N,
                    "variant_id": "rs7412"
                }

        Example:
            >>> result = client.get_variant_diseases("rs7412", max_p_value=1e-6)
            >>> for disease in result["diseases"]:
            ...     print(f"{disease['name']}: {disease['curie']}")
        """
        logger.info(f"Getting diseases for variant {variant_id}")

        # Parse variant ID
        variant_tuple = self._parse_variant_id(variant_id)

        # Query CoGEx
        disease_nodes = list(get_diseases_for_variant(variant_tuple, client=client))

        logger.debug(f"Retrieved {len(disease_nodes)} diseases")

        # Convert to dicts
        diseases = []
        for node in disease_nodes:
            disease_dict = self._format_disease_dict(node)
            diseases.append(disease_dict)

        # Filter by p-value (if available in node properties)
        filtered_diseases = [d for d in diseases if d.get("p_value", 1.0) <= max_p_value]

        logger.info(f"Found {len(filtered_diseases)} diseases for variant {variant_id}")

        return {
            "success": True,
            "diseases": filtered_diseases,
            "total_diseases": len(filtered_diseases),
            "variant_id": variant_id,
        }

    @autoclient()
    def get_variant_phenotypes(
        self,
        variant_id: str,
        max_p_value: float = 1e-5,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get GWAS phenotypes for variant.

        Queries GWAS Catalog for phenotypic traits associated with
        the specified variant. Returns traits with p-values and
        study information.

        Args:
            variant_id: Variant rsID (e.g., "rs9939609")
            max_p_value: Maximum p-value threshold (default: 1e-5)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with phenotypes and metadata:
                {
                    "success": True,
                    "phenotypes": [...],
                    "total_phenotypes": N,
                    "variant_id": "rs9939609"
                }

        Example:
            >>> result = client.get_variant_phenotypes("rs9939609", max_p_value=5e-8)
            >>> for phenotype in result["phenotypes"]:
            ...     print(f"{phenotype['name']}: p={phenotype['p_value']}")
        """
        logger.info(f"Getting phenotypes for variant {variant_id}")

        # Parse variant ID
        variant_tuple = self._parse_variant_id(variant_id)

        # Query CoGEx
        phenotype_nodes = list(get_phenotypes_for_variant_gwas(variant_tuple, client=client))

        logger.debug(f"Retrieved {len(phenotype_nodes)} phenotypes")

        # Convert to dicts
        phenotypes = []
        for node in phenotype_nodes:
            phenotype_dict = self._format_phenotype_dict(node)
            phenotypes.append(phenotype_dict)

        # Filter by p-value (if available)
        filtered_phenotypes = [p for p in phenotypes if p.get("p_value", 1.0) <= max_p_value]

        logger.info(f"Found {len(filtered_phenotypes)} phenotypes for variant {variant_id}")

        return {
            "success": True,
            "phenotypes": filtered_phenotypes,
            "total_phenotypes": len(filtered_phenotypes),
            "variant_id": variant_id,
        }

    @autoclient()
    def get_phenotype_variants(
        self,
        phenotype: str,
        max_p_value: float = 1e-5,
        min_p_value: Optional[float] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get variants from GWAS for phenotype.

        Queries GWAS Catalog for variants associated with a specific
        phenotypic trait. Useful for phenotype-driven variant discovery.

        Args:
            phenotype: Phenotype name or CURIE (e.g., "body mass index", "efo:0004340")
            max_p_value: Maximum p-value threshold (default: 1e-5)
            min_p_value: Minimum p-value threshold (optional)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with variants and metadata:
                {
                    "success": True,
                    "variants": [...],
                    "total_variants": N,
                    "phenotype": "body mass index"
                }

        Example:
            >>> result = client.get_phenotype_variants("body mass index", max_p_value=5e-8)
            >>> for variant in result["variants"]:
            ...     print(f"{variant['rsid']} near {variant.get('gene', 'unknown')}")
        """
        logger.info(f"Getting variants for phenotype {phenotype}")

        # Parse phenotype (could be CURIE or string)
        if ":" in phenotype:
            phenotype_tuple = self._parse_curie(phenotype)
        else:
            # Use as-is (CoGEx may handle string phenotypes)
            phenotype_tuple = ("phenotype", phenotype)

        # Query CoGEx
        variant_nodes = list(get_variants_for_phenotype_gwas(phenotype_tuple, client=client))

        logger.debug(f"Retrieved {len(variant_nodes)} raw variants")

        # Convert to dicts
        variants = []
        for node in variant_nodes:
            variant_dict = self._format_variant_dict(node)
            variants.append(variant_dict)

        # Apply p-value filtering
        filtered_variants = self._filter_by_pvalue(variants, max_p_value, min_p_value)

        logger.info(f"After filtering: {len(filtered_variants)} variants")

        return {
            "success": True,
            "variants": filtered_variants,
            "total_variants": len(filtered_variants),
            "phenotype": phenotype,
        }

    # Helper methods

    def _parse_curie(self, curie: str) -> Tuple[str, str]:
        """
        Parse CURIE into (namespace, identifier) tuple.

        Args:
            curie: CURIE string (e.g., "hgnc:613", "mesh:D000544")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_curie("hgnc:613")
            ("hgnc", "613")
        """
        if ":" in curie:
            namespace, identifier = curie.split(":", 1)
            return (namespace.lower(), identifier)

        # Assume gene symbol if no namespace
        logger.debug(f"No namespace in '{curie}', assuming HGNC gene symbol")
        return ("hgnc", curie)

    def _parse_variant_id(self, variant_id: str) -> Tuple[str, str]:
        """
        Parse variant ID into (namespace, identifier) tuple.

        Args:
            variant_id: Variant rsID (e.g., "rs7412", "dbsnp:rs7412")

        Returns:
            Tuple of ("dbsnp", rsID) for CoGEx

        Example:
            >>> client._parse_variant_id("rs7412")
            ("dbsnp", "rs7412")
            >>> client._parse_variant_id("dbsnp:rs7412")
            ("dbsnp", "rs7412")
        """
        if variant_id.startswith("rs"):
            return ("dbsnp", variant_id)
        elif ":" in variant_id:
            namespace, rsid = variant_id.split(":", 1)
            return (namespace.lower(), rsid)
        else:
            logger.warning(f"Unexpected variant ID format: {variant_id}")
            return ("dbsnp", variant_id)

    def _filter_by_pvalue(
        self,
        variants: List[Dict[str, Any]],
        max_p: float,
        min_p: Optional[float],
    ) -> List[Dict[str, Any]]:
        """
        Filter variants by p-value range.

        Args:
            variants: List of variant dicts
            max_p: Maximum p-value (inclusive)
            min_p: Minimum p-value (inclusive, optional)

        Returns:
            Filtered list of variants

        Example:
            >>> variants = [{"rsid": "rs1", "p_value": 1e-8}, {"rsid": "rs2", "p_value": 0.01}]
            >>> filtered = client._filter_by_pvalue(variants, max_p=1e-5, min_p=None)
            >>> len(filtered)
            1
        """
        filtered = []
        for variant in variants:
            p_value = variant.get("p_value", 1.0)

            # Check max threshold
            if p_value > max_p:
                continue

            # Check min threshold if specified
            if min_p is not None and p_value < min_p:
                continue

            filtered.append(variant)

        logger.debug(f"P-value filter: {len(filtered)}/{len(variants)} variants pass")
        return filtered

    def _filter_by_source(
        self,
        variants: List[Dict[str, Any]],
        source: str,
    ) -> List[Dict[str, Any]]:
        """
        Filter variants by data source.

        Args:
            variants: List of variant dicts
            source: Source name ("gwas_catalog" or "disgenet")

        Returns:
            Filtered list of variants

        Example:
            >>> variants = [
            ...     {"rsid": "rs1", "source": "gwas_catalog"},
            ...     {"rsid": "rs2", "source": "disgenet"}
            ... ]
            >>> filtered = client._filter_by_source(variants, "gwas_catalog")
            >>> len(filtered)
            1
        """
        source_lower = source.lower()
        filtered = [v for v in variants if v.get("source", "").lower() == source_lower]

        logger.debug(f"Source filter: {len(filtered)}/{len(variants)} variants from {source}")
        return filtered

    def _format_variant_dict(self, node: Any) -> Dict[str, Any]:
        """
        Convert variant Node to standardized dict.

        Args:
            node: CoGEx Node object

        Returns:
            Variant dict with rsID, position, p-value, etc.

        Example:
            >>> variant_dict = client._format_variant_dict(node)
            >>> print(variant_dict["rsid"])
            rs7412
        """
        # Extract node properties
        data = node.data if hasattr(node, "data") else {}

        return {
            "rsid": data.get("id", data.get("rsid", "unknown")),
            "curie": f"dbsnp:{data.get('id', 'unknown')}",
            "namespace": "dbsnp",
            "chromosome": str(data.get("chromosome", data.get("chr", "unknown"))),
            "position": int(data.get("position", data.get("pos", 0))),
            "ref_allele": data.get("ref_allele", data.get("reference", "?")),
            "alt_allele": data.get("alt_allele", data.get("alternate", "?")),
            "p_value": float(data.get("p_value", data.get("pvalue", 1.0))),
            "odds_ratio": data.get("odds_ratio", data.get("or")),
            "trait": data.get("trait", data.get("phenotype", "Unknown")),
            "study": data.get("study", data.get("study_id", "Unknown")),
            "source": data.get("source", "unknown"),
        }

    def _format_gene_dict(self, node: Any) -> Dict[str, Any]:
        """
        Convert gene Node to standardized dict.

        Args:
            node: CoGEx Node object

        Returns:
            Gene dict with name, CURIE, etc.
        """
        data = node.data if hasattr(node, "data") else {}
        namespace = node.db_ns if hasattr(node, "db_ns") else "hgnc"
        identifier = node.db_id if hasattr(node, "db_id") else data.get("id", "unknown")

        return {
            "name": data.get("name", identifier),
            "curie": f"{namespace.lower()}:{identifier}",
            "namespace": namespace.lower(),
            "identifier": identifier,
            "description": data.get("description"),
        }

    def _format_disease_dict(self, node: Any) -> Dict[str, Any]:
        """
        Convert disease Node to standardized dict.

        Args:
            node: CoGEx Node object

        Returns:
            Disease dict with name, CURIE, etc.
        """
        data = node.data if hasattr(node, "data") else {}
        namespace = node.db_ns if hasattr(node, "db_ns") else "doid"
        identifier = node.db_id if hasattr(node, "db_id") else data.get("id", "unknown")

        return {
            "name": data.get("name", identifier),
            "curie": f"{namespace.lower()}:{identifier}",
            "namespace": namespace.lower(),
            "identifier": identifier,
            "description": data.get("description"),
            "p_value": float(data.get("p_value", 1.0)),
        }

    def _format_phenotype_dict(self, node: Any) -> Dict[str, Any]:
        """
        Convert phenotype Node to standardized dict.

        Args:
            node: CoGEx Node object

        Returns:
            Phenotype dict with name, CURIE, etc.
        """
        data = node.data if hasattr(node, "data") else {}
        namespace = node.db_ns if hasattr(node, "db_ns") else "efo"
        identifier = node.db_id if hasattr(node, "db_id") else data.get("id", "unknown")

        return {
            "name": data.get("name", data.get("trait", identifier)),
            "curie": f"{namespace.lower()}:{identifier}",
            "namespace": namespace.lower(),
            "identifier": identifier,
            "description": data.get("description"),
            "p_value": float(data.get("p_value", 1.0)),
        }
