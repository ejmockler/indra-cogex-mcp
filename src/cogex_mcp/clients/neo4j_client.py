"""
Neo4j client with connection pooling and query optimization.

Provides high-performance access to INDRA CoGEx Neo4j database with:
- Connection pooling for concurrent queries
- Query timeout management
- Automatic retry with exponential backoff
- Health checking
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable, TransientError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    High-performance Neo4j client for INDRA CoGEx.

    Features:
    - Connection pooling with configurable size
    - Automatic retry on transient failures
    - Query timeout enforcement
    - Health monitoring
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        max_connection_lifetime: int = 3600,
    ):
        """
        Initialize Neo4j client.

        Args:
            uri: Neo4j bolt URI (e.g., bolt://localhost:7687)
            user: Username
            password: Password
            max_connection_pool_size: Maximum connections in pool
            connection_timeout: Connection timeout in seconds
            max_connection_lifetime: Maximum connection lifetime in seconds
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        self.max_connection_lifetime = max_connection_lifetime

        self.driver: AsyncDriver | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """
        Establish connection to Neo4j with connection pooling.

        Raises:
            ServiceUnavailable: If Neo4j is not accessible
        """
        async with self._lock:
            if self.driver is not None:
                return

            try:
                self.driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                    max_connection_pool_size=self.max_connection_pool_size,
                    connection_timeout=self.connection_timeout,
                    max_connection_lifetime=self.max_connection_lifetime,
                    # Performance optimizations
                    connection_acquisition_timeout=30.0,
                    max_transaction_retry_time=30.0,
                )

                # Verify connectivity
                await self.driver.verify_connectivity()

                logger.info(
                    f"Neo4j client connected to {self.uri} "
                    f"(pool_size={self.max_connection_pool_size})"
                )

            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise

    async def close(self) -> None:
        """Close Neo4j driver and all connections."""
        async with self._lock:
            if self.driver:
                await self.driver.close()
                self.driver = None
                logger.info("Neo4j client closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """
        Get Neo4j session from pool.

        Yields:
            AsyncSession: Neo4j session

        Raises:
            RuntimeError: If not connected
        """
        if self.driver is None:
            raise RuntimeError("Neo4j client not connected. Call connect() first.")

        session = self.driver.session()
        try:
            yield session
        finally:
            await session.close()

    @retry(
        retry=retry_if_exception_type((ServiceUnavailable, TransientError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def execute_query(
        self,
        query_name: str,
        timeout: int | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        """
        Execute named query with retry logic.

        Args:
            query_name: Name of the query to execute
            timeout: Optional query timeout in milliseconds
            **params: Query parameters

        Returns:
            Query results as dictionary

        Raises:
            Neo4jError: If query fails
            RuntimeError: If not connected
        """
        if self.driver is None:
            raise RuntimeError("Neo4j client not connected")

        # Set default limit if not provided
        if "limit" not in params:
            params["limit"] = 20

        # Set default offset if not provided
        if "offset" not in params:
            params["offset"] = 0

        # Map query name to Cypher query
        cypher = self._get_cypher_query(query_name)

        try:
            async with self.get_session() as session:
                # Execute with timeout if specified
                if timeout:
                    result = await asyncio.wait_for(
                        session.run(cypher, **params),
                        timeout=timeout / 1000.0,  # Convert ms to seconds
                    )
                else:
                    result = await session.run(cypher, **params)

                # Consume all records
                records = await result.data()

                logger.debug(f"Query '{query_name}' returned {len(records)} records")

                # Parse records to extract namespace from CURIEs
                parsed_records = self._parse_result(records, query_name)

                return {
                    "success": True,
                    "records": parsed_records,
                    "count": len(parsed_records),
                }

        except asyncio.TimeoutError:
            logger.error(f"Query '{query_name}' timed out after {timeout}ms")
            raise Neo4jError(f"Query timeout after {timeout}ms")

        except Neo4jError as e:
            logger.error(f"Neo4j query '{query_name}' failed: {e}")
            raise

    def _parse_result(self, records: list[dict[str, Any]], query_name: str) -> list[dict[str, Any]]:
        """
        Parse Neo4j records to extract namespace from CURIEs and standardize format.

        Args:
            records: Raw records from Neo4j
            query_name: Name of the query (for context)

        Returns:
            Parsed records with namespace extracted
        """
        parsed_records = []

        for record in records:
            parsed_record = dict(record)

            # Extract namespace from any CURIE ID fields
            for key in ["id", "gene_id", "tissue_id", "go_id", "pathway_id", "disease_id"]:
                if key in parsed_record and parsed_record[key]:
                    curie = parsed_record[key]
                    if isinstance(curie, str) and ":" in curie:
                        namespace, identifier = curie.split(":", 1)
                        # Add namespace and identifier as separate fields
                        parsed_record[f"{key}_namespace"] = namespace
                        parsed_record[f"{key}_identifier"] = identifier

            parsed_records.append(parsed_record)

        return parsed_records

    def _get_cypher_query(self, query_name: str) -> str:
        """
        Get Cypher query for named operation.

        Args:
            query_name: Query operation name

        Returns:
            Cypher query string

        Raises:
            ValueError: If query name is unknown
        """
        # Query catalog - maps operation names to Cypher
        # Updated with correct INDRA CoGEx schema (all genes are BioEntity nodes)
        queries = {
            # Gene queries - CORRECTED SCHEMA
            "get_gene_by_symbol": """
                MATCH (g:BioEntity)
                WHERE g.name = $symbol
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS name,
                  g.id AS id,
                  g.type AS type
                LIMIT 1
            """,
            "get_gene_by_id": """
                MATCH (g:BioEntity)
                WHERE (
                    g.id = $gene_id
                    OR g.id = ('hgnc:' + $gene_id)
                )
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS name,
                  g.id AS id,
                  g.type AS type
                LIMIT 1
            """,
            "get_tissues_for_gene": """
                MATCH (g:BioEntity)-[:expressed_in]->(t:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND t.id STARTS WITH 'uberon:'
                RETURN
                  t.name AS tissue,
                  t.id AS tissue_id,
                  t.type AS type
                LIMIT $limit
            """,
            "get_genes_in_tissue": """
                MATCH (g:BioEntity)-[:expressed_in]->(t:BioEntity)
                WHERE t.id = $tissue_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND t.id STARTS WITH 'uberon:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type
                LIMIT $limit SKIP $offset
            """,
            # GO term queries - CORRECTED SCHEMA
            "get_go_terms_for_gene": """
                MATCH (g:BioEntity)-[r]->(go:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND go.id STARTS WITH 'GO:'
                RETURN
                  go.name AS term,
                  go.id AS go_id,
                  type(r) AS relationship,
                  go.type AS go_type
                LIMIT $limit
            """,
            "get_genes_for_go_term": """
                MATCH (g:BioEntity)-[r]->(go:BioEntity)
                WHERE go.id = $go_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type,
                  type(r) AS relationship
                LIMIT $limit SKIP $offset
            """,
            # Pathway queries - CORRECTED SCHEMA
            "get_pathways_for_gene": """
                MATCH (g:BioEntity)-[r]->(p:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND (
                    p.id STARTS WITH 'reactome:' OR
                    p.id STARTS WITH 'wikipathways:' OR
                    p.id STARTS WITH 'kegg.pathway:'
                  )
                RETURN
                  p.name AS pathway,
                  p.id AS pathway_id,
                  type(r) AS relationship,
                  p.type AS pathway_type
                LIMIT $limit
            """,
            # Disease queries - CORRECTED SCHEMA
            "get_diseases_for_gene": """
                MATCH (g:BioEntity)-[a:gene_disease_association]->(d:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND (
                    d.id STARTS WITH 'mesh:' OR
                    d.id STARTS WITH 'DOID:' OR
                    d.id STARTS WITH 'EFO:' OR
                    d.id STARTS WITH 'umls:'
                  )
                RETURN
                  d.name AS disease,
                  d.id AS disease_id,
                  d.type AS disease_type
                LIMIT $limit
            """,
            # Health check
            "health_check": """
                RETURN 1 AS status
            """,
        }

        if query_name not in queries:
            raise ValueError(f"Unknown query: {query_name}")

        return queries[query_name]

    async def health_check(self) -> bool:
        """
        Check if Neo4j is healthy.

        Returns:
            True if healthy

        Raises:
            Exception: If health check fails
        """
        try:
            result = await self.execute_query("health_check")
            return result["success"]
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            raise

    async def execute_raw_cypher(
        self,
        cypher: str,
        timeout: int | None = None,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """
        Execute raw Cypher query (for advanced use cases).

        Args:
            cypher: Cypher query string
            timeout: Optional timeout in milliseconds
            **params: Query parameters

        Returns:
            List of record dictionaries

        Raises:
            Neo4jError: If query fails
        """
        if self.driver is None:
            raise RuntimeError("Neo4j client not connected")

        try:
            async with self.get_session() as session:
                if timeout:
                    result = await asyncio.wait_for(
                        session.run(cypher, **params),
                        timeout=timeout / 1000.0,
                    )
                else:
                    result = await session.run(cypher, **params)

                records = await result.data()
                return records

        except asyncio.TimeoutError:
            raise Neo4jError(f"Query timeout after {timeout}ms")

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Statistics dictionary
        """
        try:
            # Get node counts by label
            node_stats = await self.execute_raw_cypher("""
                CALL db.labels() YIELD label
                CALL apoc.cypher.run(
                    'MATCH (n:' + label + ') RETURN count(n) as count',
                    {}
                ) YIELD value
                RETURN label, value.count AS count
            """)

            # Get relationship counts by type
            rel_stats = await self.execute_raw_cypher("""
                CALL db.relationshipTypes() YIELD relationshipType
                CALL apoc.cypher.run(
                    'MATCH ()-[r:' + relationshipType + ']->() RETURN count(r) as count',
                    {}
                ) YIELD value
                RETURN relationshipType, value.count AS count
            """)

            return {
                "nodes": {stat["label"]: stat["count"] for stat in node_stats},
                "relationships": {stat["relationshipType"]: stat["count"] for stat in rel_stats},
            }

        except Exception as e:
            logger.warning(f"Failed to get statistics: {e}")
            return {"error": str(e)}
