"""
Tool 5: cogex_query_disease_or_phenotype

Bidirectional queries between diseases and phenotypes/mechanisms.

Modes:
1. disease_to_mechanisms: Disease → genes, variants, phenotypes, drugs, trials
2. phenotype_to_diseases: Phenotype → associated diseases
3. check_phenotype: Boolean check if disease has specific phenotype
"""

import logging
from typing import Any

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    DiseaseNode,
    DiseasePhenotypeQuery,
    DiseaseQueryMode,
)
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination

logger = logging.getLogger(__name__)

async def cogex_query_disease_or_phenotype(
    params: DiseasePhenotypeQuery) -> str:
    """
    Query diseases, phenotypes, and their mechanisms bidirectionally.

    This tool supports 3 query modes for comprehensive disease-phenotype exploration:

    **Mode 1: disease_to_mechanisms**
    Get comprehensive disease profile including:
    - Associated genes (gene-disease associations with scores)
    - Genetic variants (GWAS hits, disease-associated variants)
    - Phenotypes (clinical manifestations)
    - Drug therapies (approved and investigational)
    - Clinical trials (active and completed trials)

    **Mode 2: phenotype_to_diseases**
    Find diseases associated with a specific phenotype.
    Useful for differential diagnosis and phenotype-based discovery.

    **Mode 3: check_phenotype**
    Boolean check: Does a specific disease exhibit a specific phenotype?
    Quick validation for disease-phenotype relationships.

    Args:
        params (DiseasePhenotypeQuery): Query parameters including:
            - mode (DiseaseQueryMode): Query mode (required)
            - disease (str | tuple): Disease identifier for disease_to_mechanisms or check_phenotype
            - phenotype (str | tuple): Phenotype identifier for phenotype_to_diseases or check_phenotype
            - include_* flags: Control which features to include (disease_to_mechanisms only)
            - response_format (ResponseFormat): 'markdown' or 'json'
            - limit (int): Maximum results for phenotype_to_diseases (1-100, default 20)
            - offset (int): Pagination offset (default 0)

    Returns:
        str: Formatted response in requested format (JSON or Markdown)

        **disease_to_mechanisms response:**
        {
            "disease": { "name": "diabetes mellitus", "curie": "mondo:MONDO:0005015", ... },
            "genes": [...],         # Gene associations with scores
            "variants": [...],      # GWAS and disease variants
            "phenotypes": [...],    # Clinical phenotypes
            "drugs": [...],         # Drug therapies
            "trials": [...]         # Clinical trials
        }

        **phenotype_to_diseases response:**
        {
            "diseases": [...],      # List of associated diseases
            "pagination": { ... }   # Pagination metadata
        }

        **check_phenotype response:**
        {
            "has_phenotype": true,
            "disease": { ... },
            "phenotype": { ... }
        }

    Examples:
        - Get diabetes profile:
          mode="disease_to_mechanisms", disease="diabetes mellitus"

        - Find diseases with seizures:
          mode="phenotype_to_diseases", phenotype="HP:0001250"

        - Check if Alzheimer's has memory impairment:
          mode="check_phenotype", disease="Alzheimer disease", phenotype="memory impairment"

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
        if params.mode == DiseaseQueryMode.DISEASE_TO_MECHANISMS:
            result = await _disease_to_mechanisms(params)
        elif params.mode == DiseaseQueryMode.PHENOTYPE_TO_DISEASES:
            result = await _phenotype_to_diseases(params)
        elif params.mode == DiseaseQueryMode.CHECK_PHENOTYPE:
            result = await _check_phenotype(params)
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

async def _disease_to_mechanisms(
    params: DiseasePhenotypeQuery) -> dict[str, Any]:
    """
    Mode: disease_to_mechanisms
    Get comprehensive disease profile with all molecular mechanisms.
    """
    if not params.disease:
        raise ValueError("disease parameter required for disease_to_mechanisms mode")
    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(params.disease)

    # Convert EntityRef to DiseaseNode
    disease = DiseaseNode(
        name=disease_ref.name,
        curie=disease_ref.curie,
        namespace=disease_ref.namespace,
        identifier=disease_ref.identifier,
    )
    adapter = await get_adapter()
    result = {
        "disease": disease.model_dump(),
    }

    # Fetch requested features
    if params.include_genes:
        gene_data = await adapter.query(
            "get_genes_for_disease",
            disease_id=disease.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["genes"] = _parse_gene_associations(gene_data)

    if params.include_variants:
        variant_data = await adapter.query(
            "get_variants_for_disease",
            disease_id=disease.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["variants"] = _parse_variant_associations(variant_data)

    if params.include_phenotypes:
        phenotype_data = await adapter.query(
            "get_phenotypes_for_disease",
            disease_id=disease.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["phenotypes"] = _parse_phenotype_associations(phenotype_data)

    if params.include_drugs:
        drug_data = await adapter.query(
            "get_drugs_for_indication",
            disease_id=disease.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["drugs"] = _parse_drug_therapies(drug_data)

    if params.include_trials:
        trial_data = await adapter.query(
            "get_trials_for_disease",
            disease_id=disease.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_clinical_trials(trial_data)

    return result

async def _phenotype_to_diseases(
    params: DiseasePhenotypeQuery) -> dict[str, Any]:
    """
    Mode: phenotype_to_diseases
    Find diseases associated with a specific phenotype.
    """
    if not params.phenotype:
        raise ValueError("phenotype parameter required for phenotype_to_diseases mode")
    # Parse phenotype identifier
    phenotype_id = params.phenotype if isinstance(params.phenotype, str) else params.phenotype[1]

    adapter = await get_adapter()
    disease_data = await adapter.query(
        "get_diseases_for_phenotype",
        phenotype_id=phenotype_id,
        limit=params.limit,
        offset=params.offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )
    # Parse diseases
    diseases = _parse_disease_list(disease_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=diseases,
        total_count=disease_data.get("total_count", len(diseases)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "diseases": diseases,
        "pagination": pagination.model_dump(),
    }

async def _check_phenotype(
    params: DiseasePhenotypeQuery) -> dict[str, Any]:
    """
    Mode: check_phenotype
    Boolean check: Does disease have specific phenotype?
    """
    if not params.disease:
        raise ValueError("disease parameter required for check_phenotype mode")
    if not params.phenotype:
        raise ValueError("phenotype parameter required for check_phenotype mode")
    # Resolve identifiers
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(params.disease)

    # Parse phenotype identifier
    phenotype_id = params.phenotype if isinstance(params.phenotype, str) else params.phenotype[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease_ref.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )
    # Parse result
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
            "namespace": phenotype_id.split(":")[0] if ":" in phenotype_id else "unknown",
            "identifier": phenotype_id.split(":")[1] if ":" in phenotype_id else phenotype_id,
        },
    }

# ============================================================================
# Data Parsing Helpers
# ============================================================================

def _parse_gene_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    associations = []
    for record in data["records"]:
        associations.append(
            {
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "score": record.get("score", 0.0),
                "evidence_count": record.get("evidence_count", 0),
                "sources": record.get("sources", []),
            }
        )

    return associations

def _parse_variant_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse variant-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variants.append(
            {
                "variant": record.get("rsid", "unknown"),
                "gene": {
                    "name": record.get("gene", "Unknown"),
                    "curie": record.get("gene_id", "unknown:unknown"),
                    "namespace": "hgnc",
                    "identifier": record.get("gene_id", "unknown"),
                },
                "p_value": record.get("p_value"),
                "odds_ratio": record.get("odds_ratio"),
                "trait": record.get("trait"),
            }
        )

    return variants

def _parse_phenotype_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease-phenotype associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append(
            {
                "phenotype": {
                    "name": record.get("phenotype", "Unknown"),
                    "curie": record.get("phenotype_id", "unknown:unknown"),
                    "namespace": "hp",  # Human Phenotype Ontology
                    "identifier": record.get("phenotype_id", "unknown"),
                },
                "frequency": record.get("frequency"),
                "evidence_count": record.get("evidence_count", 0),
            }
        )

    return phenotypes

def _parse_drug_therapies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug therapy data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append(
            {
                "drug": {
                    "name": record.get("drug", "Unknown"),
                    "curie": record.get("drug_id", "unknown:unknown"),
                    "namespace": "chembl",
                    "identifier": record.get("drug_id", "unknown"),
                },
                "indication_type": record.get("indication_type", "unknown"),
                "max_phase": record.get("max_phase"),
                "status": record.get("status"),
            }
        )

    return drugs

def _parse_clinical_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trial data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append(
            {
                "nct_id": nct_id,
                "title": record.get("title", "Unknown Trial"),
                "phase": record.get("phase"),
                "status": record.get("status", "unknown"),
                "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
            }
        )

    return trials

def _parse_disease_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append(
            {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
                "namespace": "mondo",
                "identifier": record.get("disease_id", "unknown"),
                "description": record.get("description"),
            }
        )

    return diseases

logger.info("✓ Tool 5 (cogex_query_disease_or_phenotype) registered")
