"""
Tool 12: cogex_check_relationship

Boolean validators for specific entity relationships.

Modes:
10 relationship types covering pathways, drugs, diseases, phenotypes, variants, and cell lines
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
    RelationshipMetadata,
    RelationshipQuery,
    RelationshipType,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_check_relationship",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_check_relationship(
    params: RelationshipQuery,
    ctx: Context,
) -> str:
    """
    Check existence of specific relationships between biological entities.

    This tool provides efficient boolean validators for 10 types of relationships,
    making it ideal for quick validation checks without retrieving full datasets.

    **Relationship Types:**

    1. **gene_in_pathway**: Is gene in pathway?
       - entity1: Gene (symbol or CURIE)
       - entity2: Pathway (name or CURIE)

    2. **drug_target**: Does drug target gene/protein?
       - entity1: Drug (name or CURIE)
       - entity2: Gene/protein (symbol or CURIE)

    3. **drug_indication**: Is drug indicated for disease?
       - entity1: Drug (name or CURIE)
       - entity2: Disease (name or CURIE)

    4. **drug_side_effect**: Does drug cause side effect?
       - entity1: Drug (name or CURIE)
       - entity2: Side effect term (name or CURIE)

    5. **gene_disease**: Is gene associated with disease?
       - entity1: Gene (symbol or CURIE)
       - entity2: Disease (name or CURIE)

    6. **disease_phenotype**: Does disease have phenotype?
       - entity1: Disease (name or CURIE)
       - entity2: Phenotype (HPO term or CURIE)

    7. **gene_phenotype**: Is gene associated with phenotype?
       - entity1: Gene (symbol or CURIE)
       - entity2: Phenotype (HPO term or CURIE)

    8. **variant_association**: Is variant associated with trait/disease?
       - entity1: Variant (rsID, e.g., 'rs7412')
       - entity2: Trait/disease (name or CURIE)

    9. **cell_line_mutation**: Does cell line have mutation in gene?
       - entity1: Cell line (name, e.g., 'A549')
       - entity2: Gene (symbol or CURIE)

    10. **cell_marker**: Is gene a marker for cell type?
        - entity1: Gene (symbol or CURIE)
        - entity2: Cell type (name)

    Args:
        params (RelationshipQuery): Query parameters including:
            - relationship_type (RelationshipType): Type of relationship to check (required)
            - entity1 (str | tuple): First entity as name or (namespace, id) tuple (required)
            - entity2 (str | tuple): Second entity as name or (namespace, id) tuple (required)
            - response_format (ResponseFormat): 'markdown' or 'json' (default: markdown)

    Returns:
        str: Formatted response in requested format

        **Markdown format:**
        Simple "Yes" or "No" with optional metadata:
        - Evidence count
        - Confidence score
        - Source databases
        - Additional context

        **JSON format:**
        {
            "exists": true/false,
            "metadata": {
                "confidence": 0.95,
                "evidence_count": 15,
                "sources": ["chembl", "drugbank"],
                "additional_info": { ... }
            }
        }

    Examples:
        - Is TP53 in p53 signaling pathway?
          relationship_type="gene_in_pathway", entity1="TP53", entity2="p53 signaling"

        - Does imatinib target BCR-ABL?
          relationship_type="drug_target", entity1="imatinib", entity2="ABL1"

        - Is BRCA1 associated with breast cancer?
          relationship_type="gene_disease", entity1="BRCA1", entity2="breast cancer"

        - Does metformin cause nausea?
          relationship_type="drug_side_effect", entity1="metformin", entity2="nausea"

    Use Cases:
        - Quick validation checks: "Does this relationship exist?"
        - Filtering before detailed queries: Check existence before fetching full data
        - Batch validation: Programmatic checking of multiple relationships
        - Knowledge graph validation: Verify expected connections

    Performance:
        More efficient than full queries when you only need yes/no answers.
        Typical response time: < 500ms per check.

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

        # Route to appropriate handler based on relationship type
        if params.relationship_type == RelationshipType.GENE_IN_PATHWAY:
            result = await _check_gene_in_pathway(params, ctx)
        elif params.relationship_type == RelationshipType.DRUG_TARGET:
            result = await _check_drug_target(params, ctx)
        elif params.relationship_type == RelationshipType.DRUG_INDICATION:
            result = await _check_drug_indication(params, ctx)
        elif params.relationship_type == RelationshipType.DRUG_SIDE_EFFECT:
            result = await _check_drug_side_effect(params, ctx)
        elif params.relationship_type == RelationshipType.GENE_DISEASE:
            result = await _check_gene_disease(params, ctx)
        elif params.relationship_type == RelationshipType.DISEASE_PHENOTYPE:
            result = await _check_disease_phenotype(params, ctx)
        elif params.relationship_type == RelationshipType.GENE_PHENOTYPE:
            result = await _check_gene_phenotype(params, ctx)
        elif params.relationship_type == RelationshipType.VARIANT_ASSOCIATION:
            result = await _check_variant_association(params, ctx)
        elif params.relationship_type == RelationshipType.CELL_LINE_MUTATION:
            result = await _check_cell_line_mutation(params, ctx)
        elif params.relationship_type == RelationshipType.CELL_MARKER:
            result = await _check_cell_marker(params, ctx)
        else:
            return f"Error: Unknown relationship type '{params.relationship_type}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Check complete")
        return response

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Relationship Check Implementations
# ============================================================================


