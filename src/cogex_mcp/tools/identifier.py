"""
Tool 11: cogex_resolve_identifiers

Identifier conversion between namespaces (HGNC, UniProt, Ensembl, etc.).

Enables bidirectional mapping between different identifier systems used in biological databases.
"""

import logging
from typing import Any

from mcp.server.fastmcp import Context

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    INTERNAL_ANNOTATIONS,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import IdentifierMapping, IdentifierQuery
from cogex_mcp.server import mcp
from cogex_mcp.services.formatter import get_formatter

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_resolve_identifiers",
    annotations=INTERNAL_ANNOTATIONS,
)
async def cogex_resolve_identifiers(
    params: IdentifierQuery,
    ctx: Context,
) -> str:
    """
    Convert identifiers between different biological namespaces.

    This tool enables conversion between various biological identifier systems,
    handling 1:1 and 1:many mappings across standardized namespaces.

    **Common Conversions:**

    **Gene identifiers:**
    - hgnc.symbol → hgnc (gene symbol → HGNC ID, e.g., "TP53" → "11998")
    - hgnc → hgnc.symbol (HGNC ID → gene symbol, e.g., "11998" → "TP53")
    - hgnc → uniprot (HGNC ID → UniProt ID)
    - uniprot → hgnc (UniProt ID → HGNC ID)
    - ensembl → hgnc (Ensembl gene → HGNC ID)
    - hgnc → ensembl (HGNC ID → Ensembl gene)

    **Other namespaces:**
    - refseq → hgnc (RefSeq → HGNC ID)
    - entrez → hgnc (Entrez Gene → HGNC ID)

    **Namespace Format:**
    - Use dot notation for sub-types: "hgnc.symbol", "hgnc.alias"
    - Use lowercase: "hgnc", "uniprot", "ensembl"
    - Common namespaces: hgnc, hgnc.symbol, uniprot, ensembl, refseq, entrez

    **Handling 1:Many Mappings:**
    Some conversions produce multiple targets (e.g., one gene → multiple UniProt IDs).
    The tool returns all mappings and tracks unmapped identifiers separately.

    Args:
        params (IdentifierQuery): Query parameters including:
            - identifiers (List[str]): List of identifiers to convert
            - from_namespace (str): Source namespace (e.g., "hgnc.symbol", "uniprot")
            - to_namespace (str): Target namespace (e.g., "hgnc", "uniprot")
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted response in requested format

        **Markdown format:**
        - Summary line with mapping statistics
        - Table of successful mappings (source → target(s))
        - List of unmapped identifiers (if any)
        - Conversion notes and suggestions

        **JSON format:**
        ```json
        {
            "mappings": [
                {
                    "source_id": "TP53",
                    "target_ids": ["11998"],
                    "confidence": "exact"
                },
                {
                    "source_id": "BRCA1",
                    "target_ids": ["1100"],
                    "confidence": "exact"
                }
            ],
            "unmapped": ["INVALID1", "NOTFOUND2"],
            "statistics": {
                "total_input": 4,
                "mapped": 2,
                "unmapped": 2,
                "total_targets": 2
            }
        }
        ```

    Examples:
        - Convert gene symbols to HGNC IDs:
          identifiers=["TP53", "BRCA1", "EGFR"],
          from_namespace="hgnc.symbol",
          to_namespace="hgnc"

        - Get UniProt IDs for HGNC IDs:
          identifiers=["11998", "1100"],
          from_namespace="hgnc",
          to_namespace="uniprot"

        - Convert Ensembl to HGNC:
          identifiers=["ENSG00000141510"],
          from_namespace="ensembl",
          to_namespace="hgnc"

    Error Handling:
        - Returns actionable error messages for invalid namespaces
        - Tracks unmapped identifiers separately
        - Provides suggestions for common namespace issues
        - Handles empty input lists gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Validate inputs
        if not params.identifiers:
            return "Error: identifiers list cannot be empty"

        if not params.from_namespace or not params.to_namespace:
            return "Error: Both from_namespace and to_namespace are required"

        await ctx.report_progress(
            0.3,
            f"Converting {len(params.identifiers)} identifiers from "
            f"{params.from_namespace} to {params.to_namespace}...",
        )

        # Execute conversion
        adapter = await get_adapter()
        result = await _convert_identifiers(
            adapter=adapter,
            identifiers=params.identifiers,
            from_namespace=params.from_namespace,
            to_namespace=params.to_namespace,
            ctx=ctx,
        )

        await ctx.report_progress(0.8, "Formatting results...")

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Conversion complete")
        return response

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Implementation
# ============================================================================


async def _convert_identifiers(
    adapter,
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
    ctx: Context,
) -> dict[str, Any]:
    """
    Convert identifiers between namespaces using appropriate backend endpoint.

    Handles routing to different backend queries based on namespace pairs.
    """
    # Determine which backend endpoint to use
    endpoint, query_params = _select_endpoint(
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    await ctx.report_progress(0.5, f"Querying {endpoint}...")

    # Query backend
    conversion_data = await adapter.query(
        endpoint,
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing mappings...")

    # Parse results
    mappings, unmapped = _parse_conversion_results(
        data=conversion_data,
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    # Build response
    return {
        "mappings": [m.model_dump() for m in mappings],
        "unmapped": unmapped,
        "statistics": {
            "total_input": len(identifiers),
            "mapped": len(mappings),
            "unmapped": len(unmapped),
            "total_targets": sum(len(m.target_ids) for m in mappings),
        },
        "from_namespace": from_namespace,
        "to_namespace": to_namespace,
    }


def _select_endpoint(
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> tuple[str, dict[str, Any]]:
    """
    Select appropriate backend endpoint based on namespace pair.

    Args:
        identifiers: List of identifiers to convert
        from_namespace: Source namespace
        to_namespace: Target namespace

    Returns:
        Tuple of (endpoint_name, query_params)
    """
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
    # This endpoint should handle all other namespace pairs
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
) -> tuple[list[IdentifierMapping], list[str]]:
    """
    Parse backend conversion results into mappings and unmapped lists.

    Args:
        data: Backend response data
        identifiers: Original input identifiers
        from_namespace: Source namespace
        to_namespace: Target namespace

    Returns:
        Tuple of (mappings, unmapped_identifiers)
    """
    if not data.get("success"):
        logger.warning(f"Backend conversion failed: {data.get('error', 'unknown error')}")
        # Return all as unmapped
        return [], identifiers

    mappings_data = data.get("mappings", {})
    if not mappings_data:
        # No mappings found
        return [], identifiers

    # Build mappings
    mappings: list[IdentifierMapping] = []
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
            mapping = IdentifierMapping(
                source_id=source_id,
                target_ids=targets,
                confidence="exact" if targets else None,
            )
            mappings.append(mapping)

    return mappings, unmapped


logger.info("✓ Tool 11 (cogex_resolve_identifiers) registered")
