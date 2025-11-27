"""
Tool 2: cogex_extract_subnetwork

Graph traversal and mechanistic relationship discovery from INDRA knowledge graph.

Modes:
1. direct: Direct edges between genes (A→B)
2. mediated: Two-hop paths with intermediates (A→X→B)
3. shared_upstream: Shared regulators (A←X→B)
4. shared_downstream: Shared targets (A→X←B)
5. source_to_targets: One source gene regulating multiple targets
"""

import logging
from typing import Any

from cogex_mcp.clients.adapter import get_adapter
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    STANDARD_QUERY_TIMEOUT,
)
from cogex_mcp.schemas import (
    EntityRef,
    GeneNode,
    IndraStatement,
    NetworkStatistics,
    SubnetworkMode,
    SubnetworkQuery,
)
from cogex_mcp.services.entity_resolver import EntityResolutionError, get_resolver
from cogex_mcp.services.formatter import get_formatter

logger = logging.getLogger(__name__)

async def cogex_extract_subnetwork(
    params: SubnetworkQuery) -> str:
    """
    Extract mechanistic subnetworks from INDRA knowledge graph.

    This tool discovers mechanistic relationships between genes through graph
    traversal of the INDRA knowledge graph, which contains mechanistic
    statements like phosphorylation, activation, inhibition, etc.

    **Modes:**

    1. **direct**: Direct mechanistic edges between specified genes
       - Use when: "How do TP53 and MDM2 interact directly?"
       - Pattern: A→B (one-hop relationships)

    2. **mediated**: Two-hop paths connecting genes through intermediates
       - Use when: "What connects BRCA1 to DNA repair genes?"
       - Pattern: A→X→B (intermediary mechanisms)

    3. **shared_upstream**: Find shared regulatory inputs
       - Use when: "What regulates both JAK and STAT?"
       - Pattern: A←X→B (common regulators)

    4. **shared_downstream**: Find shared regulatory targets
       - Use when: "What do these kinases both regulate?"
       - Pattern: A→X←B (common targets)

    5. **source_to_targets**: One gene regulating multiple downstream targets
       - Use when: "What does TP53 regulate?"
       - Pattern: Source→[Targets] (one-to-many)

    **Filters:**
    - tissue_filter: Restrict to genes expressed in specific tissue
    - go_filter: Restrict to genes with specific GO term
    - statement_types: Filter by mechanism (e.g., ['Phosphorylation', 'Activation'])
    - min_evidence_count: Minimum supporting evidences
    - min_belief_score: Minimum belief score (0-1)

    **Evidence:**
    - include_evidence=False (default): Statement summaries only
    - include_evidence=True: Include evidence text snippets (increases size)

    Args:
        params (SubnetworkQuery): Query parameters including:
            - mode (SubnetworkMode): Graph traversal mode (required)
            - genes (List[str]): Gene list for most modes
            - source_gene (str): Source for source_to_targets mode
            - target_genes (List[str]): Targets for source_to_targets mode
            - tissue_filter (str): Optional tissue restriction
            - go_filter (str): Optional GO term restriction
            - include_evidence (bool): Include evidence text (default: False)
            - statement_types (List[str]): Filter by mechanism type
            - min_evidence_count (int): Minimum evidences (default: 1)
            - min_belief_score (float): Minimum belief (default: 0.0)
            - max_statements (int): Maximum results (1-500, default: 100)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Formatted subnetwork in requested format

        **Markdown format:**
        - Network summary with node/edge counts
        - Statements grouped by type
        - Evidence counts and belief scores
        - Interactive visualization suggestions

        **JSON format:**
        ```
        {
            "nodes": [{"name": "TP53", "curie": "hgnc:11998", ...}],
            "statements": [
                {
                    "stmt_hash": "...",
                    "stmt_type": "Phosphorylation",
                    "subject": {"name": "ATM", ...},
                    "object": {"name": "TP53", ...},
                    "residue": "S",
                    "position": "15",
                    "evidence_count": 12,
                    "belief_score": 0.95,
                    "sources": ["reach", "sparser"],
                    "evidence": [...]  # if include_evidence=True
                }
            ],
            "statistics": {
                "node_count": 10,
                "edge_count": 25,
                "statement_types": {"Phosphorylation": 10, "Activation": 15},
                "avg_evidence_per_statement": 8.2,
                "avg_belief_score": 0.87
            }
        }
        ```

    Examples:
        - Direct interactions:
          mode="direct", genes=["TP53", "MDM2"]

        - Find pathway:
          mode="mediated", genes=["BRCA1", "RAD51"], max_statements=50

        - Shared regulators:
          mode="shared_upstream", genes=["JAK1", "JAK2", "STAT3"]

        - Tissue-specific:
          mode="direct", genes=["GENE1", "GENE2"], tissue_filter="brain"

        - Filter by mechanism:
          mode="direct", genes=[...], statement_types=["Phosphorylation"]

    Error Handling:
        - Returns actionable error messages for invalid genes
        - Suggests alternatives for ambiguous identifiers
        - Handles missing relationships gracefully
        - Enforces character limit with intelligent truncation

    Raises:
        None (errors returned as formatted strings)
    """
    try:
        # Route to appropriate handler based on mode
        if params.mode == SubnetworkMode.DIRECT:
            result = await _extract_direct(params)
        elif params.mode == SubnetworkMode.MEDIATED:
            result = await _extract_mediated(params)
        elif params.mode == SubnetworkMode.SHARED_UPSTREAM:
            result = await _extract_shared_upstream(params)
        elif params.mode == SubnetworkMode.SHARED_DOWNSTREAM:
            result = await _extract_shared_downstream(params)
        elif params.mode == SubnetworkMode.SOURCE_TO_TARGETS:
            result = await _extract_source_to_targets(params)
        else:
            return f"Error: Unknown subnetwork mode '{params.mode}'"

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return response

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return f"Error: {str(e)}"

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return f"Error: Unexpected error occurred. {str(e)}"