async def _check_gene_in_pathway(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if gene is in pathway.
    entity1: gene, entity2: pathway
    """
    await ctx.report_progress(0.2, "Resolving gene identifier...")

    # Resolve gene
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.entity1)

    # Parse pathway identifier
    if isinstance(params.entity2, tuple):
        pathway_id = f"{params.entity2[0]}:{params.entity2[1]}"
    else:
        pathway_id = params.entity2

    await ctx.report_progress(0.5, f"Checking if {gene.name} is in pathway...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_in_pathway",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_drug_target(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if drug targets gene/protein.
    entity1: drug, entity2: gene
    """
    await ctx.report_progress(0.2, "Resolving identifiers...")

    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve target gene
    target = await resolver.resolve_gene(params.entity2)

    await ctx.report_progress(0.5, f"Checking if {drug.name} targets {target.name}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_drug_target",
        drug_id=drug.curie,
        target_id=target.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_drug_indication(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if drug is indicated for disease.
    entity1: drug, entity2: disease
    """
    await ctx.report_progress(0.2, "Resolving identifiers...")

    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    await ctx.report_progress(0.5, f"Checking if {drug.name} is indicated for {disease.name}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "drug_has_indication",
        drug_id=drug.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_drug_side_effect(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if drug causes side effect.
    entity1: drug, entity2: side effect
    """
    await ctx.report_progress(0.2, "Resolving drug identifier...")

    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Parse side effect
    side_effect_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    await ctx.report_progress(0.5, f"Checking if {drug.name} causes {side_effect_id}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_side_effect_for_drug",
        drug_id=drug.curie,
        side_effect_id=side_effect_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_gene_disease(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if gene is associated with disease.
    entity1: gene, entity2: disease
    """
    await ctx.report_progress(0.2, "Resolving identifiers...")

    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    await ctx.report_progress(0.5, f"Checking if {gene.name} is associated with {disease.name}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_disease",
        gene_id=gene.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_disease_phenotype(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if disease has phenotype.
    entity1: disease, entity2: phenotype
    """
    await ctx.report_progress(0.2, "Resolving disease identifier...")

    resolver = get_resolver()

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    await ctx.report_progress(0.5, f"Checking if {disease.name} has phenotype {phenotype_id}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_gene_phenotype(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if gene is associated with phenotype.
    entity1: gene, entity2: phenotype
    """
    await ctx.report_progress(0.2, "Resolving gene identifier...")

    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    await ctx.report_progress(0.5, f"Checking if {gene.name} is associated with {phenotype_id}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_phenotype",
        gene_id=gene.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_variant_association(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if variant is associated with trait/disease.
    entity1: variant (rsID), entity2: trait/disease
    """
    await ctx.report_progress(0.2, "Validating variant...")

    # Parse variant rsID
    variant_id = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]
    if not variant_id.startswith("rs"):
        raise ValueError(f"Variant must be an rsID starting with 'rs', got: {variant_id}")

    # Parse trait/disease
    trait_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    await ctx.report_progress(0.5, f"Checking if {variant_id} is associated with {trait_id}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_variant_associated",
        variant_id=variant_id,
        trait_id=trait_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_cell_line_mutation(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if cell line has mutation in gene.
    entity1: cell line, entity2: gene
    """
    await ctx.report_progress(0.2, "Resolving gene identifier...")

    resolver = get_resolver()

    # Parse cell line name
    cell_line = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity2)

    await ctx.report_progress(0.5, f"Checking if {cell_line} has mutation in {gene.name}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=cell_line,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


async def _check_cell_marker(
    params: RelationshipQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Check if gene is a marker for cell type.
    entity1: gene, entity2: cell type
    """
    await ctx.report_progress(0.2, "Resolving gene identifier...")

    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse cell type
    cell_type = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    await ctx.report_progress(0.5, f"Checking if {gene.name} is a marker for {cell_type}...")

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_cell_marker",
        gene_id=gene.curie,
        cell_type=cell_type,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.8, "Processing result...")

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
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


logger.info("✓ Tool 12 (cogex_check_relationship) registered")
