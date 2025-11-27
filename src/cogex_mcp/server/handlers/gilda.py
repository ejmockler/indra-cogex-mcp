"""
GILDA Biomedical Entity Grounding Handler

This handler implements the ground_biomedical_term() MCP tool for converting
natural language biomedical terms into standardized CURIEs.

Workflow:
1. User provides natural language term (e.g., "diabetes", "ALS", "TP53")
2. GILDA API grounds term to biomedical ontology identifiers
3. CURIEs are normalized to CoGEx format (lowercase namespace, no redundant prefixes)
4. Results returned with disambiguation suggestions for LLM

Design: LLM Disambiguation Pattern (not auto-selection)
- Multiple matches → LLM uses conversation context to pick correct one
- Single strong match → Recommended directly
- No matches → Helpful error message with alternatives
"""

import logging
from typing import Any, Dict, List

import mcp.types as types

from cogex_mcp.clients.gilda_client import GildaClient

logger = logging.getLogger(__name__)


async def handle(arguments: Dict[str, Any]) -> List[types.TextContent]:
    """
    Ground biomedical term to standardized CURIE using GILDA.

    Args:
        arguments: Tool parameters
            - term (str): Natural language biomedical term (REQUIRED)
            - limit (int): Maximum number of matches to return (default: 5)
            - context (str): Optional conversation context for disambiguation

    Returns:
        List of TextContent with grounding results in JSON format

    Response Format:
        {
            "term": "original search term",
            "matches": [
                {
                    "curie": "mesh:D003920",
                    "namespace": "mesh",
                    "identifier": "D003920",
                    "name": "Diabetes Mellitus",
                    "score": 0.778,
                    "entry_name": "Full database entry name"
                },
                ...
            ],
            "suggestion": "Human-readable guidance for LLM",
            "disambiguation_needed": true/false
        }
    """
    # Extract parameters
    term = arguments.get("term")
    limit = arguments.get("limit", 5)
    context = arguments.get("context", "")

    # Validate required parameters
    if not term:
        error_msg = "Missing required parameter: 'term'"
        logger.error(error_msg)
        return [types.TextContent(type="text", text=f"Error: {error_msg}")]

    logger.info(f"Grounding biomedical term: '{term}' (limit={limit})")

    try:
        # Ground term using GILDA client
        async with GildaClient() as client:
            results = await client.ground(text=term)  # GILDA API uses 'text' parameter

        # Limit results
        results = results[:limit]

        # Build response (handles empty results gracefully)
        response = _build_response(term=term, results=results, context=context)

        # Format as JSON
        import json

        response_json = json.dumps(response, indent=2)

        # Log results (check if empty first)
        if results:
            logger.info(
                f"Grounded '{term}' → {len(results)} matches "
                f"(top: {results[0]['term']['db']}:{results[0]['term']['id']})"
            )
        else:
            logger.info(f"Grounded '{term}' → no matches")

        return [types.TextContent(type="text", text=response_json)]

    except Exception as e:
        # Always return valid JSON, even on error
        import json

        error_msg = f"GILDA grounding error for '{term}': {str(e)}"
        logger.error(error_msg, exc_info=True)

        error_response = {
            "term": term,
            "matches": [],
            "suggestion": f"Error: {str(e)}. Please try alternative terms or check your connection.",
            "disambiguation_needed": False
        }

        return [types.TextContent(type="text", text=json.dumps(error_response, indent=2))]


def _build_response(
    term: str, results: List[Dict[str, Any]], context: str = ""
) -> Dict[str, Any]:
    """
    Build structured response from GILDA results.

    Args:
        term: Original search term
        results: GILDA API results (already normalized by GildaClient)
        context: Optional conversation context

    Returns:
        Structured response dictionary
    """
    # Transform GILDA results into clean match format
    matches = []
    for result in results:
        term_data = result.get("term", {})
        namespace = term_data.get("db", "")
        identifier = term_data.get("id", "")

        matches.append(
            {
                "curie": f"{namespace}:{identifier}",
                "namespace": namespace,
                "identifier": identifier,
                "name": term_data.get("text", ""),
                "score": result.get("score", 0.0),
                "entry_name": term_data.get("entry_name", ""),
            }
        )

    # Generate suggestion for LLM
    suggestion = _generate_suggestion(term=term, matches=matches)

    # Determine if disambiguation needed
    disambiguation_needed = _needs_disambiguation(matches)

    return {
        "term": term,
        "matches": matches,
        "suggestion": suggestion,
        "disambiguation_needed": disambiguation_needed,
    }


