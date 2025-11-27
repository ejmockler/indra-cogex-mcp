"""
Direct CoGEx cell marker client.

Wraps INDRA CoGEx cell marker query functions to access CellMarker database
for cell type-specific marker genes and their expression patterns across
different tissues and species.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from indra_cogex.client.neo4j_client import Neo4jClient, autoclient
from indra_cogex.client.queries import (
    get_markers_for_cell_type,
    get_cell_types_for_marker,
    is_marker_for_cell_type,
)

logger = logging.getLogger(__name__)


class CellMarkerClient:
    """
    Direct cell marker data client using CoGEx library functions.

    Provides high-level interface to CellMarker database with:
    - Cell type → marker genes mapping
    - Marker gene → cell types mapping
    - Marker status validation
    - Tissue and species filtering

    Example usage:
        >>> client = CellMarkerClient()
        >>> result = client.get_cell_type_markers(
        ...     cell_type="T cell",
        ...     tissue="blood",
        ...     species="human",
        ... )
        >>> print(f"Found {len(result['markers'])} markers")
    """

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize cell marker client.

        Args:
            neo4j_client: Optional Neo4j client. If None, uses autoclient.
        """
        self.client = neo4j_client

    @autoclient()
    def get_cell_type_markers(
        self,
        cell_type: str,
        species: str = "human",
        tissue: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get marker genes for a specific cell type.

        This method queries CellMarker database for genes that are known
        markers for a specific cell type. Results can be filtered by tissue
        and species.

        Args:
            cell_type: Cell type name (e.g., "T cell", "B cell", "Neuron")
            species: Species name (default: "human")
            tissue: Optional tissue filter (e.g., "blood", "brain")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with markers and metadata:
                {
                    "success": True,
                    "cell_type": "T cell",
                    "markers": [
                        {
                            "gene": {"name": "CD3D", "curie": "hgnc:1673", ...},
                            "marker_type": "cell surface",
                            "evidence": "experimental",
                        },
                        ...
                    ],
                    "total_markers": 15,
                }

        Example:
            >>> result = client.get_cell_type_markers(
            ...     cell_type="T cell",
            ...     tissue="blood",
            ...     species="human",
            ... )
            >>> for marker in result["markers"]:
            ...     print(f"{marker['gene']['name']} - {marker['marker_type']}")
        """
        logger.info(f"Getting markers for cell type: {cell_type} (species={species}, tissue={tissue})")

        # Parse cell type name
        parsed_cell_type = self._parse_cell_type_name(cell_type)

        # Query CoGEx for markers
        markers_data = get_markers_for_cell_type(
            parsed_cell_type,
            client=client,
        )

        logger.debug(f"Retrieved {len(markers_data)} marker records")

        # Filter by tissue if specified
        if tissue:
            markers_data = [
                m for m in markers_data
                if self._matches_tissue(m, tissue)
            ]
            logger.debug(f"After tissue filter: {len(markers_data)} markers")

        # Filter by species if specified
        if species:
            markers_data = [
                m for m in markers_data
                if self._matches_species(m, species)
            ]
            logger.debug(f"After species filter: {len(markers_data)} markers")

        # Format markers
        formatted_markers = [self._format_marker_dict(m) for m in markers_data]

        return {
            "success": True,
            "cell_type": parsed_cell_type,
            "species": species,
            "tissue": tissue,
            "markers": formatted_markers,
            "total_markers": len(formatted_markers),
        }

    @autoclient()
    def get_marker_cell_types(
        self,
        marker_gene: str,
        species: str = "human",
        tissue: Optional[str] = None,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Get cell types expressing a specific marker gene.

        This method queries CellMarker database for all cell types that
        express a specific gene as a marker. Results can be filtered by
        tissue and species.

        Args:
            marker_gene: Gene name or CURIE (e.g., "CD3D", "hgnc:1673")
            species: Species name (default: "human")
            tissue: Optional tissue filter (e.g., "blood", "brain")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with cell types and metadata:
                {
                    "success": True,
                    "marker_gene": "CD3D",
                    "cell_types": [
                        {
                            "name": "T cell",
                            "tissue": "blood",
                            "species": "human",
                            "marker_count": 15,
                        },
                        ...
                    ],
                    "total_cell_types": 5,
                }

        Example:
            >>> result = client.get_marker_cell_types(
            ...     marker_gene="CD4",
            ...     tissue="blood",
            ...     species="human",
            ... )
            >>> for cell_type in result["cell_types"]:
            ...     print(f"{cell_type['name']} ({cell_type['tissue']})")
        """
        logger.info(f"Getting cell types for marker: {marker_gene} (species={species}, tissue={tissue})")

        # Parse gene identifier
        gene_tuple = self._parse_gene_id(marker_gene)

        # Query CoGEx for cell types
        cell_types_data = get_cell_types_for_marker(
            gene_tuple,
            client=client,
        )

        logger.debug(f"Retrieved {len(cell_types_data)} cell type records")

        # Filter by tissue if specified
        if tissue:
            cell_types_data = [
                ct for ct in cell_types_data
                if self._matches_tissue(ct, tissue)
            ]
            logger.debug(f"After tissue filter: {len(cell_types_data)} cell types")

        # Filter by species if specified
        if species:
            cell_types_data = [
                ct for ct in cell_types_data
                if self._matches_species(ct, species)
            ]
            logger.debug(f"After species filter: {len(cell_types_data)} cell types")

        # Format cell types
        formatted_cell_types = [self._format_cell_type_dict(ct) for ct in cell_types_data]

        return {
            "success": True,
            "marker_gene": marker_gene,
            "species": species,
            "tissue": tissue,
            "cell_types": formatted_cell_types,
            "total_cell_types": len(formatted_cell_types),
        }

    @autoclient()
    def check_marker_status(
        self,
        cell_type: str,
        marker_gene: str,
        *,
        client: Neo4jClient,
    ) -> Dict[str, Any]:
        """
        Check if a gene is a marker for a specific cell type.

        This method performs a boolean check for marker status,
        useful for validation and filtering.

        Args:
            cell_type: Cell type name (e.g., "T cell", "B cell")
            marker_gene: Gene name or CURIE (e.g., "CD3D", "hgnc:1673")
            client: Neo4j client (injected by autoclient)

        Returns:
            Dict with boolean result:
                {
                    "success": True,
                    "is_marker": True,
                    "cell_type": "T cell",
                    "marker_gene": "CD3D",
                    "gene_id": "hgnc:1673",
                }

        Example:
            >>> result = client.check_marker_status(
            ...     cell_type="T cell",
            ...     marker_gene="CD3D",
            ... )
            >>> print(f"CD3D is T cell marker: {result['is_marker']}")
        """
        logger.info(f"Checking if {marker_gene} is a marker for {cell_type}")

        # Parse identifiers
        parsed_cell_type = self._parse_cell_type_name(cell_type)
        gene_tuple = self._parse_gene_id(marker_gene)

        # Check marker status
        is_marker = is_marker_for_cell_type(
            gene_tuple,
            parsed_cell_type,
            client=client,
        )

        logger.info(f"Marker check: {marker_gene} for {cell_type} = {is_marker}")

        # Build gene_id string
        gene_id = f"{gene_tuple[0].lower()}:{gene_tuple[1]}"

        return {
            "success": True,
            "is_marker": bool(is_marker),
            "cell_type": parsed_cell_type,
            "marker_gene": marker_gene,
            "gene_id": gene_id,
        }

    # Helper methods

    def _parse_cell_type_name(self, name: str) -> str:
        """
        Parse and normalize cell type name.

        Args:
            name: Cell type name (e.g., "T cell", "t-cell", "T-Cell")

        Returns:
            Normalized cell type name

        Example:
            >>> client._parse_cell_type_name("t-cell")
            "T cell"
            >>> client._parse_cell_type_name("B Cell")
            "B cell"
        """
        # Remove extra whitespace
        name = " ".join(name.split())

        # Handle common cell type name variations
        name_map = {
            "t-cell": "T cell",
            "t cell": "T cell",
            "tcell": "T cell",
            "b-cell": "B cell",
            "b cell": "B cell",
            "bcell": "B cell",
            "nk cell": "NK cell",
            "nk-cell": "NK cell",
            "macrophage": "Macrophage",
            "monocyte": "Monocyte",
            "neutrophil": "Neutrophil",
            "dendritic cell": "Dendritic cell",
            "neuron": "Neuron",
            "astrocyte": "Astrocyte",
        }

        normalized = name_map.get(name.lower(), name)
        logger.debug(f"Normalized cell type name: {name} -> {normalized}")
        return normalized

    def _parse_gene_id(self, gene_id: str) -> Tuple[str, str]:
        """
        Convert gene CURIE to (namespace, identifier) tuple.

        Args:
            gene_id: Gene CURIE or symbol (e.g., "hgnc:1673", "CD3D")

        Returns:
            Tuple of (namespace, identifier) for CoGEx

        Example:
            >>> client._parse_gene_id("hgnc:1673")
            ("HGNC", "1673")
            >>> client._parse_gene_id("CD3D")
            ("HGNC", "CD3D")
        """
        if ":" in gene_id:
            namespace, identifier = gene_id.split(":", 1)
            # CoGEx expects uppercase namespaces
            return (namespace.upper(), identifier)
        else:
            # Assume HGNC gene symbol
            logger.debug(f"Assuming HGNC namespace for: {gene_id}")
            return ("HGNC", gene_id)

    def _format_marker_dict(self, marker: Any) -> Dict[str, Any]:
        """
        Format individual marker dictionary.

        Args:
            marker: Raw marker data from CoGEx

        Returns:
            Formatted marker dict with gene info and marker metadata

        Example:
            >>> marker = {"gene": "CD3D", "marker_type": "cell surface", ...}
            >>> client._format_marker_dict(marker)
            {"gene": {"name": "CD3D", "curie": "hgnc:1673", ...}, ...}
        """
        # Handle both dict and object responses
        if isinstance(marker, dict):
            marker_dict = marker
        else:
            # Convert object to dict
            marker_dict = {
                "gene": getattr(marker, "gene", "Unknown"),
                "gene_id": getattr(marker, "gene_id", None),
                "namespace": getattr(marker, "namespace", "hgnc"),
                "identifier": getattr(marker, "identifier", "unknown"),
                "marker_type": getattr(marker, "marker_type", "unknown"),
                "evidence": getattr(marker, "evidence", "unknown"),
                "tissue": getattr(marker, "tissue", None),
                "species": getattr(marker, "species", "human"),
            }

        gene_name = marker_dict.get("gene", "Unknown")
        namespace = marker_dict.get("namespace", "hgnc")
        identifier = marker_dict.get("identifier", gene_name)

        return {
            "gene": {
                "name": gene_name,
                "curie": f"{namespace.lower()}:{identifier}",
                "namespace": namespace.lower(),
                "identifier": identifier,
            },
            "marker_type": marker_dict.get("marker_type", "unknown"),
            "evidence": marker_dict.get("evidence", "unknown"),
            "tissue": marker_dict.get("tissue"),
            "species": marker_dict.get("species", "human"),
        }

    def _format_cell_type_dict(self, cell_type: Any) -> Dict[str, Any]:
        """
        Format individual cell type dictionary.

        Args:
            cell_type: Raw cell type data from CoGEx

        Returns:
            Formatted cell type dict

        Example:
            >>> ct = {"name": "T cell", "tissue": "blood", ...}
            >>> client._format_cell_type_dict(ct)
            {"name": "T cell", "tissue": "blood", "species": "human", ...}
        """
        # Handle both dict and object responses
        if isinstance(cell_type, dict):
            ct_dict = cell_type
        else:
            # Convert object to dict
            ct_dict = {
                "name": getattr(cell_type, "name", "Unknown"),
                "cell_type": getattr(cell_type, "cell_type", None),
                "tissue": getattr(cell_type, "tissue", None),
                "species": getattr(cell_type, "species", "human"),
                "marker_count": getattr(cell_type, "marker_count", 0),
            }

        name = ct_dict.get("name") or ct_dict.get("cell_type", "Unknown")

        return {
            "name": name,
            "tissue": ct_dict.get("tissue", "unknown"),
            "species": ct_dict.get("species", "human"),
            "marker_count": ct_dict.get("marker_count", 0),
        }

    def _matches_tissue(self, data: Any, tissue: str) -> bool:
        """
        Check if data matches tissue filter.

        Args:
            data: Marker or cell type data (dict or object)
            tissue: Tissue name to match

        Returns:
            True if matches tissue filter

        Example:
            >>> marker = {"tissue": "blood"}
            >>> client._matches_tissue(marker, "blood")
            True
        """
        if isinstance(data, dict):
            data_tissue = data.get("tissue")
        else:
            data_tissue = getattr(data, "tissue", None)

        if not data_tissue:
            return False

        # Case-insensitive matching
        return data_tissue.lower() == tissue.lower()

    def _matches_species(self, data: Any, species: str) -> bool:
        """
        Check if data matches species filter.

        Args:
            data: Marker or cell type data (dict or object)
            species: Species name to match

        Returns:
            True if matches species filter

        Example:
            >>> marker = {"species": "human"}
            >>> client._matches_species(marker, "human")
            True
        """
        if isinstance(data, dict):
            data_species = data.get("species")
        else:
            data_species = getattr(data, "species", None)

        if not data_species:
            # Default to human if not specified
            return species.lower() == "human"

        # Case-insensitive matching
        return data_species.lower() == species.lower()
