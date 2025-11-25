"""
Tool 3: cogex_enrichment_analysis

Statistical gene set and pathway enrichment analysis.

Analysis Types:
1. discrete: Overrepresentation analysis (Fisher's exact test)
2. continuous: Gene Set Enrichment Analysis (GSEA) with ranked genes
3. signed: Directional enrichment (up/down regulation)
4. metabolite: Metabolite set enrichment analysis
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context

from cogex_mcp.server import mcp
from cogex_mcp.schemas import (
    EnrichmentQuery,
    EnrichmentType,
    EnrichmentSource,
    EnrichmentResult,
    EnrichmentStatistics,
    EntityRef,
)
from cogex_mcp.constants import (
    STATISTICAL_ANNOTATIONS,
    ResponseFormat,
    ENRICHMENT_TIMEOUT,
    CHARACTER_LIMIT,
)
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.clients.adapter import get_adapter

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_enrichment_analysis",
    annotations=STATISTICAL_ANNOTATIONS,
)
async def cogex_enrichment_analysis(
    params: EnrichmentQuery,
    ctx: Context,
) -> str:
    """
    Perform statistical gene set and pathway enrichment analysis.

    This tool supports 4 analysis types for comprehensive enrichment discovery:

    **Analysis Types:**

    1. **discrete**: Overrepresentation analysis (Fisher's exact test)
       - Use when: You have a list of differentially expressed genes
       - Input: gene_list (required), background_genes (optional)
       - Method: Fisher's exact test for categorical enrichment
       - Example: "What GO terms are enriched in my DE gene list?"

    2. **continuous**: Gene Set Enrichment Analysis (GSEA)
       - Use when: You have ranked genes (e.g., by log fold change)
       - Input: ranked_genes (dict of gene → score)
       - Method: Permutation-based GSEA with enrichment scores
       - Example: "Run GSEA on genes ranked by differential expression"

    3. **signed**: Directional enrichment analysis
       - Use when: You want up/down regulation directionality
       - Input: ranked_genes (dict of gene → signed score)
       - Method: Separate enrichment for positive/negative scoring genes
       - Example: "Find pathways enriched in upregulated vs downregulated genes"

    4. **metabolite**: Metabolite set enrichment
       - Use when: You have a list of metabolites
       - Input: gene_list (metabolite IDs)
       - Method: Metabolite-specific overrepresentation
       - Example: "Enriched pathways for detected metabolites"

    **Enrichment Sources:**

    - **go**: Gene Ontology (BP, MF, CC)
    - **reactome**: Reactome pathways
    - **wikipathways**: WikiPathways
    - **indra-upstream**: INDRA upstream regulators
    - **indra-downstream**: INDRA downstream targets
    - **phenotype**: HPO phenotype associations

    **Statistical Parameters:**

    - alpha: Significance threshold (default: 0.05)
    - correction_method: Multiple testing correction (fdr_bh, bonferroni)
    - permutations: Number of permutations for GSEA (default: 1000)
    - keep_insignificant: Include non-significant results (default: False)

    **INDRA-specific Filters:**

    - min_evidence_count: Minimum evidences (default: 1)
    - min_belief_score: Minimum belief score (default: 0.0)

    Args:
        params (EnrichmentQuery): Query parameters including:
            - analysis_type (EnrichmentType): Analysis method (required)
            - gene_list (List[str]): Genes for discrete/metabolite analysis
            - ranked_genes (Dict[str, float]): Gene→score for continuous/signed
            - background_genes (List[str]): Background set (optional)
            - source (EnrichmentSource): Enrichment database (default: GO)
            - alpha (float): Significance threshold (default: 0.05)
            - correction_method (str): Multiple testing correction (default: fdr_bh)
            - keep_insignificant (bool): Include non-sig results (default: False)
            - permutations (int): GSEA permutations (default: 1000)
            - min_evidence_count (int): Min evidences for INDRA (default: 1)
            - min_belief_score (float): Min belief for INDRA (default: 0.0)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted enrichment results in requested format

        **discrete/metabolite response:**
        ```
        {
            "results": [
                {
                    "term": {"name": "apoptotic process", "curie": "GO:0006915", ...},
                    "term_name": "apoptotic process",
                    "p_value": 0.001,
                    "adjusted_p_value": 0.015,
                    "gene_count": 12,
                    "term_size": 450,
                    "genes": ["TP53", "BCL2", ...],
                    "background_count": 20000
                }
            ],
            "statistics": {
                "total_results": 1500,
                "significant_results": 45,
                "total_genes_analyzed": 250,
                "correction_method": "fdr_bh",
                "alpha": 0.05
            }
        }
        ```

        **continuous/signed response:**
        ```
        {
            "results": [
                {
                    "term": {...},
                    "term_name": "cell cycle",
                    "p_value": 0.001,
                    "adjusted_p_value": 0.02,
                    "enrichment_score": 0.65,
                    "normalized_enrichment_score": 2.1,
                    "gene_count": 35,
                    "term_size": 500,
                    "genes": ["CDK1", "CCNB1", ...]
                }
            ],
            "statistics": {...}
        }
        ```

    Examples:
        - Discrete enrichment (GO):
          analysis_type="discrete", gene_list=["TP53", "MDM2", ...],
          source="go", alpha=0.05

        - GSEA with ranked genes:
          analysis_type="continuous", ranked_genes={"TP53": 2.5, "MDM2": -1.8, ...},
          source="reactome", permutations=1000

        - Directional enrichment:
          analysis_type="signed", ranked_genes={"GENE1": 3.2, "GENE2": -2.1, ...},
          source="go"

        - Find upstream regulators:
          analysis_type="discrete", gene_list=[...],
          source="indra-upstream", min_evidence_count=5

        - Metabolite enrichment:
          analysis_type="metabolite", gene_list=["HMDB00001", "HMDB00002", ...],
          source="reactome"

    Error Handling:
        - Returns actionable error messages for invalid genes
        - Suggests alternatives for ambiguous identifiers
        - Handles empty result sets gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating parameters...")

        # Route to appropriate handler based on analysis type
        if params.analysis_type == EnrichmentType.DISCRETE:
            result = await _analyze_discrete(params, ctx)
        elif params.analysis_type == EnrichmentType.CONTINUOUS:
            result = await _analyze_continuous(params, ctx)
        elif params.analysis_type == EnrichmentType.SIGNED:
            result = await _analyze_signed(params, ctx)
        elif params.analysis_type == EnrichmentType.METABOLITE:
            result = await _analyze_metabolite(params, ctx)
        else:
            return f"Error: Unknown analysis type '{params.analysis_type}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Enrichment analysis complete")
        return response

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return f"Error: {str(e)}"

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Mode Implementations
# ============================================================================


