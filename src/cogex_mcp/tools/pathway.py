"""
Tool 6: cogex_query_pathway

Pathway membership queries and shared pathway analysis.

Modes:
1. get_genes: Pathway → genes in pathway
2. get_pathways: Gene → pathways containing gene
3. find_shared: Genes → pathways containing ALL genes
4. check_membership: Boolean check if gene is in pathway
"""

import logging
from typing import Any

from mcp.server.fastmcp import Context

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    READONLY_ANNOTATIONS,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    PathwayNode,
    PathwayQuery,
    PathwayQueryMode,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_pathway",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_pathway(
    params: PathwayQuery,
    ctx: Context,
) -> str:
    """
    Query pathway memberships and find shared pathways.

    This tool supports 4 query modes for comprehensive pathway exploration:

    **Pathway → Genes:**
    - get_genes: Get all genes in a specific pathway

    **Gene → Pathways:**
    - get_pathways: Get all pathways containing a specific gene

    **Multi-gene Analysis:**
    - find_shared: Find pathways containing ALL specified genes

    **Boolean Check:**
    - check_membership: Check if a specific gene is in a specific pathway

    Args:
        params (PathwayQuery): Query parameters including:
            - mode (PathwayQueryMode): Query mode (required)
            - pathway (str | tuple): Pathway identifier for get_genes or check_membership
            - gene (str | tuple): Gene identifier for get_pathways or check_membership
            - genes (List[str]): List of genes for find_shared mode
            - pathway_source (str): Filter by source (reactome, wikipathways)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **get_genes response:**
        {
            "pathway": { "name": "MAPK signaling", "curie": "reactome:R-HSA-5683057", ... },
            "genes": [{ "name": "MAPK1", "curie": "hgnc:6871", ... }, ...],
            "pagination": { ... }
        }

        **get_pathways / find_shared response:**
        {
            "pathways": [
                { "name": "MAPK signaling", "source": "reactome", "gene_count": 267, ... },
                ...
            ],
            "pagination": { ... }
        }

        **check_membership response:**
        {
            "is_member": true,
            "gene": { "name": "MAPK1", "curie": "hgnc:6871", ... },
            "pathway": { "name": "MAPK signaling", "curie": "reactome:R-HSA-5683057", ... }
        }

    Examples:
        - Get genes in MAPK pathway:
          mode="get_genes", pathway="MAPK signaling"

        - Get pathways for TP53:
          mode="get_pathways", gene="TP53"

        - Find shared pathways:
          mode="find_shared", genes=["TP53", "MDM2", "ATM"]

        - Check membership:
          mode="check_membership", gene="MAPK1", pathway=("reactome", "R-HSA-5683057")

    Error Handling:
        - Returns actionable error messages for invalid identifiers
        - Suggests alternatives for ambiguous identifiers
        - Handles missing entities gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Route to appropriate handler based on mode
        if params.mode == PathwayQueryMode.GET_GENES:
            result = await _get_genes_in_pathway(params, ctx)
        elif params.mode == PathwayQueryMode.GET_PATHWAYS:
            result = await _get_pathways_for_gene(params, ctx)
        elif params.mode == PathwayQueryMode.FIND_SHARED:
            result = await _find_shared_pathways(params, ctx)
        elif params.mode == PathwayQueryMode.CHECK_MEMBERSHIP:
            result = await _check_membership(params, ctx)
        else:
            return f"Error: Unknown query mode '{params.mode}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Query complete")
        return response

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Mode Implementations
# ============================================================================


async def _get_genes_in_pathway(
    params: PathwayQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_genes
    Get all genes in a specific pathway.
    """
    if not params.pathway:
        raise ValueError("pathway parameter required for get_genes mode")

    await ctx.report_progress(0.2, "Resolving pathway identifier...")

    # Parse pathway identifier
    if isinstance(params.pathway, tuple):
        pathway_id = f"{params.pathway[0]}:{params.pathway[1]}"
    else:
        # Assume it's a pathway name or CURIE
        pathway_id = params.pathway

    await ctx.report_progress(0.3, "Fetching genes in pathway...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "pathway_id": pathway_id,
        "limit": params.limit,
        "offset": params.offset,
    }

    if params.pathway_source:
        query_params["source"] = params.pathway_source

    pathway_data = await adapter.query(
        "get_genes_in_pathway",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse pathway metadata
    pathway_node = _parse_pathway_node(pathway_data.get("pathway", {}))

    # Parse gene list
    genes = _parse_gene_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=pathway_data.get("total_count", len(genes)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "pathway": pathway_node.model_dump() if pathway_node else None,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _get_pathways_for_gene(
    params: PathwayQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_pathways
    Get all pathways containing a specific gene.
    """
    if not params.gene:
        raise ValueError("gene parameter required for get_pathways mode")

    await ctx.report_progress(0.2, "Resolving gene identifier...")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    await ctx.report_progress(0.3, f"Fetching pathways for {gene.name}...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": gene.curie,
        "limit": params.limit,
        "offset": params.offset,
    }

    if params.pathway_source:
        query_params["source"] = params.pathway_source

    pathway_data = await adapter.query(
        "get_pathways_for_gene",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "gene": gene.model_dump(),
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _find_shared_pathways(
    params: PathwayQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: find_shared
    Find pathways containing ALL specified genes.
    """
    if not params.genes or len(params.genes) < 2:
        raise ValueError("genes parameter required with at least 2 genes for find_shared mode")

    await ctx.report_progress(0.2, f"Resolving {len(params.genes)} gene identifiers...")

    # Resolve all gene identifiers
    resolver = get_resolver()
    gene_curies = []

    for gene_input in params.genes:
        gene = await resolver.resolve_gene(gene_input)
        gene_curies.append(gene.curie)

    await ctx.report_progress(0.3, f"Finding shared pathways for {len(gene_curies)} genes...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_ids": gene_curies,
        "limit": params.limit,
        "offset": params.offset,
    }

    if params.pathway_source:
        query_params["source"] = params.pathway_source

    pathway_data = await adapter.query(
        "get_shared_pathways_for_genes",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "genes": params.genes,  # Include input genes for context
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _check_membership(
    params: PathwayQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: check_membership
    Check if a specific gene is in a specific pathway.
    """
    if not params.gene:
        raise ValueError("gene parameter required for check_membership mode")
    if not params.pathway:
        raise ValueError("pathway parameter required for check_membership mode")

    await ctx.report_progress(0.2, "Resolving identifiers...")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    # Parse pathway identifier
    if isinstance(params.pathway, tuple):
        pathway_id = f"{params.pathway[0]}:{params.pathway[1]}"
    else:
        pathway_id = params.pathway

    await ctx.report_progress(0.4, f"Checking if {gene.name} is in pathway...")

    adapter = await get_adapter()
    result_data = await adapter.query(
        "is_gene_in_pathway",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing result...")

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


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_pathway_node(data: dict[str, Any]) -> PathwayNode | None:
    """Parse pathway node from backend response."""
    if not data:
        return None

    try:
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


def _parse_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
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
            }
        )

    return genes


def _parse_pathway_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append(
            {
                "name": record.get("pathway", record.get("name", "Unknown")),
                "curie": record.get("pathway_id", record.get("curie", "unknown:unknown")),
                "source": record.get("source", "unknown"),
                "description": record.get("description"),
                "gene_count": record.get("gene_count", 0),
                "url": record.get("url"),
            }
        )

    return pathways


logger.info("✓ Tool 6 (cogex_query_pathway) registered")
