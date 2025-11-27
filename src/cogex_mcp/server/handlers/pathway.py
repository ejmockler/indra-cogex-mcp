"""
Pathway

Extracted from monolithic server.py
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    ENRICHMENT_TIMEOUT,
    STANDARD_QUERY_TIMEOUT,
)

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle pathway query - Tool 6."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_genes":
            if not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: pathway parameter required for get_genes mode"
                )]
            result = await _get_genes_in_pathway(args)
        elif mode == "get_pathways":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_pathways mode"
                )]
            result = await _get_pathways_for_gene(args)
        elif mode == "find_shared":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: genes parameter required with at least 2 genes for find_shared mode"
                )]
            result = await _find_shared_pathways(args)
        elif mode == "check_membership":
            if not args.get("gene") or not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: both gene and pathway parameters required for check_membership mode"
                )]
            result = await _check_pathway_membership(args)
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


# Tool 6 Mode Handlers
async def _get_genes_in_pathway(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_genes - Get all genes in a specific pathway."""
    pathway_input = args["pathway"]

    # Parse pathway identifier
    if isinstance(pathway_input, tuple):
        pathway_id = f"{pathway_input[0]}:{pathway_input[1]}"
    else:
        pathway_id = pathway_input

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "mode": "get_genes",
        "pathway_id": pathway_id,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("pathway_query", **query_params)

    # Parse pathway metadata
    pathway_node = _parse_pathway_node(pathway_data.get("pathway", {}))

    # Parse gene list
    genes = _parse_pathway_gene_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=pathway_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "pathway": pathway_node.model_dump() if pathway_node else None,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _get_pathways_for_gene(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_pathways - Get all pathways containing a specific gene."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "mode": "get_pathways",
        "gene_id": gene.curie,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("pathway_query", **query_params)

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "gene": gene.model_dump(),
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _find_shared_pathways(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: find_shared - Find pathways containing ALL specified genes."""
    genes_input = args["genes"]

    # Resolve all gene identifiers
    resolver = get_resolver()
    gene_curies = []

    for gene_input in genes_input:
        gene = await resolver.resolve_gene(gene_input)
        gene_curies.append(gene.curie)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "mode": "find_shared",
        "gene_ids": gene_curies,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("pathway_query", **query_params)

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "genes": genes_input,
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _check_pathway_membership(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_membership - Check if a specific gene is in a specific pathway."""
    gene_input = args["gene"]
    pathway_input = args["pathway"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    # Parse pathway identifier
    if isinstance(pathway_input, tuple):
        pathway_id = f"{pathway_input[0]}:{pathway_input[1]}"
    else:
        pathway_id = pathway_input

    adapter = await get_adapter()
    result_data = await adapter.query(
        "pathway_query",
        mode="check_membership",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse result
    is_member = result_data.get("is_member", False) if result_data.get("success") else False

    # Parse pathway metadata if available
    pathway_node = None
    if result_data.get("pathway"):
        pathway_node = _parse_pathway_node(result_data["pathway"])

    return {
        "is_member": is_member,
        "gene": gene.model_dump(),
        "pathway": pathway_node.model_dump() if pathway_node else {"pathway_id": pathway_id},
    }


# Data parsing helpers for Tool 6
def _parse_pathway_node(data: dict[str, Any]) -> Any:
    """Parse pathway node from backend response."""
    if not data:
        return None

    try:
        from cogex_mcp.schemas import PathwayNode
        return PathwayNode(
            name=data.get("name", data.get("pathway", "Unknown")),
            curie=data.get("curie", data.get("pathway_id", "unknown:unknown")),
            source=data.get("source", "unknown"),
            description=data.get("description"),
            gene_count=data.get("gene_count", 0),
            url=data.get("url"),
        )
    except Exception as e:
        logger.warning(f"Error parsing pathway node: {e}")
        return None


def _parse_pathway_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from pathway backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append({
            "name": record.get("gene", record.get("name", "Unknown")),
            "curie": record.get("gene_id", record.get("curie", "unknown:unknown")),
            "namespace": "hgnc",
            "identifier": record.get("gene_id", record.get("identifier", "unknown")),
            "description": record.get("description"),
        })

    return genes


def _parse_pathway_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append({
            "name": record.get("pathway", record.get("name", "Unknown")),
            "curie": record.get("pathway_id", record.get("curie", "unknown:unknown")),
            "source": record.get("source", "unknown"),
            "description": record.get("description"),
            "gene_count": record.get("gene_count", 0),
            "url": record.get("url"),
        })

    return pathways



async def _handle_cell_line_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle cell line query - Tool 7."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_properties":
            if not args.get("cell_line"):
                return [types.TextContent(
                    type="text",
                    text="Error: cell_line parameter required for get_properties mode"
                )]
            result = await _get_cell_line_properties(args)
        elif mode == "get_mutated_genes":
            if not args.get("cell_line"):
                return [types.TextContent(
                    type="text",
                    text="Error: cell_line parameter required for get_mutated_genes mode"
                )]
            result = await _get_mutated_genes(args)
        elif mode == "get_cell_lines_with_mutation":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_cell_lines_with_mutation mode"
                )]
            result = await _get_cell_lines_with_mutation(args)
        elif mode == "check_mutation":
            if not args.get("cell_line") or not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: both cell_line and gene parameters required for check_mutation mode"
                )]
            result = await _check_cell_line_mutation(args)
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


