"""
Tool 15: cogex_analyze_kinase_enrichment

Predict upstream kinases from phosphoproteomics data.
Analyzes phosphorylation sites to identify enriched kinase activities.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context

from cogex_mcp.server import mcp
from cogex_mcp.schemas import (
    BaseToolInput,
    EntityRef,
    EnrichmentStatistics,
)
from cogex_mcp.constants import (
    STATISTICAL_ANNOTATIONS,
    ResponseFormat,
    ENRICHMENT_TIMEOUT,
    CHARACTER_LIMIT,
)
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.clients.adapter import get_adapter

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ============================================================================
# Input Schema
# ============================================================================


class KinaseEnrichmentQuery(BaseToolInput):
    """
    Input for cogex_analyze_kinase_enrichment tool.

    Analyzes phosphorylation sites to predict upstream kinases.
    """

    phosphosites: List[str] = Field(
        ...,
        description="List of phosphosites (format: 'GENE_S123', 'GENE_T456', 'GENE_Y789')",
        min_length=1,
    )

    background: Optional[List[str]] = Field(
        None,
        description="Optional background phosphosites for normalization",
    )

    # Analysis parameters
    alpha: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description="Significance threshold for enrichment",
    )

    correction_method: str = Field(
        default="fdr_bh",
        description="Multiple testing correction method (fdr_bh, bonferroni)",
    )

    @field_validator("phosphosites", "background")
    @classmethod
    def validate_phosphosite_format(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """
        Validate phosphosite format: GENE_[STY]POSITION

        Examples:
            - TP53_S15 (serine 15 on TP53)
            - MAPK1_T185 (threonine 185 on MAPK1)
            - EGFR_Y1068 (tyrosine 1068 on EGFR)
        """
        if v is None:
            return None

        # Pattern: GENE_[STY]DIGITS
        pattern = re.compile(r'^[A-Z0-9]+_[STY]\d+$', re.IGNORECASE)

        invalid_sites = []
        for site in v:
            if not pattern.match(site):
                invalid_sites.append(site)

        if invalid_sites:
            raise ValueError(
                f"Invalid phosphosite format: {', '.join(invalid_sites[:5])}. "
                f"Expected format: GENE_S123 (serine), GENE_T456 (threonine), or GENE_Y789 (tyrosine)"
            )

        return v


# ============================================================================
# Output Schemas
# ============================================================================


class KinaseEnrichmentResult(BaseModel):
    """Single kinase enrichment result."""

    kinase: EntityRef = Field(..., description="Kinase entity")
    p_value: float = Field(..., description="Raw p-value")
    adjusted_p_value: float = Field(..., description="Adjusted p-value")
    substrate_count: int = Field(
        ...,
        description="Number of input phosphosites predicted for this kinase",
    )
    total_substrates: int = Field(
        ...,
        description="Total known substrates for this kinase in database",
    )
    phosphosites: List[str] = Field(
        ...,
        description="Input phosphosites attributed to this kinase",
    )
    prediction_confidence: str = Field(
        ...,
        description="Prediction confidence: high, medium, or low",
    )


# ============================================================================
# Tool Implementation
# ============================================================================


@mcp.tool(
    name="cogex_analyze_kinase_enrichment",
    annotations=STATISTICAL_ANNOTATIONS,
)
async def cogex_analyze_kinase_enrichment(
    params: KinaseEnrichmentQuery,
    ctx: Context,
) -> str:
    """
    Predict upstream kinases from phosphoproteomics data.

    This tool analyzes phosphorylation sites to identify which kinases are likely
    responsible for the observed phosphorylation events. It performs enrichment
    analysis using kinase-substrate relationships from PhosphoSitePlus and other
    curated databases.

    **Input Format:**

    Phosphosites must be specified as: GENE_RESIDUE_POSITION
    - GENE: Gene symbol (e.g., 'TP53', 'MAPK1')
    - RESIDUE: Single letter for amino acid (S=serine, T=threonine, Y=tyrosine)
    - POSITION: Residue position number

    Examples:
    - TP53_S15 → Serine 15 on TP53
    - MAPK1_T185 → Threonine 185 on MAPK1
    - EGFR_Y1068 → Tyrosine 1068 on EGFR

    **Analysis Method:**

    The tool performs Fisher's exact test to identify kinases whose known substrates
    are significantly enriched in your phosphosite list. Results are corrected for
    multiple testing using the specified correction method.

    **Prediction Confidence:**

    - **high**: Multiple substrates detected, strong evidence in databases
    - **medium**: Moderate substrate count or evidence strength
    - **low**: Few substrates or weak database support

    **Background Set (Optional):**

    Provide a list of background phosphosites (e.g., all sites detected in your
    experiment) to normalize against detection biases. If not provided, uses the
    full database of known phosphosites as background.

    **Statistical Parameters:**

    - alpha: Significance threshold (default: 0.05)
    - correction_method: Multiple testing correction
      - 'fdr_bh': Benjamini-Hochberg FDR (recommended, default)
      - 'bonferroni': Bonferroni correction (more conservative)

    Args:
        params (KinaseEnrichmentQuery): Query parameters including:
            - phosphosites (List[str]): Phosphosites in GENE_S/T/Y###  format (required)
            - background (List[str]): Background phosphosites (optional)
            - alpha (float): Significance threshold (default: 0.05)
            - correction_method (str): Multiple testing correction (default: fdr_bh)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted enrichment results in requested format

        **JSON response:**
        ```
        {
            "results": [
                {
                    "kinase": {"name": "CDK1", "curie": "hgnc:1722", ...},
                    "p_value": 0.0001,
                    "adjusted_p_value": 0.005,
                    "substrate_count": 8,
                    "total_substrates": 45,
                    "phosphosites": ["GENE1_S10", "GENE2_T123", ...],
                    "prediction_confidence": "high"
                }
            ],
            "statistics": {
                "total_results": 250,
                "significant_results": 12,
                "total_genes_analyzed": 35,
                "correction_method": "fdr_bh",
                "alpha": 0.05
            }
        }
        ```

        **Markdown response:**
        Ranked table of enriched kinases with:
        - Kinase name and gene ID
        - P-values (raw and adjusted)
        - Substrate counts (detected / total)
        - Confidence level
        - List of phosphosites attributed to kinase

    Examples:
        - Basic kinase enrichment:
          phosphosites=["TP53_S15", "TP53_S20", "MDM2_S166"], alpha=0.05

        - With background normalization:
          phosphosites=["MAPK1_T185", "MAPK3_T202"],
          background=["GENE1_S10", "GENE2_T20", ...],
          correction_method="bonferroni"

        - High-confidence predictions only:
          phosphosites=[...], alpha=0.01, correction_method="fdr_bh"

    Use Cases:
        - "What kinases phosphorylate these sites?"
        - "Predict upstream kinases from mass spec data"
        - "Kinase enrichment analysis for phosphoproteomics"
        - "Which kinases are activated in this condition?"

    Error Handling:
        - Returns actionable error messages for invalid phosphosite format
        - Handles missing or ambiguous gene symbols
        - Gracefully manages empty result sets
        - Enforces character limit with intelligent truncation

    Notes:
        - Uses PhosphoSitePlus and other curated kinase-substrate databases
        - Results are non-deterministic due to statistical computation
        - Serine/threonine kinases and tyrosine kinases analyzed together
        - Confidence levels consider both statistics and database evidence

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        await ctx.report_progress(0.1, "Validating phosphosite formats...")

        # Validate that we have phosphosites
        if not params.phosphosites:
            return "Error: phosphosites parameter is required and cannot be empty"

        # Count unique genes in phosphosites
        unique_genes = set()
        for site in params.phosphosites:
            gene = site.split('_')[0]
            unique_genes.add(gene)

        await ctx.report_progress(
            0.2,
            f"Analyzing {len(params.phosphosites)} phosphosites from {len(unique_genes)} genes..."
        )

        # Prepare background phosphosites if provided
        background_sites = None
        if params.background:
            background_sites = params.background
            await ctx.report_progress(
                0.3,
                f"Using custom background set ({len(background_sites)} sites)..."
            )
        else:
            await ctx.report_progress(0.3, "Using default database background...")

        # Query backend
        await ctx.report_progress(0.4, "Performing kinase enrichment analysis...")

        adapter = await get_adapter()

        query_params = {
            "phosphosites": params.phosphosites,
            "alpha": params.alpha,
            "correction_method": params.correction_method,
            "timeout": ENRICHMENT_TIMEOUT,
        }

        if background_sites:
            query_params["background"] = background_sites

        enrichment_data = await adapter.query("kinase_analysis", **query_params)

        await ctx.report_progress(0.8, "Processing kinase enrichment results...")

        # Parse results
        results = _parse_kinase_results(enrichment_data)
        statistics = _compute_kinase_statistics(
            results,
            params,
            len(unique_genes)
        )

        # Build response
        response_data = {
            "results": [r.model_dump() for r in results],
            "statistics": statistics.model_dump(),
            "total_phosphosites": len(params.phosphosites),
            "unique_genes": len(unique_genes),
        }

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=response_data,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        await ctx.report_progress(1.0, "Kinase enrichment analysis complete")
        return response

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_kinase_results(
    data: Dict[str, Any],
) -> List[KinaseEnrichmentResult]:
    """Parse kinase enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse kinase entity
        kinase = EntityRef(
            name=record.get("kinase_name", "Unknown"),
            curie=record.get("kinase_id", "unknown:unknown"),
            namespace=record.get("kinase_namespace", "hgnc"),
            identifier=record.get("kinase_identifier", "unknown"),
        )

        # Determine confidence level based on substrate count and evidence
        substrate_count = record.get("substrate_count", 0)
        total_substrates = record.get("total_substrates", 0)
        p_value = record.get("adjusted_p_value", 1.0)

        # Confidence heuristics:
        # - high: 5+ substrates, p < 0.01, or >20% of known substrates
        # - medium: 3-4 substrates, p < 0.05
        # - low: 1-2 substrates
        if substrate_count >= 5 or p_value < 0.01 or (
            total_substrates > 0 and substrate_count / total_substrates > 0.2
        ):
            confidence = "high"
        elif substrate_count >= 3 and p_value < 0.05:
            confidence = "medium"
        else:
            confidence = "low"

        result = KinaseEnrichmentResult(
            kinase=kinase,
            p_value=record.get("p_value", 1.0),
            adjusted_p_value=record.get("adjusted_p_value", 1.0),
            substrate_count=substrate_count,
            total_substrates=total_substrates,
            phosphosites=record.get("phosphosites", []),
            prediction_confidence=record.get("confidence", confidence),
        )

        results.append(result)

    # Sort by adjusted p-value (most significant first)
    results.sort(key=lambda x: x.adjusted_p_value)

    return results


def _compute_kinase_statistics(
    results: List[KinaseEnrichmentResult],
    params: KinaseEnrichmentQuery,
    total_genes: int,
) -> EnrichmentStatistics:
    """Compute overall kinase enrichment statistics."""
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


logger.info("✓ Tool 15 (cogex_analyze_kinase_enrichment) registered")