# ============================================================================
# Mode Implementations
# ============================================================================

async def _extract_direct(
    params: SubnetworkQuery) -> dict[str, Any]:
    """
    Mode: direct - Extract direct mechanistic edges between specified genes.

    Finds one-hop relationships (A→B) such as phosphorylation, activation,
    inhibition, ubiquitination, and other direct molecular interactions.

    Args:
        params: SubnetworkQuery with:
            - genes: List of gene symbols or CURIEs (min 2)
            - statement_types: Optional filter (e.g., ["Phosphorylation"])
            - min_evidence_count: Minimum supporting evidences
            - min_belief_score: Minimum confidence (0-1)
            - tissue_filter: Optional tissue restriction
            - go_filter: Optional GO term restriction

    Returns:
        Dict with nodes, statements, and statistics

    Example:
        >>> params = SubnetworkQuery(
        ...     mode="direct",
        ...     genes=["TP53", "MDM2"],
        ...     min_evidence_count=2,
        ...     response_format="json"
        ... )
        >>> result = await _extract_direct(params)
        >>> print(result['statistics']['edge_count'])
        15

    See Also:
        - _extract_mediated: For indirect connections
        - docs/subnetwork_extraction_guide.md: Complete usage guide
    """
    if not params.genes or len(params.genes) < 2:
        raise ValueError("direct mode requires at least 2 genes")



    # Resolve all gene identifiers
    resolver = get_resolver()
    resolved_genes = []
    for gene in params.genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)
    # Query direct interactions
    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": params.statement_types,
        "min_evidence": params.min_evidence_count,
        "min_belief": params.min_belief_score,
        "max_statements": params.max_statements,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue_filter:
        query_params["tissue"] = params.tissue_filter
    if params.go_filter:
        query_params["go_term"] = params.go_filter

    stmt_data = await adapter.query("indra_subnetwork", **query_params)
    # Parse statements and build network
    statements = _parse_statements(stmt_data, params.include_evidence)
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_statistics(nodes, statements)

    return {
        "nodes": [n.model_dump() for n in nodes],
        "statements": [s.model_dump() for s in statements],
        "statistics": statistics.model_dump(),
    }

