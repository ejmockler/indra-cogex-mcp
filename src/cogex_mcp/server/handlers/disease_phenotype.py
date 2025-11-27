"""
Tool 1: Disease/Phenotype Query Handler

Handles disease/phenotype queries and their bidirectional relationships.

Modes:
- disease_to_mechanisms: Get comprehensive disease profile
- phenotype_to_diseases: Find diseases with a phenotype
- check_phenotype: Boolean check for disease-phenotype association
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.constants import CHARACTER_LIMIT, STANDARD_QUERY_TIMEOUT

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle disease/phenotype query."""
    mode = args.get("mode")
    disease = args.get("disease")
    phenotype = args.get("phenotype")
    response_format = args.get("response_format", "markdown")

    # Route to appropriate handler based on mode
    if mode == "disease_to_mechanisms":
        if not disease:
            return [types.TextContent(
                type="text",
                text="Error: disease parameter required for disease_to_mechanisms mode"
            )]
        result = await _disease_to_mechanisms(args)
    elif mode == "phenotype_to_diseases":
        if not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: phenotype parameter required for phenotype_to_diseases mode"
            )]
        result = await _phenotype_to_diseases(args)
    elif mode == "check_phenotype":
        if not disease or not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: both disease and phenotype parameters required for check_phenotype mode"
            )]
        result = await _check_phenotype(args)
    else:
        return [types.TextContent(
            type="text",
            text=f"Error: Unknown query mode '{mode}'"
        )]

    # Format response
    formatter = get_formatter()
    response = formatter.format_response(
        data=result,
        format_type=response_format,
        max_chars=CHARACTER_LIMIT,
    )

    return [types.TextContent(type="text", text=response)]


async def _disease_to_mechanisms(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive disease profile with all molecular mechanisms."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()

    # Call disease_query with disease_to_mechanisms mode
    result = await adapter.query(
        "disease_query",
        mode="disease_to_mechanisms",
        disease_id=disease_ref.curie,
        include_genes=args.get("include_genes", True),
        include_phenotypes=args.get("include_phenotypes", True),
        min_evidence=args.get("min_evidence", 1),
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Add resolved disease info to result
    if result.get("success"):
        result["disease"] = {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        }

    return result


async def _phenotype_to_diseases(args: dict[str, Any]) -> dict[str, Any]:
    """Find diseases associated with a specific phenotype."""
    phenotype_id = args["phenotype"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()

    # Call disease_query with phenotype_to_diseases mode
    result = await adapter.query(
        "disease_query",
        mode="phenotype_to_diseases",
        phenotype_id=phenotype_id,
        limit=limit,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Format pagination info
    if result.get("success"):
        diseases = result.get("diseases", [])
        result["pagination"] = {
            "total_count": result.get("pagination", {}).get("count", len(diseases)),
            "count": len(diseases),
            "offset": offset,
            "limit": limit,
            "has_more": len(diseases) >= limit,
        }

    return result


async def _check_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Boolean check: Does disease have specific phenotype?"""
    disease_input = args["disease"]
    phenotype_id = args["phenotype"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()

    # Note: DiseaseClient's check_association is for gene-disease, not disease-phenotype
    # So we still use the direct has_phenotype query
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease_ref.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_phenotype = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_phenotype": has_phenotype,
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        },
        "phenotype": {
            "name": phenotype_id,
            "curie": phenotype_id if ":" in phenotype_id else f"unknown:{phenotype_id}",
        },
    }
