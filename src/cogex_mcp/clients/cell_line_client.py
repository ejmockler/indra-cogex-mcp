"""
Direct CoGEx cell line client.

Wraps INDRA CoGEx cell line query functions to access CCLE and DepMap data
including mutations, copy number alterations, dependencies, and expression.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_cell_lines_with_mutation,
    get_mutated_genes_in_cell_line,
    is_gene_mutated_in_cell_line,
    get_cell_lines_with_cna,
    get_cna_genes_in_cell_line,
    has_cna_in_cell_line,
)

logger = logging.getLogger(__name__)


class CellLineClient:
    """
    Direct cell line data client using CoGEx library functions.

    Provides high-level interface to CCLE and DepMap cancer cell line data with:
    - Comprehensive cell line profiles (mutations, CNAs, dependencies, expression)
    - Mutation screening (find cell lines with specific mutations)
    - Copy number analysis (amplifications/deletions)
    - Gene dependency and expression analysis

    Example usage:
        >>> client = CellLineClient()
        >>> result = client.get_cell_line_profile(
        ...     cell_line="A549",  # Lung cancer cell line
        ...     include_mutations=True,
        ...     include_copy_number=True,
        ... )
        >>> print(f"Found {len(result['mutations'])} mutations")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize cell line client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_cell_line_profile(
        self,
        cell_line: str,
        include_mutations: bool = True,
        include_copy_number: bool = False,
        include_dependencies: bool = False,
        include_expression: bool = False,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get comprehensive cell line profile from CCLE/DepMap.

        This method queries multiple data sources in the knowledge graph to build
        a complete genomic and functional profile for a cancer cell line.

        Args:
            cell_line: Cell line name (e.g., "A549", "HeLa", "MCF7")
            include_mutations: Include mutation data from CCLE
            include_copy_number: Include copy number alteration data
            include_dependencies: Include gene dependency scores from DepMap
            include_expression: Include expression data
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with comprehensive cell line profile:
                {
                    "success": True,
                    "cell_line": "A549",
                    "mutations": [...],
                    "copy_number_alterations": [...],
                    "dependencies": [...],
                    "expression": [...],
                }

        Example:
            >>> result = client.get_cell_line_profile(
            ...     cell_line="A549",  # Non-small cell lung cancer
            ...     include_mutations=True,
            ...     include_copy_number=True,
            ... )
            >>> # Returns KRAS mutation, EGFR amplification, etc.
        """
        logger.info(f"Getting cell line profile for {cell_line}")

        # Parse cell line name
        parsed_name = self._parse_cell_line_name(cell_line)

        profile = {
            "success": True,
            "cell_line": parsed_name,
        }

        # Fetch mutations
        if include_mutations:
            logger.debug("Fetching mutations")
            mutations = get_mutated_genes_in_cell_line(parsed_name, client=client)
            profile["mutations"] = self._format_mutations(mutations)
            logger.info(f"Found {len(profile['mutations'])} mutations")

        # Fetch copy number alterations
        if include_copy_number:
            logger.debug("Fetching copy number alterations")
            cna_genes = get_cna_genes_in_cell_line(parsed_name, client=client)
            profile["copy_number_alterations"] = self._format_cna_list(cna_genes)
            logger.info(f"Found {len(profile['copy_number_alterations'])} CNAs")

        # Fetch dependencies (DepMap)
        if include_dependencies:
            logger.debug("Fetching gene dependencies")
            # Note: May need raw Cypher if no library function
            profile["dependencies"] = self._fetch_dependencies(parsed_name, client)
            logger.info(f"Found {len(profile['dependencies'])} dependencies")

        # Fetch expression
        if include_expression:
            logger.debug("Fetching expression data")
            # Note: May need raw Cypher if no library function
            profile["expression"] = self._fetch_expression(parsed_name, client)
            logger.info(f"Found {len(profile['expression'])} expression values")

        return profile

    @autoclient()
    def get_mutated_genes(
        self,
        cell_line: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get all mutated genes in a cell line.

        This method retrieves the complete mutation profile from CCLE,
        including mutation types and protein changes.

        Args:
            cell_line: Cell line name (e.g., "A549", "HeLa")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with mutated genes:
                {
                    "success": True,
                    "cell_line": "A549",
                    "mutated_genes": [...],
                    "total_mutations": 15,
                }

        Example:
            >>> result = client.get_mutated_genes(cell_line="A549")
            >>> # Returns KRAS, TP53, STK11, KEAP1, etc.
        """
        logger.info(f"Getting mutated genes for {cell_line}")

        # Parse cell line name
        parsed_name = self._parse_cell_line_name(cell_line)

        # Query mutations
        mutations = get_mutated_genes_in_cell_line(parsed_name, client=client)
        logger.debug(f"Retrieved {len(mutations)} mutations")

        # Format response
        formatted_mutations = self._format_mutations(mutations)

        return {
            "success": True,
            "cell_line": parsed_name,
            "mutated_genes": formatted_mutations,
            "total_mutations": len(formatted_mutations),
        }

    @autoclient()
    def get_cell_lines_with_mutation(
        self,
        gene_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Find cell lines with mutations in specific gene.

        This method screens CCLE to identify all cell lines harboring
        mutations in a target gene. Useful for model selection.

        Args:
            gene_id: Gene CURIE or symbol (e.g., "hgnc:6407", "KRAS")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with cell lines:
                {
                    "success": True,
                    "gene_id": "hgnc:6407",
                    "cell_lines": [...],
                    "total_cell_lines": 42,
                }

        Example:
            >>> result = client.get_cell_lines_with_mutation(gene_id="KRAS")
            >>> # Returns A549, HCT116, SW480, etc. (KRAS mutant models)
        """
        logger.info(f"Finding cell lines with mutations in {gene_id}")

        # Parse gene identifier
        gene_tuple = self._parse_gene_id(gene_id)

        # Query cell lines
        cell_lines = get_cell_lines_with_mutation(gene_tuple, client=client)
        logger.debug(f"Retrieved {len(cell_lines)} cell lines")

        # Format response
        formatted_cell_lines = []
        for cell_line in cell_lines:
            formatted_cell_lines.append(self._format_cell_line_dict(cell_line))

        return {
            "success": True,
            "gene_id": gene_id,
            "cell_lines": formatted_cell_lines,
            "total_cell_lines": len(formatted_cell_lines),
        }

    @autoclient()
    def check_mutation(
        self,
        cell_line: str,
        gene_id: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Check if gene is mutated in cell line.

        This method performs a boolean check for presence of mutation
        in a specific gene within a cell line.

        Args:
            cell_line: Cell line name (e.g., "A549")
            gene_id: Gene CURIE or symbol (e.g., "hgnc:6407", "KRAS")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with boolean result:
                {
                    "success": True,
                    "is_mutated": True,
                    "cell_line": "A549",
                    "gene_id": "hgnc:6407",
                }

        Example:
            >>> result = client.check_mutation(
            ...     cell_line="A549",
            ...     gene_id="KRAS",
            ... )
            >>> assert result["is_mutated"] == True  # A549 has KRAS mutation
        """
        logger.info(f"Checking if {gene_id} is mutated in {cell_line}")

        # Parse identifiers
        parsed_name = self._parse_cell_line_name(cell_line)
        gene_tuple = self._parse_gene_id(gene_id)

        # Check mutation
        is_mutated = is_gene_mutated_in_cell_line(
            gene_tuple,
            parsed_name,
            client=client
        )

        logger.info(f"Mutation check: {is_mutated}")

        return {
            "success": True,
            "is_mutated": bool(is_mutated),
            "cell_line": parsed_name,
            "gene_id": gene_id,
        }

    # Helper methods

    def _parse_cell_line_name(self, name: str) -> str:
        """
        Parse and normalize cell line name.

        Args:
            name: Cell line name (e.g., "A549", "a549", "HeLa")

        Returns:
            Normalized cell line name

        Example:
            >>> client._parse_cell_line_name("a549")
            "A549"
            >>> client._parse_cell_line_name("HELA")
            "HeLa"
        """
        # Remove common prefixes if present
        name = name.strip()

        # Handle known cell line name variations
        name_map = {
            "hela": "HeLa",
            "mcf7": "MCF7",
            "mcf-7": "MCF7",
            "a549": "A549",
            "hct116": "HCT116",
            "hct-116": "HCT116",
            "sw480": "SW480",
            "sw-480": "SW480",
        }

        normalized = name_map.get(name.lower(), name)
        logger.debug(f"Normalized cell line name: {name} -> {normalized}")
        return normalized

    def _parse_gene_id(self, gene_id: str) -> Tuple[str, str]:
        """
        Convert gene CURIE to (namespace, identifier) tuple.

        Args:
            gene_id: Gene CURIE or symbol (e.g., "hgnc:6407", "KRAS")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_gene_id("hgnc:6407")
            ("HGNC", "6407")
            >>> client._parse_gene_id("KRAS")
            ("HGNC", "KRAS")
        """
        if ":" in gene_id:
            namespace, identifier = gene_id.split(":", 1)
            # CoGEx expects uppercase namespaces
            return (namespace.upper(), identifier)
        else:
            # Assume HGNC gene symbol
            logger.debug(f"Assuming HGNC namespace for: {gene_id}")
            return ("HGNC", gene_id)

    def _format_mutations(self, mutations: List[Any]) -> List[Dict[str, Any]]:
        """
        Format mutations from CoGEx response.

        Args:
            mutations: List of mutation objects from CoGEx

        Returns:
            List of formatted mutation dictionaries

        Example:
            >>> mutations = [Mutation(gene="KRAS", aa_change="G12C", ...)]
            >>> client._format_mutations(mutations)
            [{"gene_id": "hgnc:6407", "gene_name": "KRAS", ...}]
        """
        formatted = []
        for mutation in mutations:
            # Handle both dict and object responses
            if isinstance(mutation, dict):
                mut_dict = mutation
            else:
                # Convert object to dict
                mut_dict = {
                    "gene": getattr(mutation, "gene", "Unknown"),
                    "namespace": getattr(mutation, "namespace", "hgnc"),
                    "identifier": getattr(mutation, "identifier", "unknown"),
                    "mutation_type": getattr(mutation, "mutation_type", "unknown"),
                    "protein_change": getattr(mutation, "protein_change", None),
                    "variant_classification": getattr(mutation, "variant_classification", None),
                }

            formatted.append(self._format_mutation_dict(mut_dict))

        return formatted

    def _format_mutation_dict(self, mutation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format individual mutation dictionary.

        Args:
            mutation: Raw mutation data

        Returns:
            Formatted mutation dict

        Example:
            >>> mut = {"gene": "KRAS", "protein_change": "G12C", ...}
            >>> client._format_mutation_dict(mut)
            {"gene_id": "hgnc:6407", "gene_name": "KRAS", ...}
        """
        gene_name = mutation.get("gene", "Unknown")
        namespace = mutation.get("namespace", "hgnc")
        identifier = mutation.get("identifier", gene_name)

        return {
            "gene_id": f"{namespace.lower()}:{identifier}",
            "gene_name": gene_name,
            "mutation_type": mutation.get("mutation_type", "unknown"),
            "protein_change": mutation.get("protein_change"),
            "variant_classification": mutation.get("variant_classification"),
            "is_driver": mutation.get("is_driver", False),
        }

    def _format_cell_line_dict(self, cell_line: Any) -> Dict[str, Any]:
        """
        Format cell line dictionary.

        Args:
            cell_line: Raw cell line data from CoGEx

        Returns:
            Formatted cell line dict

        Example:
            >>> cl = CellLine(name="A549", tissue="lung", ...)
            >>> client._format_cell_line_dict(cl)
            {"name": "A549", "tissue": "lung", ...}
        """
        # Handle both dict and object responses
        if isinstance(cell_line, dict):
            cl_dict = cell_line
        else:
            # Convert object to dict
            cl_dict = {
                "name": getattr(cell_line, "name", "Unknown"),
                "ccle_id": getattr(cell_line, "ccle_id", None),
                "depmap_id": getattr(cell_line, "depmap_id", None),
                "tissue": getattr(cell_line, "tissue", None),
                "disease": getattr(cell_line, "disease", None),
            }

        name = cl_dict.get("name", "Unknown")
        return {
            "name": name,
            "ccle_id": cl_dict.get("ccle_id", f"ccle:{name}"),
            "depmap_id": cl_dict.get("depmap_id", f"depmap:{name}"),
            "tissue": cl_dict.get("tissue"),
            "disease": cl_dict.get("disease"),
        }

    def _format_cna_list(self, cna_genes: List[Any]) -> List[Dict[str, Any]]:
        """
        Format copy number alteration list.

        Args:
            cna_genes: List of genes with CNAs from CoGEx

        Returns:
            List of formatted CNA dictionaries
        """
        formatted = []
        for cna in cna_genes:
            # Handle both dict and object responses
            if isinstance(cna, dict):
                cna_dict = cna
            else:
                cna_dict = {
                    "gene": getattr(cna, "gene", "Unknown"),
                    "namespace": getattr(cna, "namespace", "hgnc"),
                    "identifier": getattr(cna, "identifier", "unknown"),
                    "copy_number": getattr(cna, "copy_number", 2.0),
                }

            gene_name = cna_dict.get("gene", "Unknown")
            namespace = cna_dict.get("namespace", "hgnc")
            identifier = cna_dict.get("identifier", gene_name)
            copy_num = cna_dict.get("copy_number", 2.0)

            # Classify alteration type
            if copy_num > 2.5:
                alt_type = "amplification"
            elif copy_num < 1.5:
                alt_type = "deletion"
            else:
                alt_type = "neutral"

            formatted.append({
                "gene_id": f"{namespace.lower()}:{identifier}",
                "gene_name": gene_name,
                "copy_number": float(copy_num),
                "alteration_type": alt_type,
            })

        return formatted

    def _fetch_dependencies(
        self,
        cell_line: str,
        client: Neo4jClient,
    ) -> List[Dict[str, Any]]:
        """
        Fetch gene dependency scores from DepMap.

        Note: This may require raw Cypher if no library function exists.

        Args:
            cell_line: Cell line name
            client: Neo4j client

        Returns:
            List of gene dependencies with scores
        """
        # Placeholder - implement when DepMap schema is confirmed
        logger.warning(f"Dependency data not yet implemented for {cell_line}")
        return []

    def _fetch_expression(
        self,
        cell_line: str,
        client: Neo4jClient,
    ) -> List[Dict[str, Any]]:
        """
        Fetch gene expression data.

        Note: This may require raw Cypher if no library function exists.

        Args:
            cell_line: Cell line name
            client: Neo4j client

        Returns:
            List of expression values
        """
        # Placeholder - implement when expression schema is confirmed
        logger.warning(f"Expression data not yet implemented for {cell_line}")
        return []
