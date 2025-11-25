"""
Unified client adapter with automatic backend selection and fallback.

Implements:
- Connection pooling for Neo4j
- Circuit breaker pattern for fault tolerance
- Automatic fallback from Neo4j → REST
- Health checking and monitoring
- Thread-safe operations
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from cogex_mcp.clients.neo4j_client import Neo4jClient
from cogex_mcp.clients.rest_client import RestClient
from cogex_mcp.config import settings

logger = logging.getLogger(__name__)


class BackendType(str, Enum):
    """Available backend types."""

    NEO4J = "neo4j"
    REST = "rest"
    NONE = "none"


class BackendHealth(str, Enum):
    """Backend health states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, don't try
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Prevents cascading failures by temporarily stopping requests to failing backends.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening
            recovery_timeout: Seconds before attempting recovery
            success_threshold: Consecutive successes to close
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            # Check if circuit should transition to half-open
            if self.state == CircuitBreakerState.OPEN:
                if self.last_failure_time and datetime.now() - self.last_failure_time > timedelta(
                    seconds=self.recovery_timeout
                ):
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception("Circuit breaker is OPEN")

        # Execute function
        try:
            result = await func(*args, **kwargs)

            # Record success
            async with self._lock:
                self.failure_count = 0
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= self.success_threshold:
                        logger.info("Circuit breaker CLOSED after recovery")
                        self.state = CircuitBreakerState.CLOSED
                        self.success_count = 0

            return result

        except Exception as e:
            # Record failure
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = datetime.now()

                if self.state == CircuitBreakerState.HALF_OPEN:
                    logger.warning("Circuit breaker OPEN after failed recovery attempt")
                    self.state = CircuitBreakerState.OPEN
                    self.failure_count = 0
                elif self.failure_count >= self.failure_threshold:
                    logger.error(f"Circuit breaker OPEN after {self.failure_count} failures")
                    self.state = CircuitBreakerState.OPEN

            raise e

    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitBreakerState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class ClientAdapter:
    """
    Unified interface to CoGEx backends with automatic fallback.

    Manages connections to Neo4j (primary) and REST API (fallback),
    with intelligent health checking and circuit breaking.
    """

    def __init__(self):
        """Initialize client adapter with configured backends."""
        self.neo4j_client: Neo4jClient | None = None
        self.rest_client: RestClient | None = None

        self.neo4j_breaker: CircuitBreaker | None = None
        self.rest_breaker: CircuitBreaker | None = None

        self.primary_backend = BackendType.NONE
        self.fallback_backend = BackendType.NONE

        self._initialized = False
        self._lock = asyncio.Lock()

        # Health tracking
        self.neo4j_health = BackendHealth.UNKNOWN
        self.rest_health = BackendHealth.UNKNOWN
        self.last_health_check: datetime | None = None
        self.health_check_interval = 300  # 5 minutes

    async def initialize(self) -> None:
        """
        Initialize backends based on configuration.

        Sets up Neo4j and/or REST clients with connection pooling.
        """
        async with self._lock:
            if self._initialized:
                return

            logger.info("Initializing ClientAdapter")

            # Initialize Neo4j if configured
            if settings.has_neo4j_config:
                try:
                    self.neo4j_client = Neo4jClient(
                        uri=settings.neo4j_url,
                        user=settings.neo4j_user,
                        password=settings.neo4j_password,
                        max_connection_pool_size=settings.neo4j_max_connection_pool_size,
                        connection_timeout=settings.neo4j_connection_timeout,
                        max_connection_lifetime=settings.neo4j_max_connection_lifetime,
                    )
                    await self.neo4j_client.connect()
                    self.neo4j_breaker = CircuitBreaker(
                        failure_threshold=5,
                        recovery_timeout=60,
                        success_threshold=2,
                    )
                    self.primary_backend = BackendType.NEO4J
                    self.neo4j_health = BackendHealth.HEALTHY
                    logger.info("Neo4j client initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize Neo4j: {e}")
                    self.neo4j_health = BackendHealth.UNHEALTHY

            # Initialize REST client if enabled
            if settings.has_rest_fallback:
                try:
                    self.rest_client = RestClient(
                        base_url=settings.rest_api_base,
                        timeout=settings.rest_timeout_seconds,
                        max_retries=settings.rest_max_retries,
                        retry_backoff_factor=settings.rest_retry_backoff_factor,
                    )
                    await self.rest_client.initialize()
                    self.rest_breaker = CircuitBreaker(
                        failure_threshold=5,
                        recovery_timeout=60,
                        success_threshold=2,
                    )
                    if self.primary_backend == BackendType.NONE:
                        self.primary_backend = BackendType.REST
                    else:
                        self.fallback_backend = BackendType.REST
                    self.rest_health = BackendHealth.HEALTHY
                    logger.info("REST client initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize REST client: {e}")
                    self.rest_health = BackendHealth.UNHEALTHY

            # Validate at least one backend is available
            if self.primary_backend == BackendType.NONE:
                raise RuntimeError(
                    "No backends available. Configure Neo4j or enable REST fallback."
                )

            self._initialized = True
            logger.info(
                f"ClientAdapter initialized: primary={self.primary_backend}, "
                f"fallback={self.fallback_backend}"
            )

    async def close(self) -> None:
        """Close all backend connections."""
        logger.info("Closing ClientAdapter connections")

        if self.neo4j_client:
            await self.neo4j_client.close()
            logger.info("Neo4j client closed")

        if self.rest_client:
            await self.rest_client.close()
            logger.info("REST client closed")

        self._initialized = False

    async def query(
        self,
        query_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        """
        Execute query with automatic backend selection and fallback.

        Args:
            query_name: Name of the query operation
            **params: Query parameters

        Returns:
            Query results as dictionary

        Raises:
            Exception: If all backends fail
        """
        if not self._initialized:
            await self.initialize()

        # Periodically check health
        await self._check_health_if_needed()

        # Try primary backend first
        if await self._can_use_backend(self.primary_backend):
            try:
                result = await self._execute_on_backend(self.primary_backend, query_name, **params)
                logger.debug(f"Query '{query_name}' succeeded on {self.primary_backend}")
                return result
            except Exception as e:
                logger.warning(f"Query '{query_name}' failed on {self.primary_backend}: {e}")
                # Continue to fallback

        # Try fallback backend
        if await self._can_use_backend(self.fallback_backend):
            try:
                result = await self._execute_on_backend(self.fallback_backend, query_name, **params)
                logger.info(f"Query '{query_name}' succeeded on fallback {self.fallback_backend}")
                return result
            except Exception as e:
                logger.error(
                    f"Query '{query_name}' failed on fallback {self.fallback_backend}: {e}"
                )
                raise

        # No backends available
        raise RuntimeError(
            f"All backends unavailable for query '{query_name}'. "
            f"Primary: {self.primary_backend} ({self.neo4j_health}), "
            f"Fallback: {self.fallback_backend} ({self.rest_health})"
        )

    async def _can_use_backend(self, backend: BackendType) -> bool:
        """Check if backend is available for use."""
        if backend == BackendType.NONE:
            return False

        if backend == BackendType.NEO4J:
            return (
                self.neo4j_client is not None
                and self.neo4j_breaker is not None
                and not self.neo4j_breaker.is_open()
            )
        elif backend == BackendType.REST:
            return (
                self.rest_client is not None
                and self.rest_breaker is not None
                and not self.rest_breaker.is_open()
            )

        return False

    async def _execute_on_backend(
        self,
        backend: BackendType,
        query_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        """
        Execute query on specific backend through circuit breaker.

        Args:
            backend: Backend to use
            query_name: Query operation name
            **params: Query parameters

        Returns:
            Query results

        Raises:
            Exception: If backend fails or circuit is open
        """
        if backend == BackendType.NEO4J:
            return await self.neo4j_breaker.call(
                self.neo4j_client.execute_query, query_name, **params
            )
        elif backend == BackendType.REST:
            return await self.rest_breaker.call(
                self.rest_client.execute_query, query_name, **params
            )
        else:
            raise ValueError(f"Invalid backend: {backend}")

    async def _check_health_if_needed(self) -> None:
        """Check backend health if interval has passed."""
        if self.last_health_check is None or datetime.now() - self.last_health_check > timedelta(
            seconds=self.health_check_interval
        ):
            await self._check_health()

    async def _check_health(self) -> None:
        """Check health of all backends."""
        logger.debug("Checking backend health")

        # Check Neo4j
        if self.neo4j_client:
            try:
                await self.neo4j_client.health_check()
                self.neo4j_health = BackendHealth.HEALTHY
            except Exception as e:
                logger.warning(f"Neo4j health check failed: {e}")
                self.neo4j_health = BackendHealth.UNHEALTHY

        # Check REST
        if self.rest_client:
            try:
                await self.rest_client.health_check()
                self.rest_health = BackendHealth.HEALTHY
            except Exception as e:
                logger.warning(f"REST health check failed: {e}")
                self.rest_health = BackendHealth.UNHEALTHY

        self.last_health_check = datetime.now()

    def get_status(self) -> dict[str, Any]:
        """
        Get adapter status and health information.

        Returns:
            Status dictionary with both flat keys (backward-compatible)
            and nested structure (detailed info)
        """
        neo4j_available = self.neo4j_client is not None
        rest_available = self.rest_client is not None

        return {
            "initialized": self._initialized,
            "primary_backend": self.primary_backend.value,
            "fallback_backend": self.fallback_backend.value,
            # Backward-compatible flat keys for tests
            "neo4j_available": neo4j_available,
            "rest_available": rest_available,
            # Nested structure for detailed info
            "neo4j": {
                "available": neo4j_available,
                "health": self.neo4j_health.value,
                "circuit_open": (self.neo4j_breaker.is_open() if self.neo4j_breaker else None),
            },
            "rest": {
                "available": rest_available,
                "health": self.rest_health.value,
                "circuit_open": (self.rest_breaker.is_open() if self.rest_breaker else None),
            },
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
        }


# Global adapter instance
_adapter: ClientAdapter | None = None


async def get_adapter() -> ClientAdapter:
    """
    Get global client adapter instance (singleton).

    Returns:
        Initialized ClientAdapter

    Raises:
        RuntimeError: If initialization fails
    """
    global _adapter

    if _adapter is None:
        _adapter = ClientAdapter()
        await _adapter.initialize()

    return _adapter


async def close_adapter() -> None:
    """Close global client adapter."""
    global _adapter

    if _adapter:
        await _adapter.close()
        _adapter = None
