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
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
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

        self.client: Optional[httpx.AsyncClient] = None
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
    ) -> Dict[str, Any]:
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

    def _parse_response(
        self,
        raw_data: Any,
        query_name: str
    ) -> Any:
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
        self,
        entity: Any,
        default_namespace: str,
        required: bool = True
    ) -> Optional[list]:
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
        self,
        params: Dict[str, Any],
        param_names: list[str],
        namespace: str,
        required: bool = True
    ) -> Optional[list]:
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
    ) -> tuple[str, str, Dict[str, Any]]:
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
        # Helper function for cleaner parameter extraction
        def extract(param_names: list[str], namespace: str, required: bool = True) -> Optional[list]:
            """Extract and format entity parameter from multiple possible names."""
            return self._extract_entity_param(params, param_names, namespace, required)

        # ========================================================================
        # Meta & Health Endpoints
        # ========================================================================

        if query_name == "get_meta":
            return "/api/get_meta", "POST", {}  # No parameters

        elif query_name == "health_check":
            return "/api/health", "GET", {}

        # ========================================================================
        # Gene Expression Queries (Priority 1)
        # ========================================================================

        elif query_name == "get_tissues_for_gene":
            return "/api/get_tissues_for_gene", "POST", {
                "gene": extract(["gene", "gene_id"], "HGNC")
            }

        elif query_name == "get_genes_in_tissue":
            return "/api/get_genes_in_tissue", "POST", {
                "tissue": extract(["tissue", "tissue_id"], "UBERON"),
                "limit": params.get("limit", 20),
                "offset": params.get("offset", 0)
            }

        elif query_name == "is_gene_in_tissue":
            return "/api/is_gene_in_tissue", "POST", {
                "gene": extract(["gene", "gene_id"], "HGNC"),
                "tissue": extract(["tissue", "tissue_id"], "UBERON")
            }

        # ========================================================================
        # GO Term Queries (Priority 1)
        # ========================================================================

        elif query_name == "get_go_terms_for_gene":
            return "/api/get_go_terms_for_gene", "POST", {
                "gene": extract(["gene", "gene_id"], "HGNC"),
                "include_indirect": params.get("include_indirect", False)
            }

        elif query_name == "get_genes_for_go_term":
            return "/api/get_genes_for_go_term", "POST", {
                "go_term": extract(["go_term", "go_id"], "GO"),
                "include_indirect": params.get("include_indirect", False)
            }

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

    async def get_api_info(self) -> Dict[str, Any]:
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
