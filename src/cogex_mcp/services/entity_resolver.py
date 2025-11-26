"""
Entity resolution service with caching and fuzzy matching.

Resolves flexible entity inputs (symbols, names, CURIEs) to standardized entities.
Handles ambiguous identifiers with helpful suggestions.
"""

import logging

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CACHE_PREFIX_DRUG,
    CACHE_PREFIX_GENE,
    CACHE_PREFIX_ONTOLOGY,
    ERROR_AMBIGUOUS_IDENTIFIER,
    ERROR_ENTITY_NOT_FOUND,
)
from cogex_mcp.schemas import DrugNode, EntityRef, GeneNode, OntologyTerm
from cogex_mcp.services.cache import get_cache

logger = logging.getLogger(__name__)


class EntityResolutionError(Exception):
    """Base exception for entity resolution errors."""

    pass


class EntityNotFoundError(EntityResolutionError):
    """Entity not found in database."""

    def __init__(self, entity: str, suggestions: list[str] | None = None):
        self.entity = entity
        self.suggestions = suggestions or []
        message = ERROR_ENTITY_NOT_FOUND.format(entity=entity)
        if suggestions:
            message += f"\nDid you mean: {', '.join(suggestions)}?"
        super().__init__(message)


class AmbiguousIdentifierError(EntityResolutionError):
    """Identifier matches multiple entities."""

    def __init__(self, identifier: str, matches: list[dict[str, str]]):
        self.identifier = identifier
        self.matches = matches
        match_strs = [f"{m['name']} ({m['curie']})" for m in matches]
        message = ERROR_AMBIGUOUS_IDENTIFIER.format(
            identifier=identifier, matches="\n".join(f"  - {m}" for m in match_strs)
        )
        super().__init__(message)


