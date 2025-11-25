"""
Tool 8: cogex_query_clinical_trials

Query ClinicalTrials.gov data for drugs and diseases.

Modes:
1. get_for_drug: Drug → clinical trials testing that drug
2. get_for_disease: Disease → clinical trials for that disease
3. get_by_id: NCT ID → single trial details
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
    ClinicalTrialsMode,
    ClinicalTrialsQuery,
)
from cogex_mcp.server import mcp
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)


@mcp.tool(
    name="cogex_query_clinical_trials",
    annotations=READONLY_ANNOTATIONS,
)
async def cogex_query_clinical_trials(
    params: ClinicalTrialsQuery,
    ctx: Context,
) -> str:
    """
    Query ClinicalTrials.gov data for drugs and diseases.

    This tool provides 3 query modes for accessing clinical trial information
    from ClinicalTrials.gov via the CoGEx knowledge graph:

    **Query Modes:**
    - get_for_drug: Drug → clinical trials testing that drug
    - get_for_disease: Disease → clinical trials for that condition
    - get_by_id: Retrieve trial details by NCT ID

    **Filters:**
    - phase: Filter by trial phase (1, 2, 3, 4)
    - status: Filter by recruitment status (recruiting, completed, terminated, etc.)

    Args:
        params (ClinicalTrialsQuery): Query parameters including:
            - mode (ClinicalTrialsMode): Query mode (required)
            - drug (str | tuple): Drug identifier for get_for_drug mode
            - disease (str | tuple): Disease identifier for get_for_disease mode
            - trial_id (str): NCT ID for get_by_id mode (e.g., 'NCT12345678')
            - phase (List[int]): Filter by phase (optional)
            - status (str): Filter by status (optional)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **get_for_drug / get_for_disease response:**
        {
            "trials": [
                {
                    "nct_id": "NCT12345678",
                    "title": "Trial Title",
                    "phase": 3,
                    "status": "recruiting",
                    "conditions": ["Disease A", "Disease B"],
                    "interventions": ["Drug X", "Placebo"],
                    "url": "https://clinicaltrials.gov/ct2/show/NCT12345678"
                },
                ...
            ],
            "pagination": { ... }
        }

        **get_by_id response:**
        {
            "trial": {
                "nct_id": "NCT12345678",
                "title": "...",
                "phase": 3,
                "status": "recruiting",
                "conditions": [...],
                "interventions": [...],
                "start_date": "2020-01-15",
                "completion_date": "2024-12-31",
                "enrollment": 500,
                "sponsor": "Company Name",
                "url": "..."
            }
        }

    Examples:
        - Find trials for pembrolizumab:
          mode="get_for_drug", drug="pembrolizumab", phase=[3, 4]

        - Find recruiting Alzheimer's trials:
          mode="get_for_disease", disease="Alzheimer's disease", status="recruiting"

        - Get trial details:
          mode="get_by_id", trial_id="NCT12345678"

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
        if params.mode == ClinicalTrialsMode.GET_FOR_DRUG:
            result = await _get_trials_for_drug(params, ctx)
        elif params.mode == ClinicalTrialsMode.GET_FOR_DISEASE:
            result = await _get_trials_for_disease(params, ctx)
        elif params.mode == ClinicalTrialsMode.GET_BY_ID:
            result = await _get_trial_by_id(params, ctx)
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


async def _get_trials_for_drug(
    params: ClinicalTrialsQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_for_drug
    Get clinical trials testing a specific drug.
    """
    if not params.drug:
        raise ValueError("drug parameter required for get_for_drug mode")

    await ctx.report_progress(0.2, "Resolving drug identifier...")

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(params.drug)

    await ctx.report_progress(0.3, f"Querying trials for {drug.name}...")

    # Build query parameters
    query_params = {
        "drug_id": drug.curie,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.phase:
        query_params["phase"] = params.phase
    if params.status:
        query_params["status"] = params.status

    adapter = await get_adapter()
    trial_data = await adapter.query("get_trials_for_drug", **query_params)

    await ctx.report_progress(0.7, "Processing results...")

    # Parse trials
    trials = _parse_trial_list(trial_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_count", len(trials)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trials_for_disease(
    params: ClinicalTrialsQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_for_disease
    Get clinical trials for a specific disease.
    """
    if not params.disease:
        raise ValueError("disease parameter required for get_for_disease mode")

    await ctx.report_progress(0.2, "Resolving disease identifier...")

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(params.disease)

    await ctx.report_progress(0.3, f"Querying trials for {disease.name}...")

    # Build query parameters
    query_params = {
        "disease_id": disease.curie,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.phase:
        query_params["phase"] = params.phase
    if params.status:
        query_params["status"] = params.status

    adapter = await get_adapter()
    trial_data = await adapter.query("get_trials_for_disease", **query_params)

    await ctx.report_progress(0.7, "Processing results...")

    # Parse trials
    trials = _parse_trial_list(trial_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_count", len(trials)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trial_by_id(
    params: ClinicalTrialsQuery,
    ctx: Context,
) -> dict[str, Any]:
    """
    Mode: get_by_id
    Get details for a specific clinical trial by NCT ID.
    """
    if not params.trial_id:
        raise ValueError("trial_id parameter required for get_by_id mode")

    await ctx.report_progress(0.3, f"Fetching trial {params.trial_id}...")

    adapter = await get_adapter()
    trial_data = await adapter.query(
        "get_trial_by_id",
        nct_id=params.trial_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    await ctx.report_progress(0.7, "Processing trial data...")

    if not trial_data.get("success"):
        raise ValueError(f"Trial {params.trial_id} not found")

    # Parse single trial
    trial = _parse_trial(trial_data.get("record", {}))

    return {
        "trial": trial,
    }


# ============================================================================
# Data Parsing Helpers
# ============================================================================


def _parse_trial_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse list of clinical trials from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        trials.append(_parse_trial(record))

    return trials


def _parse_trial(record: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a single clinical trial record.

    Converts backend trial data to ClinicalTrial schema format.
    """
    nct_id = record.get("nct_id", "unknown")

    # Build ClinicalTrials.gov URL
    url = f"https://clinicaltrials.gov/ct2/show/{nct_id}"

    trial = {
        "nct_id": nct_id,
        "title": record.get("title", "Unknown"),
        "phase": record.get("phase"),
        "status": record.get("status", "unknown"),
        "conditions": record.get("conditions", []),
        "interventions": record.get("interventions", []),
        "url": url,
    }

    # Add optional fields if available
    if "start_date" in record:
        trial["start_date"] = record["start_date"]
    if "completion_date" in record:
        trial["completion_date"] = record["completion_date"]
    if "enrollment" in record:
        trial["enrollment"] = record["enrollment"]
    if "sponsor" in record:
        trial["sponsor"] = record["sponsor"]

    return trial


logger.info("✓ Tool 8 (cogex_query_clinical_trials) registered")
