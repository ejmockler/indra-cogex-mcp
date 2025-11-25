"""
REST API client for INDRA CoGEx with retry logic and rate limiting.

Provides access to public INDRA CoGEx REST API with:
- Exponential backoff on failures
- Rate limiting protection
- Connection pooling
- Comprehensive error handling
"""

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class RestClient:
    """
    HTTP client for INDRA CoGEx REST API.

    Features:
    - Automatic retry with exponential backoff
    - Connection pooling
    - Rate limit handling
    - Timeout enforcement
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff_factor: float = 1.5,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
    ):
        """
        Initialize REST client.

        Args:
            base_url: Base URL for API (e.g., https://discovery.indra.bio)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_backoff_factor: Exponential backoff multiplier
            max_connections: Maximum total connections
            max_keepalive_connections: Maximum keepalive connections
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor

        self.client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

        # Connection pool configuration
        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )

    async def initialize(self) -> None:
        """Initialize HTTP client with connection pooling."""
        async with self._lock:
            if self.client is not None:
                return

            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                limits=self.limits,
                headers={
                    "User-Agent": "cogex-mcp/1.0.0",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )

            logger.info(f"REST client initialized for {self.base_url}")

    async def close(self) -> None:
        """Close HTTP client and connections."""
        async with self._lock:
            if self.client:
                await self.client.aclose()
                self.client = None
                logger.info("REST client closed")

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def execute_query(
        self,
        query_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        """
        Execute named query against REST API.

        Args:
            query_name: Name of the query operation
            **params: Query parameters

        Returns:
            Query results as dictionary

        Raises:
            httpx.HTTPError: If request fails
            RuntimeError: If not initialized
        """
        if self.client is None:
            raise RuntimeError("REST client not initialized")

        # Map query name to endpoint
        endpoint, method, query_params = self._get_endpoint(query_name, **params)

        try:
            if method == "GET":
                response = await self.client.get(endpoint, params=query_params)
            elif method == "POST":
                response = await self.client.post(endpoint, json=query_params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                logger.warning(f"Rate limited, retry after {retry_after}s")
                await asyncio.sleep(retry_after)
                return await self.execute_query(query_name, **params)

            # Raise for HTTP errors
            response.raise_for_status()

            # Parse JSON response
            raw_data = response.json()

            # Parse API response format
            # Most endpoints return array of {data: {...}, labels: [...]}
            # Boolean endpoints may return simple values
            parsed_data = self._parse_response(raw_data, query_name)

            logger.debug(f"Query '{query_name}' succeeded (status={response.status_code})")

            return {
                "success": True,
                "data": parsed_data,
                "raw_data": raw_data,
                "status_code": response.status_code,
            }

        except httpx.TimeoutException as e:
            logger.error(f"Query '{query_name}' timed out: {e}")
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Query '{query_name}' failed: {e.response.status_code} - {e.response.text}"
            )
            raise

        except Exception as e:
            logger.error(f"Query '{query_name}' error: {e}")
            raise

    def _parse_response(self, raw_data: Any, query_name: str) -> Any:
        """
        Parse API response into standardized format.

        Args:
            raw_data: Raw JSON response from API
            query_name: Name of query for context

        Returns:
            Parsed data in standardized format

        Notes:
            - Entity queries return: [{data: {...}, labels: [...]}, ...]
            - Boolean queries return: boolean or simple value
            - Analysis queries return: structured results
        """
        # If response is a list of entity objects, extract data field
        if isinstance(raw_data, list):
            records = []
            for item in raw_data:
                if isinstance(item, dict) and "data" in item:
                    # Extract entity data and preserve labels
                    record = item["data"].copy() if isinstance(item["data"], dict) else item["data"]
                    if isinstance(record, dict) and "labels" in item:
                        record["_labels"] = item["labels"]
                    records.append(record)
                else:
                    # Not in expected format, keep as-is
                    records.append(item)
            return records

        # Boolean or analysis results - return as-is
        return raw_data

    def _format_entity_tuple(
        self, entity: Any, default_namespace: str, required: bool = True
    ) -> list | None:
        """
        Convert entity to [namespace, id] format required by INDRA CoGEx API.

        Args:
            entity: Entity as tuple, list, string CURIE, or plain ID
            default_namespace: Namespace to use if not specified
            required: Whether this parameter is required (default: True)

        Returns:
            List in format ["namespace", "id"], or None if entity is None and not required

        Examples:
            _format_entity_tuple(("HGNC", "11998"), "HGNC") -> ["HGNC", "11998"]
            _format_entity_tuple("HGNC:11998", "HGNC") -> ["HGNC", "11998"]
            _format_entity_tuple("11998", "HGNC") -> ["HGNC", "11998"]
            _format_entity_tuple(None, "HGNC", required=False) -> None
        """
        # Handle None/missing entities
        if entity is None:
            if required:
                raise ValueError("Required entity parameter is missing")
            return None

        if isinstance(entity, (list, tuple)) and len(entity) == 2:
            return [entity[0], entity[1]]

        if isinstance(entity, str):
            # Parse CURIE format (e.g., "HGNC:11998")
            if ":" in entity:
                namespace, identifier = entity.split(":", 1)
                return [namespace, identifier]
            # Plain ID - use default namespace
            return [default_namespace, entity]

        raise ValueError(f"Invalid entity format: {entity}")

    def _extract_entity_param(
        self, params: dict[str, Any], param_names: list[str], namespace: str, required: bool = True
    ) -> list | None:
        """
        Extract and format entity parameter from params dict.

        Tries multiple parameter names and returns formatted entity tuple.

        Args:
            params: Parameter dictionary
            param_names: List of parameter names to try
            namespace: Default namespace for entity
            required: Whether parameter is required

        Returns:
            Formatted entity tuple or None

        Raises:
            ValueError: If required parameter is missing
        """
        for param_name in param_names:
            value = params.get(param_name)
            if value is not None:
                return self._format_entity_tuple(value, namespace, required=True)

        if required:
            raise ValueError(f"Required parameter {param_names} missing")
        return None

    def _get_endpoint(
        self,
        query_name: str,
        **params: Any,
    ) -> tuple[str, str, dict[str, Any]]:
        """
        Map query names to REST endpoints with lazy parameter formatting.

        This method uses if/elif structure to avoid eager evaluation of all parameters.
        Only the selected endpoint's parameters are formatted.

        Args:
            query_name: Query operation name
            **params: Query parameters

        Returns:
            Tuple of (endpoint_path, http_method, query_params)

        Raises:
            ValueError: If query name is unknown
        """
        # Alias mappings for backward compatibility with test naming
        query_aliases = {
            # Tool 1: Gene/Feature query aliases - now handled as direct endpoints
            # Tool 6: Pathway aliases
            "pathway_get_genes": "get_genes_in_pathway",
            "pathway_get_pathways": "get_pathways_for_gene",
            "pathway_find_shared": "get_shared_pathways_for_genes",
            "pathway_check": "is_gene_in_pathway",
            # Tool 7: Cell Line aliases
            "cell_line_properties": "get_mutations_for_cell_line",
            "cell_line_mutations": "get_mutations_for_cell_line",
            "cell_lines_with_mutation": "get_cell_lines_for_mutation",
            "cell_line_check": "is_mutated_in_cell_line",
            # Tool 8: Clinical Trials aliases
            "trials_for_drug": "get_trials_for_drug",
            "trials_for_disease": "get_trials_for_disease",
            "trial_by_id": "get_trial_by_id",
            # Tool 9: Literature aliases
            "lit_statements_pmid": "get_statements_for_paper",
            "lit_evidence": "get_evidences_for_stmt_hash",
            "lit_mesh_search": "get_evidence_for_mesh",
            # Tool 10: Variant aliases
            "variants_for_gene": "get_variants_for_gene",
            "variants_for_disease": "get_variants_for_disease",
            "variant_to_genes": "get_genes_for_variant",
            "variant_to_phenotypes": "get_phenotypes_for_variant",
            "variant_check": "is_variant_associated",
        }

        # Update aliases with Tools 11-16
        query_aliases.update({
            # Tool 11: Identifier Resolution aliases
            "resolve_identifiers": "map_identifiers",
            # Tool 12: Relationship Checking aliases
            "check_relationship": "is_gene_in_pathway",  # Will be routed by relationship type
            # Tool 13: Ontology Hierarchy aliases
            "ontology_hierarchy": "get_ontology_hierarchy",
            # Tool 14: Cell Markers aliases
            "cell_markers": "get_markers_for_cell_type",
            "cell_types_for_marker": "get_cell_types_for_marker",
            "check_marker": "is_cell_marker",
            # Tool 16: Protein Functions aliases
            "gene_to_activities": "get_enzyme_activities",
            "activity_to_genes": "get_genes_for_activity",
            "check_activity": "has_enzyme_activity",
            "check_function_types": "is_kinase",  # Will be routed by function type
        })

        # Resolve alias if exists
        resolved_query_name = query_aliases.get(query_name, query_name)

        # Helper function for cleaner parameter extraction
        def extract(param_names: list[str], namespace: str, required: bool = True) -> list | None:
            """Extract and format entity parameter from multiple possible names."""
            return self._extract_entity_param(params, param_names, namespace, required)

        # ========================================================================
        # Meta & Health Endpoints
        # ========================================================================

        if resolved_query_name == "get_meta":
            return "/api/get_meta", "POST", {}  # No parameters

        elif resolved_query_name == "health_check":
            return "/api/health", "GET", {}

        # ========================================================================
        # Gene Expression Queries (Priority 1)
        # ========================================================================

        elif resolved_query_name == "get_tissues_for_gene":
            return (
                "/api/get_tissues_for_gene",
                "POST",
                {"gene": extract(["gene", "gene_id"], "HGNC")},
            )

        elif resolved_query_name == "get_genes_in_tissue":
            return (
                "/api/get_genes_in_tissue",
                "POST",
                {
                    "tissue": extract(["tissue", "tissue_id"], "UBERON"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_gene_in_tissue":
            return (
                "/api/is_gene_in_tissue",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "tissue": extract(["tissue", "tissue_id"], "UBERON"),
                },
            )

        # ========================================================================
        # GO Term Queries (Priority 1)
        # ========================================================================

        elif resolved_query_name == "get_go_terms_for_gene":
            return (
                "/api/get_go_terms_for_gene",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "include_indirect": params.get("include_indirect", False),
                },
            )

        elif resolved_query_name == "get_genes_for_go_term":
            return (
                "/api/get_genes_for_go_term",
                "POST",
                {
                    "go_term": extract(["go_term", "go_id"], "GO"),
                    "include_indirect": params.get("include_indirect", False),
                },
            )

        # ========================================================================
        # Drug Queries (Tool 4)
        # ========================================================================

        elif resolved_query_name == "get_drug_by_name":
            return (
                "/api/get_drug_by_name",
                "POST",
                {"name": params.get("name")},
            )

        elif resolved_query_name == "drug_to_profile":
            return (
                "/api/drug_to_profile",
                "POST",
                {
                    "drug": params.get("drug"),
                    "include_targets": params.get("include_targets", True),
                    "include_indications": params.get("include_indications", True),
                    "include_side_effects": params.get("include_side_effects", True),
                    "include_trials": params.get("include_trials", False),
                },
            )

        elif resolved_query_name == "side_effect_to_drugs":
            return (
                "/api/side_effect_to_drugs",
                "POST",
                {
                    "side_effect": params.get("side_effect"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        # ========================================================================
        # Disease/Phenotype Queries (Tool 5)
        # ========================================================================

        elif resolved_query_name == "get_disease_by_name":
            return (
                "/api/get_disease_by_name",
                "POST",
                {"name": params.get("name")},
            )

        elif resolved_query_name == "disease_to_mechanisms":
            return (
                "/api/disease_to_mechanisms",
                "POST",
                {
                    "disease": params.get("disease"),
                    "include_genes": params.get("include_genes", True),
                    "include_variants": params.get("include_variants", False),
                    "include_phenotypes": params.get("include_phenotypes", True),
                    "include_drugs": params.get("include_drugs", True),
                    "include_trials": params.get("include_trials", False),
                },
            )

        elif resolved_query_name == "phenotype_to_diseases":
            return (
                "/api/phenotype_to_diseases",
                "POST",
                {
                    "phenotype": params.get("phenotype"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "check_phenotype":
            return (
                "/api/check_phenotype",
                "POST",
                {
                    "disease": params.get("disease"),
                    "phenotype": params.get("phenotype"),
                },
            )

        # ========================================================================
        # Tool 6: Pathway Queries
        # ========================================================================

        elif resolved_query_name == "get_genes_in_pathway":
            return (
                "/api/get_genes_in_pathway",
                "POST",
                {
                    "pathway": extract(["pathway", "pathway_id"], "reactome"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_pathways_for_gene":
            return (
                "/api/get_pathways_for_gene",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_shared_pathways_for_genes":
            return (
                "/api/get_shared_pathways_for_genes",
                "POST",
                {
                    "genes": [extract([f"gene_{i}"], "HGNC") for i, _ in enumerate(params.get("gene_ids", []))],
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_gene_in_pathway":
            return (
                "/api/is_gene_in_pathway",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "pathway": extract(["pathway", "pathway_id"], "reactome"),
                },
            )

        # ========================================================================
        # Tool 7: Cell Line Queries
        # ========================================================================

        elif resolved_query_name == "get_mutations_for_cell_line":
            return (
                "/api/get_mutations_for_cell_line",
                "POST",
                {
                    "cell_line": params.get("cell_line"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_copy_number_for_cell_line":
            return (
                "/api/get_copy_number_for_cell_line",
                "POST",
                {
                    "cell_line": params.get("cell_line"),
                    "limit": params.get("limit", 20),
                },
            )

        elif resolved_query_name == "get_dependencies_for_cell_line":
            return (
                "/api/get_dependencies_for_cell_line",
                "POST",
                {
                    "cell_line": params.get("cell_line"),
                    "limit": params.get("limit", 20),
                },
            )

        elif resolved_query_name == "get_expression_for_cell_line":
            return (
                "/api/get_expression_for_cell_line",
                "POST",
                {
                    "cell_line": params.get("cell_line"),
                    "limit": params.get("limit", 20),
                },
            )

        elif resolved_query_name == "get_cell_lines_for_mutation":
            return (
                "/api/get_cell_lines_for_mutation",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_mutated_in_cell_line":
            return (
                "/api/is_mutated_in_cell_line",
                "POST",
                {
                    "cell_line": params.get("cell_line"),
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                },
            )

        # ========================================================================
        # Tool 8: Clinical Trials Queries
        # ========================================================================

        elif resolved_query_name == "get_trials_for_drug":
            return (
                "/api/get_trials_for_drug",
                "POST",
                {
                    "drug": extract(["drug", "drug_id"], "CHEBI"),
                    "phase": params.get("phase"),
                    "status": params.get("status"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_trials_for_disease":
            return (
                "/api/get_trials_for_disease",
                "POST",
                {
                    "disease": extract(["disease", "disease_id"], "MESH"),
                    "phase": params.get("phase"),
                    "status": params.get("status"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_trial_by_id":
            return (
                "/api/get_trial_by_id",
                "POST",
                {
                    "nct_id": params.get("nct_id"),
                },
            )

        # ========================================================================
        # Tool 9: Literature Queries
        # ========================================================================

        elif resolved_query_name == "get_statements_for_paper":
            return (
                "/api/get_statements_for_paper",
                "POST",
                {
                    "pmid": params.get("pmid"),
                    "include_evidence": params.get("include_evidence", True),
                    "max_evidence": params.get("max_evidence", 5),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_evidences_for_stmt_hash":
            return (
                "/api/get_evidences_for_stmt_hash",
                "POST",
                {
                    "stmt_hash": params.get("stmt_hash"),
                    "max_evidence": params.get("max_evidence", 5),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_evidence_for_mesh":
            return (
                "/api/get_evidence_for_mesh",
                "POST",
                {
                    "mesh_terms": params.get("mesh_terms", []),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_stmts_for_stmt_hashes":
            return (
                "/api/get_stmts_for_stmt_hashes",
                "POST",
                {
                    "stmt_hashes": params.get("stmt_hashes", []),
                    "include_evidence": params.get("include_evidence", True),
                    "max_evidence": params.get("max_evidence", 5),
                },
            )

        # ========================================================================
        # Tool 10: Variant Queries
        # ========================================================================

        elif resolved_query_name == "get_variants_for_gene":
            return (
                "/api/get_variants_for_gene",
                "POST",
                {
                    "gene": extract(["gene", "gene_id"], "HGNC"),
                    "max_p_value": params.get("max_p_value", 1e-5),
                    "source": params.get("source"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_variants_for_disease":
            return (
                "/api/get_variants_for_disease",
                "POST",
                {
                    "disease": extract(["disease", "disease_id"], "MESH"),
                    "max_p_value": params.get("max_p_value", 1e-5),
                    "source": params.get("source"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_variants_for_phenotype":
            return (
                "/api/get_variants_for_phenotype",
                "POST",
                {
                    "phenotype": params.get("phenotype_id"),
                    "max_p_value": params.get("max_p_value", 1e-5),
                    "source": params.get("source"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_genes_for_variant":
            return (
                "/api/get_genes_for_variant",
                "POST",
                {
                    "variant": params.get("variant_id"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_phenotypes_for_variant":
            return (
                "/api/get_phenotypes_for_variant",
                "POST",
                {
                    "variant": params.get("variant_id"),
                    "max_p_value": params.get("max_p_value", 1e-5),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_variant_associated":
            return (
                "/api/is_variant_associated",
                "POST",
                {
                    "variant": params.get("variant_id"),
                    "disease": extract(["disease", "disease_id"], "MESH"),
                    "max_p_value": params.get("max_p_value", 1e-5),
                },
            )

        # ========================================================================
        # Tool 11: Identifier Resolution
        # ========================================================================

        elif resolved_query_name == "symbol_to_hgnc":
            return (
                "/api/symbol_to_hgnc",
                "POST",
                {"symbols": params.get("symbols", [])},
            )

        elif resolved_query_name == "hgnc_to_uniprot":
            return (
                "/api/hgnc_to_uniprot",
                "POST",
                {"hgnc_ids": params.get("hgnc_ids", [])},
            )

        elif resolved_query_name == "map_identifiers":
            return (
                "/api/map_identifiers",
                "POST",
                {
                    "identifiers": params.get("identifiers", []),
                    "from_namespace": params.get("from_namespace"),
                    "to_namespace": params.get("to_namespace"),
                },
            )

        # ========================================================================
        # Tool 12: Relationship Checking
        # ========================================================================

        elif resolved_query_name == "is_drug_target":
            return (
                "/api/is_drug_target",
                "POST",
                {
                    "drug_id": params.get("drug_id"),
                    "target_id": params.get("target_id"),
                },
            )

        elif resolved_query_name == "drug_has_indication":
            return (
                "/api/drug_has_indication",
                "POST",
                {
                    "drug_id": params.get("drug_id"),
                    "disease_id": params.get("disease_id"),
                },
            )

        elif resolved_query_name == "is_side_effect_for_drug":
            return (
                "/api/is_side_effect_for_drug",
                "POST",
                {
                    "drug_id": params.get("drug_id"),
                    "side_effect_id": params.get("side_effect_id"),
                },
            )

        elif resolved_query_name == "is_gene_associated_with_disease":
            return (
                "/api/is_gene_associated_with_disease",
                "POST",
                {
                    "gene_id": params.get("gene_id"),
                    "disease_id": params.get("disease_id"),
                },
            )

        elif resolved_query_name == "has_phenotype":
            return (
                "/api/has_phenotype",
                "POST",
                {
                    "disease_id": params.get("disease_id"),
                    "phenotype_id": params.get("phenotype_id"),
                },
            )

        elif resolved_query_name == "is_gene_associated_with_phenotype":
            return (
                "/api/is_gene_associated_with_phenotype",
                "POST",
                {
                    "gene_id": params.get("gene_id"),
                    "phenotype_id": params.get("phenotype_id"),
                },
            )

        # ========================================================================
        # Tool 13: Ontology Hierarchy
        # ========================================================================

        elif resolved_query_name == "get_ontology_parents":
            return (
                "/api/get_ontology_parents",
                "POST",
                {
                    "term_id": params.get("term_id"),
                    "max_depth": params.get("max_depth", 2),
                },
            )

        elif resolved_query_name == "get_ontology_children":
            return (
                "/api/get_ontology_children",
                "POST",
                {
                    "term_id": params.get("term_id"),
                    "max_depth": params.get("max_depth", 2),
                },
            )

        elif resolved_query_name == "get_ontology_hierarchy":
            return (
                "/api/get_ontology_hierarchy",
                "POST",
                {
                    "term_id": params.get("term_id"),
                    "max_depth": params.get("max_depth", 2),
                },
            )

        # ========================================================================
        # Tool 14: Cell Markers
        # ========================================================================

        elif resolved_query_name == "get_markers_for_cell_type":
            return (
                "/api/get_markers_for_cell_type",
                "POST",
                {
                    "cell_type": params.get("cell_type"),
                    "tissue": params.get("tissue"),
                    "species": params.get("species", "human"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "get_cell_types_for_marker":
            return (
                "/api/get_cell_types_for_marker",
                "POST",
                {
                    "gene_id": params.get("gene_id"),
                    "tissue": params.get("tissue"),
                    "species": params.get("species", "human"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_cell_marker":
            return (
                "/api/is_cell_marker",
                "POST",
                {
                    "gene_id": params.get("gene_id"),
                    "cell_type": params.get("cell_type"),
                    "tissue": params.get("tissue"),
                    "species": params.get("species", "human"),
                },
            )

        # ========================================================================
        # Tool 16: Protein Functions
        # ========================================================================

        elif resolved_query_name == "get_enzyme_activities":
            return (
                "/api/get_enzyme_activities",
                "POST",
                {"gene_id": params.get("gene_id")},
            )

        elif resolved_query_name == "get_genes_for_activity":
            return (
                "/api/get_genes_for_activity",
                "POST",
                {
                    "activity": params.get("activity"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "is_kinase":
            return (
                "/api/is_kinase",
                "POST",
                {"gene_id": params.get("gene_id")},
            )

        elif resolved_query_name == "is_phosphatase":
            return (
                "/api/is_phosphatase",
                "POST",
                {"gene_id": params.get("gene_id")},
            )

        elif resolved_query_name == "is_transcription_factor":
            return (
                "/api/is_transcription_factor",
                "POST",
                {"gene_id": params.get("gene_id")},
            )

        elif resolved_query_name == "has_enzyme_activity":
            return (
                "/api/has_enzyme_activity",
                "POST",
                {
                    "gene_id": params.get("gene_id"),
                    "activity": params.get("activity"),
                },
            )

        # ========================================================================
        # Tool 1: Missing queries - domain_to_genes and phenotype_to_genes
        # ========================================================================

        elif resolved_query_name == "domain_to_genes":
            return (
                "/api/domain_to_genes",
                "POST",
                {
                    "domain": params.get("domain"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "phenotype_to_genes":
            return (
                "/api/phenotype_to_genes",
                "POST",
                {
                    "phenotype": params.get("phenotype"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        # ========================================================================
        # Tool 2: Subnetwork extraction
        # ========================================================================

        elif resolved_query_name == "extract_subnetwork":
            return (
                "/api/extract_subnetwork",
                "POST",
                {
                    "gene_ids": params.get("gene_ids", []),
                    "statement_types": params.get("statement_types"),
                    "min_evidence": params.get("min_evidence", 1),
                    "min_belief": params.get("min_belief", 0.0),
                    "max_statements": params.get("max_statements", 100),
                    "tissue": params.get("tissue"),
                    "go_term": params.get("go_term"),
                },
            )

        elif resolved_query_name == "indra_subnetwork":
            return (
                "/api/indra_subnetwork",
                "POST",
                {
                    "gene_ids": params.get("gene_ids", []),
                    "statement_types": params.get("statement_types"),
                    "min_evidence": params.get("min_evidence", 1),
                    "min_belief": params.get("min_belief", 0.0),
                    "max_statements": params.get("max_statements", 100),
                    "tissue": params.get("tissue"),
                    "go_term": params.get("go_term"),
                },
            )

        elif resolved_query_name == "indra_mediated_subnetwork":
            return (
                "/api/indra_mediated_subnetwork",
                "POST",
                {
                    "gene_ids": params.get("gene_ids", []),
                    "statement_types": params.get("statement_types"),
                    "min_evidence": params.get("min_evidence", 1),
                    "min_belief": params.get("min_belief", 0.0),
                    "max_statements": params.get("max_statements", 100),
                    "tissue": params.get("tissue"),
                    "go_term": params.get("go_term"),
                },
            )

        elif resolved_query_name == "source_target_analysis":
            return (
                "/api/source_target_analysis",
                "POST",
                {
                    "source_gene_id": params.get("source_gene_id"),
                    "target_gene_ids": params.get("target_gene_ids"),
                    "statement_types": params.get("statement_types"),
                    "min_evidence": params.get("min_evidence", 1),
                    "min_belief": params.get("min_belief", 0.0),
                    "max_statements": params.get("max_statements", 100),
                    "tissue": params.get("tissue"),
                    "go_term": params.get("go_term"),
                },
            )

        # ========================================================================
        # Tool 3: Enrichment analysis
        # ========================================================================

        elif resolved_query_name == "enrichment_analysis":
            return (
                "/api/enrichment_analysis",
                "POST",
                {
                    "gene_ids": params.get("gene_ids", []),
                    "analysis_type": params.get("analysis_type", "discrete"),
                    "source": params.get("source", "go"),
                    "ranked_genes": params.get("ranked_genes"),
                    "background_genes": params.get("background_genes"),
                    "alpha": params.get("alpha", 0.05),
                    "correction_method": params.get("correction_method", "fdr_bh"),
                    "keep_insignificant": params.get("keep_insignificant", False),
                    "min_belief_score": params.get("min_belief_score", 0.0),
                    "min_evidence_count": params.get("min_evidence_count", 1),
                    "permutations": params.get("permutations", 1000),
                },
            )

        # ========================================================================
        # Tool 1: Integration test endpoints (accept different param names)
        # ========================================================================

        elif resolved_query_name == "gene_to_features":
            # Note: REST API may not support this - it's a composite query
            # Fall back to basic gene lookup
            return (
                "/api/get_gene_by_symbol",
                "POST",
                {"symbol": params.get("gene")},
            )

        elif resolved_query_name == "tissue_to_genes":
            return (
                "/api/get_genes_in_tissue",
                "POST",
                {
                    "tissue": params.get("tissue"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        elif resolved_query_name == "go_to_genes":
            return (
                "/api/get_genes_for_go_term",
                "POST",
                {
                    "go_term": params.get("go_term"),
                    "limit": params.get("limit", 20),
                    "offset": params.get("offset", 0),
                },
            )

        # Unknown query - this should be caught by higher-level code
        else:
            raise ValueError(f"Unknown query: {query_name}")

    async def health_check(self) -> bool:
        """
        Check if REST API is healthy.

        Returns:
            True if healthy

        Raises:
            Exception: If health check fails
        """
        try:
            result = await self.execute_query("health_check")
            return result["success"]
        except Exception as e:
            logger.error(f"REST health check failed: {e}")
            raise

    async def get_api_info(self) -> dict[str, Any]:
        """
        Get API information and available endpoints.

        Returns:
            API info dictionary
        """
        try:
            if self.client is None:
                raise RuntimeError("REST client not initialized")

            response = await self.client.get("/api/info")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"Failed to get API info: {e}")
            return {"error": str(e)}