async def _extract_mediated(
    params: SubnetworkQuery) -> dict[str, Any]:
    """
    Mode: mediated - Find two-hop paths connecting genes through intermediates.

    Discovers indirect connections (A→X→B) revealing pathway intermediaries
    and potential drug targets that link genes mechanistically.

    Args:
        params: SubnetworkQuery with:
            - genes: List of gene symbols or CURIEs (min 2)
            - statement_types: Optional mechanism filter
            - min_evidence_count: Minimum supporting evidences
            - max_statements: Limit results (can be large)

    Returns:
        Dict with nodes (including intermediaries), statements, statistics,
        and a note indicating two-hop paths

    Example:
        >>> params = SubnetworkQuery(
        ...     mode="mediated",
        ...     genes=["BRCA1", "RAD51"],
        ...     max_statements=100
        ... )
        >>> result = await _extract_mediated(params)
        >>> # Find intermediaries (nodes not in original gene list)
        >>> intermediaries = [n for n in result['nodes']
        ...                   if n['name'] not in ['BRCA1', 'RAD51']]

    See Also:
        - _extract_direct: For direct interactions only
        - examples/subnetwork_extraction.py: Example 2 (ALS genes)
    """
    if not params.genes or len(params.genes) < 2:
        raise ValueError("mediated mode requires at least 2 genes")



    resolver = get_resolver()
    resolved_genes = []
    for gene in params.genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)
    adapter = await get_adapter()

    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": params.statement_types,
        "min_evidence": params.min_evidence_count,
        "min_belief": params.min_belief_score,
        "max_statements": params.max_statements,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if params.tissue_filter:
        query_params["tissue"] = params.tissue_filter
    if params.go_filter:
        query_params["go_term"] = params.go_filter

    stmt_data = await adapter.query("indra_mediated_subnetwork", **query_params)
    statements = _parse_statements(stmt_data, params.include_evidence)
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_statistics(nodes, statements)

    return {
        "nodes": [n.model_dump() for n in nodes],
        "statements": [s.model_dump() for s in statements],
        "statistics": statistics.model_dump(),
        "note": "Paths shown are two-hop (gene→intermediate→gene)",
    }

async def _extract_shared_upstream(
    params: SubnetworkQuery) -> dict[str, Any]:
    """
    Mode: shared_upstream - Find shared regulators (master regulators).

    Identifies proteins that regulate multiple target genes (A←X→B pattern),
    revealing master control points useful for understanding coordinated
    regulation and identifying therapeutic targets.

    Args:
        params: SubnetworkQuery with:
            - genes: List of target genes to find shared regulators for
            - statement_types: Filter mechanism (e.g., ["Phosphorylation", "Activation"])
            - min_evidence_count: Quality threshold

    Returns:
        Dict with nodes, statements, and statistics. Currently returns
        placeholder with "not yet implemented" note if backend unavailable.

    Example:
        >>> params = SubnetworkQuery(
        ...     mode="shared_upstream",
        ...     genes=["BAX", "BCL2", "CASP3"],
        ...     statement_types=["Activation", "Inhibition"]
        ... )
        >>> result = await _extract_shared_upstream(params)
        >>> if 'note' not in result or 'not yet implemented' not in result['note']:
        ...     # Backend supports this mode
        ...     regulators = {s['subject']['name'] for s in result['statements']}

    Note:
        Backend support for this mode may be limited. Check result['note']
        for implementation status.

    See Also:
        - _extract_shared_downstream: For finding shared targets instead
        - examples/subnetwork_extraction.py: Example 3 (Apoptosis regulators)
    """
    if not params.genes or len(params.genes) < 2:
        raise ValueError("shared_upstream mode requires at least 2 genes")
    resolver = get_resolver()
    resolved_genes = []
    for gene in params.genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)
    # TODO: Implement when backend query is available
    # For now, return placeholder
    return {
        "nodes": [g.model_dump() for g in resolved_genes],
        "statements": [],
        "statistics": {
            "node_count": len(resolved_genes),
            "edge_count": 0,
            "statement_types": {},
            "avg_evidence_per_statement": 0.0,
            "avg_belief_score": 0.0,
        },
        "note": "Shared upstream queries not yet implemented in backend",
    }

