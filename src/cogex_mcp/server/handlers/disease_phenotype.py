"""
Tool 1: Disease/Phenotype Query Handler

Handles disease/phenotype queries and their bidirectional relationships.

Modes:
- disease_to_mechanisms: Get comprehensive disease profile
- phenotype_to_diseases: Find diseases with a phenotype
- check_phenotype: Boolean check for disease-phenotype association
"""

import logging
from typing import Any

import mcp.types as types

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.services.entity_resolver import get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.constants import CHARACTER_LIMIT, STANDARD_QUERY_TIMEOUT

logger = logging.getLogger(__name__)


async def handle(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle disease/phenotype query."""
    mode = args.get("mode")
    disease = args.get("disease")
    phenotype = args.get("phenotype")
    response_format = args.get("response_format", "markdown")

    # Route to appropriate handler based on mode
    if mode == "disease_to_mechanisms":
        if not disease:
            return [types.TextContent(
                type="text",
                text="Error: disease parameter required for disease_to_mechanisms mode"
            )]
        result = await _disease_to_mechanisms(args)
    elif mode == "phenotype_to_diseases":
        if not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: phenotype parameter required for phenotype_to_diseases mode"
            )]
        result = await _phenotype_to_diseases(args)
    elif mode == "check_phenotype":
        if not disease or not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: both disease and phenotype parameters required for check_phenotype mode"
            )]
        result = await _check_phenotype(args)
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


async def _disease_to_mechanisms(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive disease profile with all molecular mechanisms."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    result = {
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        }
    }

    adapter = await get_adapter()

    # Fetch requested features
    if args.get("include_genes", True):
        gene_data = await adapter.query(
            "get_genes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["genes"] = _parse_gene_associations(gene_data)

    if args.get("include_variants", True):
        variant_data = await adapter.query(
            "get_variants_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["variants"] = _parse_variant_associations(variant_data)

    if args.get("include_phenotypes", True):
        phenotype_data = await adapter.query(
            "get_phenotypes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["phenotypes"] = _parse_phenotype_associations(phenotype_data)

    if args.get("include_drugs", True):
        drug_data = await adapter.query(
            "get_drugs_for_indication",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["drugs"] = _parse_drug_therapies(drug_data)

    if args.get("include_trials", True):
        trial_data = await adapter.query(
            "get_trials_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_clinical_trials(trial_data)

    return result


async def _phenotype_to_diseases(args: dict[str, Any]) -> dict[str, Any]:
    """Find diseases associated with a specific phenotype."""
    phenotype_id = args["phenotype"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    disease_data = await adapter.query(
        "get_diseases_for_phenotype",
        phenotype_id=phenotype_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    diseases = _parse_disease_list(disease_data)

    return {
        "diseases": diseases,
        "pagination": {
            "total_count": disease_data.get("total_count", len(diseases)),
            "count": len(diseases),
            "offset": offset,
            "limit": limit,
            "has_more": disease_data.get("total_count", len(diseases)) > offset + len(diseases),
        },
    }


async def _check_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Boolean check: Does disease have specific phenotype?"""
    disease_input = args["disease"]
    phenotype_id = args["phenotype"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease_ref.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_phenotype = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_phenotype": has_phenotype,
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        },
        "phenotype": {
            "name": phenotype_id,
            "curie": phenotype_id if ":" in phenotype_id else f"unknown:{phenotype_id}",
        },
    }


# Data parsing helpers
def _parse_gene_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    associations = []
    for record in data["records"]:
        associations.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
            "sources": record.get("sources", []),
        })

    return associations


def _parse_variant_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse variant-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variants.append({
            "variant": record.get("rsid", "unknown"),
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "p_value": record.get("p_value"),
            "odds_ratio": record.get("odds_ratio"),
            "trait": record.get("trait"),
        })

    return variants


def _parse_phenotype_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease-phenotype associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append({
            "phenotype": {
                "name": record.get("phenotype", "Unknown"),
                "curie": record.get("phenotype_id", "unknown:unknown"),
            },
            "frequency": record.get("frequency"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return phenotypes


def _parse_drug_therapies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug therapy data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append({
            "drug": {
                "name": record.get("drug", "Unknown"),
                "curie": record.get("drug_id", "unknown:unknown"),
            },
            "indication_type": record.get("indication_type", "unknown"),
            "max_phase": record.get("max_phase"),
            "status": record.get("status"),
        })

    return drugs


def _parse_clinical_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trial data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append({
            "nct_id": nct_id,
            "title": record.get("title", "Unknown Trial"),
            "phase": record.get("phase"),
            "status": record.get("status", "unknown"),
            "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
        })

    return trials


def _parse_disease_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "name": record.get("disease", "Unknown"),
            "curie": record.get("disease_id", "unknown:unknown"),
            "description": record.get("description"),
        })

    return diseases
