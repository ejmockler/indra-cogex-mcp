"""
Tool 10: cogex_query_variants

Query genetic variants from GWAS Catalog and DisGeNet.

Modes:
1. get_for_gene: Gene → variants in/near gene
2. get_for_disease: Disease → associated variants
3. get_for_phenotype: Phenotype → GWAS hits
4. variant_to_genes: Variant (rsID) → nearby genes
5. variant_to_phenotypes: Variant → associated phenotypes
6. check_association: Check variant-disease association
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context

if TYPE_CHECKING:
    from cogex_mcp.schemas_tool10 import PhenotypeNode, VariantNode

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    READONLY_ANNOTATIONS,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    VariantQuery,
    VariantQueryMode,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_variants",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_variants(
    params: VariantQuery,
    ctx: Context,
) -> str:
    """
    Query genetic variants from GWAS Catalog and DisGeNet.

    This tool provides 6 query modes for comprehensive variant exploration:

    **Forward Modes (entity → variants):**
    - get_for_gene: Get variants in or near a specific gene
    - get_for_disease: Get variants associated with a disease
    - get_for_phenotype: Get GWAS hits for a phenotype

    **Reverse Modes (variant → entities):**
    - variant_to_genes: Find nearby genes for a variant
    - variant_to_phenotypes: Find associated phenotypes for a variant

    **Validation Mode:**
    - check_association: Check if variant is associated with disease

    Args:
        params (VariantQuery): Query parameters including:
            - mode (VariantQueryMode): Query mode (required)
            - gene (str | tuple): Gene identifier for get_for_gene mode
            - disease (str | tuple): Disease identifier for get_for_disease mode
            - phenotype (str | tuple): Phenotype identifier for get_for_phenotype mode
            - variant (str): Variant rsID for variant_to_* and check_association modes
            - min_p_value (float): Minimum p-value filter (optional)
            - max_p_value (float): Maximum p-value threshold (default 1e-5)
            - source (str): Data source filter (gwas_catalog, disgenet)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **get_for_* modes response:**
        {
            "variants": [
                {
                    "rsid": "rs7412",
                    "chromosome": "19",
                    "position": 45411941,
                    "ref_allele": "C",
                    "alt_allele": "T",
                    "p_value": 1.2e-8,
                    "odds_ratio": 2.4,
                    "trait": "Alzheimer's disease",
                    "study": "GCST123456",
                    "source": "gwas_catalog"
                },
                ...
            ],
            "pagination": { ... }
        }

        **variant_to_genes response:**
        {
            "variant": "rs7412",
            "genes": [...],  # List of GeneNode
            "pagination": { ... }
        }

        **variant_to_phenotypes response:**
        {
            "variant": "rs7412",
            "phenotypes": [...],  # List of PhenotypeNode
            "pagination": { ... }
        }

        **check_association response:**
        {
            "is_associated": true,
            "association_strength": 1.2e-8,
            "variant": { "rsid": "rs7412", ... },
            "disease": { "name": "Alzheimer's disease", ... }
        }

    Examples:
        - GWAS hits for APOE:
          mode="get_for_gene", gene="APOE", max_p_value=1e-8

        - Alzheimer's variants:
          mode="get_for_disease", disease="Alzheimer's disease"

        - Genes near variant:
          mode="variant_to_genes", variant="rs7412"

        - Check association:
          mode="check_association", variant="rs7412", disease="Alzheimer's disease"

    Error Handling:
        - Returns actionable error messages for invalid identifiers
        - Validates rsID format (must start with 'rs')
        - Handles missing entities gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Route to appropriate handler based on mode
        if params.mode == VariantQueryMode.GET_FOR_GENE:
            result = await _get_variants_for_gene(params, ctx)
        elif params.mode == VariantQueryMode.GET_FOR_DISEASE:
            result = await _get_variants_for_disease(params, ctx)
        elif params.mode == VariantQueryMode.GET_FOR_PHENOTYPE:
            result = await _get_variants_for_phenotype(params, ctx)
        elif params.mode == VariantQueryMode.VARIANT_TO_GENES:
            result = await _variant_to_genes(params, ctx)
        elif params.mode == VariantQueryMode.VARIANT_TO_PHENOTYPES:
            result = await _variant_to_phenotypes(params, ctx)
        elif params.mode == VariantQueryMode.CHECK_ASSOCIATION:
            result = await _check_association(params, ctx)
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