async def _extract_shared_downstream(
    params: SubnetworkQuery) -> dict[str, Any]:
    """
    Mode: shared_downstream - Find shared targets (convergence points).

    Identifies proteins that are targeted by multiple source genes (A→X←B),
    revealing pathway convergence points and potential bottlenecks in
    cellular signaling.

    Args:
        params: SubnetworkQuery with:
            - genes: List of source genes to find shared targets for
            - statement_types: Filter mechanism types
            - min_evidence_count: Quality threshold

    Returns:
        Dict with nodes, statements, and statistics. Currently returns
        placeholder with "not yet implemented" note if backend unavailable.

    Example:
        >>> params = SubnetworkQuery(
        ...     mode="shared_downstream",
        ...     genes=["TP53", "MYC", "RB1"],
        ...     min_evidence_count=3
        ... )
        >>> result = await _extract_shared_downstream(params)
        >>> if 'note' not in result or 'not yet implemented' not in result['note']:
        ...     # Find genes regulated by multiple TFs
        ...     targets = {s['object']['name'] for s in result['statements']}

    Note:
        Backend support for this mode may be limited. Check result['note']
        for implementation status.

    See Also:
        - _extract_shared_upstream: For finding shared regulators instead
        - docs/subnetwork_extraction_guide.md: Mode descriptions
    """
    if not params.genes or len(params.genes) < 2:
        raise ValueError("shared_downstream mode requires at least 2 genes")
    resolver = get_resolver()
    resolved_genes = []
    for gene in params.genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)
    # TODO: Implement when backend query is available
    # For now, return placeholder
    return {
        "nodes": [g.model_dump() for g in resolved_genes],
        "statements": [],
        "statistics": {
            "node_count": len(resolved_genes),
            "edge_count": 0,
            "statement_types": {},
            "avg_evidence_per_statement": 0.0,
            "avg_belief_score": 0.0,
        },
        "note": "Shared downstream queries not yet implemented in backend",
    }

