"""
Tool 7: cogex_query_cell_line

Access Cancer Cell Line Encyclopedia (CCLE) and DepMap data for cell line mutations,
copy number alterations, gene dependencies, and expression.

Modes:
1. get_properties: Cell line → comprehensive profile (mutations, CNAs, dependencies, expression)
2. get_mutated_genes: Cell line → list of mutated genes
3. get_cell_lines_with_mutation: Gene → cell lines with that mutation
4. check_mutation: Boolean check if gene is mutated in cell line
"""

import logging
from typing import Any

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    CellLineQuery,
    CellLineQueryMode,
)
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


async def cogex_query_cell_line(
    params: CellLineQuery,
) -> str:
    """
    Query cell line data from CCLE and DepMap.

    This tool provides access to Cancer Cell Line Encyclopedia (CCLE) and DepMap
    data, supporting 4 query modes for comprehensive cell line characterization:

    **Forward Modes (cell line → data):**
    - get_properties: Get comprehensive cell line profile including mutations,
      copy number alterations, gene dependencies, and expression
    - get_mutated_genes: Get list of genes mutated in cell line

    **Reverse Mode (gene → cell lines):**
    - get_cell_lines_with_mutation: Find cell lines with specific gene mutation

    **Boolean Check:**
    - check_mutation: Check if specific gene is mutated in cell line

    Args:
        params (CellLineQuery): Query parameters including:
            - mode (CellLineQueryMode): Query mode (required)
            - cell_line (str): Cell line name for forward modes
            - gene (str | tuple): Gene identifier for reverse mode and checks
            - include_* flags: Control which features to include (get_properties only)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results for list modes (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **get_properties response:**
        {
            "cell_line": { "name": "A549", "ccle_id": "...", ... },
            "mutations": [...],           # Gene mutations
            "copy_number_alterations": [...],  # CNAs
            "dependencies": [...],        # Gene dependencies (optional)
            "expression": [...]           # Expression data (optional)
        }

        **get_mutated_genes response:**
        {
            "cell_line": { ... },
            "genes": [...],              # List of mutated genes
            "pagination": { ... }
        }

        **get_cell_lines_with_mutation response:**
        {
            "gene": { ... },
            "cell_lines": [...],         # List of cell lines
            "pagination": { ... }
        }

        **check_mutation response:**
        {
            "has_mutation": true/false,
            "cell_line": { ... },
            "gene": { ... }
        }

    Examples:
        - Get A549 cell line profile:
          mode="get_properties", cell_line="A549", include_all=True

        - Find mutated genes in HeLa:
          mode="get_mutated_genes", cell_line="HeLa", limit=50

        - Cell lines with KRAS mutations:
          mode="get_cell_lines_with_mutation", gene="KRAS", limit=100

        - Check if TP53 is mutated in A549:
          mode="check_mutation", cell_line="A549", gene="TP53"

    Error Handling:
        - Returns actionable error messages for invalid identifiers
        - Suggests alternatives for ambiguous identifiers
        - Handles missing entities gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        # Route to appropriate handler based on mode
        if params.mode == CellLineQueryMode.GET_PROPERTIES:
            result = await _get_cell_line_properties(params)
        elif params.mode == CellLineQueryMode.GET_MUTATED_GENES:
            result = await _get_mutated_genes(params)
        elif params.mode == CellLineQueryMode.GET_CELL_LINES_WITH_MUTATION:
            result = await _get_cell_lines_with_mutation(params)
        elif params.mode == CellLineQueryMode.CHECK_MUTATION:
            result = await _check_mutation(params)
        else:
            return f"Error: Unknown query mode '{params.mode}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

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


async def _get_cell_line_properties(
    params: CellLineQuery,
) -> dict[str, Any]:
    """
    Mode: get_properties
    Get comprehensive cell line profile with all requested features.
    """
    if not params.cell_line:
        raise ValueError("cell_line parameter required for get_properties mode")

    # Normalize cell line ID: add ccle: prefix if missing
    cell_line_name = params.cell_line
    cell_line_id = params.cell_line
    if not cell_line_id.startswith("ccle:"):
        # Common pattern: A549 -> ccle:A549_LUNG, MCF7 -> ccle:MCF7_BREAST
        # Try with just the name first, let Neo4j query handle with CONTAINS
        cell_line_id = params.cell_line

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
    if params.include_mutations:
        mutation_data = await adapter.query(
            "get_mutations_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["mutations"] = _parse_mutations(mutation_data)

    if params.include_copy_number:
        cna_data = await adapter.query(
            "get_copy_number_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["copy_number_alterations"] = _parse_copy_number(cna_data)

    if params.include_dependencies:
        dep_data = await adapter.query(
            "get_dependencies_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["dependencies"] = _parse_dependencies(dep_data)

    if params.include_expression:
        expr_data = await adapter.query(
            "get_expression_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_expression(expr_data)

    return result


async def _get_mutated_genes(
    params: CellLineQuery,
) -> dict[str, Any]:
    """
    Mode: get_mutated_genes
    Get list of genes mutated in cell line.
    """
    if not params.cell_line:
        raise ValueError("cell_line parameter required for get_mutated_genes mode")

    cell_line_name = params.cell_line

    adapter = await get_adapter()
    mutation_data = await adapter.query(
        "get_mutations_for_cell_line",
        cell_line=cell_line_name,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse genes from mutations
    genes = _parse_gene_list_from_mutations(mutation_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=mutation_data.get("total_count", len(genes)),
        offset=params.offset,
        limit=params.limit,
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


async def _get_cell_lines_with_mutation(
    params: CellLineQuery,
) -> dict[str, Any]:
    """
    Mode: get_cell_lines_with_mutation
    Find cell lines with specific gene mutation.
    """
    if not params.gene:
        raise ValueError("gene parameter required for get_cell_lines_with_mutation mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    adapter = await get_adapter()
    cell_line_data = await adapter.query(
        "get_cell_lines_for_mutation",
        gene_id=gene.curie,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse cell lines
    cell_lines = _parse_cell_line_list(cell_line_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_lines,
        total_count=cell_line_data.get("total_count", len(cell_lines)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "gene": gene.model_dump(),
        "cell_lines": cell_lines,
        "pagination": pagination.model_dump(),
    }


async def _check_mutation(
    params: CellLineQuery,
) -> dict[str, Any]:
    """
    Mode: check_mutation
    Check if gene is mutated in cell line.
    """
    if not params.cell_line:
        raise ValueError("cell_line parameter required for check_mutation mode")
    if not params.gene:
        raise ValueError("gene parameter required for check_mutation mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=params.cell_line,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_mutation = check_data.get("result", False)

    return {
        "has_mutation": has_mutation,
        "cell_line": {
            "name": params.cell_line,
            "ccle_id": f"ccle:{params.cell_line}",
            "depmap_id": f"depmap:{params.cell_line}",
        },
        "gene": gene.model_dump(),
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse mutations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    mutations = []
    for record in data["records"]:
        mutations.append(
            {
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "mutation_type": record.get("mutation_type", "unknown"),
                "protein_change": record.get("protein_change"),
                "is_driver": record.get("is_driver", False),
            }
        )

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

        cnas.append(
            {
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "copy_number": copy_num,
                "alteration_type": alt_type,
            }
        )

    return cnas


def _parse_dependencies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene dependencies from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    dependencies = []
    for record in data["records"]:
        dependencies.append(
            {
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "dependency_score": record.get("dependency_score", 0.0),
                "percentile": record.get("percentile"),
            }
        )

    return dependencies


def _parse_expression(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expression = []
    for record in data["records"]:
        expression.append(
            {
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "expression_value": record.get("expression_value", 0.0),
                "unit": record.get("unit", "TPM"),
            }
        )

    return expression


def _parse_gene_list_from_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from mutation data."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    seen_genes = set()

    for record in data["records"]:
        gene_name = record.get("gene", "Unknown")
        if gene_name not in seen_genes:
            seen_genes.add(gene_name)
            genes.append(
                {
                    "name": gene_name,
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                    "description": None,
                    "synonyms": [],
                }
            )

    return genes


def _parse_cell_line_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_line_name = record.get("cell_line", "Unknown")
        cell_lines.append(
            {
                "name": cell_line_name,
                "ccle_id": record.get("ccle_id", f"ccle:{cell_line_name}"),
                "depmap_id": record.get("depmap_id", f"depmap:{cell_line_name}"),
                "tissue": record.get("tissue"),
                "disease": record.get("disease"),
            }
        )

    return cell_lines


logger.info("✓ Tool 7 (cogex_query_cell_line) registered")
