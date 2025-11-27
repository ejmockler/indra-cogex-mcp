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

    # Build query parameters for unified cell_marker_query
    query_params = {
        "mode": "get_markers",
        "cell_type": params.cell_type,
        "species": params.species or "human",
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add tissue filter if specified
    if params.tissue:
        query_params["tissue"] = params.tissue

    marker_data = await adapter.query(
        "cell_marker_query",
        **query_params,
    )

    # Client returns formatted data directly
    markers = marker_data.get("markers", [])

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=markers,
        total_count=marker_data.get("total_markers", len(markers)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "cell_type": {
            "name": marker_data.get("cell_type", params.cell_type),
            "species": marker_data.get("species", params.species or "human"),
            "tissue": marker_data.get("tissue", params.tissue),
            "marker_count": marker_data.get("total_markers", len(markers)),
        },
        "markers": markers,
        "pagination": pagination.model_dump(),
    }


async def _get_cell_types_for_marker(params) -> dict[str, Any]:
    """Mode: get_cell_types - Find cell types that express a specific marker gene."""
    if not params.marker:
        raise ValueError("marker parameter required for get_cell_types mode")

    adapter = await get_adapter()

    # Build query parameters for unified cell_marker_query
    query_params = {
        "mode": "get_cell_types",
        "marker": params.marker,
        "species": params.species or "human",
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add tissue filter if specified
    if params.tissue:
        query_params["tissue"] = params.tissue

    cell_type_data = await adapter.query(
        "cell_marker_query",
        **query_params,
    )

    # Client returns formatted data directly
    cell_types = cell_type_data.get("cell_types", [])

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_types,
        total_count=cell_type_data.get("total_cell_types", len(cell_types)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "marker": {
            "name": params.marker,
            "species": cell_type_data.get("species", params.species or "human"),
        },
        "cell_types": cell_types,
        "pagination": pagination.model_dump(),
    }


async def _check_marker_status(params) -> dict[str, Any]:
    """Mode: check_marker - Check if a specific gene is a marker for a specific cell type."""
    if not params.cell_type:
        raise ValueError("cell_type parameter required for check_marker mode")
    if not params.marker:
        raise ValueError("marker parameter required for check_marker mode")

    adapter = await get_adapter()

    # Build query parameters for unified cell_marker_query
    query_params = {
        "mode": "check_marker",
        "cell_type": params.cell_type,
        "marker": params.marker,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    check_data = await adapter.query(
        "cell_marker_query",
        **query_params,
    )

    # Client returns formatted data directly
    is_marker = check_data.get("is_marker", False)

    return {
        "is_marker": is_marker,
        "marker": {
            "name": check_data.get("marker_gene", params.marker),
            "gene_id": check_data.get("gene_id", "unknown"),
        },
        "cell_type": {
            "name": check_data.get("cell_type", params.cell_type),
            "species": params.species or "human",
            "tissue": params.tissue,
        },
    }


