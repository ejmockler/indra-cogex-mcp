"""
Variants

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
    """Handle variants query - Tool 10."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_gene":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_for_gene mode"
                )]
            result = await _get_variants_for_gene(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_variants_for_disease(args)
        elif mode == "get_for_phenotype":
            if not args.get("phenotype"):
                return [types.TextContent(
                    type="text",
                    text="Error: phenotype parameter required for get_for_phenotype mode"
                )]
            result = await _get_variants_for_phenotype(args)
        elif mode == "variant_to_genes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_genes mode"
                )]
            result = await _variant_to_genes(args)
        elif mode == "variant_to_phenotypes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_phenotypes mode"
                )]
            result = await _variant_to_phenotypes(args)
        elif mode == "check_association":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for check_association mode"
                )]
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for check_association mode"
                )]
            result = await _check_variant_association(args)
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


# Tool 10 Mode Handlers
async def _get_variants_for_gene(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_gene - Get variants in or near a specific gene."""
    gene_input = args["gene"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_gene",
        gene_id=gene.curie,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse variants and apply p-value filtering
    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_disease(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_disease - Get variants associated with a disease."""
    disease_input = args["disease"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_disease",
        disease_id=disease.curie,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_phenotype - Get GWAS hits for a phenotype."""
    phenotype_input = args["phenotype"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Parse phenotype identifier
    phenotype_id = phenotype_input if isinstance(phenotype_input, str) else phenotype_input[1]

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_phenotype",
        phenotype_id=phenotype_id,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _variant_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: variant_to_genes - Find nearby genes for a variant."""
    variant = args["variant"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_variant",
        variant_id=variant,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse genes
    genes = _parse_gene_list_for_variant(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "variant": variant,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _variant_to_phenotypes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: variant_to_phenotypes - Find associated phenotypes for a variant."""
    variant = args["variant"]
    max_p_value = args.get("max_p_value", 0.00001)
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    phenotype_data = await adapter.query(
        "get_phenotypes_for_variant",
        variant_id=variant,
        max_p_value=max_p_value,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse phenotypes
    phenotypes = _parse_phenotype_list_for_variant(phenotype_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=phenotypes,
        total_count=phenotype_data.get("total_count", len(phenotypes)),
        offset=offset,
        limit=limit,
    )

    return {
        "variant": variant,
        "phenotypes": phenotypes,
        "pagination": pagination.model_dump(),
    }


async def _check_variant_association(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_association - Check if variant is associated with disease."""
    variant = args["variant"]
    disease_input = args["disease"]
    max_p_value = args.get("max_p_value", 0.00001)

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    assoc_data = await adapter.query(
        "is_variant_associated",
        variant_id=variant,
        disease_id=disease.curie,
        max_p_value=max_p_value,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Extract association information
    is_associated = assoc_data.get("is_associated", False) if assoc_data.get("success") else False
    association_strength = assoc_data.get("p_value", None)

    # Get variant details if associated
    variant_info = None
    if is_associated and assoc_data.get("variant"):
        variant_info = _parse_variant_node(assoc_data["variant"])

    return {
        "is_associated": is_associated,
        "association_strength": association_strength,
        "variant": variant_info if variant_info else {"rsid": variant},
        "disease": {
            "name": disease.name,
            "curie": disease.curie,
            "namespace": disease.namespace,
            "identifier": disease.identifier,
        },
    }


# Data parsing helpers for Tool 10
def _parse_variant_node(data: dict[str, Any]) -> dict[str, Any]:
    """Parse single variant from backend response."""
    return {
        "rsid": data.get("rsid", data.get("variant_id", "unknown")),
        "chromosome": str(data.get("chromosome", "unknown")),
        "position": int(data.get("position", 0)),
        "ref_allele": data.get("ref_allele", data.get("reference", "?")),
        "alt_allele": data.get("alt_allele", data.get("alternate", "?")),
        "p_value": float(data.get("p_value", 1.0)),
        "odds_ratio": data.get("odds_ratio"),
        "trait": data.get("trait", data.get("phenotype", "Unknown trait")),
        "study": data.get("study", data.get("study_id", "Unknown study")),
        "source": data.get("source", "unknown"),
    }


def _parse_variant_list(data: dict[str, Any], min_p_value: float | None, max_p_value: float) -> list[dict[str, Any]]:
    """Parse variant list from backend response with p-value filtering."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variant = _parse_variant_node(record)

        # Apply p-value filtering
        if min_p_value is not None and variant["p_value"] < min_p_value:
            continue
        if variant["p_value"] > max_p_value:
            continue

        variants.append(variant)

    return variants


def _parse_phenotype_node_for_variant(data: dict[str, Any]) -> dict[str, Any]:
    """Parse single phenotype from backend response."""
    return {
        "name": data.get("phenotype", data.get("name", "Unknown")),
        "curie": data.get("curie", data.get("phenotype_id", "unknown:unknown")),
        "namespace": data.get("namespace", "hpo"),
        "identifier": data.get("identifier", data.get("phenotype_id", "unknown")),
        "description": data.get("description"),
    }


def _parse_phenotype_list_for_variant(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse phenotype list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append(_parse_phenotype_node_for_variant(record))

    return phenotypes


def _parse_gene_list_for_variant(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
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
            "synonyms": record.get("synonyms", []),
        })

    return genes



