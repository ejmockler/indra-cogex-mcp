"""
Cell Markers

Extracted from monolithic server.py
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    ENRICHMENT_TIMEOUT,
    STANDARD_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle cell markers query - Tool 14."""
    try:
        # Parse params
        from cogex_mcp.schemas import CellMarkerQuery, CellMarkerMode
        params = CellMarkerQuery(**args)

        # Route to appropriate handler based on mode
        if params.mode == CellMarkerMode.GET_MARKERS:
            result = await _get_markers_for_cell_type(params)
        elif params.mode == CellMarkerMode.GET_CELL_TYPES:
            result = await _get_cell_types_for_marker(params)
        elif params.mode == CellMarkerMode.CHECK_MARKER:
            result = await _check_marker_status(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown query mode '{params.mode}'")]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Cell Markers Mode Implementations

async def _get_markers_for_cell_type(params) -> dict[str, Any]:
    """Mode: get_markers - Get marker genes for a specific cell type."""
    if not params.cell_type:
        raise ValueError("cell_type parameter required for get_markers mode")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "cell_type": params.cell_type,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    marker_data = await adapter.query(
        "get_markers_for_cell_type",
        **query_params,
    )

    # Parse cell type metadata
    cell_type_node = _parse_cell_type_node(
        marker_data.get("cell_type", {}),
        params.cell_type,
        params.tissue,
        params.species,
    )

    # Parse marker list
    markers = _parse_marker_list(marker_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=markers,
        total_count=marker_data.get("total_count", len(markers)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "cell_type": cell_type_node,
        "markers": markers,
        "pagination": pagination.model_dump(),
    }


async def _get_cell_types_for_marker(params) -> dict[str, Any]:
    """Mode: get_cell_types - Find cell types that express a specific marker gene."""
    if not params.marker:
        raise ValueError("marker parameter required for get_cell_types mode")

    # Resolve marker gene identifier
    resolver = get_resolver()
    marker_gene = await resolver.resolve_gene(params.marker)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": marker_gene.curie,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    cell_type_data = await adapter.query(
        "get_cell_types_for_marker",
        **query_params,
    )

    # Parse cell type list
    cell_types = _parse_cell_type_list(cell_type_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_types,
        total_count=cell_type_data.get("total_count", len(cell_types)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "marker": marker_gene.model_dump(),
        "cell_types": cell_types,
        "pagination": pagination.model_dump(),
    }


async def _check_marker_status(params) -> dict[str, Any]:
    """Mode: check_marker - Check if a specific gene is a marker for a specific cell type."""
    if not params.cell_type:
        raise ValueError("cell_type parameter required for check_marker mode")
    if not params.marker:
        raise ValueError("marker parameter required for check_marker mode")

    # Resolve marker gene identifier
    resolver = get_resolver()
    marker_gene = await resolver.resolve_gene(params.marker)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": marker_gene.curie,
        "cell_type": params.cell_type,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    check_data = await adapter.query(
        "is_cell_marker",
        **query_params,
    )

    # Parse result
    is_marker = check_data.get("is_marker", False) if check_data.get("success") else False

    # Parse cell type metadata if available
    cell_type_node = None
    if check_data.get("cell_type"):
        cell_type_node = _parse_cell_type_node(
            check_data["cell_type"],
            params.cell_type,
            params.tissue,
            params.species,
        )
    else:
        # Create basic cell type node
        cell_type_node = {
            "name": params.cell_type,
            "tissue": params.tissue or "unknown",
            "species": params.species or "human",
            "marker_count": 0,
        }

    return {
        "is_marker": is_marker,
        "marker": marker_gene.model_dump(),
        "cell_type": cell_type_node,
    }


def _parse_cell_type_node(
    data: dict[str, Any],
    cell_type_name: str,
    tissue: str | None,
    species: str,
) -> dict[str, Any]:
    """Parse cell type node from backend response."""
    if not data:
        return {
            "name": cell_type_name,
            "tissue": tissue or "unknown",
            "species": species or "human",
            "marker_count": 0,
        }

    return {
        "name": data.get("name", cell_type_name),
        "tissue": data.get("tissue", tissue or "unknown"),
        "species": data.get("species", species or "human"),
        "marker_count": data.get("marker_count", 0),
    }


def _parse_marker_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse marker list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    markers = []
    for record in data["records"]:
        gene_name = record.get("gene", record.get("marker", "Unknown"))
        gene_id = record.get("gene_id", record.get("marker_id", "unknown:unknown"))

        # Extract namespace and identifier from CURIE
        namespace = "hgnc"
        identifier = gene_id
        if ":" in gene_id:
            namespace, identifier = gene_id.split(":", 1)

        markers.append(
            {
                "gene": {
                    "name": gene_name,
                    "curie": gene_id,
                    "namespace": namespace,
                    "identifier": identifier,
                },
                "marker_type": record.get("marker_type", "unknown"),
                "evidence": record.get("evidence", "unknown"),
            }
        )

    return markers


def _parse_cell_type_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell type list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_types = []
    for record in data["records"]:
        cell_types.append(
            {
                "name": record.get("cell_type", record.get("name", "Unknown")),
                "tissue": record.get("tissue", "unknown"),
                "species": record.get("species", "human"),
                "marker_count": record.get("marker_count", 0),
            }
        )

    return cell_types


