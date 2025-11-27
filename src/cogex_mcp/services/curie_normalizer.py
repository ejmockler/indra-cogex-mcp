"""CURIE normalization for GILDA results.

This module normalizes CURIEs returned by GILDA to be compatible with CoGEx.
GILDA often returns redundant namespace prefixes (e.g., namespace="CHEBI",
identifier="CHEBI:8863") which need to be normalized to CoGEx format ("chebi:8863").
"""


def normalize_curie(namespace: str, identifier: str) -> str:
    """
    Normalize GILDA CURIE to CoGEx-compatible format.

    GILDA returns CURIEs with redundant namespace prefixes:
        namespace="CHEBI", identifier="CHEBI:8863"

    CoGEx expects:
        "chebi:8863"

    This function:
    1. Converts namespace to lowercase
    2. Removes redundant namespace prefix from identifier if present
    3. Returns properly formatted CURIE

    Args:
        namespace: GILDA namespace (e.g., "CHEBI", "DOID", "MESH", "HGNC")
        identifier: GILDA identifier (e.g., "CHEBI:8863", "DOID:332", "D000690")

    Returns:
        Normalized CURIE string in format "namespace:identifier"

    Examples:
        >>> normalize_curie("CHEBI", "CHEBI:8863")
        'chebi:8863'
        >>> normalize_curie("DOID", "DOID:332")
        'doid:332'
        >>> normalize_curie("MESH", "D000690")
        'mesh:D000690'
        >>> normalize_curie("HGNC", "HGNC:5468")
        'hgnc:5468'
        >>> normalize_curie("GO", "GO:0005783")
        'go:0005783'
        >>> normalize_curie("chebi", "8863")
        'chebi:8863'
    """
    namespace_lower = namespace.lower()

    # Remove redundant namespace prefix from identifier (case-insensitive check)
    if ":" in identifier:
        prefix, id_part = identifier.split(":", 1)
        if prefix.lower() == namespace_lower:
            identifier = id_part

    return f"{namespace_lower}:{identifier}"


def normalize_gilda_results(results: list[dict]) -> list[dict]:
    """
    Normalize CURIEs in GILDA results in-place.

    Modifies the input list by normalizing the namespace and identifier fields
    in each result's "term" dictionary. This ensures all CURIEs are in CoGEx
    format before they're cached or returned to the client.

    Args:
        results: GILDA grounding results (list of dictionaries)
            Each result should have structure:
            {
                "term": {
                    "db": "CHEBI",         # namespace
                    "id": "CHEBI:8863",    # identifier
                    "text": "...",
                    ...
                },
                "score": 0.85,
                ...
            }

    Returns:
        Modified results with normalized CURIEs (same list object, modified in-place)

    Examples:
        >>> results = [
        ...     {
        ...         "term": {"db": "CHEBI", "id": "CHEBI:8863", "text": "Propranolol"},
        ...         "score": 0.95
        ...     },
        ...     {
        ...         "term": {"db": "DOID", "id": "DOID:332", "text": "ALS"},
        ...         "score": 0.88
        ...     }
        ... ]
        >>> normalized = normalize_gilda_results(results)
        >>> results[0]["term"]["db"]
        'chebi'
        >>> results[0]["term"]["id"]
        '8863'
        >>> results[1]["term"]["db"]
        'doid'
        >>> results[1]["term"]["id"]
        '332'
        >>> normalized is results  # In-place modification
        True
    """
    for result in results:
        term = result.get("term", {})
        namespace = term.get("db", "")
        identifier = term.get("id", "")

        if namespace and identifier:
            # Normalize identifier: remove redundant namespace prefix
            # Case-insensitive check for prefix
            if identifier.upper().startswith(namespace.upper() + ":"):
                term["id"] = identifier.split(":", 1)[1]

            # Ensure lowercase namespace
            term["db"] = namespace.lower()

    return results
