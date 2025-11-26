"""
Cell Line

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


# Tool 7 Mode Handlers
async def _get_cell_line_properties(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_properties - Get comprehensive cell line profile with all requested features."""
    cell_line_name = args["cell_line"]

    adapter = await get_adapter()
    result = {
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
            "tissue": None,
            "disease": None,
        },
    }

    # Fetch requested features
    if args.get("include_mutations", True):
        mutation_data = await adapter.query(
            "get_mutations_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["mutations"] = _parse_cell_line_mutations(mutation_data)

    if args.get("include_copy_number", True):
        cna_data = await adapter.query(
            "get_copy_number_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["copy_number_alterations"] = _parse_copy_number(cna_data)

    if args.get("include_dependencies", False):
        dep_data = await adapter.query(
            "get_dependencies_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["dependencies"] = _parse_dependencies(dep_data)

    if args.get("include_expression", False):
        expr_data = await adapter.query(
            "get_expression_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_cell_line_expression(expr_data)

    return result


async def _get_mutated_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_mutated_genes - Get list of genes mutated in cell line."""
    cell_line_name = args["cell_line"]

    adapter = await get_adapter()
    mutation_data = await adapter.query(
        "get_mutations_for_cell_line",
        cell_line=cell_line_name,
        limit=args.get("limit", 20),
        offset=args.get("offset", 0),
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse genes from mutations
    genes = _parse_gene_list_from_cell_line_mutations(mutation_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=mutation_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
        },
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _get_cell_lines_with_mutation(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_cell_lines_with_mutation - Find cell lines with specific gene mutation."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    cell_line_data = await adapter.query(
        "get_cell_lines_for_mutation",
        gene_id=gene.curie,
        limit=args.get("limit", 20),
        offset=args.get("offset", 0),
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse cell lines
    cell_lines = _parse_cell_line_list(cell_line_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_lines,
        total_count=cell_line_data.get("total_count", len(cell_lines)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "gene": gene.model_dump(),
        "cell_lines": cell_lines,
        "pagination": pagination.model_dump(),
    }


async def _check_cell_line_mutation(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_mutation - Check if gene is mutated in cell line."""
    cell_line_name = args["cell_line"]
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=cell_line_name,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_mutation = check_data.get("result", False)

    return {
        "has_mutation": has_mutation,
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
        },
        "gene": gene.model_dump(),
    }


# Data parsing helpers for Tool 7
def _parse_cell_line_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse mutations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    mutations = []
    for record in data["records"]:
        mutations.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "mutation_type": record.get("mutation_type", "unknown"),
            "protein_change": record.get("protein_change"),
            "is_driver": record.get("is_driver", False),
        })

    return mutations


def _parse_copy_number(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse copy number alterations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cnas = []
    for record in data["records"]:
        copy_num = record.get("copy_number", 2.0)
        if copy_num > 2.5:
            alt_type = "amplification"
        elif copy_num < 1.5:
            alt_type = "deletion"
        else:
            alt_type = "neutral"

        cnas.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "copy_number": copy_num,
            "alteration_type": alt_type,
        })

    return cnas


def _parse_dependencies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene dependencies from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    dependencies = []
    for record in data["records"]:
        dependencies.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "dependency_score": record.get("dependency_score", 0.0),
            "percentile": record.get("percentile"),
        })

    return dependencies


def _parse_cell_line_expression(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expression = []
    for record in data["records"]:
        expression.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "expression_value": record.get("expression_value", 0.0),
            "unit": record.get("unit", "TPM"),
        })

    return expression


def _parse_gene_list_from_cell_line_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from mutation data."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    seen_genes = set()

    for record in data["records"]:
        gene_name = record.get("gene", "Unknown")
        if gene_name not in seen_genes:
            seen_genes.add(gene_name)
            genes.append({
                "name": gene_name,
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
                "description": None,
                "synonyms": [],
            })

    return genes


def _parse_cell_line_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_line_name = record.get("cell_line", "Unknown")
        cell_lines.append({
            "name": cell_line_name,
            "ccle_id": record.get("ccle_id", f"ccle:{cell_line_name}"),
            "depmap_id": record.get("depmap_id", f"depmap:{cell_line_name}"),
            "tissue": record.get("tissue"),
            "disease": record.get("disease"),
        })

    return cell_lines


async def _handle_clinical_trials_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle clinical trials query - Tool 8."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_drug":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for get_for_drug mode"
                )]
            result = await _get_trials_for_drug(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_trials_for_disease(args)
        elif mode == "get_by_id":
            if not args.get("trial_id"):
                return [types.TextContent(
                    type="text",
                    text="Error: trial_id parameter required for get_by_id mode"
                )]
            result = await _get_trial_by_id(args)
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