class EntityResolver:
    """
    Resolve entity identifiers to standardized representations.

    Supports:
    - Gene symbols ("TP53")
    - CURIEs ("hgnc:11998")
    - Tuples (("hgnc", "11998"))
    - Fuzzy matching with suggestions
    - Caching for performance
    """

    def __init__(self):
        """Initialize entity resolver."""
        self.cache = get_cache()

    async def resolve_gene(
        self,
        identifier: str | tuple[str, str],
    ) -> GeneNode:
        """
        Resolve gene identifier to standardized gene node.

        Args:
            identifier: Gene symbol, CURIE, or (namespace, id) tuple

        Returns:
            GeneNode with standardized information

        Raises:
            EntityNotFoundError: If gene not found
            AmbiguousIdentifierError: If identifier is ambiguous
        """
        # Normalize identifier
        cache_key = self._make_gene_cache_key(identifier)

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            logger.debug(f"Gene resolved from cache: {identifier}")
            return GeneNode(**cached)

        # Resolve gene
        gene = await self._resolve_gene_from_backend(identifier)

        # Cache result
        await self.cache.set(cache_key, gene.model_dump())

        return gene

    async def _resolve_gene_from_backend(
        self,
        identifier: str | tuple[str, str],
    ) -> GeneNode:
        """Resolve gene from backend (Neo4j or REST) with correct query routing."""
        adapter = await get_adapter()

        # Route to appropriate query based on identifier type
        if isinstance(identifier, tuple):
            # Tuple format: ("HGNC", "11998")
            namespace, gene_id = identifier
            query_name = "get_gene_by_id"
            query_params = {"gene_id": gene_id}

        elif ":" in identifier:
            # CURIE format: "hgnc:11998"
            namespace, gene_id = identifier.split(":", 1)
            query_name = "get_gene_by_id"
            query_params = {"gene_id": gene_id}

        else:
            # Symbol format: "TP53"
            query_name = "get_gene_by_symbol"
            query_params = {"symbol": identifier}

        try:
            result = await adapter.query(query_name, **query_params)

            if not result.get("success") or not result.get("records"):
                raise EntityNotFoundError(
                    entity=str(identifier),
                    suggestions=await self._get_gene_suggestions(identifier),
                )

            records = result["records"]

            # Check for ambiguous matches
            if len(records) > 1:
                matches = [
                    {
                        "name": r.get("name", "Unknown"),
                        "curie": f"{r.get('namespace', 'unknown')}:{r.get('id', 'unknown')}",
                    }
                    for r in records
                ]
                raise AmbiguousIdentifierError(identifier=str(identifier), matches=matches)

            # Convert to GeneNode
            record = records[0]
            # Use id_identifier for the numeric part, fall back to extracting from id
            identifier = record.get("id_identifier") or record.get("id", "unknown")
            if ":" in str(identifier) and not record.get("id_identifier"):
                # Extract numeric part from CURIE if id_identifier not available
                identifier = identifier.split(":", 1)[-1]

            namespace = record.get("id_namespace") or record.get("namespace", "hgnc")

            return GeneNode(
                name=record.get("name", "Unknown"),
                curie=f"{namespace}:{identifier}",
                namespace=namespace,
                identifier=identifier,
                description=record.get("description"),
                synonyms=record.get("synonyms", []),
            )

        except (EntityNotFoundError, AmbiguousIdentifierError):
            raise
        except Exception as e:
            logger.error(f"Error resolving gene {identifier}: {e}")
            raise EntityResolutionError(f"Failed to resolve gene: {e}")

    async def _get_gene_suggestions(self, identifier: str) -> list[str]:
        """Get fuzzy match suggestions for gene identifier."""
        # Simple fuzzy matching - in production, use edit distance
        # For now, return empty suggestions
        # TODO: Implement fuzzy matching with Levenshtein distance
        return []

    def _make_gene_cache_key(self, identifier: str | tuple[str, str]) -> str:
        """Create cache key for gene identifier."""
        if isinstance(identifier, tuple):
            return self.cache.make_key(CACHE_PREFIX_GENE, identifier[0], identifier[1])
        else:
            return self.cache.make_key(CACHE_PREFIX_GENE, identifier)

    async def resolve_drug(self, identifier: str | tuple[str, str]) -> DrugNode:
        """
        Resolve drug identifier to DrugNode.

        Args:
            identifier: Drug name, CURIE, or (namespace, id) tuple

        Returns:
            DrugNode with standardized information

        Raises:
            EntityNotFoundError: If drug not found
        """
        # Normalize identifier
        cache_key = self._make_drug_cache_key(identifier)

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            logger.debug(f"Drug resolved from cache: {identifier}")
            return DrugNode(**cached)

        # Resolve drug
        drug = await self._resolve_drug_from_backend(identifier)

        # Cache result
        await self.cache.set(cache_key, drug.model_dump())

        return drug

    async def _resolve_drug_from_backend(
        self,
        identifier: str | tuple[str, str],
    ) -> DrugNode:
        """Resolve drug from backend (Neo4j or REST)."""
        adapter = await get_adapter()

        # Handle different identifier formats
        if isinstance(identifier, tuple):
            namespace, drug_id = identifier
            query_params = {"namespace": namespace, "drug_id": drug_id}
        elif ":" in identifier:
            # CURIE format
            namespace, drug_id = identifier.split(":", 1)
            query_params = {"namespace": namespace, "drug_id": drug_id}
        else:
            # Assume drug name
            query_params = {"name": identifier}

        try:
            result = await adapter.query("get_drug_by_name", **query_params)

            if not result.get("success") or not result.get("records"):
                raise EntityNotFoundError(
                    entity=str(identifier),
                    suggestions=[],
                )

            records = result["records"]

            # Check for ambiguous matches
            if len(records) > 1:
                matches = [
                    {
                        "name": r.get("name", "Unknown"),
                        "curie": f"{r.get('namespace', 'unknown')}:{r.get('id', 'unknown')}",
                    }
                    for r in records
                ]
                raise AmbiguousIdentifierError(identifier=str(identifier), matches=matches)

            # Convert to DrugNode
            record = records[0]
            return DrugNode(
                name=record.get("name", "Unknown"),
                curie=f"{record.get('namespace', 'chembl')}:{record.get('id', 'unknown')}",
                namespace=record.get("namespace", "chembl"),
                identifier=record.get("id", "unknown"),
                synonyms=record.get("synonyms", []),
                drug_type=record.get("drug_type"),
            )

        except (EntityNotFoundError, AmbiguousIdentifierError):
            raise
        except Exception as e:
            logger.error(f"Error resolving drug {identifier}: {e}")
            raise EntityResolutionError(f"Failed to resolve drug: {e}")

    def _make_drug_cache_key(self, identifier: str | tuple[str, str]) -> str:
        """Create cache key for drug identifier."""
        if isinstance(identifier, tuple):
            return self.cache.make_key(CACHE_PREFIX_DRUG, identifier[0], identifier[1])
        else:
            return self.cache.make_key(CACHE_PREFIX_DRUG, identifier)

    async def resolve_disease(self, identifier: str | tuple[str, str]) -> EntityRef:
        """
        Resolve disease identifier to EntityRef.

        Args:
            identifier: Disease name or CURIE

        Returns:
            EntityRef for disease

        Raises:
            EntityNotFoundError: If disease not found
        """
        adapter = await get_adapter()

        # Handle different identifier formats
        if isinstance(identifier, tuple):
            namespace, disease_id = identifier
            query_params = {"namespace": namespace, "disease_id": disease_id}
        elif ":" in identifier:
            # CURIE format
            namespace, disease_id = identifier.split(":", 1)
            query_params = {"namespace": namespace, "disease_id": disease_id}
        else:
            # Assume disease name
            query_params = {"name": identifier}

        try:
            result = await adapter.query("get_disease_by_name", **query_params)

            if not result.get("success") or not result.get("records"):
                raise EntityNotFoundError(
                    entity=str(identifier),
                    suggestions=[],
                )

            records = result["records"]

            # Check for ambiguous matches
            if len(records) > 1:
                matches = [
                    {
                        "name": r.get("name", "Unknown"),
                        "curie": r.get("id", "unknown:unknown"),
                    }
                    for r in records
                ]
                raise AmbiguousIdentifierError(identifier=str(identifier), matches=matches)

            # Convert to EntityRef
            record = records[0]
            disease_id = record.get("id", "unknown:unknown")

            # Extract namespace from CURIE
            if ":" in disease_id:
                namespace, identifier_part = disease_id.split(":", 1)
            else:
                namespace = "unknown"
                identifier_part = disease_id

            return EntityRef(
                name=record.get("name", str(identifier)),
                curie=disease_id,
                namespace=namespace,
                identifier=identifier_part,
            )

        except (EntityNotFoundError, AmbiguousIdentifierError):
            raise
        except Exception as e:
            logger.error(f"Error resolving disease {identifier}: {e}")
            raise EntityResolutionError(f"Failed to resolve disease: {e}")

    async def resolve_pathway(self, identifier: str | tuple[str, str]) -> EntityRef:
        """
        Resolve pathway identifier to EntityRef.

        Args:
            identifier: Pathway name, CURIE, or (namespace, id) tuple

        Returns:
            EntityRef for pathway

        Raises:
            EntityNotFoundError: If pathway not found
        """
        # Handle tuple format
        if isinstance(identifier, tuple):
            namespace, pathway_id = identifier
            return EntityRef(
                name=pathway_id,
                curie=f"{namespace}:{pathway_id}",
                namespace=namespace,
                identifier=pathway_id,
            )

        # Handle CURIE format
        elif ":" in identifier and not " " in identifier:
            # It's a CURIE like "reactome:R-HSA-109581"
            namespace, pathway_id = identifier.split(":", 1)
            return EntityRef(
                name=pathway_id,
                curie=identifier,
                namespace=namespace,
                identifier=pathway_id,
            )

        # Handle pathway name - need to search database
        else:
            # Search for pathway by name in database
            adapter = await get_adapter()

            try:
                result = await adapter.query("search_pathway_by_name", name=identifier)

                if not result.get("success") or not result.get("records"):
                    raise EntityNotFoundError(
                        entity=identifier,
                        suggestions=[],
                    )

                records = result["records"]

                # Check for ambiguous matches
                if len(records) > 1:
                    matches = [
                        {
                            "name": r.get("name", "Unknown"),
                            "curie": r.get("pathway_id", "unknown:unknown"),
                        }
                        for r in records
                    ]
                    raise AmbiguousIdentifierError(identifier=identifier, matches=matches)

                # Convert to EntityRef
                record = records[0]
                pathway_id = record.get("pathway_id", "unknown:unknown")

                # Extract namespace from CURIE
                if ":" in pathway_id:
                    namespace, identifier_part = pathway_id.split(":", 1)
                else:
                    namespace = "unknown"
                    identifier_part = pathway_id

                return EntityRef(
                    name=record.get("name", identifier),
                    curie=pathway_id,
                    namespace=namespace,
                    identifier=identifier_part,
                )

            except (EntityNotFoundError, AmbiguousIdentifierError):
                raise
            except Exception as e:
                logger.error(f"Error resolving pathway {identifier}: {e}")
                raise EntityResolutionError(f"Failed to resolve pathway: {e}")

    async def resolve_ontology_term(self, identifier: str | tuple[str, str]) -> OntologyTerm:
        """
        Resolve ontology term identifier to OntologyTerm.

        Args:
            identifier: Ontology term name, CURIE, or (namespace, id) tuple
                       (e.g., 'GO:0006915', ('go', 'GO:0006915'), 'apoptosis')

        Returns:
            OntologyTerm with standardized information

        Raises:
            EntityNotFoundError: If term not found
        """
        # Normalize identifier
        cache_key = self._make_ontology_cache_key(identifier)

        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            logger.debug(f"Ontology term resolved from cache: {identifier}")
            return OntologyTerm(**cached)

        # Resolve ontology term
        term = await self._resolve_ontology_from_backend(identifier)

        # Cache result
        await self.cache.set(cache_key, term.model_dump())

        return term

    async def _resolve_ontology_from_backend(
        self,
        identifier: str | tuple[str, str],
    ) -> OntologyTerm:
        """Resolve ontology term from backend (Neo4j or REST)."""
        adapter = await get_adapter()

        # Handle different identifier formats
        if isinstance(identifier, tuple):
            namespace, term_id = identifier
            query_params = {"namespace": namespace, "term_id": term_id}
        elif ":" in identifier:
            # CURIE format
            namespace, term_id = identifier.split(":", 1)
            query_params = {"namespace": namespace, "term_id": term_id}
        else:
            # Assume term name
            query_params = {"name": identifier}

        try:
            result = await adapter.query("get_ontology_term", **query_params)

            if not result.get("success") or not result.get("records"):
                # For now, return a basic OntologyTerm for unknown terms
                logger.warning(f"Ontology term not found: {identifier}, returning basic node")
                if isinstance(identifier, tuple):
                    namespace, term_id = identifier
                    return OntologyTerm(
                        name=term_id,
                        curie=f"{namespace}:{term_id}",
                        namespace=namespace,
                        depth=0,
                    )
                elif ":" in identifier:
                    namespace, term_id = identifier.split(":", 1)
                    return OntologyTerm(
                        name=term_id,
                        curie=identifier,
                        namespace=namespace,
                        depth=0,
                    )
                else:
                    return OntologyTerm(
                        name=identifier,
                        curie=f"unknown:{identifier}",
                        namespace="unknown",
                        depth=0,
                    )

            records = result["records"]

            # Check for ambiguous matches
            if len(records) > 1:
                matches = [
                    {
                        "name": r.get("name", "Unknown"),
                        "curie": f"{r.get('namespace', 'unknown')}:{r.get('id', 'unknown')}",
                    }
                    for r in records
                ]
                raise AmbiguousIdentifierError(identifier=str(identifier), matches=matches)

            # Convert to OntologyTerm
            record = records[0]
            return OntologyTerm(
                name=record.get("name", "Unknown"),
                curie=f"{record.get('namespace', 'go')}:{record.get('id', 'unknown')}",
                namespace=record.get("namespace", "go"),
                definition=record.get("definition"),
                depth=0,  # Will be set by hierarchy traversal
                relationship=None,  # Will be set by hierarchy traversal
            )

        except (EntityNotFoundError, AmbiguousIdentifierError):
            raise
        except Exception as e:
            logger.error(f"Error resolving ontology term {identifier}: {e}")
            raise EntityResolutionError(f"Failed to resolve ontology term: {e}")

    def _make_ontology_cache_key(self, identifier: str | tuple[str, str]) -> str:
        """Create cache key for ontology term identifier."""
        if isinstance(identifier, tuple):
            return self.cache.make_key(CACHE_PREFIX_ONTOLOGY, identifier[0], identifier[1])
        else:
            return self.cache.make_key(CACHE_PREFIX_ONTOLOGY, identifier)


# Singleton instance
_resolver: EntityResolver | None = None


def get_resolver() -> EntityResolver:
    """
    Get global entity resolver instance (singleton).

    Returns:
        EntityResolver instance
    """
    global _resolver

    if _resolver is None:
        _resolver = EntityResolver()

    return _resolver
