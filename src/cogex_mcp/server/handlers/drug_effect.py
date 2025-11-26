"""
Drug Effect

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
    """Handle drug/effect query - Tool 5."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "drug_to_profile":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for drug_to_profile mode"
                )]
            result = await _drug_to_profile(args)
        elif mode == "side_effect_to_drugs":
            if not args.get("side_effect"):
                return [types.TextContent(
                    type="text",
                    text="Error: side_effect parameter required for side_effect_to_drugs mode"
                )]
            result = await _side_effect_to_drugs(args)
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


# Tool 5 Mode Handlers
async def _drug_to_profile(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: drug_to_profile - Get comprehensive drug profile with all requested features."""
    drug_input = args["drug"]

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(drug_input)

    adapter = await get_adapter()
    result = {
        "drug": {
            "name": drug.name,
            "curie": drug.curie,
            "namespace": drug.namespace,
            "identifier": drug.identifier,
        }
    }

    # Fetch requested features
    if args.get("include_targets", True):
        target_data = await adapter.query(
            "get_targets_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["targets"] = _parse_drug_targets(target_data)

    if args.get("include_indications", True):
        indication_data = await adapter.query(
            "get_indications_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["indications"] = _parse_drug_indications(indication_data)

    if args.get("include_side_effects", True):
        side_effect_data = await adapter.query(
            "get_side_effects_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["side_effects"] = _parse_drug_side_effects(side_effect_data)

    if args.get("include_trials", False):
        trial_data = await adapter.query(
            "get_trials_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_drug_trials(trial_data)

    if args.get("include_cell_lines", False):
        cell_line_data = await adapter.query(
            "get_sensitive_cell_lines_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["cell_lines"] = _parse_drug_cell_lines(cell_line_data)

    return result


async def _side_effect_to_drugs(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: side_effect_to_drugs - Find drugs associated with a specific side effect."""
    side_effect_input = args["side_effect"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Parse side effect identifier
    # For now, accept side effect name directly
    side_effect_id = side_effect_input if isinstance(side_effect_input, str) else side_effect_input[1]

    adapter = await get_adapter()
    drug_data = await adapter.query(
        "get_drugs_for_side_effect",
        side_effect_id=side_effect_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse drugs
    drugs = _parse_drug_list_for_side_effect(drug_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=drugs,
        total_count=drug_data.get("total_count", len(drugs)),
        offset=offset,
        limit=limit,
    )

    return {
        "drugs": drugs,
        "pagination": pagination.model_dump(),
    }


# Data parsing helpers for Tool 5
def _parse_drug_targets(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug targets from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    targets = []
    for record in data["records"]:
        targets.append({
            "target": {
                "name": record.get("target", "Unknown"),
                "curie": record.get("target_id", "unknown:unknown"),
                "namespace": record.get("target_namespace", "hgnc"),
                "identifier": record.get("target_id", "unknown"),
            },
            "action_type": record.get("action_type"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return targets


def _parse_drug_indications(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug indications from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    indications = []
    for record in data["records"]:
        indications.append({
            "disease": {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
                "namespace": "mondo",
                "identifier": record.get("disease_id", "unknown"),
            },
            "indication_type": record.get("indication_type", "unknown"),
            "max_phase": record.get("max_phase"),
        })

    return indications


def _parse_drug_side_effects(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse side effects from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    side_effects = []
    for record in data["records"]:
        side_effects.append({
            "effect": {
                "name": record.get("effect", "Unknown"),
                "curie": record.get("effect_id", "unknown:unknown"),
                "namespace": "umls",
                "identifier": record.get("effect_id", "unknown"),
            },
            "frequency": record.get("frequency"),
        })

    return side_effects


def _parse_drug_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trials from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append({
            "nct_id": nct_id,
            "title": record.get("title", "Unknown"),
            "phase": record.get("phase"),
            "status": record.get("status", "unknown"),
            "conditions": record.get("conditions", []),
            "interventions": record.get("interventions", []),
            "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
        })

    return trials


def _parse_drug_cell_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line sensitivity data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_lines.append({
            "cell_line": record.get("cell_line", "Unknown"),
            "sensitivity_score": record.get("sensitivity_score", 0.0),
        })

    return cell_lines


def _parse_drug_list_for_side_effect(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append({
            "name": record.get("drug", "Unknown"),
            "curie": record.get("drug_id", "unknown:unknown"),
            "namespace": "chembl",
            "identifier": record.get("drug_id", "unknown"),
            "synonyms": record.get("synonyms", []),
            "drug_type": record.get("drug_type"),
        })

    return drugs


async def _handle_pathway_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle pathway query - Tool 6."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_genes":
            if not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: pathway parameter required for get_genes mode"
                )]
            result = await _get_genes_in_pathway(args)
        elif mode == "get_pathways":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_pathways mode"
                )]
            result = await _get_pathways_for_gene(args)
        elif mode == "find_shared":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: genes parameter required with at least 2 genes for find_shared mode"
                )]
            result = await _find_shared_pathways(args)
        elif mode == "check_membership":
            if not args.get("gene") or not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: both gene and pathway parameters required for check_membership mode"
                )]
            result = await _check_pathway_membership(args)
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


