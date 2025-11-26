"""
Protein Function

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
    """Handle protein functions query - Tool 16."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "gene_to_activities":
            result = await _get_enzyme_activities(args)
        elif mode == "activity_to_genes":
            result = await _get_genes_for_activity(args)
        elif mode == "check_activity":
            result = await _check_enzyme_activity(args)
        elif mode == "check_function_types":
            result = await _check_function_types(args)
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

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 16 Mode Handlers
async def _get_enzyme_activities(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: gene_to_activities - Get all enzyme activities for a specific gene."""
    gene_input = args.get("gene")
    if not gene_input:
        raise ValueError("gene parameter required for gene_to_activities mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Fetch enzyme activities from backend
    activity_data = await adapter.query(
        "get_enzyme_activities",
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse activities
    activities = _parse_enzyme_activities(activity_data)

    return {
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
        "activities": activities,
    }


async def _get_genes_for_activity(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: activity_to_genes - Find all genes with a specific enzyme activity."""
    enzyme_activity = args.get("enzyme_activity")
    if not enzyme_activity:
        raise ValueError("enzyme_activity parameter required for activity_to_genes mode")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "activity": enzyme_activity,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }

    gene_data = await adapter.query(
        "get_genes_for_activity",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse gene list
    genes = _parse_gene_list_protein_function(gene_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "activity": enzyme_activity,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _check_enzyme_activity(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_activity - Check if a gene has a specific enzyme activity."""
    gene_input = args.get("gene")
    enzyme_activity = args.get("enzyme_activity")

    if not gene_input:
        raise ValueError("gene parameter required for check_activity mode")
    if not enzyme_activity:
        raise ValueError("enzyme_activity parameter required for check_activity mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Check specific activity based on type
    activity_lower = enzyme_activity.lower()

    # Map activity names to backend check functions
    if activity_lower in ["kinase", "protein kinase"]:
        check_data = await adapter.query(
            "is_kinase",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    elif activity_lower in ["phosphatase", "protein phosphatase"]:
        check_data = await adapter.query(
            "is_phosphatase",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    elif activity_lower in ["transcription_factor", "transcription factor", "tf"]:
        check_data = await adapter.query(
            "is_transcription_factor",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    else:
        # Generic activity check
        check_data = await adapter.query(
            "has_enzyme_activity",
            gene_id=gene.curie,
            activity=enzyme_activity,
            timeout=STANDARD_QUERY_TIMEOUT,
        )

    has_activity = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_activity": has_activity,
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
        "activity": enzyme_activity,
    }


async def _check_function_types(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_function_types - Batch check if genes have specific function types."""
    # Determine which genes to check
    genes_to_check = []

    if args.get("genes"):
        genes_to_check = args["genes"]
    elif args.get("gene"):
        genes_to_check = [args["gene"]]
    else:
        raise ValueError("Either gene or genes parameter required for check_function_types mode")

    function_types = args.get("function_types")
    if not function_types:
        raise ValueError("function_types parameter required for check_function_types mode")

    # Resolve all gene identifiers
    resolver = get_resolver()
    resolved_genes = {}

    for gene_input in genes_to_check:
        try:
            gene = await resolver.resolve_gene(gene_input)
            resolved_genes[gene.name] = gene
        except EntityResolutionError as e:
            logger.warning(f"Could not resolve gene '{gene_input}': {e}")
            # Include unresolved genes with None value
            resolved_genes[str(gene_input)] = None

    adapter = await get_adapter()
    function_checks = {}

    # Check each function type for each gene
    for gene_name, gene in resolved_genes.items():
        if gene is None:
            # Gene could not be resolved
            function_checks[gene_name] = dict.fromkeys(function_types, False)
            continue

        gene_results = {}

        for function_type in function_types:
            function_lower = function_type.lower()

            try:
                # Map function type to backend endpoint
                if function_lower in ["kinase", "protein_kinase"]:
                    check_data = await adapter.query(
                        "is_kinase",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                elif function_lower in ["phosphatase", "protein_phosphatase"]:
                    check_data = await adapter.query(
                        "is_phosphatase",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                elif function_lower in ["transcription_factor", "transcription factor", "tf"]:
                    check_data = await adapter.query(
                        "is_transcription_factor",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                else:
                    logger.warning(f"Unknown function type: {function_type}")
                    gene_results[function_type] = False
                    continue

                has_function = (
                    check_data.get("result", False) if check_data.get("success") else False
                )
                gene_results[function_type] = has_function

            except Exception as e:
                logger.warning(f"Error checking {function_type} for {gene_name}: {e}")
                gene_results[function_type] = False

        function_checks[gene_name] = gene_results

    return {
        "function_checks": function_checks,
        "genes_checked": len(resolved_genes),
        "function_types": function_types,
    }


# Data parsing helpers for Tool 16
def _parse_enzyme_activities(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse enzyme activities from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    activities = []
    for record in data["records"]:
        activities.append(
            {
                "activity": record.get("activity", "Unknown"),
                "ec_number": record.get("ec_number"),
                "confidence": record.get("confidence", "medium"),
                "evidence_sources": record.get("evidence_sources", []),
            }
        )

    return activities


def _parse_gene_list_protein_function(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append(
            {
                "name": record.get("gene", record.get("name", "Unknown")),
                "curie": record.get("gene_id", record.get("curie", "unknown:unknown")),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", record.get("identifier", "unknown")),
                "description": record.get("description"),
                "synonyms": record.get("synonyms", []),
            }
        )

    return genes


