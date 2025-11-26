"""
Tool 1: cogex_query_gene_or_feature

Bidirectional queries between genes and their features (tissues, GO terms, domains, phenotypes).

Modes:
1. gene_to_features: Gene → comprehensive profile
2. tissue_to_genes: Tissue → genes expressed there
3. go_to_genes: GO term → annotated genes
4. domain_to_genes: Protein domain → genes containing it
5. phenotype_to_genes: Phenotype → associated genes
"""

import logging
from typing import Any

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    GeneFeatureQuery,
    QueryMode,
)
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)

async def cogex_query_gene_or_feature(
    params: GeneFeatureQuery) -> str:
    """
    Query genes and their features bidirectionally.

    This tool supports 5 query modes for comprehensive gene-feature exploration:

    **Forward Mode (gene → features):**
    - gene_to_features: Get all features for a specific gene (expression, GO terms,
      pathways, diseases, domains, variants, phenotypes, codependencies)

    **Reverse Modes (feature → genes):**
    - tissue_to_genes: Find genes expressed in a specific tissue
    - go_to_genes: Find genes annotated with a specific GO term
    - domain_to_genes: Find genes containing a specific protein domain
    - phenotype_to_genes: Find genes associated with a specific phenotype

    Args:
        params (GeneFeatureQuery): Query parameters including:
            - mode (QueryMode): Query direction (required)
            - gene (str | tuple): Gene identifier for gene_to_features mode
            - tissue (str | tuple): Tissue identifier for tissue_to_genes mode
            - go_term (str | tuple): GO term for go_to_genes mode
            - domain (str | tuple): Domain identifier for domain_to_genes mode
            - phenotype (str | tuple): Phenotype identifier for phenotype_to_genes mode
            - include_* flags: Control which features to include (gene_to_features only)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results for reverse modes (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **gene_to_features response:**
        {
            "gene": { "name": "TP53", "curie": "hgnc:11998", ... },
            "expression": [...],  # Tissue expression data
            "go_terms": [...],    # Gene Ontology annotations
            "pathways": [...],    # Pathway memberships
            "diseases": [...],    # Disease associations
            "domains": [...],     # Protein domains (optional)
            "variants": [...],    # Genetic variants (optional)
            "phenotypes": [...],  # Phenotype associations (optional)
            "codependencies": [...]  # Gene codependencies (optional)
        }

        **Reverse mode responses:**
        {
            "genes": [...],        # List of genes
            "pagination": { ... }  # Pagination metadata
        }

    Examples:
        - Get TP53 profile:
          mode="gene_to_features", gene="TP53", include_all=True

        - Find brain-expressed genes:
          mode="tissue_to_genes", tissue="brain", limit=50

        - Find kinase genes:
          mode="go_to_genes", go_term="GO:0016301", limit=100

        - Find genes with SH2 domain:
          mode="domain_to_genes", domain="SH2", limit=50

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
        if params.mode == QueryMode.GENE_TO_FEATURES:
            result = await _gene_to_features(params)
        elif params.mode == QueryMode.TISSUE_TO_GENES:
            result = await _tissue_to_genes(params)
        elif params.mode == QueryMode.GO_TO_GENES:
            result = await _go_to_genes(params)
        elif params.mode == QueryMode.DOMAIN_TO_GENES:
            result = await _domain_to_genes(params)
        elif params.mode == QueryMode.PHENOTYPE_TO_GENES:
            result = await _phenotype_to_genes(params)
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

async def _gene_to_features(
    params: GeneFeatureQuery) -> dict[str, Any]:
    """
    Mode: gene_to_features
    Get comprehensive gene profile with all requested features.
    """
    if not params.gene:
        raise ValueError("gene parameter required for gene_to_features mode")
    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.gene)
    adapter = await get_adapter()
    result = {
        "gene": gene.model_dump(),
    }

    # Fetch requested features
    if params.include_expression:
        expression_data = await adapter.query(
            "get_tissues_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_expression_data(expression_data)

    if params.include_go_terms:
        go_data = await adapter.query(
            "get_go_terms_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["go_terms"] = _parse_go_annotations(go_data)

    if params.include_pathways:
        pathway_data = await adapter.query(
            "get_pathways_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["pathways"] = _parse_pathway_memberships(pathway_data)

    if params.include_diseases:
        disease_data = await adapter.query(
            "get_diseases_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["diseases"] = _parse_disease_associations(disease_data)

    # Optional features (more expensive queries)
    if params.include_domains:
        # TODO: Implement when backend query is available
        result["domains"] = []

    if params.include_variants:
        # TODO: Implement when backend query is available
        result["variants"] = []

    if params.include_phenotypes:
        # TODO: Implement when backend query is available
        result["phenotypes"] = []

    if params.include_codependencies:
        # TODO: Implement when backend query is available
        result["codependencies"] = []

    return result

async def _tissue_to_genes(
    params: GeneFeatureQuery) -> dict[str, Any]:
    """
    Mode: tissue_to_genes
    Find genes expressed in a specific tissue.
    """
    if not params.tissue:
        raise ValueError("tissue parameter required for tissue_to_genes mode")
    # Resolve tissue identifier
    # For now, accept tissue name directly
    # TODO: Implement tissue resolution
    tissue_id = params.tissue if isinstance(params.tissue, str) else params.tissue[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_in_tissue",
        tissue_id=tissue_id,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )
    # Parse genes
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
        "genes": genes,
        "pagination": pagination.model_dump(),
    }

async def _go_to_genes(
    params: GeneFeatureQuery) -> dict[str, Any]:
    """
    Mode: go_to_genes
    Find genes annotated with a specific GO term.
    """
    if not params.go_term:
        raise ValueError("go_term parameter required for go_to_genes mode")
    # Parse GO term identifier
    go_id = params.go_term if isinstance(params.go_term, str) else params.go_term[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_go_term",
        go_id=go_id,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )
    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "genes": genes,
        "pagination": pagination.model_dump(),
    }

async def _domain_to_genes(
    params: GeneFeatureQuery) -> dict[str, Any]:
    """
    Mode: domain_to_genes
    Find genes containing a specific protein domain.
    """
    if not params.domain:
        raise ValueError("domain parameter required for domain_to_genes mode")
    # TODO: Implement when backend query is available
    # For now, return placeholder
    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": params.offset,
            "limit": params.limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Domain queries not yet implemented in backend",
    }

async def _phenotype_to_genes(
    params: GeneFeatureQuery) -> dict[str, Any]:
    """
    Mode: phenotype_to_genes
    Find genes associated with a specific phenotype.
    """
    if not params.phenotype:
        raise ValueError("phenotype parameter required for phenotype_to_genes mode")
    # TODO: Implement when backend query is available
    # For now, return placeholder
    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": params.offset,
            "limit": params.limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Phenotype queries not yet implemented in backend",
    }

# ============================================================================
# Data Parsing Helpers
# ============================================================================

def _parse_expression_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse tissue expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expressions = []
    for record in data["records"]:
        expressions.append(
            {
                "tissue": {
                    "name": record.get("tissue", "Unknown"),
                    "curie": record.get("tissue_id", "unknown:unknown"),
                    "namespace": "uberon",  # Common tissue ontology
                    "identifier": record.get("tissue_id", "unknown"),
                },
                "confidence": record.get("confidence", "unknown"),
                "evidence_count": record.get("evidence_count", 0),
            }
        )

    return expressions

def _parse_go_annotations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse GO annotations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    annotations = []
    for record in data["records"]:
        annotations.append(
            {
                "go_term": {
                    "name": record.get("term", "Unknown"),
                    "curie": record.get("go_id", "unknown:unknown"),
                    "namespace": "go",
                    "identifier": record.get("go_id", "unknown"),
                },
                "aspect": record.get("aspect", "unknown"),
                "evidence_code": record.get("evidence_code", "N/A"),
            }
        )

    return annotations

def _parse_pathway_memberships(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway memberships from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append(
            {
                "pathway": {
                    "name": record.get("pathway", "Unknown"),
                    "curie": record.get("pathway_id", "unknown:unknown"),
                    "namespace": record.get("source", "unknown"),
                    "identifier": record.get("pathway_id", "unknown"),
                },
                "source": record.get("source", "unknown"),
            }
        )

    return pathways

def _parse_disease_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append(
            {
                "disease": {
                    "name": record.get("disease", "Unknown"),
                    "curie": record.get("disease_id", "unknown:unknown"),
                    "namespace": "mondo",
                    "identifier": record.get("disease_id", "unknown"),
                },
                "score": record.get("score", 0.0),
                "evidence_count": record.get("evidence_count", 0),
                "sources": record.get("sources", []),
            }
        )

    return diseases

def _parse_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append(
            {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            }
        )

    return genes

logger.info("✓ Tool 1 (cogex_query_gene_or_feature) registered")