async def _get_variants_for_gene(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_for_gene
    Get variants in or near a specific gene.
    """
    if not params.gene:
        raise ValueError("gene parameter required for get_for_gene mode")

    await ctx.report_progress(0.2, "Resolving gene identifier...")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)

    await ctx.report_progress(0.3, f"Fetching variants for {gene.name}...")

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_gene",
        gene_id=gene.curie,
        max_p_value=params.max_p_value,
        source=params.source,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse variants and apply p-value filtering
    variants = _parse_variant_list(variant_data, params)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "variants": [v.model_dump() for v in variants],
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_disease(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_for_disease
    Get variants associated with a disease.
    """
    if not params.disease:
        raise ValueError("disease parameter required for get_for_disease mode")

    await ctx.report_progress(0.2, "Resolving disease identifier...")

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(params.disease)

    await ctx.report_progress(0.3, f"Fetching variants for {disease.name}...")

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_disease",
        disease_id=disease.curie,
        max_p_value=params.max_p_value,
        source=params.source,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    variants = _parse_variant_list(variant_data, params)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "variants": [v.model_dump() for v in variants],
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_phenotype(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_for_phenotype
    Get GWAS hits for a phenotype.
    """
    if not params.phenotype:
        raise ValueError("phenotype parameter required for get_for_phenotype mode")

    await ctx.report_progress(0.2, "Resolving phenotype identifier...")

    # Resolve phenotype identifier
    phenotype_id = params.phenotype if isinstance(params.phenotype, str) else params.phenotype[1]

    await ctx.report_progress(0.3, "Fetching variants for phenotype...")

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_phenotype",
        phenotype_id=phenotype_id,
        max_p_value=params.max_p_value,
        source=params.source,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    variants = _parse_variant_list(variant_data, params)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "variants": [v.model_dump() for v in variants],
        "pagination": pagination.model_dump(),
    }


async def _variant_to_genes(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: variant_to_genes
    Find nearby genes for a variant.
    """
    if not params.variant:
        raise ValueError("variant parameter required for variant_to_genes mode")

    await ctx.report_progress(0.3, f"Querying genes near {params.variant}...")

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_variant",
        variant_id=params.variant,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse genes
    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "variant": params.variant,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _variant_to_phenotypes(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: variant_to_phenotypes
    Find associated phenotypes for a variant.
    """
    if not params.variant:
        raise ValueError("variant parameter required for variant_to_phenotypes mode")

    await ctx.report_progress(0.3, f"Querying phenotypes for {params.variant}...")

    adapter = await get_adapter()
    phenotype_data = await adapter.query(
        "get_phenotypes_for_variant",
        variant_id=params.variant,
        max_p_value=params.max_p_value,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse phenotypes
    phenotypes = _parse_phenotype_list(phenotype_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=phenotypes,
        total_count=phenotype_data.get("total_count", len(phenotypes)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "variant": params.variant,
        "phenotypes": [p.model_dump() for p in phenotypes],
        "pagination": pagination.model_dump(),
    }


async def _check_association(
    params: VariantQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: check_association
    Check if variant is associated with disease.
    """
    if not params.variant:
        raise ValueError("variant parameter required for check_association mode")
    if not params.disease:
        raise ValueError("disease parameter required for check_association mode")

    await ctx.report_progress(0.2, "Resolving disease identifier...")

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(params.disease)

    await ctx.report_progress(0.4, f"Checking association for {params.variant}...")

    adapter = await get_adapter()
    assoc_data = await adapter.query(
        "is_variant_associated",
        variant_id=params.variant,
        disease_id=disease.curie,
        max_p_value=params.max_p_value,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing results...")

    # Extract association information
    is_associated = assoc_data.get("is_associated", False)
    association_strength = assoc_data.get("p_value", None)

    # Get variant details if associated
    variant_info = None
    if is_associated and assoc_data.get("variant"):
        variant_info = _parse_variant_node(assoc_data["variant"])

    return {
        "is_associated": is_associated,
        "association_strength": association_strength,
        "variant": variant_info.model_dump() if variant_info else {"rsid": params.variant},
        "disease": disease.model_dump(),
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_variant_node(data: dict[str, Any]) -> VariantNode:
    """Parse single variant from backend response."""
    # Import locally to avoid circular dependency
    from cogex_mcp.schemas_tool10 import VariantNode

    return VariantNode(
        rsid=data.get("rsid", data.get("variant_id", "unknown")),
        chromosome=str(data.get("chromosome", "unknown")),
        position=int(data.get("position", 0)),
        ref_allele=data.get("ref_allele", data.get("reference", "?")),
        alt_allele=data.get("alt_allele", data.get("alternate", "?")),
        p_value=float(data.get("p_value", 1.0)),
        odds_ratio=data.get("odds_ratio"),
        trait=data.get("trait", data.get("phenotype", "Unknown trait")),
        study=data.get("study", data.get("study_id", "Unknown study")),
        source=data.get("source", "unknown"),
    )


def _parse_variant_list(data: dict[str, Any], params: VariantQuery) -> list[VariantNode]:
    """Parse variant list from backend response with p-value filtering."""

    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variant = _parse_variant_node(record)

        # Apply p-value filtering
        if params.min_p_value is not None and variant.p_value < params.min_p_value:
            continue
        if variant.p_value > params.max_p_value:
            continue

        variants.append(variant)

    return variants


def _parse_phenotype_node(data: dict[str, Any]) -> PhenotypeNode:
    """Parse single phenotype from backend response."""
    from cogex_mcp.schemas_tool10 import PhenotypeNode

    return PhenotypeNode(
        name=data.get("phenotype", data.get("name", "Unknown")),
        curie=data.get("curie", data.get("phenotype_id", "unknown:unknown")),
        namespace=data.get("namespace", "hpo"),
        identifier=data.get("identifier", data.get("phenotype_id", "unknown")),
        description=data.get("description"),
    )


def _parse_phenotype_list(data: dict[str, Any]) -> list[PhenotypeNode]:
    """Parse phenotype list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append(_parse_phenotype_node(record))

    return phenotypes


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


logger.info("✓ Tool 10 (cogex_query_variants) registered")
