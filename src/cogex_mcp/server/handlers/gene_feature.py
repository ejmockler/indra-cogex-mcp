"""
Gene Feature

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


# Tool 2: Gene/Feature Query - Mode Handlers
# ============================================================================

async def _gene_to_features(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive gene profile with all requested features."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    result = {
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
    }

    # Fetch requested features
    if args.get("include_expression", True):
        expression_data = await adapter.query(
            "get_tissues_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_expression_data(expression_data)

    if args.get("include_go_terms", True):
        go_data = await adapter.query(
            "get_go_terms_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["go_terms"] = _parse_go_annotations(go_data)

    if args.get("include_pathways", True):
        pathway_data = await adapter.query(
            "get_pathways_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["pathways"] = _parse_pathway_memberships(pathway_data)

    if args.get("include_diseases", True):
        disease_data = await adapter.query(
            "get_diseases_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["diseases"] = _parse_disease_associations(disease_data)

    # Optional features
    if args.get("include_domains", False):
        result["domains"] = []

    if args.get("include_variants", False):
        result["variants"] = []

    if args.get("include_phenotypes", False):
        result["phenotypes"] = []

    if args.get("include_codependencies", False):
        result["codependencies"] = []

    return result


async def _tissue_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes expressed in a specific tissue."""
    tissue_input = args["tissue"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # For now, accept tissue name directly
    tissue_id = tissue_input if isinstance(tissue_input, str) else tissue_input[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_in_tissue",
        tissue_id=tissue_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _go_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes annotated with a specific GO term."""
    go_input = args["go_term"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    go_id = go_input if isinstance(go_input, str) else go_input[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_go_term",
        go_id=go_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _domain_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes containing a specific protein domain."""
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Domain queries not yet implemented in backend",
    }


async def _phenotype_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes associated with a specific phenotype."""
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Phenotype queries not yet implemented in backend",
    }


# Data parsing helpers for Tool 2
def _parse_expression_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse tissue expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expressions = []
    for record in data["records"]:
        expressions.append({
            "tissue": {
                "name": record.get("tissue", "Unknown"),
                "curie": record.get("tissue_id", "unknown:unknown"),
                "namespace": "uberon",
                "identifier": record.get("tissue_id", "unknown"),
            },
            "confidence": record.get("confidence", "unknown"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return expressions


def _parse_go_annotations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse GO annotations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    annotations = []
    for record in data["records"]:
        annotations.append({
            "go_term": {
                "name": record.get("term", "Unknown"),
                "curie": record.get("go_id", "unknown:unknown"),
                "namespace": "go",
                "identifier": record.get("go_id", "unknown"),
            },
            "aspect": record.get("aspect", "unknown"),
            "evidence_code": record.get("evidence_code", "N/A"),
        })

    return annotations


def _parse_pathway_memberships(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway memberships from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append({
            "pathway": {
                "name": record.get("pathway", "Unknown"),
                "curie": record.get("pathway_id", "unknown:unknown"),
                "namespace": record.get("source", "unknown"),
                "identifier": record.get("pathway_id", "unknown"),
            },
            "source": record.get("source", "unknown"),
        })

    return pathways


def _parse_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append({
            "name": record.get("gene", "Unknown"),
            "curie": record.get("gene_id", "unknown:unknown"),
            "namespace": "hgnc",
            "identifier": record.get("gene_id", "unknown"),
        })

    return genes


def _parse_disease_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "disease": {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
        })

    return diseases


# ============================================================================
# Tool Handler Stubs (implementations would continue similarly for all tools)
# ============================================================================

async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle gene/feature query - Tool 2."""
    mode = args.get("mode")
    response_format = args.get("response_format", "markdown")

    # Route to appropriate handler based on mode
    if mode == "gene_to_features":
        if not args.get("gene"):
            return [types.TextContent(
                type="text",
                text="Error: gene parameter required for gene_to_features mode"
            )]
        result = await _gene_to_features(args)
    elif mode == "tissue_to_genes":
        if not args.get("tissue"):
            return [types.TextContent(
                type="text",
                text="Error: tissue parameter required for tissue_to_genes mode"
            )]
        result = await _tissue_to_genes(args)
    elif mode == "go_to_genes":
        if not args.get("go_term"):
            return [types.TextContent(
                type="text",
                text="Error: go_term parameter required for go_to_genes mode"
            )]
        result = await _go_to_genes(args)
    elif mode == "domain_to_genes":
        if not args.get("domain"):
            return [types.TextContent(
                type="text",
                text="Error: domain parameter required for domain_to_genes mode"
            )]
        result = await _domain_to_genes(args)
    elif mode == "phenotype_to_genes":
        if not args.get("phenotype"):
            return [types.TextContent(
                type="text",
                text="Error: phenotype parameter required for phenotype_to_genes mode"
            )]
        result = await _phenotype_to_genes(args)
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


async def _handle_subnetwork_extraction(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle subnetwork extraction - Tool 3."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "direct":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: direct mode requires at least 2 genes"
                )]
            result = await _extract_direct(args)
        elif mode == "mediated":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: mediated mode requires at least 2 genes"
                )]
            result = await _extract_mediated(args)
        elif mode == "shared_upstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_upstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_upstream(args)
        elif mode == "shared_downstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_downstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_downstream(args)
        elif mode == "source_to_targets":
            if not args.get("source_gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: source_to_targets mode requires source_gene parameter"
                )]
            result = await _extract_source_to_targets(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown subnetwork mode '{mode}'"
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