async def _extract_source_to_targets(
    params: SubnetworkQuery) -> dict[str, Any]:
    """
    Mode: source_to_targets - Map downstream signaling from one source gene.

    Finds all (or specified) downstream targets of a source gene, useful for
    mapping kinase substrates, transcription factor targets, or any
    one-to-many regulatory relationship.

    Args:
        params: SubnetworkQuery with:
            - source_gene: Source gene symbol or CURIE (required)
            - target_genes: Optional list of specific targets to check
            - statement_types: Filter mechanisms (e.g., ["Phosphorylation"])
            - min_evidence_count: Evidence threshold

    Returns:
        Dict with source_gene info, nodes, statements, and statistics.
        If target_genes specified, only shows connections to those targets.

    Example:
        >>> # Find all MAPK1 phosphorylation targets
        >>> params = SubnetworkQuery(
        ...     mode="source_to_targets",
        ...     source_gene="MAPK1",
        ...     statement_types=["Phosphorylation"],
        ...     max_statements=200
        ... )
        >>> result = await _extract_source_to_targets(params)
        >>> substrates = {s['object']['name'] for s in result['statements']}
        >>> print(f"MAPK1 phosphorylates {len(substrates)} proteins")

        >>> # Check specific targets only
        >>> params = SubnetworkQuery(
        ...     mode="source_to_targets",
        ...     source_gene="MAPK1",
        ...     target_genes=["FOS", "JUN", "ELK1"],
        ...     statement_types=["Phosphorylation"]
        ... )
        >>> result = await _extract_source_to_targets(params)

    See Also:
        - _extract_direct: For bidirectional interactions
        - examples/subnetwork_extraction.py: Example 6 (Advanced filtering)
    """
    if not params.source_gene:
        raise ValueError("source_to_targets mode requires source_gene parameter")
    resolver = get_resolver()
    source = await resolver.resolve_gene(params.source_gene)

    # Optionally resolve target genes if specified
    target_genes = []
    if params.target_genes:

        for gene in params.target_genes:
            resolved = await resolver.resolve_gene(gene)
            target_genes.append(resolved)
    adapter = await get_adapter()

    query_params = {
        "source_gene_id": source.curie,
        "statement_types": params.statement_types,
        "min_evidence": params.min_evidence_count,
        "min_belief": params.min_belief_score,
        "max_statements": params.max_statements,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if target_genes:
        query_params["target_gene_ids"] = [g.curie for g in target_genes]
    if params.tissue_filter:
        query_params["tissue"] = params.tissue_filter
    if params.go_filter:
        query_params["go_term"] = params.go_filter

    stmt_data = await adapter.query("source_target_analysis", **query_params)
    statements = _parse_statements(stmt_data, params.include_evidence)
    all_resolved = [source] + target_genes
    nodes = _extract_nodes_from_statements(statements, all_resolved)
    statistics = _compute_statistics(nodes, statements)

    return {
        "source_gene": source.model_dump(),
        "nodes": [n.model_dump() for n in nodes],
        "statements": [s.model_dump() for s in statements],
        "statistics": statistics.model_dump(),
    }

# ============================================================================
# Data Parsing Helpers
# ============================================================================

def _parse_statements(
    data: dict[str, Any],
    include_evidence: bool = False,
) -> list[IndraStatement]:
    """
    Parse INDRA statements from backend response into structured format.

    Converts raw Neo4j/backend response into typed IndraStatement objects
    with subject, object, mechanism type, evidence counts, and optional
    evidence text snippets.

    Args:
        data: Backend response dict with 'success' flag and 'statements'/'records' list
        include_evidence: If True, include evidence text snippets in results

    Returns:
        List of IndraStatement objects with full metadata

    Example:
        >>> data = {
        ...     "success": True,
        ...     "statements": [
        ...         {"hash": "abc", "type": "Phosphorylation",
        ...          "subj_name": "ATM", "obj_name": "TP53",
        ...          "evidence_count": 12, "belief": 0.95}
        ...     ]
        ... }
        >>> stmts = _parse_statements(data, include_evidence=False)
        >>> print(stmts[0].stmt_type, stmts[0].evidence_count)
        Phosphorylation 12
    """
    if not data.get("success"):
        return []

    # Statements might be in 'records' or 'statements' depending on backend
    records = data.get("statements") or data.get("records") or []
    if not records:
        return []

    statements = []
    for record in records:
        stmt = IndraStatement(
            stmt_hash=record.get("hash", ""),
            stmt_type=record.get("type", "Unknown"),
            subject=EntityRef(
                name=record.get("subj_name", "Unknown"),
                curie=record.get("subj_id", "unknown:unknown"),
                namespace=record.get("subj_namespace", "unknown"),
                identifier=record.get("subj_identifier", "unknown"),
            ),
            object=EntityRef(
                name=record.get("obj_name", "Unknown"),
                curie=record.get("obj_id", "unknown:unknown"),
                namespace=record.get("obj_namespace", "unknown"),
                identifier=record.get("obj_identifier", "unknown"),
            ),
            residue=record.get("residue"),
            position=record.get("position"),
            evidence_count=record.get("evidence_count", 0),
            belief_score=record.get("belief", 0.0),
            sources=record.get("sources", []),
            evidence=record.get("evidence") if include_evidence else None,
        )
        statements.append(stmt)

    return statements

def _extract_nodes_from_statements(
    statements: list[IndraStatement],
    resolved_genes: list[GeneNode],
) -> list[GeneNode]:
    """
    Extract unique nodes from statements and query genes.

    Builds complete node list by combining:
    1. Original query genes (always included)
    2. Additional nodes discovered in statements (intermediaries, etc.)

    Args:
        statements: List of parsed INDRA statements
        resolved_genes: Original query genes (from entity resolver)

    Returns:
        List of unique GeneNode objects (no duplicates by CURIE)

    Example:
        >>> resolved = [GeneNode(name="TP53", curie="hgnc:11998", ...)]
        >>> stmts = [...]  # Includes ATM→TP53 phosphorylation
        >>> nodes = _extract_nodes_from_statements(stmts, resolved)
        >>> node_names = {n.name for n in nodes}
        >>> print("ATM" in node_names)  # Found in statements
        True
        >>> print("TP53" in node_names)  # From resolved_genes
        True
    """
    nodes_dict: dict[str, GeneNode] = {}

    # Add resolved genes first
    for gene in resolved_genes:
        nodes_dict[gene.curie] = gene

    # Extract nodes from statements
    for stmt in statements:
        # Add subject if not already present
        if stmt.subject.curie not in nodes_dict:
            nodes_dict[stmt.subject.curie] = GeneNode(
                name=stmt.subject.name,
                curie=stmt.subject.curie,
                namespace=stmt.subject.namespace,
                identifier=stmt.subject.identifier,
            )

        # Add object if not already present
        if stmt.object.curie not in nodes_dict:
            nodes_dict[stmt.object.curie] = GeneNode(
                name=stmt.object.name,
                curie=stmt.object.curie,
                namespace=stmt.object.namespace,
                identifier=stmt.object.identifier,
            )

    return list(nodes_dict.values())

def _compute_statistics(
    nodes: list[GeneNode],
    statements: list[IndraStatement],
) -> NetworkStatistics:
    """
    Compute network-level statistics from parsed network data.

    Calculates summary metrics including node/edge counts, statement type
    distribution, and average evidence quality metrics.

    Args:
        nodes: List of unique GeneNode objects in network
        statements: List of IndraStatement objects (edges)

    Returns:
        NetworkStatistics object with:
            - node_count: Number of unique genes/proteins
            - edge_count: Number of mechanistic relationships
            - statement_types: Dict mapping type → count (e.g., {"Phosphorylation": 15})
            - avg_evidence_per_statement: Mean evidence count
            - avg_belief_score: Mean confidence score

    Example:
        >>> nodes = [...]  # 10 nodes
        >>> stmts = [...]  # 25 statements
        >>> stats = _compute_statistics(nodes, stmts)
        >>> print(f"Network: {stats.node_count} nodes, {stats.edge_count} edges")
        Network: 10 nodes, 25 edges
        >>> print(f"Quality: {stats.avg_belief_score:.2f}")
        Quality: 0.87

    See Also:
        - NetworkStatistics schema in schemas.py
    """
    # Count statement types
    stmt_types: dict[str, int] = {}
    total_evidence = 0
    total_belief = 0.0

    for stmt in statements:
        stmt_types[stmt.stmt_type] = stmt_types.get(stmt.stmt_type, 0) + 1
        total_evidence += stmt.evidence_count
        total_belief += stmt.belief_score

    return NetworkStatistics(
        node_count=len(nodes),
        edge_count=len(statements),
        statement_types=stmt_types,
        avg_evidence_per_statement=total_evidence / len(statements) if statements else 0.0,
        avg_belief_score=total_belief / len(statements) if statements else 0.0,
    )

logger.info("✓ Tool 2 (cogex_extract_subnetwork) registered")
