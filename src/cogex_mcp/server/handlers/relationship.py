"""
Relationship

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
    """Handle relationship check - Tool 12."""
    try:
        # Parse params
        from cogex_mcp.schemas import RelationshipQuery, RelationshipType
        params = RelationshipQuery(**args)

        # Route to appropriate handler based on relationship type
        if params.relationship_type == RelationshipType.GENE_IN_PATHWAY:
            result = await _check_gene_in_pathway(params)
        elif params.relationship_type == RelationshipType.DRUG_TARGET:
            result = await _check_drug_target(params)
        elif params.relationship_type == RelationshipType.DRUG_INDICATION:
            result = await _check_drug_indication(params)
        elif params.relationship_type == RelationshipType.DRUG_SIDE_EFFECT:
            result = await _check_drug_side_effect(params)
        elif params.relationship_type == RelationshipType.GENE_DISEASE:
            result = await _check_gene_disease(params)
        elif params.relationship_type == RelationshipType.DISEASE_PHENOTYPE:
            result = await _check_disease_phenotype(params)
        elif params.relationship_type == RelationshipType.GENE_PHENOTYPE:
            result = await _check_gene_phenotype(params)
        elif params.relationship_type == RelationshipType.VARIANT_ASSOCIATION:
            result = await _check_variant_association(params)
        elif params.relationship_type == RelationshipType.CELL_LINE_MUTATION:
            result = await _check_cell_line_mutation(params)
        elif params.relationship_type == RelationshipType.CELL_MARKER:
            result = await _check_cell_marker(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown relationship type '{params.relationship_type}'")]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Relationship Check Implementations

async def _check_gene_in_pathway(params) -> dict[str, Any]:
    """Check if gene is in pathway. entity1: gene, entity2: pathway"""
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.entity1)

    # Parse pathway identifier
    if isinstance(params.entity2, tuple):
        pathway_id = f"{params.entity2[0]}:{params.entity2[1]}"
    else:
        pathway_id = params.entity2

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_in_pathway",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_in_pathway",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": pathway_id, "type": "pathway"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_target(params) -> dict[str, Any]:
    """Check if drug targets gene/protein. entity1: drug, entity2: gene"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve target gene
    target = await resolver.resolve_gene(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_drug_target",
        drug_id=drug.curie,
        target_id=target.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("confidence"),
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_target",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": target.name, "curie": target.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_indication(params) -> dict[str, Any]:
    """Check if drug is indicated for disease. entity1: drug, entity2: disease"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "drug_has_indication",
        drug_id=drug.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_indication",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": disease.name, "curie": disease.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_side_effect(params) -> dict[str, Any]:
    """Check if drug causes side effect. entity1: drug, entity2: side effect"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Parse side effect
    side_effect_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_side_effect_for_drug",
        drug_id=drug.curie,
        side_effect_id=side_effect_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_side_effect",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": side_effect_id, "type": "side_effect"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_gene_disease(params) -> dict[str, Any]:
    """Check if gene is associated with disease. entity1: gene, entity2: disease"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_disease",
        gene_id=gene.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("score"),  # Use association score as confidence
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_disease",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": disease.name, "curie": disease.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_disease_phenotype(params) -> dict[str, Any]:
    """Check if disease has phenotype. entity1: disease, entity2: phenotype"""
    resolver = get_resolver()

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "disease_phenotype",
        "entity1": {"name": disease.name, "curie": disease.curie},
        "entity2": {"name": phenotype_id, "type": "phenotype"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_gene_phenotype(params) -> dict[str, Any]:
    """Check if gene is associated with phenotype. entity1: gene, entity2: phenotype"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_phenotype",
        gene_id=gene.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_phenotype",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": phenotype_id, "type": "phenotype"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_variant_association(params) -> dict[str, Any]:
    """Check if variant is associated with trait/disease. entity1: variant (rsID), entity2: trait/disease"""
    # Parse variant rsID
    variant_id = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]
    if not variant_id.startswith("rs"):
        raise ValueError(f"Variant must be an rsID starting with 'rs', got: {variant_id}")

    # Parse trait/disease
    trait_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_variant_associated",
        variant_id=variant_id,
        trait_id=trait_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("p_value"),  # Use p-value as confidence indicator
            evidence_count=check_data["metadata"].get("study_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "variant_association",
        "entity1": {"name": variant_id, "type": "variant"},
        "entity2": {"name": trait_id, "type": "trait"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_cell_line_mutation(params) -> dict[str, Any]:
    """Check if cell line has mutation in gene. entity1: cell line, entity2: gene"""
    resolver = get_resolver()

    # Parse cell line name
    cell_line = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=cell_line,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("mutation_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "cell_line_mutation",
        "entity1": {"name": cell_line, "type": "cell_line"},
        "entity2": {"name": gene.name, "curie": gene.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_cell_marker(params) -> dict[str, Any]:
    """Check if gene is a marker for cell type. entity1: gene, entity2: cell type"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse cell type
    cell_type = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_cell_marker",
        gene_id=gene.curie,
        cell_type=cell_type,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("marker_confidence"),
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "cell_marker",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": cell_type, "type": "cell_type"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


