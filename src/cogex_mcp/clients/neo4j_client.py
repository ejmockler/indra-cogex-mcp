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

        # Set default min_evidence if not provided (for INDRA statement queries)
        if "min_evidence" not in params:
            params["min_evidence"] = 1

        # Set default min_belief if not provided (for INDRA statement queries)
        if "min_belief" not in params:
            params["min_belief"] = 0.0

        # Set default max_statements if not provided (for INDRA statement queries)
        if "max_statements" not in params:
            params["max_statements"] = 100

        # Set default ontology term resolution parameters (for get_ontology_term)
        if "term_id" not in params:
            params["term_id"] = None
        if "name" not in params:
            params["name"] = None
        if "namespace" not in params:
            params["namespace"] = None

        # Handle check_relationship dispatcher
        if query_name == "check_relationship" and "relationship_type" in params:
            query_name, params = self._dispatch_relationship_check(params)

        # Handle extract_subnetwork dispatcher and parameter transformation
        if query_name == "extract_subnetwork":
            query_name, params = self._dispatch_subnetwork_mode(params)

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

    def _dispatch_relationship_check(self, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Dispatch check_relationship query to appropriate specific relationship query.

        Args:
            params: Query parameters including relationship_type, entity1, entity2

        Returns:
            Tuple of (specific_query_name, transformed_params)

        Raises:
            ValueError: If relationship type is unknown or required parameters missing
        """
        relationship_type = params.get("relationship_type")
        entity1 = params.get("entity1")
        entity2 = params.get("entity2")

        if not relationship_type or not entity1 or not entity2:
            raise ValueError(
                f"Required parameters missing: relationship_type={relationship_type}, "
                f"entity1={entity1}, entity2={entity2}"
            )

        # Map relationship type to specific query and parameter names
        # Note: entity resolution should be done by the tool layer before calling adapter
        relationship_mappings = {
            "gene_in_pathway": ("is_gene_in_pathway", {"gene_id": entity1, "pathway_id": entity2}),
            "drug_target": ("is_drug_target", {"drug_id": entity1, "target_id": entity2}),
            "drug_indication": ("drug_has_indication", {"drug_id": entity1, "disease_id": entity2}),
            "drug_side_effect": ("is_side_effect_for_drug", {"drug_id": entity1, "side_effect_id": entity2}),
            "gene_disease": ("is_gene_associated_with_disease", {"gene_id": entity1, "disease_id": entity2}),
            "disease_phenotype": ("has_phenotype", {"disease_id": entity1, "phenotype_id": entity2}),
            "gene_phenotype": ("is_gene_associated_with_phenotype", {"gene_id": entity1, "phenotype_id": entity2}),
            "variant_association": ("is_variant_associated", {"variant_id": entity1, "disease_id": entity2}),
            "cell_line_mutation": ("is_mutated_in_cell_line", {"cell_line": entity1, "gene_id": entity2}),
            "cell_marker": ("is_cell_marker", {"gene_id": entity1, "cell_type": entity2}),
        }

        # Normalize relationship_type to lowercase with underscores
        # Handle both string and enum values
        type_str = str(relationship_type)
        # If it's an enum like "RelationshipType.GENE_IN_PATHWAY", extract the value
        if "." in type_str:
            type_str = type_str.split(".")[-1]
        normalized_type = type_str.lower().replace("-", "_")

        if normalized_type not in relationship_mappings:
            raise ValueError(
                f"Unknown relationship type: {relationship_type}. "
                f"Valid types: {list(relationship_mappings.keys())}"
            )

        query_name, transformed_params = relationship_mappings[normalized_type]

        # Preserve other parameters like limit, offset, timeout
        for key in ["limit", "offset", "response_format"]:
            if key in params and key not in transformed_params:
                transformed_params[key] = params[key]

        logger.debug(f"Dispatched check_relationship({relationship_type}) -> {query_name}")
        return query_name, transformed_params

    def _dispatch_subnetwork_mode(self, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Dispatch extract_subnetwork query to appropriate mode-specific query.

        Args:
            params: Query parameters including mode parameter

        Returns:
            Tuple of (specific_query_name, transformed_params)

        Raises:
            ValueError: If mode is unknown or required parameters missing
        """
        mode = params.get("mode", "direct")

        # Map mode to specific query names
        mode_mappings = {
            "direct": "indra_subnetwork",
            "mediated": "indra_mediated_subnetwork",
            "shared_upstream": "indra_subnetwork",  # TODO: Implement when backend available
            "shared_downstream": "indra_subnetwork",  # TODO: Implement when backend available
            "source_to_targets": "source_target_analysis",
        }

        # Normalize mode to lowercase
        normalized_mode = str(mode).lower()
        # Handle enum values like "SubnetworkMode.DIRECT"
        if "." in normalized_mode:
            normalized_mode = normalized_mode.split(".")[-1]

        if normalized_mode not in mode_mappings:
            raise ValueError(
                f"Unknown subnetwork mode: {mode}. "
                f"Valid modes: {list(mode_mappings.keys())}"
            )

        query_name = mode_mappings[normalized_mode]

        # Transform parameters (genes/source_gene/target_genes → gene_ids/source_gene_id/target_gene_ids)
        transformed_params = self._transform_subnetwork_params(params)

        # Remove mode parameter as it's not needed in the Cypher query
        transformed_params.pop("mode", None)

        logger.debug(f"Dispatched extract_subnetwork(mode={mode}) -> {query_name}")
        return query_name, transformed_params

    def _transform_subnetwork_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Transform SubnetworkQuery schema parameters to Neo4j query parameters.

        Maps schema field names to Cypher parameter names:
        - genes → gene_ids
        - source_gene → source_gene_id
        - target_genes → target_gene_ids
        - min_evidence_count → min_evidence
        - min_belief_score → min_belief
        - (max_statements stays the same)

        Args:
            params: Query parameters with schema field names

        Returns:
            Transformed parameters with Cypher parameter names
        """
        transformed = dict(params)

        # Transform parameter names
        if "genes" in transformed:
            transformed["gene_ids"] = transformed.pop("genes")

        if "source_gene" in transformed:
            transformed["source_gene_id"] = transformed.pop("source_gene")

        if "target_genes" in transformed:
            transformed["target_gene_ids"] = transformed.pop("target_genes")

        if "min_evidence_count" in transformed:
            transformed["min_evidence"] = transformed.pop("min_evidence_count")

        if "min_belief_score" in transformed:
            transformed["min_belief"] = transformed.pop("min_belief_score")

        logger.debug(f"Transformed extract_subnetwork params: {list(params.keys())} -> {list(transformed.keys())}")
        return transformed

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
        # Alias mappings for backward compatibility with test naming
        query_aliases = {
            # Tool 1: Gene/Feature query aliases - now handled as direct queries
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
                SKIP $offset LIMIT $limit
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
                SKIP $offset LIMIT $limit
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
            # ========================================================================
            # Tool 4: Drug Queries
            # ========================================================================
            "get_drug_by_name": """
                MATCH (drug:BioEntity)
                WHERE toLower(drug.name) CONTAINS toLower($name)
                  AND (
                    drug.id STARTS WITH 'chebi:' OR
                    drug.id STARTS WITH 'drugbank:' OR
                    drug.id STARTS WITH 'chembl:'
                  )
                  AND drug.obsolete = false
                RETURN
                  drug.name AS name,
                  drug.id AS id,
                  drug.type AS type
                LIMIT 10
            """,
            "drug_to_profile": """
                MATCH (drug:BioEntity)
                WHERE (drug.name = $drug OR drug.id = $drug)
                  AND (
                    drug.id STARTS WITH 'chebi:' OR
                    drug.id STARTS WITH 'drugbank:' OR
                    drug.id STARTS WITH 'chembl:'
                  )
                  AND drug.obsolete = false
                OPTIONAL MATCH (drug)-[:targets]->(target:BioEntity)
                WHERE target.id STARTS WITH 'hgnc:' AND target.obsolete = false
                OPTIONAL MATCH (drug)-[:has_indication]->(indication:BioEntity)
                WHERE (
                  indication.id STARTS WITH 'mesh:' OR
                  indication.id STARTS WITH 'DOID:' OR
                  indication.id STARTS WITH 'EFO:'
                )
                OPTIONAL MATCH (drug)-[:has_side_effect]->(effect:BioEntity)
                RETURN
                  drug.name AS drug_name,
                  drug.id AS drug_id,
                  drug.type AS drug_type,
                  collect(DISTINCT {name: target.name, id: target.id}) AS targets,
                  collect(DISTINCT {name: indication.name, id: indication.id}) AS indications,
                  collect(DISTINCT {name: effect.name, id: effect.id}) AS side_effects
                LIMIT 1
            """,
            "side_effect_to_drugs": """
                MATCH (effect:BioEntity)<-[:has_side_effect]-(drug:BioEntity)
                WHERE (effect.name = $side_effect OR effect.id = $side_effect)
                  AND (
                    drug.id STARTS WITH 'chebi:' OR
                    drug.id STARTS WITH 'drugbank:' OR
                    drug.id STARTS WITH 'chembl:'
                  )
                  AND drug.obsolete = false
                RETURN
                  drug.name AS drug_name,
                  drug.id AS drug_id,
                  drug.type AS drug_type,
                  effect.name AS side_effect_name,
                  effect.id AS side_effect_id
                SKIP $offset LIMIT $limit
            """,
            "get_targets_for_drug": """
                MATCH (drug:BioEntity)-[:targets]->(target:BioEntity)
                WHERE drug.id = $drug_id
                  AND target.id STARTS WITH 'hgnc:'
                  AND target.obsolete = false
                RETURN
                  target.name AS target,
                  target.id AS target_id,
                  'unknown' AS action_type,
                  1 AS evidence_count
                SKIP $offset LIMIT $limit
            """,
            "get_indications_for_drug": """
                MATCH (drug:BioEntity)-[:has_indication]->(disease:BioEntity)
                WHERE drug.id = $drug_id
                  AND (
                    disease.id STARTS WITH 'mesh:' OR
                    disease.id STARTS WITH 'DOID:' OR
                    disease.id STARTS WITH 'EFO:' OR
                    disease.id STARTS WITH 'mondo:'
                  )
                  AND disease.obsolete = false
                RETURN
                  disease.name AS disease,
                  disease.id AS disease_id,
                  'approved' AS indication_type,
                  4 AS max_phase
                SKIP $offset LIMIT $limit
            """,
            "get_side_effects_for_drug": """
                MATCH (drug:BioEntity)-[:has_side_effect]->(effect:BioEntity)
                WHERE drug.id = $drug_id
                RETURN
                  effect.name AS effect,
                  effect.id AS effect_id,
                  'common' AS frequency
                SKIP $offset LIMIT $limit
            """,
            "get_sensitive_cell_lines_for_drug": """
                MATCH (drug:BioEntity)-[:sensitive_to]-(cell_line:BioEntity)
                WHERE drug.id = $drug_id
                  AND cell_line.id STARTS WITH 'ccle:'
                RETURN
                  cell_line.name AS cell_line,
                  0.5 AS sensitivity_score
                SKIP $offset LIMIT $limit
            """,
            # ========================================================================
            # Tool 5: Disease/Phenotype Queries
            # ========================================================================
            "get_disease_by_name": """
                MATCH (disease:BioEntity)
                WHERE toLower(disease.name) CONTAINS toLower($name)
                  AND (
                    disease.id STARTS WITH 'mesh:' OR
                    disease.id STARTS WITH 'DOID:' OR
                    disease.id STARTS WITH 'EFO:' OR
                    disease.id STARTS WITH 'mondo:'
                  )
                  AND disease.obsolete = false
                RETURN
                  disease.name AS name,
                  disease.id AS id,
                  disease.type AS type
                LIMIT 10
            """,
            "disease_to_mechanisms": """
                MATCH (disease:BioEntity)
                WHERE (disease.name = $disease OR disease.id = $disease)
                  AND (
                    disease.id STARTS WITH 'mesh:' OR
                    disease.id STARTS WITH 'DOID:' OR
                    disease.id STARTS WITH 'EFO:' OR
                    disease.id STARTS WITH 'mondo:'
                  )
                  AND disease.obsolete = false
                OPTIONAL MATCH (gene:BioEntity)-[:gene_disease_association]->(disease)
                WHERE gene.id STARTS WITH 'hgnc:' AND gene.obsolete = false
                OPTIONAL MATCH (disease)-[:has_phenotype]->(phenotype:BioEntity)
                WHERE phenotype.id STARTS WITH 'HP:'
                OPTIONAL MATCH (drug:BioEntity)-[:has_indication]->(disease)
                WHERE (
                  drug.id STARTS WITH 'chebi:' OR
                  drug.id STARTS WITH 'drugbank:' OR
                  drug.id STARTS WITH 'chembl:'
                )
                RETURN
                  disease.name AS disease_name,
                  disease.id AS disease_id,
                  disease.type AS disease_type,
                  collect(DISTINCT {name: gene.name, id: gene.id}) AS genes,
                  collect(DISTINCT {name: phenotype.name, id: phenotype.id}) AS phenotypes,
                  collect(DISTINCT {name: drug.name, id: drug.id}) AS drugs
                LIMIT 1
            """,
            "phenotype_to_diseases": """
                MATCH (phenotype:BioEntity)<-[:has_phenotype]-(disease:BioEntity)
                WHERE (phenotype.name = $phenotype OR phenotype.id = $phenotype)
                  AND phenotype.id STARTS WITH 'HP:'
                  AND (
                    disease.id STARTS WITH 'mesh:' OR
                    disease.id STARTS WITH 'DOID:' OR
                    disease.id STARTS WITH 'EFO:' OR
                    disease.id STARTS WITH 'mondo:'
                  )
                  AND disease.obsolete = false
                RETURN
                  disease.name AS disease_name,
                  disease.id AS disease_id,
                  disease.type AS disease_type,
                  phenotype.name AS phenotype_name,
                  phenotype.id AS phenotype_id
                SKIP $offset LIMIT $limit
            """,
            "check_phenotype": """
                MATCH (disease:BioEntity)
                WHERE (disease.name = $disease OR disease.id = $disease)
                  AND (
                    disease.id STARTS WITH 'mesh:' OR
                    disease.id STARTS WITH 'DOID:' OR
                    disease.id STARTS WITH 'EFO:' OR
                    disease.id STARTS WITH 'mondo:'
                  )
                  AND disease.obsolete = false
                OPTIONAL MATCH (disease)-[:has_phenotype]->(phenotype:BioEntity)
                WHERE (phenotype.name = $phenotype OR phenotype.id = $phenotype)
                  AND phenotype.id STARTS WITH 'HP:'
                RETURN
                  disease.name AS disease_name,
                  disease.id AS disease_id,
                  phenotype.name AS phenotype_name,
                  phenotype.id AS phenotype_id,
                  CASE WHEN phenotype IS NOT NULL THEN true ELSE false END AS has_phenotype
                LIMIT 1
            """,
            "get_genes_for_disease": """
                MATCH (gene:BioEntity)-[:gene_disease_association]->(disease:BioEntity)
                WHERE disease.id = $disease_id
                  AND gene.id STARTS WITH 'hgnc:'
                  AND gene.obsolete = false
                RETURN
                  gene.name AS gene,
                  gene.id AS gene_id,
                  0.5 AS score,
                  1 AS evidence_count,
                  ['disgenet'] AS sources
                SKIP $offset LIMIT $limit
            """,
            "get_variants_for_disease": """
                MATCH (disease:BioEntity)-[:has_variant]->(variant:BioEntity)-[:affects]->(gene:BioEntity)
                WHERE disease.id = $disease_id
                  AND variant.id STARTS WITH 'rs'
                  AND gene.id STARTS WITH 'hgnc:'
                  AND gene.obsolete = false
                RETURN
                  variant.id AS rsid,
                  gene.name AS gene,
                  gene.id AS gene_id,
                  variant.p_value AS p_value,
                  variant.odds_ratio AS odds_ratio,
                  variant.trait AS trait
                SKIP $offset LIMIT $limit
            """,
            "get_phenotypes_for_disease": """
                MATCH (disease:BioEntity)-[:has_phenotype]->(phenotype:BioEntity)
                WHERE disease.id = $disease_id
                  AND phenotype.id STARTS WITH 'HP:'
                RETURN
                  phenotype.name AS phenotype,
                  phenotype.id AS phenotype_id,
                  'common' AS frequency,
                  1 AS evidence_count
                SKIP $offset LIMIT $limit
            """,
            "get_drugs_for_indication": """
                MATCH (drug:BioEntity)-[:has_indication]->(disease:BioEntity)
                WHERE disease.id = $disease_id
                  AND (
                    drug.id STARTS WITH 'chebi:' OR
                    drug.id STARTS WITH 'drugbank:' OR
                    drug.id STARTS WITH 'chembl:'
                  )
                  AND drug.obsolete = false
                RETURN
                  drug.name AS drug,
                  drug.id AS drug_id,
                  'approved' AS indication_type,
                  4 AS max_phase,
                  'marketed' AS status
                SKIP $offset LIMIT $limit
            """,
            # ========================================================================
            # Tool 6: Pathway Queries
            # CORRECTED: Uses 'haspart' relationship (Pathway->Gene direction)
            # ========================================================================
            "search_pathway_by_name": """
                // Search for pathways by name (fuzzy matching)
                MATCH (p:BioEntity)
                WHERE (
                    p.name CONTAINS $name OR
                    toLower(p.name) CONTAINS toLower($name)
                  )
                  AND (
                    p.id STARTS WITH 'reactome:' OR
                    p.id STARTS WITH 'wikipathways:' OR
                    p.id STARTS WITH 'kegg.pathway:'
                  )
                  AND p.obsolete = false
                RETURN
                  p.name AS name,
                  p.id AS pathway_id
                ORDER BY size(p.name) ASC
                LIMIT 10
            """,
            "search_disease_by_name": """
                // Search for diseases by name (case-insensitive matching)
                MATCH (d:BioEntity)
                WHERE toLower(d.name) CONTAINS toLower($name)
                  AND (
                    d.id STARTS WITH 'doid:' OR
                    d.id STARTS WITH 'mondo:' OR
                    d.id STARTS WITH 'mesh:' OR
                    d.id STARTS WITH 'hp:' OR
                    d.id STARTS WITH 'efo:'
                  )
                  AND (d.obsolete = false OR d.obsolete IS NULL)
                  AND d.name IS NOT NULL
                RETURN
                  d.name AS name,
                  d.id AS disease_id,
                  split(d.id, ':')[0] AS namespace
                ORDER BY
                  CASE WHEN toLower(d.name) = toLower($name) THEN 0 ELSE 1 END,
                  size(d.name) ASC
                LIMIT 10
            """,
            "search_drug_by_name": """
                // Search for drugs by name (case-insensitive matching)
                MATCH (d:BioEntity)
                WHERE toLower(d.name) CONTAINS toLower($name)
                  AND (
                    d.id STARTS WITH 'chebi:' OR
                    d.id STARTS WITH 'chembl:' OR
                    d.id STARTS WITH 'pubchem:' OR
                    d.id STARTS WITH 'drugbank:'
                  )
                  AND (d.obsolete = false OR d.obsolete IS NULL)
                  AND d.name IS NOT NULL
                RETURN
                  d.name AS name,
                  d.id AS drug_id,
                  split(d.id, ':')[0] AS namespace
                ORDER BY
                  CASE WHEN toLower(d.name) = toLower($name) THEN 0 ELSE 1 END,
                  size(d.name) ASC
                LIMIT 10
            """,
            "get_genes_in_pathway": """
                // CORRECTED: haspart goes FROM pathway TO gene
                MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
                WHERE p.id = $pathway_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND (
                    p.id STARTS WITH 'reactome:' OR
                    p.id STARTS WITH 'wikipathways:' OR
                    p.id STARTS WITH 'kegg.pathway:'
                  )
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type
                SKIP $offset LIMIT $limit
            """,
            "get_pathways_for_gene": """
                // CORRECTED: haspart goes FROM pathway TO gene
                MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
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
                  p.type AS pathway_type
                SKIP $offset LIMIT $limit
            """,
            "get_shared_pathways_for_genes": """
                // CORRECTED: haspart goes FROM pathway TO gene
                MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
                WHERE g.id IN $gene_ids
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND (
                    p.id STARTS WITH 'reactome:' OR
                    p.id STARTS WITH 'wikipathways:' OR
                    p.id STARTS WITH 'kegg.pathway:'
                  )
                WITH p, collect(DISTINCT g.id) AS genes
                WHERE size(genes) = size($gene_ids)
                RETURN
                  p.name AS pathway,
                  p.id AS pathway_id,
                  p.type AS pathway_type
                SKIP $offset LIMIT $limit
            """,
            "is_gene_in_pathway": """
                // CORRECTED: haspart goes FROM pathway TO gene
                MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
                WHERE g.id = $gene_id
                  AND p.id = $pathway_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  count(*) > 0 AS is_member,
                  p.name AS pathway,
                  p.id AS pathway_id
                LIMIT 1
            """,
            # ========================================================================
            # Tool 7: Cell Line Queries
            # CORRECTED: Uses direct 'mutated_in' relationship (Gene->CellLine)
            # Note: Cell lines use CCLE IDs (e.g., ccle:A549_LUNG)
            # ========================================================================
            "get_mutations_for_cell_line": """
                // CORRECTED: Direct Gene -[:mutated_in]-> CellLine relationship
                // No intermediate mutation nodes, simpler than expected
                // Support both exact match (ccle:A549_LUNG) and partial (A549)
                MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
                WHERE (c.id = $cell_line OR c.id CONTAINS $cell_line)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND c.id STARTS WITH 'ccle:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  'mutation' AS mutation_type,
                  null AS protein_change
                SKIP $offset LIMIT $limit
            """,
            "get_copy_number_for_cell_line": """
                // CORRECTED: Direct Gene -[:copy_number_altered_in]-> CellLine
                // Support both exact match and partial match
                MATCH (g:BioEntity)-[:copy_number_altered_in]->(c:BioEntity)
                WHERE (c.id = $cell_line OR c.id CONTAINS $cell_line)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND c.id STARTS WITH 'ccle:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  'altered' AS copy_number
                LIMIT $limit
            """,
            "get_dependencies_for_cell_line": """
                // Gene dependency data may not be in Neo4j
                // Placeholder query - may need REST API fallback
                MATCH (g:BioEntity)-[:codependent_with]-(other:BioEntity)
                WHERE g.id = $cell_line
                  AND other.id STARTS WITH 'hgnc:'
                  AND other.obsolete = false
                RETURN
                  other.name AS gene,
                  other.id AS gene_id
                LIMIT $limit
            """,
            "get_expression_for_cell_line": """
                // Expression data may not be in Neo4j
                // Placeholder query - may need REST API fallback
                MATCH (c:BioEntity)-[:expresses]->(g:BioEntity)
                WHERE c.id = $cell_line
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS gene,
                  g.id AS gene_id
                LIMIT $limit
            """,
            "get_cell_lines_for_mutation": """
                // CORRECTED: Direct Gene -[:mutated_in]-> CellLine
                MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND c.id STARTS WITH 'ccle:'
                RETURN
                  c.name AS cell_line,
                  c.id AS ccle_id
                SKIP $offset LIMIT $limit
            """,
            "is_mutated_in_cell_line": """
                // CORRECTED: Direct Gene -[:mutated_in]-> CellLine
                // Support both exact match and partial match
                MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
                WHERE g.id = $gene_id
                  AND (c.id = $cell_line OR c.id CONTAINS $cell_line)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  count(*) > 0 AS result
                LIMIT 1
            """,
            # ========================================================================
            # Tool 8: Clinical Trials Queries
            # ========================================================================
            "get_trials_for_drug": """
                MATCH (d:BioEntity)-[:tested_in]->(t:BioEntity)
                WHERE d.id = $drug_id
                  AND t.id STARTS WITH 'clinicaltrials:'
                RETURN
                  split(t.id, ':')[1] AS nct_id,
                  t.name AS title,
                  null AS phase,
                  null AS status,
                  [] AS conditions,
                  [] AS interventions
                SKIP $offset LIMIT $limit
            """,
            "get_trials_for_disease": """
                MATCH (dis:BioEntity)-[:has_trial]->(t:BioEntity)
                WHERE dis.id = $disease_id
                  AND t.id STARTS WITH 'clinicaltrials:'
                RETURN
                  split(t.id, ':')[1] AS nct_id,
                  t.name AS title,
                  null AS phase,
                  null AS status,
                  [] AS conditions,
                  [] AS interventions
                SKIP $offset LIMIT $limit
            """,
            "get_trial_by_id": """
                MATCH (t:BioEntity)
                WHERE t.id = 'clinicaltrials:' + $nct_id
                RETURN
                  split(t.id, ':')[1] AS nct_id,
                  t.name AS title,
                  null AS phase,
                  null AS status,
                  null AS start_date,
                  null AS completion_date,
                  [] AS conditions,
                  [] AS interventions
                LIMIT 1
            """,
            # ========================================================================
            # Tool 9: Literature Queries
            # ========================================================================
            "get_statements_for_paper": """
                MATCH (pub:Publication)-[:has_statement]->(s:Statement)
                WHERE pub.pmid = $pmid
                RETURN
                  s.hash AS hash,
                  s.type AS type,
                  s.subj_name AS subj_name,
                  s.subj_id AS subj_id,
                  s.obj_name AS obj_name,
                  s.obj_id AS obj_id,
                  s.belief AS belief
                SKIP $offset LIMIT $limit
            """,
            "get_evidences_for_stmt_hash": """
                MATCH (s:Statement)-[:has_evidence]->(e:Evidence)
                WHERE s.hash = $stmt_hash
                RETURN
                  e.text AS text,
                  e.pmid AS pmid,
                  e.source_api AS source_api
                SKIP $offset LIMIT $limit
            """,
            "get_evidence_for_mesh": """
                MATCH (pub:Publication)-[:has_mesh_term]->(m:MeshTerm)
                WHERE m.term IN $mesh_terms
                RETURN
                  pub.pmid AS pmid,
                  pub.title AS title,
                  pub.journal AS journal,
                  pub.year AS year
                SKIP $offset LIMIT $limit
            """,
            "get_stmts_for_stmt_hashes": """
                MATCH (s:Statement)
                WHERE s.hash IN $stmt_hashes
                RETURN
                  s.hash AS hash,
                  s.type AS type,
                  s.subj_name AS subj_name,
                  s.subj_id AS subj_id,
                  s.obj_name AS obj_name,
                  s.obj_id AS obj_id,
                  s.belief AS belief
                LIMIT 100
            """,
            # ========================================================================
            # Tool 10: Variant Queries
            # CORRECTED: Uses 'variant_gene_association' (Variant->Gene direction)
            # Note: Variants use dbsnp: namespace (e.g., dbsnp:rs7412)
            # ========================================================================
            "get_variants_for_gene": """
                // CORRECTED: Variant -[:variant_gene_association]-> Gene
                MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND v.id STARTS WITH 'dbsnp:'
                RETURN
                  v.id AS rsid,
                  v.name AS variant_name,
                  null AS chromosome,
                  null AS position,
                  null AS ref_allele,
                  null AS alt_allele,
                  null AS p_value
                SKIP $offset LIMIT $limit
            """,
            "get_variants_for_disease": """
                // CORRECTED: Disease -[:variant_disease_association]-> Variant
                MATCH (d:BioEntity)-[:variant_disease_association]->(v:BioEntity)
                WHERE d.id = $disease_id
                  AND v.id STARTS WITH 'dbsnp:'
                RETURN
                  v.id AS rsid,
                  v.name AS variant_name,
                  null AS chromosome,
                  null AS position,
                  null AS ref_allele,
                  null AS alt_allele,
                  null AS p_value,
                  null AS trait
                SKIP $offset LIMIT $limit
            """,
            "get_variants_for_phenotype": """
                // CORRECTED: Phenotype -[:variant_phenotype_association]-> Variant
                MATCH (ph:BioEntity)-[:variant_phenotype_association]->(v:BioEntity)
                WHERE ph.id = $phenotype_id
                  AND v.id STARTS WITH 'dbsnp:'
                RETURN
                  v.id AS rsid,
                  v.name AS variant_name,
                  null AS chromosome,
                  null AS position,
                  null AS p_value,
                  null AS trait
                SKIP $offset LIMIT $limit
            """,
            "get_genes_for_variant": """
                // CORRECTED: Variant -[:variant_gene_association]-> Gene
                MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
                WHERE v.id = $variant_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND v.id STARTS WITH 'dbsnp:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type
                SKIP $offset LIMIT $limit
            """,
            "get_phenotypes_for_variant": """
                // CORRECTED: Variant -[:variant_phenotype_association]-> Phenotype
                MATCH (v:BioEntity)-[:variant_phenotype_association]->(ph:BioEntity)
                WHERE v.id = $variant_id
                  AND v.id STARTS WITH 'dbsnp:'
                  AND ph.id STARTS WITH 'HP:'
                RETURN
                  ph.name AS phenotype,
                  ph.id AS phenotype_id,
                  ph.type AS type
                SKIP $offset LIMIT $limit
            """,
            "is_variant_associated": """
                // CORRECTED: Disease -[:variant_disease_association]-> Variant
                MATCH (d:BioEntity)-[:variant_disease_association]->(v:BioEntity)
                WHERE d.id = $disease_id
                  AND v.id = $variant_id
                  AND v.id STARTS WITH 'dbsnp:'
                RETURN
                  count(*) > 0 AS is_associated,
                  null AS p_value
                LIMIT 1
            """,
            # ========================================================================
            # Tool 11: Identifier Resolution
            # ========================================================================
            "symbol_to_hgnc": """
                MATCH (g:BioEntity)
                WHERE g.name IN $symbols
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN g.name AS symbol, g.id AS hgnc_id
            """,
            "hgnc_to_symbol": """
                MATCH (g:BioEntity)
                WHERE g.id IN [id IN $hgnc_ids | CASE WHEN id STARTS WITH 'hgnc:' THEN id ELSE 'hgnc:' + id END]
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN g.id AS hgnc_id, g.name AS symbol
            """,
            "hgnc_to_uniprot": """
                MATCH (g:BioEntity)-[:xref]-(u:BioEntity)
                WHERE g.id IN [id IN $hgnc_ids | CASE WHEN id STARTS WITH 'hgnc:' THEN id ELSE 'hgnc:' + id END]
                  AND g.obsolete = false
                  AND u.id STARTS WITH 'uniprot:'
                RETURN g.id AS hgnc_id, collect(DISTINCT u.id) AS uniprot_ids
            """,
            "map_identifiers": """
                MATCH (source:BioEntity)
                WHERE source.id IN $identifiers
                OPTIONAL MATCH (source)-[:xref]-(target:BioEntity)
                WHERE target.id STARTS WITH ($to_namespace + ':')
                RETURN source.id AS source_id, collect(DISTINCT target.id) AS target_ids
            """,
            # ========================================================================
            # Tool 12: Relationship Checking (10 types)
            # ========================================================================
            "is_drug_target": """
                // Check both [:targets] and [:indra_rel] for drug-target relationships
                MATCH (d:BioEntity), (t:BioEntity)
                WHERE d.id = $drug_id
                  AND t.id = $target_id
                  AND (d.id STARTS WITH 'chebi:' OR d.id STARTS WITH 'chembl:' OR d.id STARTS WITH 'drugbank:')
                  AND t.id STARTS WITH 'hgnc:'
                OPTIONAL MATCH path1 = (d)-[:targets]->(t)
                OPTIONAL MATCH path2 = (d)-[r:indra_rel]-(t)
                WHERE r.stmt_type IN ['Inhibition', 'Activation', 'IncreaseAmount', 'DecreaseAmount']
                WITH path1, path2
                RETURN (path1 IS NOT NULL OR path2 IS NOT NULL) AS result
            """,
            "drug_has_indication": """
                MATCH (d:BioEntity)-[:has_indication]->(dis:BioEntity)
                WHERE d.id = $drug_id
                  AND dis.id = $disease_id
                  AND (d.id STARTS WITH 'chebi:' OR d.id STARTS WITH 'chembl:' OR d.id STARTS WITH 'drugbank:')
                RETURN COUNT(*) > 0 AS result
            """,
            "is_side_effect_for_drug": """
                MATCH (d:BioEntity)-[:has_side_effect]->(se:BioEntity)
                WHERE d.id = $drug_id
                  AND (se.name = $side_effect_id OR se.id = $side_effect_id)
                  AND (d.id STARTS WITH 'chebi:' OR d.id STARTS WITH 'chembl:' OR d.id STARTS WITH 'drugbank:')
                RETURN COUNT(*) > 0 AS result
            """,
            "is_gene_associated_with_disease": """
                // Check both [:gene_disease_association] and [:indra_rel] for gene-disease relationships
                MATCH (g:BioEntity), (d:BioEntity)
                WHERE g.id = $gene_id
                  AND d.id = $disease_id
                  AND g.id STARTS WITH 'hgnc:'
                OPTIONAL MATCH path1 = (g)-[:gene_disease_association]->(d)
                OPTIONAL MATCH path2 = (g)-[r:indra_rel]-(d)
                WITH path1, path2
                RETURN (path1 IS NOT NULL OR path2 IS NOT NULL) AS result
            """,
            "has_phenotype": """
                MATCH (d:BioEntity)-[:has_phenotype]->(p:BioEntity)
                WHERE d.id = $disease_id
                  AND (p.id = $phenotype_id OR p.name = $phenotype_id)
                  AND p.id STARTS WITH 'HP:'
                RETURN COUNT(*) > 0 AS result
            """,
            "is_gene_associated_with_phenotype": """
                MATCH (g:BioEntity)-[:associated_with]->(p:BioEntity)
                WHERE g.id = $gene_id
                  AND (p.id = $phenotype_id OR p.name = $phenotype_id)
                  AND g.id STARTS WITH 'hgnc:'
                  AND p.id STARTS WITH 'HP:'
                RETURN COUNT(*) > 0 AS result
            """,
            # ========================================================================
            # Tool 13: Ontology Hierarchy
            # ========================================================================
            "get_ontology_term": """
                MATCH (term:BioEntity)
                WHERE term.obsolete = false
                  AND (
                    ($term_id IS NOT NULL AND term.id = $term_id) OR
                    ($name IS NOT NULL AND term.name = $name) OR
                    ($namespace IS NOT NULL AND $term_id IS NOT NULL AND term.id = $namespace + ':' + $term_id)
                  )
                  AND (
                    term.id STARTS WITH 'GO:' OR
                    term.id STARTS WITH 'HP:' OR
                    term.id STARTS WITH 'MONDO:' OR
                    term.id STARTS WITH 'DOID:' OR
                    term.id STARTS WITH 'EFO:' OR
                    term.id STARTS WITH 'UBERON:' OR
                    term.id STARTS WITH 'CL:' OR
                    term.id STARTS WITH 'CHEBI:'
                  )
                RETURN
                  term.name AS name,
                  term.id AS id,
                  split(term.id, ':')[0] AS namespace,
                  term.definition AS definition
                LIMIT 10
            """,
            "get_ontology_parents": """
                MATCH path = (child:BioEntity)-[:isa|part_of*1..10]->(parent:BioEntity)
                WHERE child.id = $term_id
                  AND child.obsolete = false
                  AND parent.obsolete = false
                  AND LENGTH(path) <= $max_depth
                RETURN
                  parent.name AS name,
                  parent.id AS curie,
                  LENGTH(path) AS depth,
                  type(last(relationships(path))) AS relationship
                ORDER BY depth
            """,
            "get_ontology_children": """
                MATCH path = (parent:BioEntity)<-[:isa|part_of*1..10]-(child:BioEntity)
                WHERE parent.id = $term_id
                  AND parent.obsolete = false
                  AND child.obsolete = false
                  AND LENGTH(path) <= $max_depth
                RETURN
                  child.name AS name,
                  child.id AS curie,
                  LENGTH(path) AS depth,
                  type(last(relationships(path))) AS relationship
                ORDER BY depth
            """,
            "get_ontology_hierarchy": """
                MATCH (root:BioEntity)
                WHERE root.id = $term_id
                  AND root.obsolete = false
                OPTIONAL MATCH parent_path = (root)-[:isa|part_of*1..10]->(parent:BioEntity)
                WHERE parent.obsolete = false
                  AND LENGTH(parent_path) <= $max_depth
                OPTIONAL MATCH child_path = (root)<-[:isa|part_of*1..10]-(child:BioEntity)
                WHERE child.obsolete = false
                  AND LENGTH(child_path) <= $max_depth
                RETURN
                  root.name AS root_name,
                  root.id AS root_id,
                  collect(DISTINCT {name: parent.name, curie: parent.id, depth: LENGTH(parent_path), relationship: type(last(relationships(parent_path)))}) AS parents,
                  collect(DISTINCT {name: child.name, curie: child.id, depth: LENGTH(child_path), relationship: type(last(relationships(child_path)))}) AS children
            """,
            # ========================================================================
            # Tool 14: Cell Markers
            # ========================================================================
            "get_markers_for_cell_type": """
                MATCH (g:BioEntity)-[:marker_for]->(ct:BioEntity)
                WHERE (ct.name = $cell_type OR ct.id CONTAINS $cell_type)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  'canonical' AS marker_type,
                  'CellMarker' AS evidence
                SKIP $offset LIMIT $limit
            """,
            "get_cell_types_for_marker": """
                MATCH (g:BioEntity)-[:marker_for]->(ct:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  ct.name AS cell_type,
                  ct.id AS cell_type_id,
                  'unknown' AS tissue,
                  'human' AS species
                SKIP $offset LIMIT $limit
            """,
            "is_cell_marker": """
                MATCH (g:BioEntity)-[:marker_for]->(ct:BioEntity)
                WHERE g.id = $gene_id
                  AND (ct.name = $cell_type OR ct.id CONTAINS $cell_type)
                  AND g.id STARTS WITH 'hgnc:'
                RETURN COUNT(*) > 0 AS result
            """,
            # ========================================================================
            # Tool 16: Protein Functions  
            # Implemented using GO term annotations (properties don't exist in Neo4j)
            # ========================================================================
            "get_enzyme_activities": """
                // Get protein activities from GO term annotations
                MATCH (g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                OPTIONAL MATCH (g)-[r]->(go:BioEntity)
                WHERE go.id STARTS WITH 'GO:'
                  AND (
                    // Kinase GO terms
                    go.id IN ['GO:0016301', 'GO:0004672', 'GO:0016773'] OR
                    go.name CONTAINS 'kinase activity' OR
                    // Phosphatase GO terms
                    go.id IN ['GO:0016791', 'GO:0004721', 'GO:0008138'] OR
                    go.name CONTAINS 'phosphatase activity' OR
                    // Transcription factor GO terms
                    go.id IN ['GO:0003700', 'GO:0000981', 'GO:0001227'] OR
                    go.name CONTAINS 'DNA-binding transcription factor activity'
                  )
                WITH g, collect(DISTINCT go) AS go_terms
                UNWIND go_terms AS go_term
                WITH g, go_term,
                  CASE
                    WHEN go_term.id IN ['GO:0016301', 'GO:0004672', 'GO:0016773']
                      OR go_term.name CONTAINS 'kinase activity'
                    THEN 'kinase'
                    WHEN go_term.id IN ['GO:0016791', 'GO:0004721', 'GO:0008138']
                      OR go_term.name CONTAINS 'phosphatase activity'
                    THEN 'phosphatase'
                    WHEN go_term.id IN ['GO:0003700', 'GO:0000981', 'GO:0001227']
                      OR go_term.name CONTAINS 'DNA-binding transcription factor activity'
                    THEN 'transcription_factor'
                    ELSE null
                  END AS activity
                WHERE activity IS NOT NULL
                RETURN DISTINCT
                  activity AS activity,
                  null AS ec_number,
                  'high' AS confidence
            """,
            "get_genes_for_activity": """
                // Find genes with specific activity using GO terms
                MATCH (g:BioEntity)-[r]->(go:BioEntity)
                WHERE g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND go.id STARTS WITH 'GO:'
                  AND (
                    // Kinase activity
                    (toLower($activity) = 'kinase' AND (
                      go.id IN ['GO:0016301', 'GO:0004672', 'GO:0016773'] OR
                      go.name CONTAINS 'kinase activity'
                    )) OR
                    // Phosphatase activity
                    (toLower($activity) = 'phosphatase' AND (
                      go.id IN ['GO:0016791', 'GO:0004721', 'GO:0008138'] OR
                      go.name CONTAINS 'phosphatase activity'
                    )) OR
                    // Transcription factor
                    (toLower($activity) CONTAINS 'transcription' AND (
                      go.id IN ['GO:0003700', 'GO:0000981', 'GO:0001227'] OR
                      go.name CONTAINS 'DNA-binding transcription factor activity'
                    ))
                  )
                RETURN DISTINCT
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type
                SKIP $offset LIMIT $limit
            """,
            "is_kinase": """
                // Check if gene is a kinase using GO terms
                MATCH (g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                OPTIONAL MATCH (g)-[r]->(go:BioEntity)
                WHERE go.id STARTS WITH 'GO:'
                  AND (
                    go.id IN ['GO:0016301', 'GO:0004672', 'GO:0016773'] OR
                    go.name CONTAINS 'kinase activity'
                  )
                RETURN count(go) > 0 AS result
            """,
            "is_phosphatase": """
                // Check if gene is a phosphatase using GO terms
                MATCH (g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                OPTIONAL MATCH (g)-[r]->(go:BioEntity)
                WHERE go.id STARTS WITH 'GO:'
                  AND (
                    go.id IN ['GO:0016791', 'GO:0004721', 'GO:0008138'] OR
                    go.name CONTAINS 'phosphatase activity'
                  )
                RETURN count(go) > 0 AS result
            """,
            "is_transcription_factor": """
                // Check if gene is a transcription factor using GO terms
                MATCH (g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                OPTIONAL MATCH (g)-[r]->(go:BioEntity)
                WHERE go.id STARTS WITH 'GO:'
                  AND (
                    go.id IN ['GO:0003700', 'GO:0000981', 'GO:0001227'] OR
                    go.name CONTAINS 'DNA-binding transcription factor activity'
                  )
                RETURN count(go) > 0 AS result
            """,
            "has_enzyme_activity": """
                // Generic activity check using GO terms
                MATCH (g:BioEntity)
                WHERE g.id = $gene_id
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                OPTIONAL MATCH (g)-[r]->(go:BioEntity)
                WHERE go.id STARTS WITH 'GO:'
                  AND (
                    CASE
                      WHEN toLower($activity) = 'kinase' THEN (
                        go.id IN ['GO:0016301', 'GO:0004672', 'GO:0016773'] OR
                        go.name CONTAINS 'kinase activity'
                      )
                      WHEN toLower($activity) = 'phosphatase' THEN (
                        go.id IN ['GO:0016791', 'GO:0004721', 'GO:0008138'] OR
                        go.name CONTAINS 'phosphatase activity'
                      )
                      WHEN toLower($activity) CONTAINS 'transcription' THEN (
                        go.id IN ['GO:0003700', 'GO:0000981', 'GO:0001227'] OR
                        go.name CONTAINS 'DNA-binding transcription factor activity'
                      )
                      ELSE false
                    END
                  )
                RETURN count(go) > 0 AS result
            """,
            # ========================================================================
            # Tool 1: Missing queries - domain_to_genes and phenotype_to_genes
            # ========================================================================
            "domain_to_genes": """
                MATCH (g:BioEntity)-[:has_domain]->(d:BioEntity)
                WHERE (d.name = $domain OR d.id CONTAINS $domain)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND (
                    d.id STARTS WITH 'interpro:' OR
                    d.id STARTS WITH 'pfam:' OR
                    d.id STARTS WITH 'prosite:'
                  )
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type,
                  d.name AS domain_name,
                  d.id AS domain_id
                SKIP $offset LIMIT $limit
            """,
            "phenotype_to_genes": """
                MATCH (g:BioEntity)-[:associated_with]->(p:BioEntity)
                WHERE (p.id = $phenotype OR p.name = $phenotype)
                  AND p.id STARTS WITH 'HP:'
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type,
                  p.name AS phenotype_name,
                  p.id AS phenotype_id
                SKIP $offset LIMIT $limit
            """,
            # ========================================================================
            # Tool 2: Subnetwork extraction - INDRA relationship queries
            # CORRECTED: Uses indra_rel relationships, not Statement nodes
            # ========================================================================
            "extract_subnetwork": """
                // Direct mode: Find direct INDRA relationships between specified genes
                MATCH (g1:BioEntity)-[r:indra_rel]-(g2:BioEntity)
                WHERE g1.id IN $gene_ids
                  AND g2.id IN $gene_ids
                  AND g1.id <> g2.id
                  AND r.evidence_count >= $min_evidence
                  AND r.belief >= $min_belief
                  AND g1.id STARTS WITH 'hgnc:'
                  AND g2.id STARTS WITH 'hgnc:'
                WITH g1, g2, r
                ORDER BY r.belief DESC, r.evidence_count DESC
                LIMIT $max_statements
                RETURN
                  r.stmt_hash AS hash,
                  r.stmt_type AS type,
                  g1.name AS subj_name,
                  g1.id AS subj_id,
                  g2.name AS obj_name,
                  g2.id AS obj_id,
                  null AS residue,
                  null AS position,
                  r.evidence_count AS evidence_count,
                  r.belief AS belief,
                  r.source_counts AS sources
            """,
            "indra_subnetwork": """
                // Direct edges between genes via indra_rel relationships
                MATCH (g1:BioEntity)-[r:indra_rel]-(g2:BioEntity)
                WHERE g1.id IN $gene_ids
                  AND g2.id IN $gene_ids
                  AND g1.id <> g2.id
                  AND r.evidence_count >= $min_evidence
                  AND r.belief >= $min_belief
                  AND g1.id STARTS WITH 'hgnc:'
                  AND g2.id STARTS WITH 'hgnc:'
                WITH g1, g2, r
                ORDER BY r.belief DESC, r.evidence_count DESC
                LIMIT $max_statements
                RETURN
                  r.stmt_hash AS hash,
                  r.stmt_type AS type,
                  g1.name AS subj_name,
                  g1.id AS subj_id,
                  g2.name AS obj_name,
                  g2.id AS obj_id,
                  null AS residue,
                  null AS position,
                  r.evidence_count AS evidence_count,
                  r.belief AS belief,
                  r.source_counts AS sources
            """,
            "indra_mediated_subnetwork": """
                // Two-hop paths: A→X→B via indra_rel relationships
                // Find genes that mediate relationships between input genes
                MATCH (g1:BioEntity)-[r1:indra_rel]-(mediator:BioEntity)-[r2:indra_rel]-(g2:BioEntity)
                WHERE g1.id IN $gene_ids
                  AND g2.id IN $gene_ids
                  AND g1.id <> g2.id
                  AND mediator.id STARTS WITH 'hgnc:'
                  AND NOT mediator.id IN $gene_ids
                  AND r1.evidence_count >= $min_evidence
                  AND r2.evidence_count >= $min_evidence
                  AND r1.belief >= $min_belief
                  AND r2.belief >= $min_belief
                  AND g1.id STARTS WITH 'hgnc:'
                  AND g2.id STARTS WITH 'hgnc:'
                WITH g1, mediator, g2, r1, r2
                ORDER BY (r1.belief + r2.belief) / 2.0 DESC
                LIMIT $max_statements
                WITH g1, mediator, g2, r1, r2
                UNWIND [
                  {
                    hash: r1.stmt_hash,
                    type: r1.stmt_type,
                    subj_name: g1.name,
                    subj_id: g1.id,
                    obj_name: mediator.name,
                    obj_id: mediator.id,
                    evidence_count: r1.evidence_count,
                    belief: r1.belief,
                    sources: r1.source_counts
                  },
                  {
                    hash: r2.stmt_hash,
                    type: r2.stmt_type,
                    subj_name: mediator.name,
                    subj_id: mediator.id,
                    obj_name: g2.name,
                    obj_id: g2.id,
                    evidence_count: r2.evidence_count,
                    belief: r2.belief,
                    sources: r2.source_counts
                  }
                ] AS stmt
                RETURN DISTINCT
                  stmt.hash AS hash,
                  stmt.type AS type,
                  stmt.subj_name AS subj_name,
                  stmt.subj_id AS subj_id,
                  stmt.obj_name AS obj_name,
                  stmt.obj_id AS obj_id,
                  null AS residue,
                  null AS position,
                  stmt.evidence_count AS evidence_count,
                  stmt.belief AS belief,
                  stmt.sources AS sources
            """,
            "source_target_analysis": """
                // One source gene to multiple targets via indra_rel
                MATCH (source:BioEntity)-[r:indra_rel]->(target:BioEntity)
                WHERE source.id = $source_gene_id
                  AND ($target_gene_ids IS NULL OR target.id IN $target_gene_ids)
                  AND r.evidence_count >= $min_evidence
                  AND r.belief >= $min_belief
                  AND source.id STARTS WITH 'hgnc:'
                  AND target.id STARTS WITH 'hgnc:'
                WITH source, target, r
                ORDER BY r.belief DESC, r.evidence_count DESC
                LIMIT $max_statements
                RETURN
                  r.stmt_hash AS hash,
                  r.stmt_type AS type,
                  source.name AS subj_name,
                  source.id AS subj_id,
                  target.name AS obj_name,
                  target.id AS obj_id,
                  null AS residue,
                  null AS position,
                  r.evidence_count AS evidence_count,
                  r.belief AS belief,
                  r.source_counts AS sources
            """,
            # ========================================================================
            # Tool 3: Enrichment analysis placeholder
            # ========================================================================
            "enrichment_analysis": """
                // Placeholder - enrichment requires statistical computation
                // This query would need backend support or client-side calculation
                MATCH (g:BioEntity)
                WHERE g.id IN $gene_ids
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  'enrichment_not_implemented' AS note
                LIMIT 10
            """,
            # Health check
            "health_check": """
                RETURN 1 AS status
            """,
            # ========================================================================
            # Tool 1: Integration test aliases (accept different param names)
            # ========================================================================
            "gene_to_features": """
                MATCH (g:BioEntity)
                WHERE (g.name = $gene OR g.id = $gene OR g.id = ('hgnc:' + $gene))
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                RETURN
                  g.name AS name,
                  g.id AS id,
                  g.type AS type
                LIMIT 1
            """,
            "tissue_to_genes": """
                MATCH (g:BioEntity)-[:expressed_in]->(t:BioEntity)
                WHERE (t.name = $tissue OR t.id = $tissue OR t.id CONTAINS $tissue)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND t.id STARTS WITH 'uberon:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type
                SKIP $offset LIMIT $limit
            """,
            "go_to_genes": """
                MATCH (g:BioEntity)-[r]->(go:BioEntity)
                WHERE (go.id = $go_term OR go.name = $go_term)
                  AND g.id STARTS WITH 'hgnc:'
                  AND g.obsolete = false
                  AND go.id STARTS WITH 'GO:'
                RETURN
                  g.name AS gene,
                  g.id AS gene_id,
                  g.type AS type,
                  type(r) AS relationship
                SKIP $offset LIMIT $limit
            """,
        }

        if resolved_query_name not in queries:
            raise ValueError(f"Unknown query: {query_name}")

        return queries[resolved_query_name]

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

    # ========================================================================
    # Tool 11: Identifier Mapping Methods
    # ========================================================================

    async def get_xrefs_for_entity(
        self,
        entity_id: str,
        target_namespace: str | None = None,
        limit: int = 50,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get cross-references for an entity.

        Uses `xref` relationships in Neo4j to find equivalent identifiers
        in other namespaces.

        Args:
            entity_id: Source entity CURIE (e.g., 'hgnc:11998')
            target_namespace: Filter to specific namespace (e.g., 'uniprot')
            limit: Max results

        Returns:
            {
                "success": True,
                "records": [
                    {
                        "source_id": "hgnc:11998",
                        "target_id": "uniprot:P04637",
                        "target_namespace": "uniprot"
                    }
                ],
                "count": 1
            }
        """
        try:
            # Use map_identifiers query with appropriate parameters
            result = await self.execute_query(
                "map_identifiers",
                identifiers=[entity_id],
                to_namespace=target_namespace if target_namespace else "",
                limit=limit,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting xrefs for {entity_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def map_identifiers(
        self,
        identifiers: list[str],
        to_namespace: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Map identifiers from one namespace to another.

        Args:
            identifiers: List of source CURIEs
            to_namespace: Target namespace (e.g., 'uniprot')

        Returns:
            {
                "success": True,
                "records": [
                    {
                        "source_id": "hgnc:11998",
                        "target_ids": ["uniprot:P04637"]
                    }
                ],
                "count": 1
            }
        """
        try:
            result = await self.execute_query(
                "map_identifiers",
                identifiers=identifiers,
                to_namespace=to_namespace,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error mapping identifiers: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    # ========================================================================
    # Tool 12: Pathway Methods
    # ========================================================================

    async def get_pathway_hierarchy(
        self,
        pathway_id: str,
        max_depth: int = 2,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get pathway hierarchy (parent/child pathways).

        Args:
            pathway_id: Pathway CURIE (e.g., 'reactome:R-HSA-109581')
            max_depth: How many levels to traverse

        Returns:
            Records with pathway relationships
        """
        try:
            # Neo4j schema doesn't have pathway hierarchy relationships
            # This would need to be implemented when data is available
            logger.warning(f"Pathway hierarchy not implemented in Neo4j schema")
            return {"success": False, "records": [], "count": 0, "error": "Not implemented"}
        except Exception as e:
            logger.error(f"Error getting pathway hierarchy for {pathway_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def get_pathway_genes(
        self,
        pathway_id: str,
        limit: int = 100,
        offset: int = 0,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get genes in a pathway.

        Args:
            pathway_id: Pathway CURIE
            limit: Max results
            offset: Skip first N results

        Returns:
            Records with genes in pathway
        """
        try:
            result = await self.execute_query(
                "get_genes_in_pathway",
                pathway_id=pathway_id,
                limit=limit,
                offset=offset,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting genes for pathway {pathway_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    # ========================================================================
    # Tool 13: Ontology Hierarchy Methods
    # ========================================================================

    async def get_ontology_parents(
        self,
        term_id: str,
        max_depth: int = 2,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get parent terms in ontology hierarchy.

        Uses `isa` and `partof` relationships to traverse upward.

        Args:
            term_id: Term CURIE (e.g., 'GO:0006915')
            max_depth: How many levels up (1 = immediate parents)

        Returns:
            Records with: parent_id (curie), parent_name (name), relationship_type (relationship), depth
        """
        try:
            result = await self.execute_query(
                "get_ontology_parents",
                term_id=term_id,
                max_depth=max_depth,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting parents for {term_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def get_ontology_children(
        self,
        term_id: str,
        max_depth: int = 2,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get child terms in ontology hierarchy.

        Uses `isa` and `partof` relationships to traverse downward.

        Args:
            term_id: Term CURIE (e.g., 'GO:0006915')
            max_depth: How many levels down

        Returns:
            Records with child terms
        """
        try:
            result = await self.execute_query(
                "get_ontology_children",
                term_id=term_id,
                max_depth=max_depth,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting children for {term_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def get_ontology_ancestors(
        self,
        term_id: str,
        max_depth: int = 10,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get all ancestors (transitive closure) in ontology hierarchy.

        Args:
            term_id: Term CURIE
            max_depth: Maximum depth to traverse

        Returns:
            Records with all ancestor terms
        """
        try:
            # Same as get_ontology_parents but with higher depth
            result = await self.execute_query(
                "get_ontology_parents",
                term_id=term_id,
                max_depth=max_depth,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting ancestors for {term_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    # ========================================================================
    # Tool 14: Relationship Checking Methods
    # ========================================================================

    async def check_relationship(
        self,
        gene1_id: str,
        gene2_id: str,
        relationship_types: list[str] | None = None,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Check if a relationship exists between two genes.

        Queries indra_rel relationships primarily.

        Args:
            gene1_id: First gene CURIE
            gene2_id: Second gene CURIE
            relationship_types: Filter by stmt_type (e.g., ['Phosphorylation'])

        Returns:
            {
                "success": True,
                "exists": True,
                "relationships": [
                    {
                        "type": "Phosphorylation",
                        "belief": 0.95,
                        "evidence_count": 10
                    }
                ]
            }
        """
        try:
            # Query for indra_rel relationships between the two genes
            cypher = """
                MATCH (g1:BioEntity)-[r:indra_rel]-(g2:BioEntity)
                WHERE g1.id = $gene1_id
                  AND g2.id = $gene2_id
                  AND g1.id STARTS WITH 'hgnc:'
                  AND g2.id STARTS WITH 'hgnc:'
            """

            if relationship_types:
                cypher += "  AND r.stmt_type IN $relationship_types\n"

            cypher += """
                RETURN
                  r.stmt_type AS type,
                  r.belief AS belief,
                  r.evidence_count AS evidence_count
                ORDER BY r.belief DESC
                LIMIT 20
            """

            params = {
                "gene1_id": gene1_id,
                "gene2_id": gene2_id,
            }
            if relationship_types:
                params["relationship_types"] = relationship_types

            records = await self.execute_raw_cypher(cypher, timeout=timeout, **params)

            return {
                "success": True,
                "exists": len(records) > 0,
                "relationships": records,
                "count": len(records),
            }
        except Exception as e:
            logger.error(f"Error checking relationship {gene1_id} - {gene2_id}: {e}")
            return {
                "success": False,
                "exists": False,
                "relationships": [],
                "count": 0,
                "error": str(e)
            }

    async def get_relationship_types(
        self,
        gene1_id: str,
        gene2_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get all relationship types between two genes.

        Args:
            gene1_id: First gene CURIE
            gene2_id: Second gene CURIE

        Returns:
            List of relationship types (stmt_types) that exist
        """
        try:
            result = await self.check_relationship(
                gene1_id=gene1_id,
                gene2_id=gene2_id,
                relationship_types=None,
                timeout=timeout
            )

            # Extract unique relationship types
            types = list(set([r["type"] for r in result.get("relationships", [])]))

            return {
                "success": True,
                "types": types,
                "count": len(types),
            }
        except Exception as e:
            logger.error(f"Error getting relationship types: {e}")
            return {"success": False, "types": [], "count": 0, "error": str(e)}

    # ========================================================================
    # Tool 15: Clinical Trials Methods
    # ========================================================================

    async def get_trials_for_drug(
        self,
        drug_id: str,
        phase: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get clinical trials for a drug.

        Args:
            drug_id: Drug CURIE
            phase: Filter by phase (e.g., 'Phase 3')
            status: Filter by status (e.g., 'Completed')
            limit: Max results
            offset: Skip first N results

        Returns:
            Records with trial information
        """
        try:
            result = await self.execute_query(
                "get_trials_for_drug",
                drug_id=drug_id,
                limit=limit,
                offset=offset,
                timeout=timeout
            )

            # Filter by phase/status if specified
            records = result["records"]
            if phase:
                records = [r for r in records if r.get("phase") == phase]
            if status:
                records = [r for r in records if r.get("status") == status]

            return {
                "success": True,
                "records": records,
                "count": len(records),
            }
        except Exception as e:
            logger.error(f"Error getting trials for drug {drug_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def get_trials_for_disease(
        self,
        disease_id: str,
        phase: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get clinical trials for a disease.

        Args:
            disease_id: Disease CURIE
            phase: Filter by phase
            status: Filter by status
            limit: Max results
            offset: Skip first N results

        Returns:
            Records with trial information
        """
        try:
            result = await self.execute_query(
                "get_trials_for_disease",
                disease_id=disease_id,
                limit=limit,
                offset=offset,
                timeout=timeout
            )

            # Filter by phase/status if specified
            records = result["records"]
            if phase:
                records = [r for r in records if r.get("phase") == phase]
            if status:
                records = [r for r in records if r.get("status") == status]

            return {
                "success": True,
                "records": records,
                "count": len(records),
            }
        except Exception as e:
            logger.error(f"Error getting trials for disease {disease_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def get_trial_by_id(
        self,
        nct_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get clinical trial by NCT ID.

        Args:
            nct_id: NCT identifier (e.g., 'NCT00000102')

        Returns:
            Trial details
        """
        try:
            result = await self.execute_query(
                "get_trial_by_id",
                nct_id=nct_id,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting trial {nct_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    # ========================================================================
    # Tool 16: Protein Function Methods
    # ========================================================================

    async def get_activities_for_protein(
        self,
        gene_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Get molecular activities/functions for a protein.

        Args:
            gene_id: Gene CURIE

        Returns:
            Records with activities (kinase, phosphatase, etc.)
        """
        try:
            result = await self.execute_query(
                "get_enzyme_activities",
                gene_id=gene_id,
                timeout=timeout
            )

            return {
                "success": True,
                "records": result["records"],
                "count": result["count"],
            }
        except Exception as e:
            logger.error(f"Error getting activities for {gene_id}: {e}")
            return {"success": False, "records": [], "count": 0, "error": str(e)}

    async def is_kinase(
        self,
        gene_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Check if a gene encodes a kinase.

        Args:
            gene_id: Gene CURIE

        Returns:
            {"success": True, "result": True/False}
        """
        try:
            result = await self.execute_query(
                "is_kinase",
                gene_id=gene_id,
                timeout=timeout
            )

            is_kinase = False
            if result["records"]:
                is_kinase = result["records"][0].get("result", False)

            return {
                "success": True,
                "result": is_kinase,
            }
        except Exception as e:
            logger.error(f"Error checking if {gene_id} is kinase: {e}")
            return {"success": False, "result": False, "error": str(e)}

    async def is_phosphatase(
        self,
        gene_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Check if a gene encodes a phosphatase.

        Args:
            gene_id: Gene CURIE

        Returns:
            {"success": True, "result": True/False}
        """
        try:
            result = await self.execute_query(
                "is_phosphatase",
                gene_id=gene_id,
                timeout=timeout
            )

            is_phosphatase = False
            if result["records"]:
                is_phosphatase = result["records"][0].get("result", False)

            return {
                "success": True,
                "result": is_phosphatase,
            }
        except Exception as e:
            logger.error(f"Error checking if {gene_id} is phosphatase: {e}")
            return {"success": False, "result": False, "error": str(e)}

    async def is_transcription_factor(
        self,
        gene_id: str,
        timeout: int = 30000,
    ) -> dict[str, Any]:
        """
        Check if a gene encodes a transcription factor.

        Args:
            gene_id: Gene CURIE

        Returns:
            {"success": True, "result": True/False}
        """
        try:
            result = await self.execute_query(
                "is_transcription_factor",
                gene_id=gene_id,
                timeout=timeout
            )

            is_tf = False
            if result["records"]:
                is_tf = result["records"][0].get("result", False)

            return {
                "success": True,
                "result": is_tf,
            }
        except Exception as e:
            logger.error(f"Error checking if {gene_id} is transcription factor: {e}")
            return {"success": False, "result": False, "error": str(e)}

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
