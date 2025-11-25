"""
Tool 4: cogex_query_drug_or_effect

Bidirectional queries between drugs and their effects/properties.

Modes:
1. drug_to_profile: Drug → comprehensive profile (targets, indications, side effects, trials, cell lines)
2. side_effect_to_drugs: Side effect → drugs causing that effect
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
    DrugEffectQuery,
    DrugQueryMode,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_drug_or_effect",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_drug_or_effect(
    params: DrugEffectQuery,
    ctx: Context,
) -> str:
    """
    Query drugs and their effects bidirectionally.

    This tool supports 2 query modes for comprehensive drug characterization
    and reverse lookup by side effects:

    **Forward Mode (drug → profile):**
    - drug_to_profile: Get comprehensive drug profile including targets,
      indications, side effects, clinical trials, and cell line sensitivities

    **Reverse Mode (effect → drugs):**
    - side_effect_to_drugs: Find drugs associated with a specific side effect

    Args:
        params (DrugEffectQuery): Query parameters including:
            - mode (DrugQueryMode): Query direction (required)
            - drug (str | tuple): Drug identifier for drug_to_profile mode
            - side_effect (str | tuple): Side effect term for side_effect_to_drugs mode
            - include_* flags: Control which features to include (drug_to_profile only)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results for reverse mode (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **drug_to_profile response:**
        {
            "drug": { "name": "Imatinib", "curie": "chembl:CHEMBL941", ... },
            "targets": [...],        # Drug targets with action types
            "indications": [...],    # Disease indications with phases
            "side_effects": [...],   # Side effects with frequencies
            "trials": [...],         # Clinical trials (optional)
            "cell_lines": [...]      # Cell line sensitivities (optional)
        }

        **side_effect_to_drugs response:**
        {
            "drugs": [...],          # List of drugs
            "pagination": { ... }    # Pagination metadata
        }

    Examples:
        - Get imatinib profile:
          mode="drug_to_profile", drug="imatinib", include_all=True

        - Find drugs causing nausea:
          mode="side_effect_to_drugs", side_effect="nausea", limit=50

        - Get targets for aspirin:
          mode="drug_to_profile", drug="aspirin", include_targets=True,
          include_indications=False, include_side_effects=False

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
        if params.mode == DrugQueryMode.DRUG_TO_PROFILE:
            result = await _drug_to_profile(params, ctx)
        elif params.mode == DrugQueryMode.SIDE_EFFECT_TO_DRUGS:
            result = await _side_effect_to_drugs(params, ctx)
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


async def _drug_to_profile(
    params: DrugEffectQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: drug_to_profile
    Get comprehensive drug profile with all requested features.
    """
    if not params.drug:
        raise ValueError("drug parameter required for drug_to_profile mode")

    await ctx.report_progress(0.2, "Resolving drug identifier...")

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(params.drug)

    await ctx.report_progress(0.3, f"Fetching profile for {drug.name}...")

    adapter = await get_adapter()
    result = {
        "drug": drug.model_dump(),
    }

    # Fetch requested features
    if params.include_targets:
        await ctx.report_progress(0.4, "Fetching drug targets...")
        target_data = await adapter.query(
            "get_targets_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["targets"] = _parse_targets(target_data)

    if params.include_indications:
        await ctx.report_progress(0.5, "Fetching disease indications...")
        indication_data = await adapter.query(
            "get_indications_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["indications"] = _parse_indications(indication_data)

    if params.include_side_effects:
        await ctx.report_progress(0.6, "Fetching side effects...")
        side_effect_data = await adapter.query(
            "get_side_effects_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["side_effects"] = _parse_side_effects(side_effect_data)

    if params.include_trials:
        await ctx.report_progress(0.7, "Fetching clinical trials...")
        trial_data = await adapter.query(
            "get_trials_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_trials(trial_data)

    if params.include_cell_lines:
        await ctx.report_progress(0.85, "Fetching cell line sensitivities...")
        cell_line_data = await adapter.query(
            "get_sensitive_cell_lines_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["cell_lines"] = _parse_cell_lines(cell_line_data)

    return result


async def _side_effect_to_drugs(
    params: DrugEffectQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: side_effect_to_drugs
    Find drugs associated with a specific side effect.
    """
    if not params.side_effect:
        raise ValueError("side_effect parameter required for side_effect_to_drugs mode")

    await ctx.report_progress(0.3, "Querying drugs for side effect...")

    # Parse side effect identifier
    # For now, accept side effect name directly
    # TODO: Implement side effect resolution
    side_effect_id = (
        params.side_effect if isinstance(params.side_effect, str) else params.side_effect[1]
    )

    adapter = await get_adapter()
    drug_data = await adapter.query(
        "get_drugs_for_side_effect",
        side_effect_id=side_effect_id,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing results...")

    # Parse drugs
    drugs = _parse_drug_list(drug_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=drugs,
        total_count=drug_data.get("total_count", len(drugs)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "drugs": drugs,
        "pagination": pagination.model_dump(),
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_targets(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug targets from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    targets = []
    for record in data["records"]:
        targets.append(
            {
                "target": {
                    "name": record.get("target", "Unknown"),
                    "curie": record.get("target_id", "unknown:unknown"),
                    "namespace": record.get("target_namespace", "hgnc"),
                    "identifier": record.get("target_id", "unknown"),
                },
                "action_type": record.get("action_type"),
                "evidence_count": record.get("evidence_count", 0),
            }
        )

    return targets


def _parse_indications(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug indications from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    indications = []
    for record in data["records"]:
        indications.append(
            {
                "disease": {
                    "name": record.get("disease", "Unknown"),
                    "curie": record.get("disease_id", "unknown:unknown"),
                    "namespace": "mondo",
                    "identifier": record.get("disease_id", "unknown"),
                },
                "indication_type": record.get("indication_type", "unknown"),
                "max_phase": record.get("max_phase"),
            }
        )

    return indications


def _parse_side_effects(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse side effects from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    side_effects = []
    for record in data["records"]:
        side_effects.append(
            {
                "effect": {
                    "name": record.get("effect", "Unknown"),
                    "curie": record.get("effect_id", "unknown:unknown"),
                    "namespace": "umls",
                    "identifier": record.get("effect_id", "unknown"),
                },
                "frequency": record.get("frequency"),
            }
        )

    return side_effects


def _parse_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trials from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append(
            {
                "nct_id": nct_id,
                "title": record.get("title", "Unknown"),
                "phase": record.get("phase"),
                "status": record.get("status", "unknown"),
                "conditions": record.get("conditions", []),
                "interventions": record.get("interventions", []),
                "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
            }
        )

    return trials


def _parse_cell_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line sensitivity data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_lines.append(
            {
                "cell_line": record.get("cell_line", "Unknown"),
                "sensitivity_score": record.get("sensitivity_score", 0.0),
            }
        )

    return cell_lines


def _parse_drug_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append(
            {
                "name": record.get("drug", "Unknown"),
                "curie": record.get("drug_id", "unknown:unknown"),
                "namespace": "chembl",
                "identifier": record.get("drug_id", "unknown"),
                "synonyms": record.get("synonyms", []),
                "drug_type": record.get("drug_type"),
            }
        )

    return drugs


logger.info("✓ Tool 4 (cogex_query_drug_or_effect) registered")