def _generate_suggestion(term: str, matches: List[Dict[str, Any]]) -> str:
    """
    Generate human-readable suggestion for LLM.

    Args:
        term: Original search term
        matches: List of grounding matches

    Returns:
        Suggestion text
    """
    if not matches:
        return (
            f"No matches found for '{term}'. "
            "Try alternative spellings, synonyms, or more specific terms. "
            "For diseases, try full disease names (e.g., 'diabetes mellitus' instead of 'diabetes'). "
            "For genes, try official gene symbols (e.g., 'TP53' instead of 'p53')."
        )

    if len(matches) == 1:
        match = matches[0]
        entity_type = _infer_entity_type(match["namespace"])
        return (
            f"Strong match found: {match['name']} ({match['curie']}, score={match['score']:.3f}). "
            f"This is a {entity_type}. "
            f"Recommended next step: Use {_suggest_tool(match['namespace'])} with CURIE '{match['curie']}'."
        )

    # Multiple matches - need disambiguation
    top_match = matches[0]
    second_match = matches[1]
    score_diff = top_match["score"] - second_match["score"]

    if score_diff > 0.3:
        # Clear winner
        entity_type = _infer_entity_type(top_match["namespace"])
        return (
            f"Top match: {top_match['name']} ({top_match['curie']}, score={top_match['score']:.3f}). "
            f"This is a {entity_type}. "
            f"Other matches have significantly lower scores. "
            f"Recommended: Use {_suggest_tool(top_match['namespace'])} with CURIE '{top_match['curie']}'."
        )

    # Ambiguous - need LLM disambiguation
    namespaces = {m["namespace"] for m in matches}
    entity_types = [_infer_entity_type(ns) for ns in namespaces]

    return (
        f"Multiple matches found for '{term}' across {len(namespaces)} namespaces: {', '.join(sorted(namespaces))}. "
        f"Entity types: {', '.join(set(entity_types))}. "
        f"Top matches: {matches[0]['name']} ({matches[0]['curie']}, score={matches[0]['score']:.3f}), "
        f"{matches[1]['name']} ({matches[1]['curie']}, score={matches[1]['score']:.3f}). "
        "Please clarify which entity the user is asking about based on conversation context, "
        "then use the appropriate CURIE."
    )


def _needs_disambiguation(matches: List[Dict[str, Any]]) -> bool:
    """
    Determine if matches require LLM disambiguation.

    Args:
        matches: List of grounding matches

    Returns:
        True if disambiguation needed, False otherwise
    """
    if len(matches) <= 1:
        return False

    # Check if scores are similar (within 0.2)
    top_score = matches[0]["score"]
    second_score = matches[1]["score"]

    return abs(top_score - second_score) < 0.2


def _infer_entity_type(namespace: str) -> str:
    """
    Infer entity type from namespace.

    Args:
        namespace: Ontology namespace (e.g., 'mesh', 'hgnc', 'chebi')

    Returns:
        Human-readable entity type
    """
    disease_namespaces = ["mesh", "doid", "mondo", "hp"]
    gene_namespaces = ["hgnc", "uniprot", "ensembl"]
    drug_namespaces = ["chebi", "chembl", "drugbank", "pubchem"]
    pathway_namespaces = ["reactome", "wikipathways", "go"]

    if namespace in disease_namespaces:
        return "disease/phenotype"
    elif namespace in gene_namespaces:
        return "gene"
    elif namespace in drug_namespaces:
        return "drug/chemical"
    elif namespace in pathway_namespaces:
        return "pathway/process"
    else:
        return f"{namespace} entity"


def _suggest_tool(namespace: str) -> str:
    """
    Suggest appropriate CoGEx tool for namespace.

    Args:
        namespace: Ontology namespace

    Returns:
        Recommended tool name
    """
    disease_namespaces = ["mesh", "doid", "mondo", "hp"]
    gene_namespaces = ["hgnc", "uniprot", "ensembl"]
    drug_namespaces = ["chebi", "chembl", "drugbank", "pubchem"]
    pathway_namespaces = ["reactome", "wikipathways", "go"]

    if namespace in disease_namespaces:
        return "query_disease_or_phenotype"
    elif namespace in gene_namespaces:
        return "query_gene_or_feature"
    elif namespace in drug_namespaces:
        return "query_drug_or_effect"
    elif namespace in pathway_namespaces:
        return "query_pathway"
    else:
        return "appropriate CoGEx tool"
