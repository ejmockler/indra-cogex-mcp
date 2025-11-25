"""
Configuration management using Pydantic Settings.

Loads environment variables with validation, defaults, and type safety.
Follows MCP best practices for secure credential management.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file explicitly before creating Settings instance
# Search for .env file in project root (parent of src/)
_current_file = Path(__file__)
_project_root = _current_file.parent.parent.parent
_env_file = _project_root / ".env"

# Load .env file if it exists (don't error if missing)
load_dotenv(dotenv_path=_env_file, override=False)


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All settings have sensible defaults and are validated on load.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars
    )

    # ========================================================================
    # Neo4j Configuration (Optional - Best Performance)
    # ========================================================================

    neo4j_url: Optional[str] = Field(
        default=None,
        description="Neo4j bolt URL (e.g., bolt://localhost:7687)",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: Optional[str] = Field(
        default=None,
        description="Neo4j password",
    )
    neo4j_max_connection_pool_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum connection pool size",
    )
    neo4j_connection_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Connection timeout in seconds",
    )
    neo4j_max_connection_lifetime: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Maximum connection lifetime in seconds",
    )

    # ========================================================================
    # REST API Configuration (Fallback)
    # ========================================================================

    use_rest_fallback: bool = Field(
        default=True,
        description="Use REST API when Neo4j unavailable",
    )
    rest_api_base: str = Field(
        default="https://discovery.indra.bio",
        description="Base URL for INDRA CoGEx REST API",
    )
    rest_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="HTTP request timeout",
    )
    rest_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed requests",
    )
    rest_retry_backoff_factor: float = Field(
        default=1.5,
        ge=1.0,
        le=5.0,
        description="Exponential backoff multiplier",
    )

    # ========================================================================
    # Caching Configuration
    # ========================================================================

    cache_enabled: bool = Field(
        default=True,
        description="Enable LRU caching for entities",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache entry TTL (time-to-live)",
    )
    cache_max_size: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Maximum cache entries",
    )
    cache_stats_interval: int = Field(
        default=300,
        ge=0,
        description="Log cache stats interval (0=disabled)",
    )

    # ========================================================================
    # Performance Configuration
    # ========================================================================

    character_limit: int = Field(
        default=25000,
        ge=1000,
        le=100000,
        description="Maximum response size in characters",
    )
    query_timeout_ms: int = Field(
        default=5000,
        ge=100,
        le=60000,
        description="Default query timeout in milliseconds",
    )
    enrichment_timeout_ms: int = Field(
        default=15000,
        ge=1000,
        le=120000,
        description="Enrichment analysis timeout",
    )
    subnetwork_timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=60000,
        description="Subnetwork extraction timeout",
    )
    max_concurrent_queries: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent query operations",
    )
    max_concurrent_enrichments: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum concurrent enrichment analyses",
    )

    # ========================================================================
    # MCP Server Configuration
    # ========================================================================

    mcp_server_name: str = Field(
        default="cogex_mcp",
        description="MCP server name",
    )
    transport: str = Field(
        default="stdio",
        description="Transport mode: stdio or http",
    )
    http_host: str = Field(
        default="127.0.0.1",
        description="HTTP server host (if transport=http)",
    )
    http_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="HTTP server port (if transport=http)",
    )

    # ========================================================================
    # Logging Configuration
    # ========================================================================

    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: str = Field(
        default="json",
        description="Log format: json or text",
    )

    # ========================================================================
    # Development/Debug Configuration
    # ========================================================================

    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging",
    )
    enable_profiling: bool = Field(
        default=False,
        description="Enable performance profiling (adds overhead)",
    )
    strict_validation: bool = Field(
        default=False,
        description="Validate all responses against schemas (slow)",
    )

    # ========================================================================
    # Validators
    # ========================================================================

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of {valid_levels}"
            )
        return v_upper

    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        """Validate transport mode."""
        valid_transports = {"stdio", "http"}
        v_lower = v.lower()
        if v_lower not in valid_transports:
            raise ValueError(
                f"Invalid transport: {v}. Must be 'stdio' or 'http'"
            )
        return v_lower

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = {"json", "text"}
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(
                f"Invalid log format: {v}. Must be 'json' or 'text'"
            )
        return v_lower

    # ========================================================================
    # Computed Properties
    # ========================================================================

    @property
    def has_neo4j_config(self) -> bool:
        """Check if Neo4j is configured."""
        return bool(self.neo4j_url and self.neo4j_password)

    @property
    def has_rest_fallback(self) -> bool:
        """Check if REST fallback is available."""
        return self.use_rest_fallback and bool(self.rest_api_base)

    def validate_connectivity(self) -> None:
        """
        Validate that at least one backend is configured.

        Raises:
            ValueError: If no backend is available.
        """
        if not self.has_neo4j_config and not self.has_rest_fallback:
            env_file_path = Path(__file__).parent.parent.parent / ".env"
            env_file_exists = env_file_path.exists()

            error_msg = [
                "No backend configured for INDRA CoGEx MCP server.",
                "",
                "Please configure credentials using ONE of these methods:",
                "",
                "Option 1 - Neo4j Direct Access (Best Performance):",
                "  1. Copy .env.example to .env",
                "  2. Set NEO4J_URL=bolt://your-server:7687",
                "  3. Set NEO4J_USER=neo4j",
                "  4. Set NEO4J_PASSWORD=your_password",
                "",
                "Option 2 - REST API Fallback (Public Access):",
                "  1. Set USE_REST_FALLBACK=true",
                "  2. Set REST_API_BASE=https://discovery.indra.bio",
                "",
            ]

            if env_file_exists:
                error_msg.extend([
                    f"Found .env file at: {env_file_path}",
                    "Please verify your credentials are correctly set.",
                ])
            else:
                error_msg.extend([
                    f"No .env file found at: {env_file_path}",
                    "Copy .env.example to .env and configure your credentials.",
                ])

            error_msg.append("\nSecurity Note: Never commit .env files to version control!")

            raise ValueError("\n".join(error_msg))


# Global settings instance
# Loaded once at import time
settings = Settings()

# Validate on load
settings.validate_connectivity()
