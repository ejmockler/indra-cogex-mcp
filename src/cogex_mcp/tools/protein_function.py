"""
Tool 16: cogex_query_protein_functions

Enzyme activities and protein function classifications.

Modes:
1. gene_to_activities: Gene → enzyme activities
2. activity_to_genes: Activity → genes (paginated)
3. check_activity: Boolean check if gene has specific activity
4. check_function_types: Batch check kinase/phosphatase/TF for gene lists
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
    ProteinFunctionMode,
    ProteinFunctionQuery,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_protein_functions",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_protein_functions(
    params: ProteinFunctionQuery,
    ctx: Context,
) -> str:
    """
    Query enzyme activities and protein function types.

    This tool provides access to enzyme activity annotations and protein function
    classifications, supporting 4 query modes for comprehensive function analysis:

    **Gene → Activities:**
    - gene_to_activities: Get all enzyme activities for a specific gene

    **Activity → Genes:**
    - activity_to_genes: Find all genes with a specific enzyme activity (paginated)

    **Boolean Checks:**
    - check_activity: Check if a gene has a specific enzyme activity
    - check_function_types: Batch check if genes are kinases/phosphatases/TFs

    Args:
        params (ProteinFunctionQuery): Query parameters including:
            - mode (ProteinFunctionMode): Query mode (required)
            - gene (str | tuple): Gene identifier for gene_to_activities, check_activity
            - genes (List[str]): List of genes for batch check_function_types
            - enzyme_activity (str): Activity name for activity_to_genes, check_activity
            - function_types (List[str]): Types to check (kinase, phosphatase, transcription_factor)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **gene_to_activities response:**
        {
            "gene": { "name": "EGFR", "curie": "hgnc:3236", ... },
            "activities": [
                { "activity": "kinase", "ec_number": "EC:2.7.10.1", "confidence": "high", ... },
                ...
            ]
        }

        **activity_to_genes response:**
        {
            "activity": "kinase",
            "genes": [{ "name": "EGFR", "curie": "hgnc:3236", ... }, ...],
            "pagination": { ... }
        }

        **check_activity response:**
        {
            "has_activity": true,
            "gene": { "name": "EGFR", "curie": "hgnc:3236", ... },
            "activity": "kinase"
        }

        **check_function_types response:**
        {
            "function_checks": {
                "TP53": { "kinase": false, "phosphatase": false, "transcription_factor": true },
                "EGFR": { "kinase": true, "phosphatase": false, "transcription_factor": false },
                ...
            }
        }

    Examples:
        - Get enzyme activities for EGFR:
          mode="gene_to_activities", gene="EGFR"

        - Find all kinases:
          mode="activity_to_genes", enzyme_activity="kinase", limit=100

        - Check if TP53 is a transcription factor:
          mode="check_function_types", gene="TP53", function_types=["transcription_factor"]

        - Batch check function types:
          mode="check_function_types", genes=["TP53", "EGFR", "MAPK1"],
          function_types=["kinase", "phosphatase", "transcription_factor"]

    Function Types:
        - kinase: Protein kinases (phosphorylate other proteins)
        - phosphatase: Protein phosphatases (remove phosphate groups)
        - transcription_factor: Transcription factors (regulate gene expression)

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
        if params.mode == ProteinFunctionMode.GENE_TO_ACTIVITIES:
            result = await _get_enzyme_activities(params, ctx)
        elif params.mode == ProteinFunctionMode.ACTIVITY_TO_GENES:
            result = await _get_genes_for_activity(params, ctx)
        elif params.mode == ProteinFunctionMode.CHECK_ACTIVITY:
            result = await _check_enzyme_activity(params, ctx)
        elif params.mode == ProteinFunctionMode.CHECK_FUNCTION_TYPES:
            result = await _check_function_types(params, ctx)
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


async def _get_enzyme_activities(
    params: ProteinFunctionQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: gene_to_activities
    Get all enzyme activities for a specific gene.
    """
    if not params.gene:
        raise ValueError("gene parameter required for gene_to_activities mode")

    await ctx.report_progress(0.2, "Resolving gene identifier...")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    await ctx.report_progress(0.3, f"Fetching enzyme activities for {gene.name}...")

    adapter = await get_adapter()

    # Fetch enzyme activities from backend
    activity_data = await adapter.query(
        "get_enzyme_activities",
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse activities
    activities = _parse_enzyme_activities(activity_data)

    return {
        "gene": gene.model_dump(),
        "activities": activities,
    }


async def _get_genes_for_activity(
    params: ProteinFunctionQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: activity_to_genes
    Find all genes with a specific enzyme activity.
    """
    if not params.enzyme_activity:
        raise ValueError("enzyme_activity parameter required for activity_to_genes mode")

    await ctx.report_progress(0.2, f"Fetching genes with '{params.enzyme_activity}' activity...")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "activity": params.enzyme_activity,
        "limit": params.limit,
        "offset": params.offset,
    }

    gene_data = await adapter.query(
        "get_genes_for_activity",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse gene list
    genes = _parse_gene_list(gene_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "activity": params.enzyme_activity,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _check_enzyme_activity(
    params: ProteinFunctionQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: check_activity
    Check if a gene has a specific enzyme activity.
    """
    if not params.gene:
        raise ValueError("gene parameter required for check_activity mode")
    if not params.enzyme_activity:
        raise ValueError("enzyme_activity parameter required for check_activity mode")

    await ctx.report_progress(0.2, "Resolving gene identifier...")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    await ctx.report_progress(
        0.4, f"Checking if {gene.name} has '{params.enzyme_activity}' activity..."
    )

    adapter = await get_adapter()

    # Check specific activity based on type
    activity_lower = params.enzyme_activity.lower()

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
            activity=params.enzyme_activity,
            timeout=STANDARD_QUERY_TIMEOUT,
        )

    has_activity = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_activity": has_activity,
        "gene": gene.model_dump(),
        "activity": params.enzyme_activity,
    }


async def _check_function_types(
    params: ProteinFunctionQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: check_function_types
    Batch check if genes have specific function types (kinase, phosphatase, TF).
    """
    # Determine which genes to check
    genes_to_check = []

    if params.genes:
        genes_to_check = params.genes
    elif params.gene:
        genes_to_check = [params.gene]
    else:
        raise ValueError("Either gene or genes parameter required for check_function_types mode")

    if not params.function_types:
        raise ValueError("function_types parameter required for check_function_types mode")

    await ctx.report_progress(0.2, f"Resolving {len(genes_to_check)} gene identifiers...")

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

    await ctx.report_progress(0.4, f"Checking function types for {len(resolved_genes)} genes...")

    adapter = await get_adapter()
    function_checks = {}

    # Check each function type for each gene
    total_checks = len(resolved_genes) * len(params.function_types)
    current_check = 0

    for gene_name, gene in resolved_genes.items():
        if gene is None:
            # Gene could not be resolved
            function_checks[gene_name] = dict.fromkeys(params.function_types, False)
            continue

        gene_results = {}

        for function_type in params.function_types:
            current_check += 1
            progress = 0.4 + (0.5 * current_check / total_checks)
            await ctx.report_progress(progress, f"Checking {gene_name} for {function_type}...")

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
        "function_types": params.function_types,
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


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
                "synonyms": record.get("synonyms", []),
            }
        )

    return genes


logger.info("✓ Tool 16 (cogex_query_protein_functions) registered")
