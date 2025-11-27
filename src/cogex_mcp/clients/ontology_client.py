"""
Direct CoGEx ontology client.

Wraps INDRA CoGEx ontology functions for ontology hierarchy navigation.
Provides methods to query parent/child terms in ontology hierarchies like
GO (Gene Ontology), HPO (Human Phenotype Ontology), and MONDO (disease ontology).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_ontology_parent_terms,
    get_ontology_child_terms,
)

logger = logging.getLogger(__name__)


class OntologyClient:
    """
    Direct ontology hierarchy queries using CoGEx library functions.

    Provides high-level interface to ontology navigation with:
    - Parent/ancestor term retrieval
    - Child/descendant term retrieval
    - Bidirectional hierarchy traversal
    - Multi-level depth control

    Supports multiple ontologies:
    - GO (Gene Ontology): Biological processes, molecular functions, cellular components
    - HPO (Human Phenotype Ontology): Clinical phenotypes and diseases
    - MONDO: Disease ontology with cross-references
    - Others: Any ontology in CoGEx with hierarchical relationships

    Example usage:
        >>> client = OntologyClient()
        >>> result = client.get_hierarchy(
        ...     term="GO:0006915",  # apoptosis
        ...     direction="both",
        ...     max_depth=2,
        ... )
        >>> print(f"Found {len(result['parents'])} parents, {len(result['children'])} children")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize ontology client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_hierarchy(
        self,
        term: str,
        direction: str = "parents",
        max_depth: int = 2,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Navigate ontology hierarchy in specified direction(s).

        This is the primary method for ontology navigation. It can traverse:
        - Upward (parents/ancestors): More general terms
        - Downward (children/descendants): More specific terms
        - Both directions: Complete local hierarchy

        Args:
            term: Ontology term CURIE (e.g., "GO:0006915", "HP:0001250")
            direction: Navigation direction: "parents", "children", or "both"
            max_depth: Maximum traversal depth (1-5, default: 2)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with hierarchy data:
                {
                    "success": True,
                    "term": "GO:0006915",
                    "term_name": "apoptotic process",
                    "parents": [...],  # List of parent terms (if direction includes parents)
                    "children": [...],  # List of child terms (if direction includes children)
                    "total_parents": 5,
                    "total_children": 42
                }

        Example:
            >>> # Get parent hierarchy for apoptosis
            >>> result = client.get_hierarchy(
            ...     term="GO:0006915",
            ...     direction="parents",
            ...     max_depth=3,
            ... )
            >>> for parent in result["parents"]:
            ...     print(f"  {parent['name']} ({parent['curie']}) - depth {parent['depth']}")

            >>> # Get complete local hierarchy
            >>> result = client.get_hierarchy(
            ...     term="HP:0001250",  # seizures
            ...     direction="both",
            ...     max_depth=2,
            ... )
        """
        logger.info(f"Getting {direction} hierarchy for term: {term}, max_depth={max_depth}")

        # Validate direction
        if direction not in ("parents", "children", "both"):
            raise ValueError(f"Invalid direction: {direction}. Must be 'parents', 'children', or 'both'")

        # Validate depth
        if not (1 <= max_depth <= 5):
            raise ValueError(f"Invalid max_depth: {max_depth}. Must be between 1 and 5")

        # Parse term CURIE
        namespace, identifier = self._parse_term_id(term)

        # Initialize result
        result = {
            "success": True,
            "term": term,
            "term_name": None,
            "parents": None,
            "children": None,
            "total_parents": 0,
            "total_children": 0,
        }

        # Fetch parents if requested
        if direction in ("parents", "both"):
            parents_list = self._traverse_hierarchy(
                term=term,
                direction="parents",
                max_depth=max_depth,
                client=client,
            )
            result["parents"] = parents_list
            result["total_parents"] = len(parents_list)

        # Fetch children if requested
        if direction in ("children", "both"):
            children_list = self._traverse_hierarchy(
                term=term,
                direction="children",
                max_depth=max_depth,
                client=client,
            )
            result["children"] = children_list
            result["total_children"] = len(children_list)

        logger.info(
            f"Retrieved hierarchy: {result['total_parents']} parents, "
            f"{result['total_children']} children"
        )

        return result

    @autoclient()
    def get_parent_terms(
        self,
        term: str,
        max_depth: int = 2,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get parent/ancestor terms in ontology hierarchy.

        Traverses upward to more general terms (e.g., "cell death" → "biological process").

        Args:
            term: Ontology term CURIE (e.g., "GO:0006915")
            max_depth: Maximum traversal depth (1-5, default: 2)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with parent terms:
                {
                    "success": True,
                    "term": "GO:0006915",
                    "parents": [...],
                    "total_parents": 5
                }

        Example:
            >>> result = client.get_parent_terms(
            ...     term="GO:0006915",  # apoptotic process
            ...     max_depth=3,
            ... )
            >>> print(f"Found {result['total_parents']} ancestor terms")
        """
        logger.info(f"Getting parent terms for: {term}, max_depth={max_depth}")

        # Validate depth
        if not (1 <= max_depth <= 5):
            raise ValueError(f"Invalid max_depth: {max_depth}. Must be between 1 and 5")

        # Traverse hierarchy
        parents_list = self._traverse_hierarchy(
            term=term,
            direction="parents",
            max_depth=max_depth,
            client=client,
        )

        result = {
            "success": True,
            "term": term,
            "parents": parents_list,
            "total_parents": len(parents_list),
        }

        logger.info(f"Retrieved {result['total_parents']} parent terms")
        return result

    @autoclient()
    def get_child_terms(
        self,
        term: str,
        max_depth: int = 2,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get child/descendant terms in ontology hierarchy.

        Traverses downward to more specific terms (e.g., "cell death" → "apoptosis").

        Args:
            term: Ontology term CURIE (e.g., "GO:0008219")
            max_depth: Maximum traversal depth (1-5, default: 2)
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with child terms:
                {
                    "success": True,
                    "term": "GO:0008219",
                    "children": [...],
                    "total_children": 42
                }

        Example:
            >>> result = client.get_child_terms(
            ...     term="GO:0008219",  # cell death
            ...     max_depth=2,
            ... )
            >>> for child in result["children"]:
            ...     print(f"  - {child['name']} (depth {child['depth']})")
        """
        logger.info(f"Getting child terms for: {term}, max_depth={max_depth}")

        # Validate depth
        if not (1 <= max_depth <= 5):
            raise ValueError(f"Invalid max_depth: {max_depth}. Must be between 1 and 5")

        # Traverse hierarchy
        children_list = self._traverse_hierarchy(
            term=term,
            direction="children",
            max_depth=max_depth,
            client=client,
        )

        result = {
            "success": True,
            "term": term,
            "children": children_list,
            "total_children": len(children_list),
        }

        logger.info(f"Retrieved {result['total_children']} child terms")
        return result

    # Helper methods

    def _parse_term_id(self, term: str) -> Tuple[str, str]:
        """
        Parse ontology term CURIE into (namespace, identifier) tuple.

        Args:
            term: CURIE string (e.g., "GO:0006915", "HP:0001250")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Raises:
            ValueError: If term format is invalid

        Example:
            >>> client._parse_term_id("GO:0006915")
            ("GO", "0006915")
            >>> client._parse_term_id("HP:0001250")
            ("HP", "0001250")
        """
        if ":" not in term:
            raise ValueError(
                f"Invalid term format: '{term}'. Expected CURIE format like 'GO:0006915'"
            )

        namespace, identifier = term.split(":", 1)

        # Validate namespace
        if not namespace:
            raise ValueError(f"Empty namespace in term: '{term}'")

        # Validate identifier
        if not identifier:
            raise ValueError(f"Empty identifier in term: '{term}'")

        return (namespace.upper(), identifier)

    def _format_term_dict(self, node: Any, depth: int = 1) -> Dict[str, Any]:
        """
        Format ontology term node as dictionary.

        Args:
            node: CoGEx Node object from ontology query
            depth: Depth level in hierarchy (1 = immediate parent/child)

        Returns:
            Formatted term dictionary with standardized fields

        Example:
            >>> node = Node(db_ns="GO", db_id="0006915", labels=["BiologicalProcess"])
            >>> formatted = client._format_term_dict(node, depth=2)
            >>> formatted
            {
                "curie": "go:0006915",
                "name": "apoptotic process",
                "namespace": "go",
                "identifier": "0006915",
                "depth": 2,
                "relationship": "is_a"
            }
        """
        # Extract namespace and identifier
        namespace = getattr(node, "db_ns", "unknown")
        identifier = getattr(node, "db_id", "unknown")

        # Extract name (may be in different attributes)
        name = None
        if hasattr(node, "name"):
            name = node.name
        elif hasattr(node, "data") and isinstance(node.data, dict):
            name = node.data.get("name")

        if not name:
            name = f"{namespace}:{identifier}"

        # Build CURIE
        curie = f"{namespace.lower()}:{identifier}"

        return {
            "curie": curie,
            "name": name,
            "namespace": namespace.lower(),
            "identifier": identifier,
            "depth": depth,
            "relationship": "is_a",  # Default relationship type
        }

    def _traverse_hierarchy(
        self,
        term: str,
        direction: str,
        max_depth: int,
        client: Neo4jClient,
    ) -> List[Dict[str, Any]]:
        """
        Recursively traverse ontology hierarchy up to max_depth.

        This implements breadth-first traversal to collect all terms
        within the specified depth range.

        Args:
            term: Starting ontology term CURIE
            direction: "parents" or "children"
            max_depth: Maximum depth to traverse
            client: Neo4j client

        Returns:
            List of formatted term dictionaries with depth information

        Example:
            >>> terms = client._traverse_hierarchy(
            ...     term="GO:0006915",
            ...     direction="parents",
            ...     max_depth=2,
            ...     client=client,
            ... )
            >>> len(terms)
            5
        """
        logger.debug(f"Traversing {direction} for {term}, max_depth={max_depth}")

        # Parse term
        namespace, identifier = self._parse_term_id(term)
        term_tuple = (namespace, identifier)

        # Choose appropriate CoGEx function
        if direction == "parents":
            query_func = get_ontology_parent_terms
        elif direction == "children":
            query_func = get_ontology_child_terms
        else:
            raise ValueError(f"Invalid direction: {direction}")

        # Collect all terms with BFS
        all_terms = []
        visited = set()
        current_level = [term_tuple]

        for current_depth in range(1, max_depth + 1):
            if not current_level:
                break

            next_level = []

            for current_term in current_level:
                # Skip if already visited
                term_key = f"{current_term[0]}:{current_term[1]}"
                if term_key in visited:
                    continue
                visited.add(term_key)

                # Query CoGEx
                try:
                    related_nodes = query_func(current_term, client=client)

                    # Process results
                    for node in related_nodes:
                        formatted = self._format_term_dict(node, depth=current_depth)

                        # Add to results
                        all_terms.append(formatted)

                        # Add to next level for further traversal
                        node_ns = getattr(node, "db_ns", "unknown")
                        node_id = getattr(node, "db_id", "unknown")
                        next_level.append((node_ns, node_id))

                except Exception as e:
                    logger.warning(f"Error querying {direction} for {current_term}: {e}")
                    continue

            current_level = next_level

        logger.debug(f"Found {len(all_terms)} {direction} terms")
        return all_terms
