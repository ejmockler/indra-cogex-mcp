"""
Identifier

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
    """Handle identifier resolution - Tool 11."""
    try:
        identifiers = args.get("identifiers")
        from_namespace = args.get("from_namespace")
        to_namespace = args.get("to_namespace")
        response_format = args.get("response_format", "markdown")

        # Validate inputs
        if not identifiers:
            return [types.TextContent(
                type="text",
                text="Error: identifiers list cannot be empty"
            )]

        if not from_namespace or not to_namespace:
            return [types.TextContent(
                type="text",
                text="Error: Both from_namespace and to_namespace are required"
            )]

        # Execute conversion
        adapter = await get_adapter()
        result = await _convert_identifiers(
            adapter=adapter,
            identifiers=identifiers,
            from_namespace=from_namespace,
            to_namespace=to_namespace,
        )

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 11 Implementation
async def _convert_identifiers(
    adapter,
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> dict[str, Any]:
    """Convert identifiers between namespaces using appropriate backend endpoint."""
    # Determine which backend endpoint to use
    endpoint, query_params = _select_identifier_endpoint(
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    # Query backend
    conversion_data = await adapter.query(
        endpoint,
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse results
    mappings, unmapped = _parse_conversion_results(
        data=conversion_data,
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    # Build response
    return {
        "mappings": mappings,
        "unmapped": unmapped,
        "statistics": {
            "total_input": len(identifiers),
            "mapped": len(mappings),
            "unmapped": len(unmapped),
            "total_targets": sum(len(m["target_ids"]) for m in mappings),
        },
        "from_namespace": from_namespace,
        "to_namespace": to_namespace,
    }


def _select_identifier_endpoint(
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> tuple[str, dict[str, Any]]:
    """Select appropriate backend endpoint based on namespace pair."""
    from_ns = from_namespace.lower()
    to_ns = to_namespace.lower()

    # Special case: hgnc.symbol → hgnc (symbol to HGNC ID)
    if from_ns == "hgnc.symbol" and to_ns == "hgnc":
        return "symbol_to_hgnc", {
            "symbols": identifiers,
        }

    # Special case: hgnc → uniprot
    if from_ns == "hgnc" and to_ns == "uniprot":
        return "hgnc_to_uniprot", {
            "hgnc_ids": identifiers,
        }

    # Generic case: use general map_identifiers endpoint
    return "map_identifiers", {
        "identifiers": identifiers,
        "from_namespace": from_namespace,
        "to_namespace": to_namespace,
    }


def _parse_conversion_results(
    data: dict[str, Any],
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse backend conversion results into mappings and unmapped lists."""
    if not data.get("success"):
        logger.warning(f"Backend conversion failed: {data.get('error', 'unknown error')}")
        # Return all as unmapped
        return [], identifiers

    mappings_data = data.get("mappings", {})
    if not mappings_data:
        # No mappings found
        return [], identifiers

    # Build mappings
    mappings: list[dict[str, Any]] = []
    unmapped: list[str] = []

    for source_id in identifiers:
        targets = mappings_data.get(source_id)

        if targets is None or (isinstance(targets, list) and len(targets) == 0):
            # No mapping found for this identifier
            unmapped.append(source_id)
        else:
            # Normalize to list
            if not isinstance(targets, list):
                targets = [targets]

            # Create mapping
            mapping = {
                "source_id": source_id,
                "target_ids": targets,
                "confidence": "exact" if targets else None,
            }
            mappings.append(mapping)

    return mappings, unmapped



