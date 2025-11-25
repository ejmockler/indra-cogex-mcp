"""
Constants used throughout the application.

Includes character limits, timeouts, and standard values.
"""

from enum import Enum

# ============================================================================
# MCP Protocol Constants
# ============================================================================

CHARACTER_LIMIT = 25000  # Maximum response size
TRUNCATION_MESSAGE = (
    "\n\n⚠️ Response truncated to stay within {limit:,} character limit. "
    "Use pagination (limit/offset) or filters to refine results."
)

# ============================================================================
# Response Format
# ============================================================================


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"  # Human-readable formatted text
    JSON = "json"  # Machine-readable structured data


# ============================================================================
# Standard Annotations
# ============================================================================

# Read-only tools (no modifications)
READONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

# Non-idempotent tools (statistical computations may vary)
STATISTICAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,  # Statistical results may vary slightly
    "openWorldHint": True,
}

# Tools using internal data only (no external API calls)
INTERNAL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,  # Uses internal mappings only
}

# ============================================================================
# Pagination Defaults
# ============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# ============================================================================
# Timeout Values (milliseconds)
# ============================================================================

# Simple single-entity lookups
SIMPLE_QUERY_TIMEOUT = 1000  # 1 second

# Standard multi-entity queries
STANDARD_QUERY_TIMEOUT = 5000  # 5 seconds

# Complex graph operations
SUBNETWORK_TIMEOUT = 10000  # 10 seconds

# Statistical analyses (GSEA, enrichment)
ENRICHMENT_TIMEOUT = 15000  # 15 seconds

# Maximum for any operation
MAX_TIMEOUT = 60000  # 60 seconds

# ============================================================================
# Cache Configuration
# ============================================================================

# Cache key prefixes for different entity types
CACHE_PREFIX_GENE = "gene:"
CACHE_PREFIX_DRUG = "drug:"
CACHE_PREFIX_DISEASE = "disease:"
CACHE_PREFIX_PATHWAY = "pathway:"
CACHE_PREFIX_ONTOLOGY = "ontology:"

# ============================================================================
# Entity Type Identifiers
# ============================================================================


class EntityType(str, Enum):
    """Types of biomedical entities in CoGEx."""

    GENE = "gene"
    PROTEIN = "protein"
    DRUG = "drug"
    DISEASE = "disease"
    PHENOTYPE = "phenotype"
    TISSUE = "tissue"
    CELL_TYPE = "cell_type"
    CELL_LINE = "cell_line"
    PATHWAY = "pathway"
    GO_TERM = "go_term"
    MESH_TERM = "mesh_term"
    VARIANT = "variant"
    PUBLICATION = "publication"


# ============================================================================
# Database Source Identifiers
# ============================================================================

# Integrated databases in CoGEx
COGEX_DATABASES = {
    "bgee": "BGee - Gene expression",
    "go": "Gene Ontology",
    "reactome": "Reactome Pathways",
    "wikipathways": "WikiPathways",
    "chembl": "ChEMBL - Drugs and targets",
    "sider": "SIDER - Side effects",
    "disgenet": "DisGeNet - Disease associations",
    "gwas_catalog": "GWAS Catalog",
    "ccle": "Cancer Cell Line Encyclopedia",
    "depmap": "DepMap - Gene dependencies",
    "clinicaltrials": "ClinicalTrials.gov",
    "pubmed": "PubMed literature",
    "hpo": "Human Phenotype Ontology",
    "mondo": "MONDO Disease Ontology",
    "cellmarker": "CellMarker Database",
    "phosphositeplus": "PhosphoSitePlus",
}

# ============================================================================
# Confidence Levels
# ============================================================================


class ConfidenceLevel(str, Enum):
    """Evidence confidence levels in CoGEx."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# ============================================================================
# Error Messages
# ============================================================================

ERROR_NO_BACKEND = (
    "No backend available. Configure either:\n"
    "1. Neo4j: Set NEO4J_URL and NEO4J_PASSWORD, or\n"
    "2. REST API: Set USE_REST_FALLBACK=true"
)

ERROR_ENTITY_NOT_FOUND = (
    "Entity '{entity}' not found in CoGEx. "
    "Try:\n"
    "- Verify spelling\n"
    "- Use namespace:ID format (e.g., 'hgnc:11998' for TP53)\n"
    "- Search with cogex_resolve_identifiers"
)

ERROR_AMBIGUOUS_IDENTIFIER = (
    "Identifier '{identifier}' matches multiple entities:\n{matches}\n"
    "Specify using (namespace, id) tuple format."
)

ERROR_TIMEOUT = (
    "Query timeout after {timeout_ms}ms. "
    "Try:\n"
    "- Reduce result size with limit parameter\n"
    "- Add filters to narrow query\n"
    "- Use more specific identifiers"
)

ERROR_RATE_LIMIT = (
    "Rate limit exceeded. Please wait {retry_after}s before retrying."
)
