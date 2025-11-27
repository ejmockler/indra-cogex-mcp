"""
Clinical Trials

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
    """Handle clinical trials query - Tool 8."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_drug":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for get_for_drug mode"
                )]
            result = await _get_trials_for_drug(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_trials_for_disease(args)
        elif mode == "get_by_id":
            if not args.get("trial_id"):
                return [types.TextContent(
                    type="text",
                    text="Error: trial_id parameter required for get_by_id mode"
                )]
            result = await _get_trial_by_id(args)
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


# Tool 8 Mode Handlers
async def _get_trials_for_drug(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_drug - Get clinical trials testing a specific drug."""
    drug_input = args["drug"]

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(drug_input)

    # Build query parameters
    query_params = {
        "mode": "get_for_drug",
        "drug_id": drug.curie,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if args.get("phase"):
        query_params["phase"] = args["phase"]
    if args.get("status"):
        query_params["status"] = args["status"]

    adapter = await get_adapter()
    trial_data = await adapter.query("clinical_trial_query", **query_params)

    # Extract trials from response
    trials = trial_data.get("trials", [])

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_trials", len(trials)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trials_for_disease(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_disease - Get clinical trials for a specific disease."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    # Build query parameters
    query_params = {
        "mode": "get_for_disease",
        "disease_id": disease.curie,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if args.get("phase"):
        query_params["phase"] = args["phase"]
    if args.get("status"):
        query_params["status"] = args["status"]

    adapter = await get_adapter()
    trial_data = await adapter.query("clinical_trial_query", **query_params)

    # Extract trials from response
    trials = trial_data.get("trials", [])

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_trials", len(trials)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trial_by_id(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_by_id - Get details for a specific clinical trial by NCT ID."""
    trial_id = args["trial_id"]

    adapter = await get_adapter()
    trial_data = await adapter.query(
        "clinical_trial_query",
        mode="get_by_id",
        trial_id=trial_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    if not trial_data.get("success"):
        raise ValueError(f"Trial {trial_id} not found")

    return {
        "trial_details": trial_data,
    }





# ============================================================================