async def _analyze_discrete(
    params: EnrichmentQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: discrete
    Overrepresentation analysis using Fisher's exact test.
    """
    if not params.gene_list:
        raise ValueError("gene_list parameter required for discrete analysis")

    await ctx.report_progress(0.2, f"Resolving {len(params.gene_list)} genes...")

    # Resolve gene identifiers
    resolver = get_resolver()
    resolved_genes = []
    failed_genes = []

    for gene in params.gene_list:
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_genes.append(resolved)
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_genes:
        raise ValueError(
            f"No genes could be resolved. Failed: {', '.join(failed_genes)}"
        )

    if failed_genes:
        logger.info(
            f"Proceeding with {len(resolved_genes)}/{len(params.gene_list)} genes. "
            f"Failed: {', '.join(failed_genes[:5])}{'...' if len(failed_genes) > 5 else ''}"
        )

    # Optionally resolve background genes
    background_gene_ids = None
    if params.background_genes:
        await ctx.report_progress(
            0.3, f"Resolving {len(params.background_genes)} background genes..."
        )
        background_resolved = []
        for gene in params.background_genes:
            try:
                resolved = await resolver.resolve_gene(gene)
                background_resolved.append(resolved)
            except EntityResolutionError:
                pass
        background_gene_ids = [g.curie for g in background_resolved]

    await ctx.report_progress(
        0.4, f"Running discrete enrichment ({params.source.value})..."
    )

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "source": params.source.value,
        "alpha": params.alpha,
        "correction_method": params.correction_method,
        "keep_insignificant": params.keep_insignificant,
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_gene_ids:
        query_params["background_gene_ids"] = background_gene_ids

    # Add INDRA-specific parameters if applicable
    if params.source in [EnrichmentSource.INDRA_UPSTREAM, EnrichmentSource.INDRA_DOWNSTREAM]:
        query_params["min_evidence_count"] = params.min_evidence_count
        query_params["min_belief_score"] = params.min_belief_score

    enrichment_data = await adapter.query("discrete_analysis", **query_params)

    await ctx.report_progress(0.8, "Processing enrichment results...")

    # Parse results
    results = _parse_enrichment_results(enrichment_data, params.analysis_type)
    statistics = _compute_enrichment_stats(results, params, len(resolved_genes))

    return {
        "results": [r.model_dump() for r in results],
        "statistics": statistics.model_dump(),
        "resolved_genes": len(resolved_genes),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_continuous(
    params: EnrichmentQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: continuous
    Gene Set Enrichment Analysis (GSEA) with ranked gene list.
    """
    if not params.ranked_genes:
        raise ValueError("ranked_genes parameter required for continuous analysis")

    await ctx.report_progress(
        0.2, f"Resolving {len(params.ranked_genes)} ranked genes..."
    )

    # Resolve gene identifiers and preserve scores
    resolver = get_resolver()
    resolved_ranking: Dict[str, float] = {}
    failed_genes = []

    for gene, score in params.ranked_genes.items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(
            f"No genes could be resolved. Failed: {', '.join(failed_genes)}"
        )

    await ctx.report_progress(
        0.4,
        f"Running GSEA with {params.permutations} permutations ({params.source.value})...",
    )

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "source": params.source.value,
        "alpha": params.alpha,
        "correction_method": params.correction_method,
        "permutations": params.permutations,
        "keep_insignificant": params.keep_insignificant,
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    if params.source in [EnrichmentSource.INDRA_UPSTREAM, EnrichmentSource.INDRA_DOWNSTREAM]:
        query_params["min_evidence_count"] = params.min_evidence_count
        query_params["min_belief_score"] = params.min_belief_score

    enrichment_data = await adapter.query("continuous_analysis", **query_params)

    await ctx.report_progress(0.8, "Processing GSEA results...")

    # Parse results
    results = _parse_enrichment_results(enrichment_data, params.analysis_type)
    statistics = _compute_enrichment_stats(results, params, len(resolved_ranking))

    return {
        "results": [r.model_dump() for r in results],
        "statistics": statistics.model_dump(),
        "resolved_genes": len(resolved_ranking),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_signed(
    params: EnrichmentQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: signed
    Directional enrichment analysis (separate up/down regulation).
    """
    if not params.ranked_genes:
        raise ValueError("ranked_genes parameter required for signed analysis")

    await ctx.report_progress(
        0.2, f"Resolving {len(params.ranked_genes)} ranked genes..."
    )

    # Resolve gene identifiers and preserve signed scores
    resolver = get_resolver()
    resolved_ranking: Dict[str, float] = {}
    failed_genes = []

    for gene, score in params.ranked_genes.items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(
            f"No genes could be resolved. Failed: {', '.join(failed_genes)}"
        )

    # Count up/down regulated genes
    upregulated = sum(1 for score in resolved_ranking.values() if score > 0)
    downregulated = sum(1 for score in resolved_ranking.values() if score < 0)

    await ctx.report_progress(
        0.4,
        f"Running signed enrichment ({upregulated} up, {downregulated} down, {params.source.value})...",
    )

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "source": params.source.value,
        "alpha": params.alpha,
        "correction_method": params.correction_method,
        "permutations": params.permutations,
        "keep_insignificant": params.keep_insignificant,
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    if params.source in [EnrichmentSource.INDRA_UPSTREAM, EnrichmentSource.INDRA_DOWNSTREAM]:
        query_params["min_evidence_count"] = params.min_evidence_count
        query_params["min_belief_score"] = params.min_belief_score

    enrichment_data = await adapter.query("signed_analysis", **query_params)

    await ctx.report_progress(0.8, "Processing directional enrichment results...")

    # Parse results
    results = _parse_enrichment_results(enrichment_data, params.analysis_type)
    statistics = _compute_enrichment_stats(results, params, len(resolved_ranking))

    return {
        "results": [r.model_dump() for r in results],
        "statistics": statistics.model_dump(),
        "resolved_genes": len(resolved_ranking),
        "upregulated_count": upregulated,
        "downregulated_count": downregulated,
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_metabolite(
    params: EnrichmentQuery,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Mode: metabolite
    Metabolite set enrichment analysis.
    """
    if not params.gene_list:
        raise ValueError("gene_list parameter required for metabolite analysis")

    await ctx.report_progress(
        0.2, f"Validating {len(params.gene_list)} metabolite identifiers..."
    )

    # For metabolite analysis, we don't resolve through gene resolver
    # Metabolites have their own identifier format (e.g., HMDB, ChEBI)
    # Pass them directly to backend
    metabolite_ids = params.gene_list

    # Optionally resolve background metabolites
    background_metabolite_ids = params.background_genes if params.background_genes else None

    await ctx.report_progress(
        0.4, f"Running metabolite enrichment ({params.source.value})..."
    )

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "metabolite_ids": metabolite_ids,
        "source": params.source.value,
        "alpha": params.alpha,
        "correction_method": params.correction_method,
        "keep_insignificant": params.keep_insignificant,
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_metabolite_ids:
        query_params["background_metabolite_ids"] = background_metabolite_ids

    enrichment_data = await adapter.query(
        "metabolite_discrete_analysis", **query_params
    )

    await ctx.report_progress(0.8, "Processing metabolite enrichment results...")

    # Parse results
    results = _parse_enrichment_results(enrichment_data, params.analysis_type)
    statistics = _compute_enrichment_stats(results, params, len(metabolite_ids))

    return {
        "results": [r.model_dump() for r in results],
        "statistics": statistics.model_dump(),
        "total_metabolites": len(metabolite_ids),
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_enrichment_results(
    data: Dict[str, Any],
    analysis_type: EnrichmentType,
) -> List[EnrichmentResult]:
    """Parse enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse term entity
        term = EntityRef(
            name=record.get("term_name", "Unknown"),
            curie=record.get("term_id", "unknown:unknown"),
            namespace=record.get("term_namespace", "unknown"),
            identifier=record.get("term_identifier", "unknown"),
        )

        # Build result object
        result_dict = {
            "term": term,
            "term_name": record.get("term_name", "Unknown"),
            "p_value": record.get("p_value", 1.0),
            "adjusted_p_value": record.get("adjusted_p_value", 1.0),
            "gene_count": record.get("gene_count", 0),
            "term_size": record.get("term_size", 0),
            "genes": record.get("genes", []),
            "background_count": record.get("background_count"),
        }

        # Add GSEA-specific fields for continuous/signed analysis
        if analysis_type in [EnrichmentType.CONTINUOUS, EnrichmentType.SIGNED]:
            result_dict["enrichment_score"] = record.get("enrichment_score")
            result_dict["normalized_enrichment_score"] = record.get(
                "normalized_enrichment_score"
            )

        results.append(EnrichmentResult(**result_dict))

    return results


def _compute_enrichment_stats(
    results: List[EnrichmentResult],
    params: EnrichmentQuery,
    total_genes: int,
) -> EnrichmentStatistics:
    """Compute overall enrichment statistics."""
    # Count significant results
    significant_results = sum(
        1 for r in results if r.adjusted_p_value <= params.alpha
    )

    return EnrichmentStatistics(
        total_results=len(results),
        significant_results=significant_results,
        total_genes_analyzed=total_genes,
        correction_method=params.correction_method,
        alpha=params.alpha,
    )


logger.info("✓ Tool 3 (cogex_enrichment_analysis) registered")
