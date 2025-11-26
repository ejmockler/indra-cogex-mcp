#!/usr/bin/env python3
"""
INDRA CoGEx MCP Server - Low-Level Implementation

Uses the low-level MCP SDK instead of FastMCP for better Claude Code compatibility.
All 16 tools migrated from FastMCP to low-level SDK.
"""

import asyncio
import json
import logging
import re
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from cogex_mcp.clients.adapter import close_adapter, get_adapter
from cogex_mcp.config import settings
from cogex_mcp.services.cache import get_cache
from cogex_mcp.services.entity_resolver import get_resolver, EntityResolutionError
from cogex_mcp.services.formatter import get_formatter
from cogex_mcp.services.pagination import get_pagination
from cogex_mcp.constants import (
    CHARACTER_LIMIT,
    ENRICHMENT_TIMEOUT,
    STANDARD_QUERY_TIMEOUT,
    ResponseFormat,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if settings.log_format == "text"
    else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

# Initialize server
server = Server("cogex_mcp")

# Global state
_adapter = None
_cache = None


async def initialize_backend():
    """Initialize backend connections and services."""
    global _adapter, _cache

    logger.info("🚀 Starting INDRA CoGEx MCP Server (Low-Level)")
    logger.info(
        f"Configuration: primary_backend={settings.has_neo4j_config}, "
        f"fallback={settings.has_rest_fallback}"
    )

    # Initialize client adapter
    _adapter = await get_adapter()
    logger.info("✓ Client adapter initialized")

    # Initialize cache
    _cache = get_cache()
    logger.info(
        f"✓ Cache initialized: max_size={_cache.max_size}, "
        f"ttl={_cache.ttl_seconds}s, enabled={_cache.enabled}"
    )

    # Get adapter status
    status = _adapter.get_status()
    logger.info(f"Backend status: {status}")
    logger.info("✓ Server initialization complete")


async def cleanup_backend():
    """Cleanup backend connections."""
    logger.info("🛑 Shutting down INDRA CoGEx MCP Server")

    if _cache and _cache.enabled:
        stats = _cache.get_stats()
        logger.info(f"Final cache stats: {stats}")

    await close_adapter()
    logger.info("✓ Connections closed")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools."""
    return [
        # Tool 1: Disease/Phenotype Query
        types.Tool(
            name="query_disease_or_phenotype",
            description="""Query diseases, phenotypes, and their mechanisms bidirectionally.

This tool supports 3 query modes for comprehensive disease-phenotype exploration:

**Mode 1: disease_to_mechanisms**
Get comprehensive disease profile including associated genes, genetic variants,
phenotypes, drug therapies, and clinical trials.

**Mode 2: phenotype_to_diseases**
Find diseases associated with a specific phenotype. Useful for differential
diagnosis and phenotype-based discovery.

**Mode 3: check_phenotype**
Boolean check: Does a specific disease exhibit a specific phenotype?

Examples:
- Get diabetes profile: mode="disease_to_mechanisms", disease="diabetes mellitus"
- Find diseases with seizures: mode="phenotype_to_diseases", phenotype="HP:0001250"
- Check if Alzheimer's has memory impairment: mode="check_phenotype",
  disease="Alzheimer disease", phenotype="memory impairment"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": [
                            "disease_to_mechanisms",
                            "phenotype_to_diseases",
                            "check_phenotype",
                        ],
                        "description": "Query mode",
                    },
                    "disease": {
                        "type": "string",
                        "description": "Disease name or CURIE (e.g., 'diabetes' or 'mondo:MONDO:0005015')",
                    },
                    "phenotype": {
                        "type": "string",
                        "description": "Phenotype term or CURIE (e.g., 'HP:0001250' or 'seizures')",
                    },
                    "include_genes": {
                        "type": "boolean",
                        "description": "Include associated genes (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_variants": {
                        "type": "boolean",
                        "description": "Include genetic variants (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_phenotypes": {
                        "type": "boolean",
                        "description": "Include phenotypes (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_drugs": {
                        "type": "boolean",
                        "description": "Include drug therapies (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "include_trials": {
                        "type": "boolean",
                        "description": "Include clinical trials (disease_to_mechanisms only)",
                        "default": True,
                    },
                    "response_format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "description": "Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
                        "default": "markdown",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (phenotype_to_diseases mode)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset",
                        "minimum": 0,
                        "default": 0,
                    },
                },
                "required": ["mode"],
            },
        ),
        # Tool 2: Gene/Feature Query
        types.Tool(
            name="query_gene_or_feature",
            description="""Query genes and their features bidirectionally.

This tool supports 5 query modes for comprehensive gene-feature exploration:

**Forward Mode (gene → features):**
- gene_to_features: Get all features for a specific gene (expression, GO terms,
  pathways, diseases, domains, variants, phenotypes, codependencies)

**Reverse Modes (feature → genes):**
- tissue_to_genes: Find genes expressed in a specific tissue
- go_to_genes: Find genes annotated with a specific GO term
- domain_to_genes: Find genes containing a specific protein domain
- phenotype_to_genes: Find genes associated with a specific phenotype

Examples:
- Get TP53 profile: mode="gene_to_features", gene="TP53"
- Find brain genes: mode="tissue_to_genes", tissue="brain"
- Find kinases: mode="go_to_genes", go_term="GO:0016301"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["gene_to_features", "tissue_to_genes", "go_to_genes", "domain_to_genes", "phenotype_to_genes"],
                        "description": "Query mode",
                    },
                    "gene": {"type": "string", "description": "Gene identifier for gene_to_features"},
                    "tissue": {"type": "string", "description": "Tissue identifier for tissue_to_genes"},
                    "go_term": {"type": "string", "description": "GO term for go_to_genes"},
                    "domain": {"type": "string", "description": "Domain identifier for domain_to_genes"},
                    "phenotype": {"type": "string", "description": "Phenotype identifier for phenotype_to_genes"},
                    "include_expression": {"type": "boolean", "default": True},
                    "include_go_terms": {"type": "boolean", "default": True},
                    "include_pathways": {"type": "boolean", "default": True},
                    "include_diseases": {"type": "boolean", "default": True},
                    "include_domains": {"type": "boolean", "default": False},
                    "include_variants": {"type": "boolean", "default": False},
                    "include_phenotypes": {"type": "boolean", "default": False},
                    "include_codependencies": {"type": "boolean", "default": False},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 3: Subnetwork Extraction
        types.Tool(
            name="extract_subnetwork",
            description="""Extract mechanistic subnetworks from INDRA knowledge graph.

Query modes:
- direct: Direct edges between genes (A→B)
- mediated: Two-hop paths (A→X→B)
- shared_upstream: Shared regulators (A←X→B)
- shared_downstream: Shared targets (A→X←B)
- source_to_targets: One source gene → multiple targets

Examples:
- Direct interactions: mode="direct", genes=["TP53", "MDM2"]
- Find pathway: mode="mediated", genes=["BRCA1", "RAD51"]
- Shared regulators: mode="shared_upstream", genes=["JAK1", "STAT3"]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["direct", "mediated", "shared_upstream", "shared_downstream", "source_to_targets"]},
                    "genes": {"type": "array", "items": {"type": "string"}},
                    "source_gene": {"type": "string"},
                    "target_genes": {"type": "array", "items": {"type": "string"}},
                    "tissue_filter": {"type": "string"},
                    "go_filter": {"type": "string"},
                    "include_evidence": {"type": "boolean", "default": False},
                    "statement_types": {"type": "array", "items": {"type": "string"}},
                    "min_evidence_count": {"type": "integer", "default": 1},
                    "min_belief_score": {"type": "number", "default": 0.0},
                    "max_statements": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["mode"],
            },
        ),
        # Tool 4: Enrichment Analysis
        types.Tool(
            name="enrichment_analysis",
            description="""Perform statistical gene set and pathway enrichment analysis.

Analysis types:
- discrete: Overrepresentation (Fisher's exact test)
- continuous: GSEA with ranked genes
- signed: Directional enrichment (up/down regulation)
- metabolite: Metabolite set enrichment

Sources: go, reactome, wikipathways, indra-upstream, indra-downstream, phenotype

Examples:
- Discrete GO enrichment: analysis_type="discrete", gene_list=["TP53", "MDM2"], source="go"
- GSEA: analysis_type="continuous", ranked_genes={"TP53": 2.5, "MDM2": -1.8}, source="reactome"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_type": {"type": "string", "enum": ["discrete", "continuous", "signed", "metabolite"]},
                    "gene_list": {"type": "array", "items": {"type": "string"}},
                    "ranked_genes": {"type": "object"},
                    "background_genes": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string", "enum": ["go", "reactome", "wikipathways", "indra-upstream", "indra-downstream", "phenotype"], "default": "go"},
                    "alpha": {"type": "number", "default": 0.05},
                    "correction_method": {"type": "string", "default": "fdr_bh"},
                    "keep_insignificant": {"type": "boolean", "default": False},
                    "permutations": {"type": "integer", "default": 1000},
                    "min_evidence_count": {"type": "integer", "default": 1},
                    "min_belief_score": {"type": "number", "default": 0.0},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["analysis_type"],
            },
        ),
        # Tool 5: Drug/Effect Query
        types.Tool(
            name="query_drug_or_effect",
            description="""Query drugs and their effects bidirectionally.

Modes:
- drug_to_profile: Drug → comprehensive profile (targets, indications, side effects, trials, cell lines)
- side_effect_to_drugs: Side effect → drugs causing that effect

Examples:
- Get imatinib profile: mode="drug_to_profile", drug="imatinib"
- Find drugs causing nausea: mode="side_effect_to_drugs", side_effect="nausea"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["drug_to_profile", "side_effect_to_drugs"]},
                    "drug": {"type": "string"},
                    "side_effect": {"type": "string"},
                    "include_targets": {"type": "boolean", "default": True},
                    "include_indications": {"type": "boolean", "default": True},
                    "include_side_effects": {"type": "boolean", "default": True},
                    "include_trials": {"type": "boolean", "default": False},
                    "include_cell_lines": {"type": "boolean", "default": False},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 6: Pathway Query
        types.Tool(
            name="query_pathway",
            description="""Query pathway memberships and find shared pathways.

Modes:
- get_genes: Pathway → genes in pathway
- get_pathways: Gene → pathways containing gene
- find_shared: Genes → pathways containing ALL genes
- check_membership: Boolean check if gene is in pathway

Examples:
- Get genes in MAPK: mode="get_genes", pathway="MAPK signaling"
- Get pathways for TP53: mode="get_pathways", gene="TP53"
- Find shared pathways: mode="find_shared", genes=["TP53", "MDM2"]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_genes", "get_pathways", "find_shared", "check_membership"]},
                    "pathway": {"type": "string"},
                    "gene": {"type": "string"},
                    "genes": {"type": "array", "items": {"type": "string"}},
                    "pathway_source": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 7: Cell Line Query
        types.Tool(
            name="query_cell_line",
            description="""Query cell line data from CCLE and DepMap.

Modes:
- get_properties: Cell line → profile (mutations, CNAs, dependencies, expression)
- get_mutated_genes: Cell line → list of mutated genes
- get_cell_lines_with_mutation: Gene → cell lines with that mutation
- check_mutation: Boolean check if gene is mutated in cell line

Examples:
- Get A549 profile: mode="get_properties", cell_line="A549"
- Find KRAS mutant cell lines: mode="get_cell_lines_with_mutation", gene="KRAS"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_properties", "get_mutated_genes", "get_cell_lines_with_mutation", "check_mutation"]},
                    "cell_line": {"type": "string"},
                    "gene": {"type": "string"},
                    "include_mutations": {"type": "boolean", "default": True},
                    "include_copy_number": {"type": "boolean", "default": True},
                    "include_dependencies": {"type": "boolean", "default": False},
                    "include_expression": {"type": "boolean", "default": False},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 8: Clinical Trials Query
        types.Tool(
            name="query_clinical_trials",
            description="""Query ClinicalTrials.gov data for drugs and diseases.

Modes:
- get_for_drug: Drug → clinical trials testing that drug
- get_for_disease: Disease → clinical trials for that disease
- get_by_id: NCT ID → trial details

Examples:
- Find trials for pembrolizumab: mode="get_for_drug", drug="pembrolizumab"
- Find Alzheimer's trials: mode="get_for_disease", disease="Alzheimer's disease"
- Get trial details: mode="get_by_id", trial_id="NCT12345678"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_for_drug", "get_for_disease", "get_by_id"]},
                    "drug": {"type": "string"},
                    "disease": {"type": "string"},
                    "trial_id": {"type": "string"},
                    "phase": {"type": "array", "items": {"type": "integer"}},
                    "status": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 9: Literature Query
        types.Tool(
            name="query_literature",
            description="""Access PubMed literature and INDRA statement evidence.

Modes:
- get_statements_for_pmid: PMID → INDRA statements from that paper
- get_evidence_for_statement: Statement hash → evidence texts
- search_by_mesh: MeSH terms → publications
- get_statements_by_hashes: Batch retrieve statements by hashes

Examples:
- Get statements from paper: mode="get_statements_for_pmid", pmid="12345678"
- Get evidence: mode="get_evidence_for_statement", statement_hash="abc123"
- Search literature: mode="search_by_mesh", mesh_terms=["autophagy", "cancer"]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_statements_for_pmid", "get_evidence_for_statement", "search_by_mesh", "get_statements_by_hashes"]},
                    "pmid": {"type": "string"},
                    "statement_hash": {"type": "string"},
                    "mesh_terms": {"type": "array", "items": {"type": "string"}},
                    "statement_hashes": {"type": "array", "items": {"type": "string"}},
                    "include_evidence_text": {"type": "boolean", "default": True},
                    "max_evidence_per_statement": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 10: Variants Query
        types.Tool(
            name="query_variants",
            description="""Query genetic variants from GWAS Catalog and DisGeNet.

Modes:
- get_for_gene: Gene → variants in/near gene
- get_for_disease: Disease → associated variants
- get_for_phenotype: Phenotype → GWAS hits
- variant_to_genes: Variant (rsID) → nearby genes
- variant_to_phenotypes: Variant → associated phenotypes
- check_association: Check variant-disease association

Examples:
- GWAS hits for APOE: mode="get_for_gene", gene="APOE"
- Alzheimer's variants: mode="get_for_disease", disease="Alzheimer's disease"
- Genes near variant: mode="variant_to_genes", variant="rs7412"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_for_gene", "get_for_disease", "get_for_phenotype", "variant_to_genes", "variant_to_phenotypes", "check_association"]},
                    "gene": {"type": "string"},
                    "disease": {"type": "string"},
                    "phenotype": {"type": "string"},
                    "variant": {"type": "string"},
                    "min_p_value": {"type": "number"},
                    "max_p_value": {"type": "number", "default": 0.00001},
                    "source": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 11: Identifier Resolution
        types.Tool(
            name="resolve_identifiers",
            description="""Convert identifiers between different biological namespaces.

Common conversions:
- hgnc.symbol → hgnc (gene symbol → HGNC ID)
- hgnc → uniprot (HGNC ID → UniProt ID)
- uniprot → hgnc (UniProt ID → HGNC ID)
- ensembl → hgnc (Ensembl gene → HGNC ID)

Examples:
- Convert symbols to HGNC IDs:
  identifiers=["TP53", "BRCA1"], from_namespace="hgnc.symbol", to_namespace="hgnc"
- Get UniProt IDs:
  identifiers=["11998", "1100"], from_namespace="hgnc", to_namespace="uniprot"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifiers": {"type": "array", "items": {"type": "string"}},
                    "from_namespace": {"type": "string"},
                    "to_namespace": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["identifiers", "from_namespace", "to_namespace"],
            },
        ),
        # Tool 12: Relationship Check
        types.Tool(
            name="check_relationship",
            description="""Check existence of specific relationships between biological entities.

Relationship types:
- gene_in_pathway: Is gene in pathway?
- drug_target: Does drug target gene/protein?
- drug_indication: Is drug indicated for disease?
- drug_side_effect: Does drug cause side effect?
- gene_disease: Is gene associated with disease?
- disease_phenotype: Does disease have phenotype?
- gene_phenotype: Is gene associated with phenotype?
- variant_association: Is variant associated with trait/disease?
- cell_line_mutation: Does cell line have mutation in gene?
- cell_marker: Is gene a marker for cell type?

Examples:
- Is TP53 in p53 signaling? relationship_type="gene_in_pathway", entity1="TP53", entity2="p53 signaling"
- Does imatinib target ABL1? relationship_type="drug_target", entity1="imatinib", entity2="ABL1"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "relationship_type": {"type": "string", "enum": ["gene_in_pathway", "drug_target", "drug_indication", "drug_side_effect", "gene_disease", "disease_phenotype", "gene_phenotype", "variant_association", "cell_line_mutation", "cell_marker"]},
                    "entity1": {"type": "string"},
                    "entity2": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["relationship_type", "entity1", "entity2"],
            },
        ),
        # Tool 13: Ontology Hierarchy
        types.Tool(
            name="get_ontology_hierarchy",
            description="""Navigate ontology hierarchies (GO, HPO, MONDO, etc.).

Modes:
- parents: Get parent/ancestor terms
- children: Get child/descendant terms
- both: Get both parents and children

Examples:
- Get parents of apoptosis: term="GO:0006915", direction="parents", max_depth=3
- Get children: term="GO:0009987", direction="children", max_depth=2
- Full hierarchy: term="apoptosis", direction="both", max_depth=2
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "direction": {"type": "string", "enum": ["parents", "children", "both"]},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 5, "default": 2},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["term", "direction"],
            },
        ),
        # Tool 14: Cell Markers Query
        types.Tool(
            name="query_cell_markers",
            description="""Query CellMarker database for cell type markers.

Modes:
- get_markers: Cell type → marker genes
- get_cell_types: Marker gene → cell types
- check_marker: Boolean check if gene is a marker for cell type

Examples:
- Get markers for T cells: mode="get_markers", cell_type="T cell"
- Find cell types expressing CD4: mode="get_cell_types", marker="CD4"
- Check if CD8A is T cell marker: mode="check_marker", cell_type="T cell", marker="CD8A"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["get_markers", "get_cell_types", "check_marker"]},
                    "cell_type": {"type": "string"},
                    "marker": {"type": "string"},
                    "tissue": {"type": "string"},
                    "species": {"type": "string", "default": "human"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
        # Tool 15: Kinase Enrichment
        types.Tool(
            name="analyze_kinase_enrichment",
            description="""Predict upstream kinases from phosphoproteomics data.

Analyzes phosphorylation sites to identify enriched kinase activities.

Input format: GENE_RESIDUE_POSITION (e.g., TP53_S15, MAPK1_T185, EGFR_Y1068)
- S = serine, T = threonine, Y = tyrosine

Examples:
- Basic analysis: phosphosites=["TP53_S15", "TP53_S20", "MDM2_S166"]
- With background: phosphosites=[...], background=["GENE1_S10", ...]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "phosphosites": {"type": "array", "items": {"type": "string"}},
                    "background": {"type": "array", "items": {"type": "string"}},
                    "alpha": {"type": "number", "default": 0.05},
                    "correction_method": {"type": "string", "default": "fdr_bh"},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                },
                "required": ["phosphosites"],
            },
        ),
        # Tool 16: Protein Functions Query
        types.Tool(
            name="query_protein_functions",
            description="""Query enzyme activities and protein function types.

Modes:
- gene_to_activities: Gene → enzyme activities
- activity_to_genes: Activity → genes (paginated)
- check_activity: Boolean check if gene has specific activity
- check_function_types: Batch check kinase/phosphatase/TF for gene lists

Function types: kinase, phosphatase, transcription_factor

Examples:
- Get activities for EGFR: mode="gene_to_activities", gene="EGFR"
- Find all kinases: mode="activity_to_genes", enzyme_activity="kinase"
- Batch check: mode="check_function_types", genes=["TP53", "EGFR"], function_types=["kinase", "transcription_factor"]
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["gene_to_activities", "activity_to_genes", "check_activity", "check_function_types"]},
                    "gene": {"type": "string"},
                    "genes": {"type": "array", "items": {"type": "string"}},
                    "enzyme_activity": {"type": "string"},
                    "function_types": {"type": "array", "items": {"type": "string"}},
                    "response_format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "required": ["mode"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        # Route to appropriate handler
        if name == "query_disease_or_phenotype":
            return await _handle_disease_phenotype_query(arguments)
        elif name == "query_gene_or_feature":
            return await _handle_gene_feature_query(arguments)
        elif name == "extract_subnetwork":
            return await _handle_subnetwork_extraction(arguments)
        elif name == "enrichment_analysis":
            return await _handle_enrichment_analysis(arguments)
        elif name == "query_drug_or_effect":
            return await _handle_drug_effect_query(arguments)
        elif name == "query_pathway":
            return await _handle_pathway_query(arguments)
        elif name == "query_cell_line":
            return await _handle_cell_line_query(arguments)
        elif name == "query_clinical_trials":
            return await _handle_clinical_trials_query(arguments)
        elif name == "query_literature":
            return await _handle_literature_query(arguments)
        elif name == "query_variants":
            return await _handle_variants_query(arguments)
        elif name == "resolve_identifiers":
            return await _handle_identifier_resolution(arguments)
        elif name == "check_relationship":
            return await _handle_relationship_check(arguments)
        elif name == "get_ontology_hierarchy":
            return await _handle_ontology_hierarchy(arguments)
        elif name == "query_cell_markers":
            return await _handle_cell_markers_query(arguments)
        elif name == "analyze_kinase_enrichment":
            return await _handle_kinase_enrichment(arguments)
        elif name == "query_protein_functions":
            return await _handle_protein_functions_query(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Tool error in {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


# ============================================================================
# Tool 1: Disease/Phenotype Query
# ============================================================================

async def _handle_disease_phenotype_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle disease/phenotype query."""
    mode = args.get("mode")
    disease = args.get("disease")
    phenotype = args.get("phenotype")
    response_format = args.get("response_format", "markdown")

    # Route to appropriate handler based on mode
    if mode == "disease_to_mechanisms":
        if not disease:
            return [types.TextContent(
                type="text",
                text="Error: disease parameter required for disease_to_mechanisms mode"
            )]
        result = await _disease_to_mechanisms(args)
    elif mode == "phenotype_to_diseases":
        if not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: phenotype parameter required for phenotype_to_diseases mode"
            )]
        result = await _phenotype_to_diseases(args)
    elif mode == "check_phenotype":
        if not disease or not phenotype:
            return [types.TextContent(
                type="text",
                text="Error: both disease and phenotype parameters required for check_phenotype mode"
            )]
        result = await _check_phenotype(args)
    else:
        return [types.TextContent(
            type="text",
            text=f"Error: Unknown query mode '{mode}'"
        )]

    # Format response
    formatter = get_formatter()
    response = formatter.format_response(
        data=result,
        format_type=response_format,
        max_chars=CHARACTER_LIMIT,
    )

    return [types.TextContent(type="text", text=response)]


async def _disease_to_mechanisms(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive disease profile with all molecular mechanisms."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    result = {
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        }
    }

    adapter = await get_adapter()

    # Fetch requested features
    if args.get("include_genes", True):
        gene_data = await adapter.query(
            "get_genes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["genes"] = _parse_gene_associations(gene_data)

    if args.get("include_variants", True):
        variant_data = await adapter.query(
            "get_variants_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["variants"] = _parse_variant_associations(variant_data)

    if args.get("include_phenotypes", True):
        phenotype_data = await adapter.query(
            "get_phenotypes_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["phenotypes"] = _parse_phenotype_associations(phenotype_data)

    if args.get("include_drugs", True):
        drug_data = await adapter.query(
            "get_drugs_for_indication",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["drugs"] = _parse_drug_therapies(drug_data)

    if args.get("include_trials", True):
        trial_data = await adapter.query(
            "get_trials_for_disease",
            disease_id=disease_ref.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_clinical_trials(trial_data)

    return result


async def _phenotype_to_diseases(args: dict[str, Any]) -> dict[str, Any]:
    """Find diseases associated with a specific phenotype."""
    phenotype_id = args["phenotype"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    disease_data = await adapter.query(
        "get_diseases_for_phenotype",
        phenotype_id=phenotype_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    diseases = _parse_disease_list(disease_data)

    return {
        "diseases": diseases,
        "pagination": {
            "total_count": disease_data.get("total_count", len(diseases)),
            "count": len(diseases),
            "offset": offset,
            "limit": limit,
            "has_more": disease_data.get("total_count", len(diseases)) > offset + len(diseases),
        },
    }


async def _check_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Boolean check: Does disease have specific phenotype?"""
    disease_input = args["disease"]
    phenotype_id = args["phenotype"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease_ref = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease_ref.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_phenotype = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_phenotype": has_phenotype,
        "disease": {
            "name": disease_ref.name,
            "curie": disease_ref.curie,
            "namespace": disease_ref.namespace,
            "identifier": disease_ref.identifier,
        },
        "phenotype": {
            "name": phenotype_id,
            "curie": phenotype_id if ":" in phenotype_id else f"unknown:{phenotype_id}",
        },
    }


# Data parsing helpers for Tool 1
def _parse_gene_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    associations = []
    for record in data["records"]:
        associations.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
            "sources": record.get("sources", []),
        })

    return associations


def _parse_variant_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse variant-disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variants.append({
            "variant": record.get("rsid", "unknown"),
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
            },
            "p_value": record.get("p_value"),
            "odds_ratio": record.get("odds_ratio"),
            "trait": record.get("trait"),
        })

    return variants


def _parse_phenotype_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease-phenotype associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append({
            "phenotype": {
                "name": record.get("phenotype", "Unknown"),
                "curie": record.get("phenotype_id", "unknown:unknown"),
            },
            "frequency": record.get("frequency"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return phenotypes


def _parse_drug_therapies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug therapy data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append({
            "drug": {
                "name": record.get("drug", "Unknown"),
                "curie": record.get("drug_id", "unknown:unknown"),
            },
            "indication_type": record.get("indication_type", "unknown"),
            "max_phase": record.get("max_phase"),
            "status": record.get("status"),
        })

    return drugs


def _parse_clinical_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trial data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append({
            "nct_id": nct_id,
            "title": record.get("title", "Unknown Trial"),
            "phase": record.get("phase"),
            "status": record.get("status", "unknown"),
            "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
        })

    return trials


def _parse_disease_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "name": record.get("disease", "Unknown"),
            "curie": record.get("disease_id", "unknown:unknown"),
            "description": record.get("description"),
        })

    return diseases


# ============================================================================
# Tool 2: Gene/Feature Query - Mode Handlers
# ============================================================================

async def _gene_to_features(args: dict[str, Any]) -> dict[str, Any]:
    """Get comprehensive gene profile with all requested features."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    result = {
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
    }

    # Fetch requested features
    if args.get("include_expression", True):
        expression_data = await adapter.query(
            "get_tissues_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_expression_data(expression_data)

    if args.get("include_go_terms", True):
        go_data = await adapter.query(
            "get_go_terms_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["go_terms"] = _parse_go_annotations(go_data)

    if args.get("include_pathways", True):
        pathway_data = await adapter.query(
            "get_pathways_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["pathways"] = _parse_pathway_memberships(pathway_data)

    if args.get("include_diseases", True):
        disease_data = await adapter.query(
            "get_diseases_for_gene",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["diseases"] = _parse_disease_associations(disease_data)

    # Optional features
    if args.get("include_domains", False):
        result["domains"] = []

    if args.get("include_variants", False):
        result["variants"] = []

    if args.get("include_phenotypes", False):
        result["phenotypes"] = []

    if args.get("include_codependencies", False):
        result["codependencies"] = []

    return result


async def _tissue_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes expressed in a specific tissue."""
    tissue_input = args["tissue"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # For now, accept tissue name directly
    tissue_id = tissue_input if isinstance(tissue_input, str) else tissue_input[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_in_tissue",
        tissue_id=tissue_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _go_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes annotated with a specific GO term."""
    go_input = args["go_term"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    go_id = go_input if isinstance(go_input, str) else go_input[1]

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_go_term",
        go_id=go_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    genes = _parse_gene_list(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _domain_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes containing a specific protein domain."""
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Domain queries not yet implemented in backend",
    }


async def _phenotype_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Find genes associated with a specific phenotype."""
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    return {
        "genes": [],
        "pagination": {
            "total_count": 0,
            "count": 0,
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
        },
        "note": "Phenotype queries not yet implemented in backend",
    }


# Data parsing helpers for Tool 2
def _parse_expression_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse tissue expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expressions = []
    for record in data["records"]:
        expressions.append({
            "tissue": {
                "name": record.get("tissue", "Unknown"),
                "curie": record.get("tissue_id", "unknown:unknown"),
                "namespace": "uberon",
                "identifier": record.get("tissue_id", "unknown"),
            },
            "confidence": record.get("confidence", "unknown"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return expressions


def _parse_go_annotations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse GO annotations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    annotations = []
    for record in data["records"]:
        annotations.append({
            "go_term": {
                "name": record.get("term", "Unknown"),
                "curie": record.get("go_id", "unknown:unknown"),
                "namespace": "go",
                "identifier": record.get("go_id", "unknown"),
            },
            "aspect": record.get("aspect", "unknown"),
            "evidence_code": record.get("evidence_code", "N/A"),
        })

    return annotations


def _parse_pathway_memberships(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway memberships from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append({
            "pathway": {
                "name": record.get("pathway", "Unknown"),
                "curie": record.get("pathway_id", "unknown:unknown"),
                "namespace": record.get("source", "unknown"),
                "identifier": record.get("pathway_id", "unknown"),
            },
            "source": record.get("source", "unknown"),
        })

    return pathways


def _parse_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append({
            "name": record.get("gene", "Unknown"),
            "curie": record.get("gene_id", "unknown:unknown"),
            "namespace": "hgnc",
            "identifier": record.get("gene_id", "unknown"),
        })

    return genes


# ============================================================================
# Tool Handler Stubs (implementations would continue similarly for all tools)
# ============================================================================

async def _handle_gene_feature_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle gene/feature query - Tool 2."""
    mode = args.get("mode")
    response_format = args.get("response_format", "markdown")

    # Route to appropriate handler based on mode
    if mode == "gene_to_features":
        if not args.get("gene"):
            return [types.TextContent(
                type="text",
                text="Error: gene parameter required for gene_to_features mode"
            )]
        result = await _gene_to_features(args)
    elif mode == "tissue_to_genes":
        if not args.get("tissue"):
            return [types.TextContent(
                type="text",
                text="Error: tissue parameter required for tissue_to_genes mode"
            )]
        result = await _tissue_to_genes(args)
    elif mode == "go_to_genes":
        if not args.get("go_term"):
            return [types.TextContent(
                type="text",
                text="Error: go_term parameter required for go_to_genes mode"
            )]
        result = await _go_to_genes(args)
    elif mode == "domain_to_genes":
        if not args.get("domain"):
            return [types.TextContent(
                type="text",
                text="Error: domain parameter required for domain_to_genes mode"
            )]
        result = await _domain_to_genes(args)
    elif mode == "phenotype_to_genes":
        if not args.get("phenotype"):
            return [types.TextContent(
                type="text",
                text="Error: phenotype parameter required for phenotype_to_genes mode"
            )]
        result = await _phenotype_to_genes(args)
    else:
        return [types.TextContent(
            type="text",
            text=f"Error: Unknown query mode '{mode}'"
        )]

    # Format response
    formatter = get_formatter()
    response = formatter.format_response(
        data=result,
        format_type=response_format,
        max_chars=CHARACTER_LIMIT,
    )

    return [types.TextContent(type="text", text=response)]


async def _handle_subnetwork_extraction(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle subnetwork extraction - Tool 3."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "direct":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: direct mode requires at least 2 genes"
                )]
            result = await _extract_direct(args)
        elif mode == "mediated":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: mediated mode requires at least 2 genes"
                )]
            result = await _extract_mediated(args)
        elif mode == "shared_upstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_upstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_upstream(args)
        elif mode == "shared_downstream":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: shared_downstream mode requires at least 2 genes"
                )]
            result = await _extract_shared_downstream(args)
        elif mode == "source_to_targets":
            if not args.get("source_gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: source_to_targets mode requires source_gene parameter"
                )]
            result = await _extract_source_to_targets(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown subnetwork mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 3 Mode Handlers
async def _extract_direct(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: direct - Extract direct mechanistic edges between specified genes."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("indra_subnetwork", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_network_statistics(nodes, statements)

    return {"nodes": nodes, "statements": statements, "statistics": statistics}


async def _extract_mediated(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: mediated - Find two-hop paths connecting genes through intermediates."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("indra_mediated_subnetwork", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    nodes = _extract_nodes_from_statements(statements, resolved_genes)
    statistics = _compute_network_statistics(nodes, statements)

    return {"nodes": nodes, "statements": statements, "statistics": statistics, "note": "Paths shown are two-hop"}


async def _extract_shared_upstream(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: shared_upstream - Find shared regulators."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    return {
        "nodes": [{"name": g.name, "curie": g.curie, "namespace": g.namespace, "identifier": g.identifier} for g in resolved_genes],
        "statements": [],
        "statistics": {"node_count": len(resolved_genes), "edge_count": 0, "statement_types": {}, "avg_evidence_per_statement": 0.0, "avg_belief_score": 0.0},
        "note": "Shared upstream queries not yet implemented in backend",
    }


async def _extract_shared_downstream(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: shared_downstream - Find shared targets."""
    genes = args["genes"]
    resolver = get_resolver()
    resolved_genes = []
    for gene in genes:
        resolved = await resolver.resolve_gene(gene)
        resolved_genes.append(resolved)

    return {
        "nodes": [{"name": g.name, "curie": g.curie, "namespace": g.namespace, "identifier": g.identifier} for g in resolved_genes],
        "statements": [],
        "statistics": {"node_count": len(resolved_genes), "edge_count": 0, "statement_types": {}, "avg_evidence_per_statement": 0.0, "avg_belief_score": 0.0},
        "note": "Shared downstream queries not yet implemented in backend",
    }


async def _extract_source_to_targets(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: source_to_targets - Find all downstream targets of a source gene."""
    source_gene = args["source_gene"]
    resolver = get_resolver()
    source = await resolver.resolve_gene(source_gene)

    target_genes = []
    if args.get("target_genes"):
        for gene in args["target_genes"]:
            resolved = await resolver.resolve_gene(gene)
            target_genes.append(resolved)

    adapter = await get_adapter()
    query_params = {
        "source_gene_id": source.curie,
        "statement_types": args.get("statement_types"),
        "min_evidence": args.get("min_evidence_count", 1),
        "min_belief": args.get("min_belief_score", 0.0),
        "max_statements": args.get("max_statements", 100),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }
    if target_genes:
        query_params["target_gene_ids"] = [g.curie for g in target_genes]
    if args.get("tissue_filter"):
        query_params["tissue"] = args["tissue_filter"]
    if args.get("go_filter"):
        query_params["go_term"] = args["go_filter"]

    stmt_data = await adapter.query("source_target_analysis", **query_params)
    statements = _parse_subnetwork_statements(stmt_data, args.get("include_evidence", False))
    all_resolved = [source] + target_genes
    nodes = _extract_nodes_from_statements(statements, all_resolved)
    statistics = _compute_network_statistics(nodes, statements)

    return {
        "source_gene": {"name": source.name, "curie": source.curie, "namespace": source.namespace, "identifier": source.identifier},
        "nodes": nodes,
        "statements": statements,
        "statistics": statistics,
    }


def _parse_subnetwork_statements(data: dict[str, Any], include_evidence: bool = False) -> list[dict[str, Any]]:
    """Parse INDRA statements from backend response."""
    if not data.get("success") or not data.get("statements"):
        return []

    statements = []
    for record in data["statements"]:
        stmt = {
            "stmt_hash": record.get("hash", ""),
            "stmt_type": record.get("type", "Unknown"),
            "subject": {
                "name": record.get("subj_name", "Unknown"),
                "curie": record.get("subj_id", "unknown:unknown"),
                "namespace": record.get("subj_namespace", "unknown"),
                "identifier": record.get("subj_identifier", "unknown"),
            },
            "object": {
                "name": record.get("obj_name", "Unknown"),
                "curie": record.get("obj_id", "unknown:unknown"),
                "namespace": record.get("obj_namespace", "unknown"),
                "identifier": record.get("obj_identifier", "unknown"),
            },
            "residue": record.get("residue"),
            "position": record.get("position"),
            "evidence_count": record.get("evidence_count", 0),
            "belief_score": record.get("belief", 0.0),
            "sources": record.get("sources", []),
        }
        if include_evidence:
            stmt["evidence"] = record.get("evidence")
        statements.append(stmt)

    return statements


def _extract_nodes_from_statements(statements: list[dict[str, Any]], resolved_genes: list) -> list[dict[str, Any]]:
    """Extract unique nodes from statements and resolved genes."""
    nodes_dict: dict[str, dict[str, Any]] = {}
    for gene in resolved_genes:
        nodes_dict[gene.curie] = {"name": gene.name, "curie": gene.curie, "namespace": gene.namespace, "identifier": gene.identifier}

    for stmt in statements:
        if stmt["subject"]["curie"] not in nodes_dict:
            nodes_dict[stmt["subject"]["curie"]] = stmt["subject"]
        if stmt["object"]["curie"] not in nodes_dict:
            nodes_dict[stmt["object"]["curie"]] = stmt["object"]

    return list(nodes_dict.values())


def _compute_network_statistics(nodes: list[dict[str, Any]], statements: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute network-level statistics."""
    stmt_types: dict[str, int] = {}
    total_evidence = 0
    total_belief = 0.0

    for stmt in statements:
        stmt_type = stmt["stmt_type"]
        stmt_types[stmt_type] = stmt_types.get(stmt_type, 0) + 1
        total_evidence += stmt["evidence_count"]
        total_belief += stmt["belief_score"]

    return {
        "node_count": len(nodes),
        "edge_count": len(statements),
        "statement_types": stmt_types,
        "avg_evidence_per_statement": total_evidence / len(statements) if statements else 0.0,
        "avg_belief_score": total_belief / len(statements) if statements else 0.0,
    }


async def _handle_enrichment_analysis(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle enrichment analysis - Tool 4."""
    try:
        analysis_type = args.get("analysis_type")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on analysis type
        if analysis_type == "discrete":
            result = await _analyze_discrete(args)
        elif analysis_type == "continuous":
            result = await _analyze_continuous(args)
        elif analysis_type == "signed":
            result = await _analyze_signed(args)
        elif analysis_type == "metabolite":
            result = await _analyze_metabolite(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown analysis type '{analysis_type}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 4 Mode Handlers
async def _analyze_discrete(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: discrete - Overrepresentation analysis using Fisher's exact test."""
    if not args.get("gene_list"):
        raise ValueError("gene_list parameter required for discrete analysis")

    # Resolve gene identifiers
    resolver = get_resolver()
    resolved_genes = []
    failed_genes = []

    for gene in args["gene_list"]:
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_genes.append(resolved)
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_genes:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    if failed_genes:
        logger.info(
            f"Proceeding with {len(resolved_genes)}/{len(args['gene_list'])} genes. "
            f"Failed: {', '.join(failed_genes[:5])}{'...' if len(failed_genes) > 5 else ''}"
        )

    # Optionally resolve background genes
    background_gene_ids = None
    if args.get("background_genes"):
        background_resolved = []
        for gene in args["background_genes"]:
            try:
                resolved = await resolver.resolve_gene(gene)
                background_resolved.append(resolved)
            except EntityResolutionError:
                pass
        background_gene_ids = [g.curie for g in background_resolved]

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "gene_ids": [g.curie for g in resolved_genes],
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_gene_ids:
        query_params["background_gene_ids"] = background_gene_ids

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("discrete_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="discrete")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_genes))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_genes),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_continuous(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: continuous - Gene Set Enrichment Analysis (GSEA) with ranked gene list."""
    if not args.get("ranked_genes"):
        raise ValueError("ranked_genes parameter required for continuous analysis")

    # Resolve gene identifiers and preserve scores
    resolver = get_resolver()
    resolved_ranking: dict[str, float] = {}
    failed_genes = []

    for gene, score in args["ranked_genes"].items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "permutations": args.get("permutations", 1000),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("continuous_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="continuous")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_ranking))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_ranking),
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_signed(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: signed - Directional enrichment analysis (separate up/down regulation)."""
    if not args.get("ranked_genes"):
        raise ValueError("ranked_genes parameter required for signed analysis")

    # Resolve gene identifiers and preserve signed scores
    resolver = get_resolver()
    resolved_ranking: dict[str, float] = {}
    failed_genes = []

    for gene, score in args["ranked_genes"].items():
        try:
            resolved = await resolver.resolve_gene(gene)
            resolved_ranking[resolved.curie] = score
        except EntityResolutionError as e:
            logger.warning(f"Failed to resolve gene '{gene}': {e}")
            failed_genes.append(gene)

    if not resolved_ranking:
        raise ValueError(f"No genes could be resolved. Failed: {', '.join(failed_genes)}")

    # Count up/down regulated genes
    upregulated = sum(1 for score in resolved_ranking.values() if score > 0)
    downregulated = sum(1 for score in resolved_ranking.values() if score < 0)

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "ranked_genes": resolved_ranking,
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "permutations": args.get("permutations", 1000),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    # Add INDRA-specific parameters if applicable
    source = args.get("source", "go")
    if source in ["indra-upstream", "indra-downstream"]:
        query_params["min_evidence_count"] = args.get("min_evidence_count", 1)
        query_params["min_belief_score"] = args.get("min_belief_score", 0.0)

    enrichment_data = await adapter.query("signed_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="signed")
    statistics = _compute_enrichment_statistics(results, args, len(resolved_ranking))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "resolved_genes": len(resolved_ranking),
        "upregulated_count": upregulated,
        "downregulated_count": downregulated,
        "failed_genes": failed_genes if failed_genes else None,
    }


async def _analyze_metabolite(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: metabolite - Metabolite set enrichment analysis."""
    if not args.get("gene_list"):
        raise ValueError("gene_list parameter required for metabolite analysis")

    # For metabolite analysis, we don't resolve through gene resolver
    # Metabolites have their own identifier format (e.g., HMDB, ChEBI)
    # Pass them directly to backend
    metabolite_ids = args["gene_list"]

    # Optionally resolve background metabolites
    background_metabolite_ids = args.get("background_genes") if args.get("background_genes") else None

    # Query backend
    adapter = await get_adapter()

    query_params = {
        "metabolite_ids": metabolite_ids,
        "source": args.get("source", "go"),
        "alpha": args.get("alpha", 0.05),
        "correction_method": args.get("correction_method", "fdr_bh"),
        "keep_insignificant": args.get("keep_insignificant", False),
        "timeout": ENRICHMENT_TIMEOUT,
    }

    if background_metabolite_ids:
        query_params["background_metabolite_ids"] = background_metabolite_ids

    enrichment_data = await adapter.query("metabolite_discrete_analysis", **query_params)

    # Parse results
    results = _parse_enrichment_results(enrichment_data, analysis_type="metabolite")
    statistics = _compute_enrichment_statistics(results, args, len(metabolite_ids))

    return {
        "results": [r for r in results],
        "statistics": statistics,
        "total_metabolites": len(metabolite_ids),
    }


# Data parsing helpers for Tool 4
def _parse_enrichment_results(data: dict[str, Any], analysis_type: str) -> list[dict[str, Any]]:
    """Parse enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse term entity
        term = {
            "name": record.get("term_name", "Unknown"),
            "curie": record.get("term_id", "unknown:unknown"),
            "namespace": record.get("term_namespace", "unknown"),
            "identifier": record.get("term_identifier", "unknown"),
        }

        # Build result object
        result_dict = {
            "term": term,
            "term_name": record.get("term_name", "Unknown"),
            "p_value": record.get("p_value", 1.0),
            "adjusted_p_value": record.get("adjusted_p_value", 1.0),
            "gene_count": record.get("gene_count", 0),
            "term_size": record.get("term_size", 0),
            "genes": record.get("genes", []),
            "background_count": record.get("background_count"),
        }

        # Add GSEA-specific fields for continuous/signed analysis
        if analysis_type in ["continuous", "signed"]:
            result_dict["enrichment_score"] = record.get("enrichment_score")
            result_dict["normalized_enrichment_score"] = record.get("normalized_enrichment_score")

        results.append(result_dict)

    return results


def _compute_enrichment_statistics(results: list[dict[str, Any]], args: dict[str, Any], total_genes: int) -> dict[str, Any]:
    """Compute overall enrichment statistics."""
    # Count significant results
    alpha = args.get("alpha", 0.05)
    significant_results = sum(1 for r in results if r.get("adjusted_p_value", 1.0) <= alpha)

    return {
        "total_results": len(results),
        "significant_results": significant_results,
        "total_genes_analyzed": total_genes,
        "correction_method": args.get("correction_method", "fdr_bh"),
        "alpha": alpha,
    }


def _parse_disease_associations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse disease associations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    diseases = []
    for record in data["records"]:
        diseases.append({
            "disease": {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
            },
            "score": record.get("score", 0.0),
            "evidence_count": record.get("evidence_count", 0),
        })

    return diseases


async def _handle_drug_effect_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle drug/effect query - Tool 5."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "drug_to_profile":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for drug_to_profile mode"
                )]
            result = await _drug_to_profile(args)
        elif mode == "side_effect_to_drugs":
            if not args.get("side_effect"):
                return [types.TextContent(
                    type="text",
                    text="Error: side_effect parameter required for side_effect_to_drugs mode"
                )]
            result = await _side_effect_to_drugs(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 5 Mode Handlers
async def _drug_to_profile(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: drug_to_profile - Get comprehensive drug profile with all requested features."""
    drug_input = args["drug"]

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(drug_input)

    adapter = await get_adapter()
    result = {
        "drug": {
            "name": drug.name,
            "curie": drug.curie,
            "namespace": drug.namespace,
            "identifier": drug.identifier,
        }
    }

    # Fetch requested features
    if args.get("include_targets", True):
        target_data = await adapter.query(
            "get_targets_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["targets"] = _parse_drug_targets(target_data)

    if args.get("include_indications", True):
        indication_data = await adapter.query(
            "get_indications_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["indications"] = _parse_drug_indications(indication_data)

    if args.get("include_side_effects", True):
        side_effect_data = await adapter.query(
            "get_side_effects_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["side_effects"] = _parse_drug_side_effects(side_effect_data)

    if args.get("include_trials", False):
        trial_data = await adapter.query(
            "get_trials_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["trials"] = _parse_drug_trials(trial_data)

    if args.get("include_cell_lines", False):
        cell_line_data = await adapter.query(
            "get_sensitive_cell_lines_for_drug",
            drug_id=drug.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["cell_lines"] = _parse_drug_cell_lines(cell_line_data)

    return result


async def _side_effect_to_drugs(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: side_effect_to_drugs - Find drugs associated with a specific side effect."""
    side_effect_input = args["side_effect"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Parse side effect identifier
    # For now, accept side effect name directly
    side_effect_id = side_effect_input if isinstance(side_effect_input, str) else side_effect_input[1]

    adapter = await get_adapter()
    drug_data = await adapter.query(
        "get_drugs_for_side_effect",
        side_effect_id=side_effect_id,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse drugs
    drugs = _parse_drug_list_for_side_effect(drug_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=drugs,
        total_count=drug_data.get("total_count", len(drugs)),
        offset=offset,
        limit=limit,
    )

    return {
        "drugs": drugs,
        "pagination": pagination.model_dump(),
    }


# Data parsing helpers for Tool 5
def _parse_drug_targets(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug targets from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    targets = []
    for record in data["records"]:
        targets.append({
            "target": {
                "name": record.get("target", "Unknown"),
                "curie": record.get("target_id", "unknown:unknown"),
                "namespace": record.get("target_namespace", "hgnc"),
                "identifier": record.get("target_id", "unknown"),
            },
            "action_type": record.get("action_type"),
            "evidence_count": record.get("evidence_count", 0),
        })

    return targets


def _parse_drug_indications(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug indications from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    indications = []
    for record in data["records"]:
        indications.append({
            "disease": {
                "name": record.get("disease", "Unknown"),
                "curie": record.get("disease_id", "unknown:unknown"),
                "namespace": "mondo",
                "identifier": record.get("disease_id", "unknown"),
            },
            "indication_type": record.get("indication_type", "unknown"),
            "max_phase": record.get("max_phase"),
        })

    return indications


def _parse_drug_side_effects(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse side effects from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    side_effects = []
    for record in data["records"]:
        side_effects.append({
            "effect": {
                "name": record.get("effect", "Unknown"),
                "curie": record.get("effect_id", "unknown:unknown"),
                "namespace": "umls",
                "identifier": record.get("effect_id", "unknown"),
            },
            "frequency": record.get("frequency"),
        })

    return side_effects


def _parse_drug_trials(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse clinical trials from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        nct_id = record.get("nct_id", "unknown")
        trials.append({
            "nct_id": nct_id,
            "title": record.get("title", "Unknown"),
            "phase": record.get("phase"),
            "status": record.get("status", "unknown"),
            "conditions": record.get("conditions", []),
            "interventions": record.get("interventions", []),
            "url": f"https://clinicaltrials.gov/ct2/show/{nct_id}",
        })

    return trials


def _parse_drug_cell_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line sensitivity data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_lines.append({
            "cell_line": record.get("cell_line", "Unknown"),
            "sensitivity_score": record.get("sensitivity_score", 0.0),
        })

    return cell_lines


def _parse_drug_list_for_side_effect(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse drug list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    drugs = []
    for record in data["records"]:
        drugs.append({
            "name": record.get("drug", "Unknown"),
            "curie": record.get("drug_id", "unknown:unknown"),
            "namespace": "chembl",
            "identifier": record.get("drug_id", "unknown"),
            "synonyms": record.get("synonyms", []),
            "drug_type": record.get("drug_type"),
        })

    return drugs


async def _handle_pathway_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle pathway query - Tool 6."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_genes":
            if not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: pathway parameter required for get_genes mode"
                )]
            result = await _get_genes_in_pathway(args)
        elif mode == "get_pathways":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_pathways mode"
                )]
            result = await _get_pathways_for_gene(args)
        elif mode == "find_shared":
            if not args.get("genes") or len(args.get("genes", [])) < 2:
                return [types.TextContent(
                    type="text",
                    text="Error: genes parameter required with at least 2 genes for find_shared mode"
                )]
            result = await _find_shared_pathways(args)
        elif mode == "check_membership":
            if not args.get("gene") or not args.get("pathway"):
                return [types.TextContent(
                    type="text",
                    text="Error: both gene and pathway parameters required for check_membership mode"
                )]
            result = await _check_pathway_membership(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 6 Mode Handlers
async def _get_genes_in_pathway(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_genes - Get all genes in a specific pathway."""
    pathway_input = args["pathway"]

    # Parse pathway identifier
    if isinstance(pathway_input, tuple):
        pathway_id = f"{pathway_input[0]}:{pathway_input[1]}"
    else:
        pathway_id = pathway_input

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "pathway_id": pathway_id,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("get_genes_in_pathway", **query_params)

    # Parse pathway metadata
    pathway_node = _parse_pathway_node(pathway_data.get("pathway", {}))

    # Parse gene list
    genes = _parse_pathway_gene_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=pathway_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "pathway": pathway_node.model_dump() if pathway_node else None,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _get_pathways_for_gene(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_pathways - Get all pathways containing a specific gene."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": gene.curie,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("get_pathways_for_gene", **query_params)

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "gene": gene.model_dump(),
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _find_shared_pathways(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: find_shared - Find pathways containing ALL specified genes."""
    genes_input = args["genes"]

    # Resolve all gene identifiers
    resolver = get_resolver()
    gene_curies = []

    for gene_input in genes_input:
        gene = await resolver.resolve_gene(gene_input)
        gene_curies.append(gene.curie)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_ids": gene_curies,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    if args.get("pathway_source"):
        query_params["source"] = args["pathway_source"]

    pathway_data = await adapter.query("get_shared_pathways_for_genes", **query_params)

    # Parse pathway list
    pathways = _parse_pathway_list(pathway_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=pathways,
        total_count=pathway_data.get("total_count", len(pathways)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "genes": genes_input,
        "pathways": pathways,
        "pagination": pagination.model_dump(),
    }


async def _check_pathway_membership(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_membership - Check if a specific gene is in a specific pathway."""
    gene_input = args["gene"]
    pathway_input = args["pathway"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    # Parse pathway identifier
    if isinstance(pathway_input, tuple):
        pathway_id = f"{pathway_input[0]}:{pathway_input[1]}"
    else:
        pathway_id = pathway_input

    adapter = await get_adapter()
    result_data = await adapter.query(
        "is_gene_in_pathway",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse result
    is_member = result_data.get("is_member", False) if result_data.get("success") else False

    # Parse pathway metadata if available
    pathway_node = None
    if result_data.get("pathway"):
        pathway_node = _parse_pathway_node(result_data["pathway"])

    return {
        "is_member": is_member,
        "gene": gene.model_dump(),
        "pathway": pathway_node.model_dump() if pathway_node else {"pathway_id": pathway_id},
    }


# Data parsing helpers for Tool 6
def _parse_pathway_node(data: dict[str, Any]) -> Any:
    """Parse pathway node from backend response."""
    if not data:
        return None

    try:
        from cogex_mcp.schemas import PathwayNode
        return PathwayNode(
            name=data.get("name", data.get("pathway", "Unknown")),
            curie=data.get("curie", data.get("pathway_id", "unknown:unknown")),
            source=data.get("source", "unknown"),
            description=data.get("description"),
            gene_count=data.get("gene_count", 0),
            url=data.get("url"),
        )
    except Exception as e:
        logger.warning(f"Error parsing pathway node: {e}")
        return None


def _parse_pathway_gene_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from pathway backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append({
            "name": record.get("gene", record.get("name", "Unknown")),
            "curie": record.get("gene_id", record.get("curie", "unknown:unknown")),
            "namespace": "hgnc",
            "identifier": record.get("gene_id", record.get("identifier", "unknown")),
            "description": record.get("description"),
        })

    return genes


def _parse_pathway_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse pathway list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    pathways = []
    for record in data["records"]:
        pathways.append({
            "name": record.get("pathway", record.get("name", "Unknown")),
            "curie": record.get("pathway_id", record.get("curie", "unknown:unknown")),
            "source": record.get("source", "unknown"),
            "description": record.get("description"),
            "gene_count": record.get("gene_count", 0),
            "url": record.get("url"),
        })

    return pathways



async def _handle_cell_line_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle cell line query - Tool 7."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_properties":
            if not args.get("cell_line"):
                return [types.TextContent(
                    type="text",
                    text="Error: cell_line parameter required for get_properties mode"
                )]
            result = await _get_cell_line_properties(args)
        elif mode == "get_mutated_genes":
            if not args.get("cell_line"):
                return [types.TextContent(
                    type="text",
                    text="Error: cell_line parameter required for get_mutated_genes mode"
                )]
            result = await _get_mutated_genes(args)
        elif mode == "get_cell_lines_with_mutation":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_cell_lines_with_mutation mode"
                )]
            result = await _get_cell_lines_with_mutation(args)
        elif mode == "check_mutation":
            if not args.get("cell_line") or not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: both cell_line and gene parameters required for check_mutation mode"
                )]
            result = await _check_cell_line_mutation(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 7 Mode Handlers
async def _get_cell_line_properties(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_properties - Get comprehensive cell line profile with all requested features."""
    cell_line_name = args["cell_line"]

    adapter = await get_adapter()
    result = {
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
            "tissue": None,
            "disease": None,
        },
    }

    # Fetch requested features
    if args.get("include_mutations", True):
        mutation_data = await adapter.query(
            "get_mutations_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["mutations"] = _parse_cell_line_mutations(mutation_data)

    if args.get("include_copy_number", True):
        cna_data = await adapter.query(
            "get_copy_number_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["copy_number_alterations"] = _parse_copy_number(cna_data)

    if args.get("include_dependencies", False):
        dep_data = await adapter.query(
            "get_dependencies_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["dependencies"] = _parse_dependencies(dep_data)

    if args.get("include_expression", False):
        expr_data = await adapter.query(
            "get_expression_for_cell_line",
            cell_line=cell_line_name,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
        result["expression"] = _parse_cell_line_expression(expr_data)

    return result


async def _get_mutated_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_mutated_genes - Get list of genes mutated in cell line."""
    cell_line_name = args["cell_line"]

    adapter = await get_adapter()
    mutation_data = await adapter.query(
        "get_mutations_for_cell_line",
        cell_line=cell_line_name,
        limit=args.get("limit", 20),
        offset=args.get("offset", 0),
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse genes from mutations
    genes = _parse_gene_list_from_cell_line_mutations(mutation_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=mutation_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
        },
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _get_cell_lines_with_mutation(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_cell_lines_with_mutation - Find cell lines with specific gene mutation."""
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    cell_line_data = await adapter.query(
        "get_cell_lines_for_mutation",
        gene_id=gene.curie,
        limit=args.get("limit", 20),
        offset=args.get("offset", 0),
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse cell lines
    cell_lines = _parse_cell_line_list(cell_line_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_lines,
        total_count=cell_line_data.get("total_count", len(cell_lines)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "gene": gene.model_dump(),
        "cell_lines": cell_lines,
        "pagination": pagination.model_dump(),
    }


async def _check_cell_line_mutation(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_mutation - Check if gene is mutated in cell line."""
    cell_line_name = args["cell_line"]
    gene_input = args["gene"]

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=cell_line_name,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    has_mutation = check_data.get("result", False)

    return {
        "has_mutation": has_mutation,
        "cell_line": {
            "name": cell_line_name,
            "ccle_id": f"ccle:{cell_line_name}",
            "depmap_id": f"depmap:{cell_line_name}",
        },
        "gene": gene.model_dump(),
    }


# Data parsing helpers for Tool 7
def _parse_cell_line_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse mutations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    mutations = []
    for record in data["records"]:
        mutations.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "mutation_type": record.get("mutation_type", "unknown"),
            "protein_change": record.get("protein_change"),
            "is_driver": record.get("is_driver", False),
        })

    return mutations


def _parse_copy_number(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse copy number alterations from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cnas = []
    for record in data["records"]:
        copy_num = record.get("copy_number", 2.0)
        if copy_num > 2.5:
            alt_type = "amplification"
        elif copy_num < 1.5:
            alt_type = "deletion"
        else:
            alt_type = "neutral"

        cnas.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "copy_number": copy_num,
            "alteration_type": alt_type,
        })

    return cnas


def _parse_dependencies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene dependencies from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    dependencies = []
    for record in data["records"]:
        dependencies.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "dependency_score": record.get("dependency_score", 0.0),
            "percentile": record.get("percentile"),
        })

    return dependencies


def _parse_cell_line_expression(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse expression data from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    expression = []
    for record in data["records"]:
        expression.append({
            "gene": {
                "name": record.get("gene", "Unknown"),
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
            },
            "expression_value": record.get("expression_value", 0.0),
            "unit": record.get("unit", "TPM"),
        })

    return expression


def _parse_gene_list_from_cell_line_mutations(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from mutation data."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    seen_genes = set()

    for record in data["records"]:
        gene_name = record.get("gene", "Unknown")
        if gene_name not in seen_genes:
            seen_genes.add(gene_name)
            genes.append({
                "name": gene_name,
                "curie": record.get("gene_id", "unknown:unknown"),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", "unknown"),
                "description": None,
                "synonyms": [],
            })

    return genes


def _parse_cell_line_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell line list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_lines = []
    for record in data["records"]:
        cell_line_name = record.get("cell_line", "Unknown")
        cell_lines.append({
            "name": cell_line_name,
            "ccle_id": record.get("ccle_id", f"ccle:{cell_line_name}"),
            "depmap_id": record.get("depmap_id", f"depmap:{cell_line_name}"),
            "tissue": record.get("tissue"),
            "disease": record.get("disease"),
        })

    return cell_lines


async def _handle_clinical_trials_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle clinical trials query - Tool 8."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_drug":
            if not args.get("drug"):
                return [types.TextContent(
                    type="text",
                    text="Error: drug parameter required for get_for_drug mode"
                )]
            result = await _get_trials_for_drug(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_trials_for_disease(args)
        elif mode == "get_by_id":
            if not args.get("trial_id"):
                return [types.TextContent(
                    type="text",
                    text="Error: trial_id parameter required for get_by_id mode"
                )]
            result = await _get_trial_by_id(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 8 Mode Handlers
async def _get_trials_for_drug(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_drug - Get clinical trials testing a specific drug."""
    drug_input = args["drug"]

    # Resolve drug identifier
    resolver = get_resolver()
    drug = await resolver.resolve_drug(drug_input)

    # Build query parameters
    query_params = {
        "drug_id": drug.curie,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if args.get("phase"):
        query_params["phase"] = args["phase"]
    if args.get("status"):
        query_params["status"] = args["status"]

    adapter = await get_adapter()
    trial_data = await adapter.query("get_trials_for_drug", **query_params)

    # Parse trials
    trials = _parse_trial_list(trial_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_count", len(trials)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trials_for_disease(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_disease - Get clinical trials for a specific disease."""
    disease_input = args["disease"]

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    # Build query parameters
    query_params = {
        "disease_id": disease.curie,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if args.get("phase"):
        query_params["phase"] = args["phase"]
    if args.get("status"):
        query_params["status"] = args["status"]

    adapter = await get_adapter()
    trial_data = await adapter.query("get_trials_for_disease", **query_params)

    # Parse trials
    trials = _parse_trial_list(trial_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=trials,
        total_count=trial_data.get("total_count", len(trials)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "trials": trials,
        "pagination": pagination.model_dump(),
    }


async def _get_trial_by_id(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_by_id - Get details for a specific clinical trial by NCT ID."""
    trial_id = args["trial_id"]

    adapter = await get_adapter()
    trial_data = await adapter.query(
        "get_trial_by_id",
        nct_id=trial_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    if not trial_data.get("success"):
        raise ValueError(f"Trial {trial_id} not found")

    # Parse single trial
    trial = _parse_single_trial(trial_data.get("record", {}))

    return {
        "trial": trial,
    }


# Data parsing helpers for Tool 8
def _parse_trial_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse list of clinical trials from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    trials = []
    for record in data["records"]:
        trials.append(_parse_single_trial(record))

    return trials


def _parse_single_trial(record: dict[str, Any]) -> dict[str, Any]:
    """Parse a single clinical trial record."""
    nct_id = record.get("nct_id", "unknown")

    # Build ClinicalTrials.gov URL
    url = f"https://clinicaltrials.gov/ct2/show/{nct_id}"

    trial = {
        "nct_id": nct_id,
        "title": record.get("title", "Unknown"),
        "phase": record.get("phase"),
        "status": record.get("status", "unknown"),
        "conditions": record.get("conditions", []),
        "interventions": record.get("interventions", []),
        "url": url,
    }

    # Add optional fields if available
    if "start_date" in record:
        trial["start_date"] = record["start_date"]
    if "completion_date" in record:
        trial["completion_date"] = record["completion_date"]
    if "enrollment" in record:
        trial["enrollment"] = record["enrollment"]
    if "sponsor" in record:
        trial["sponsor"] = record["sponsor"]

    return trial



# ============================================================================
# Tool 9: Literature Query
# ============================================================================

async def _handle_literature_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle literature query - Tool 9."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_statements_for_pmid":
            if not args.get("pmid"):
                return [types.TextContent(
                    type="text",
                    text="Error: pmid parameter required for get_statements_for_pmid mode"
                )]
            result = await _get_statements_for_pmid(args)
        elif mode == "get_evidence_for_statement":
            if not args.get("statement_hash"):
                return [types.TextContent(
                    type="text",
                    text="Error: statement_hash parameter required for get_evidence_for_statement mode"
                )]
            result = await _get_evidence_for_statement(args)
        elif mode == "search_by_mesh":
            if not args.get("mesh_terms") or len(args.get("mesh_terms", [])) == 0:
                return [types.TextContent(
                    type="text",
                    text="Error: mesh_terms parameter required for search_by_mesh mode"
                )]
            result = await _search_by_mesh(args)
        elif mode == "get_statements_by_hashes":
            if not args.get("statement_hashes") or len(args.get("statement_hashes", [])) == 0:
                return [types.TextContent(
                    type="text",
                    text="Error: statement_hashes parameter required for get_statements_by_hashes mode"
                )]
            result = await _get_statements_by_hashes(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown literature query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 9 Mode Handlers
async def _get_statements_for_pmid(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_statements_for_pmid - Retrieve INDRA statements from a specific PubMed publication."""
    pmid = args["pmid"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    include_evidence_text = args.get("include_evidence_text", True)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "pmid": pmid,
        "limit": limit,
        "offset": offset,
        "include_evidence": include_evidence_text,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_statements_for_paper", **query_params)

    # Parse statements
    statements = _parse_literature_statements(stmt_data, include_evidence_text)

    # Build pagination
    total_count = stmt_data.get("total_count", len(statements))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(statements),
        offset=offset,
        limit=limit,
    )

    return {
        "pmid": pmid,
        "statements": statements,
        "pagination": pagination,
    }


async def _get_evidence_for_statement(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_evidence_for_statement - Retrieve evidence text snippets for a specific INDRA statement."""
    statement_hash = args["statement_hash"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "stmt_hash": statement_hash,
        "limit": limit,
        "offset": offset,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    evidence_data = await adapter.query("get_evidences_for_stmt_hash", **query_params)

    # Parse evidence
    evidence_list = _parse_literature_evidence(evidence_data)

    # Build pagination
    total_count = evidence_data.get("total_count", len(evidence_list))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(evidence_list),
        offset=offset,
        limit=limit,
    )

    return {
        "statement_hash": statement_hash,
        "evidence": evidence_list,
        "pagination": pagination,
    }


async def _search_by_mesh(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: search_by_mesh - Search PubMed publications by MeSH terms."""
    mesh_terms = args["mesh_terms"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    query_params = {
        "mesh_terms": mesh_terms,
        "limit": limit,
        "offset": offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    pub_data = await adapter.query("get_evidence_for_mesh", **query_params)

    # Parse publications
    publications = _parse_literature_publications(pub_data)

    # Build pagination
    total_count = pub_data.get("total_count", len(publications))
    pagination = _build_literature_pagination(
        total_count=total_count,
        count=len(publications),
        offset=offset,
        limit=limit,
    )

    return {
        "mesh_terms": mesh_terms,
        "publications": publications,
        "pagination": pagination,
    }


async def _get_statements_by_hashes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_statements_by_hashes - Batch retrieve INDRA statements by their hashes."""
    statement_hashes = args["statement_hashes"]
    include_evidence_text = args.get("include_evidence_text", True)
    max_evidence_per_statement = args.get("max_evidence_per_statement", 5)

    adapter = await get_adapter()
    query_params = {
        "stmt_hashes": statement_hashes,
        "include_evidence": include_evidence_text,
        "max_evidence": max_evidence_per_statement,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    stmt_data = await adapter.query("get_stmts_for_stmt_hashes", **query_params)

    # Parse statements
    statements = _parse_literature_statements(stmt_data, include_evidence_text)

    # Build pagination (batch retrieval doesn't use offset/limit)
    pagination = _build_literature_pagination(
        total_count=len(statements),
        count=len(statements),
        offset=0,
        limit=len(statements),
    )

    return {
        "statements": statements,
        "pagination": pagination,
    }


# Data parsing helpers for Tool 9
def _parse_literature_statements(data: dict[str, Any], include_evidence: bool = False) -> list[dict[str, Any]]:
    """Parse INDRA statements from backend response."""
    if not data.get("success") or not data.get("statements"):
        return []

    statements = []
    for record in data["statements"]:
        # Parse evidence if requested
        evidence = None
        if include_evidence and record.get("evidence"):
            evidence = record["evidence"]

        stmt = {
            "stmt_hash": record.get("hash", ""),
            "stmt_type": record.get("type", "Unknown"),
            "subject": {
                "name": record.get("subj_name", "Unknown"),
                "curie": record.get("subj_id", "unknown:unknown"),
                "namespace": record.get("subj_namespace", "unknown"),
                "identifier": record.get("subj_identifier", "unknown"),
            },
            "object": {
                "name": record.get("obj_name", "Unknown"),
                "curie": record.get("obj_id", "unknown:unknown"),
                "namespace": record.get("obj_namespace", "unknown"),
                "identifier": record.get("obj_identifier", "unknown"),
            },
            "residue": record.get("residue"),
            "position": record.get("position"),
            "evidence_count": record.get("evidence_count", 0),
            "belief_score": record.get("belief", 0.0),
            "sources": record.get("sources", []),
            "evidence": evidence,
        }
        statements.append(stmt)

    return statements


def _parse_literature_evidence(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse evidence snippets from backend response."""
    if not data.get("success") or not data.get("evidence"):
        return []

    evidence_list = []
    for record in data["evidence"]:
        evidence = {
            "text": record.get("text", ""),
            "pmid": record.get("pmid"),
            "source_api": record.get("source_api", "unknown"),
            "annotations": record.get("annotations"),
        }
        evidence_list.append(evidence)

    return evidence_list


def _parse_literature_publications(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PubMed publications from backend response."""
    if not data.get("success") or not data.get("publications"):
        return []

    publications = []
    for record in data["publications"]:
        pmid = record.get("pmid", "")
        pub = {
            "pmid": pmid,
            "title": record.get("title", ""),
            "authors": record.get("authors", []),
            "journal": record.get("journal", ""),
            "year": record.get("year", 0),
            "abstract": record.get("abstract"),
            "mesh_terms": record.get("mesh_terms", []),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
        publications.append(pub)

    return publications


def _build_literature_pagination(total_count: int, count: int, offset: int, limit: int) -> dict[str, Any]:
    """Build pagination metadata."""
    has_more = (offset + count) < total_count
    next_offset = offset + count if has_more else None

    return {
        "total_count": total_count,
        "count": count,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset,
    }

async def _handle_variants_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle variants query - Tool 10."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "get_for_gene":
            if not args.get("gene"):
                return [types.TextContent(
                    type="text",
                    text="Error: gene parameter required for get_for_gene mode"
                )]
            result = await _get_variants_for_gene(args)
        elif mode == "get_for_disease":
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for get_for_disease mode"
                )]
            result = await _get_variants_for_disease(args)
        elif mode == "get_for_phenotype":
            if not args.get("phenotype"):
                return [types.TextContent(
                    type="text",
                    text="Error: phenotype parameter required for get_for_phenotype mode"
                )]
            result = await _get_variants_for_phenotype(args)
        elif mode == "variant_to_genes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_genes mode"
                )]
            result = await _variant_to_genes(args)
        elif mode == "variant_to_phenotypes":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for variant_to_phenotypes mode"
                )]
            result = await _variant_to_phenotypes(args)
        elif mode == "check_association":
            if not args.get("variant"):
                return [types.TextContent(
                    type="text",
                    text="Error: variant parameter required for check_association mode"
                )]
            if not args.get("disease"):
                return [types.TextContent(
                    type="text",
                    text="Error: disease parameter required for check_association mode"
                )]
            result = await _check_variant_association(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 10 Mode Handlers
async def _get_variants_for_gene(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_gene - Get variants in or near a specific gene."""
    gene_input = args["gene"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_gene",
        gene_id=gene.curie,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse variants and apply p-value filtering
    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_disease(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_disease - Get variants associated with a disease."""
    disease_input = args["disease"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_disease",
        disease_id=disease.curie,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _get_variants_for_phenotype(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: get_for_phenotype - Get GWAS hits for a phenotype."""
    phenotype_input = args["phenotype"]
    max_p_value = args.get("max_p_value", 0.00001)
    min_p_value = args.get("min_p_value")
    source = args.get("source")
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    # Parse phenotype identifier
    phenotype_id = phenotype_input if isinstance(phenotype_input, str) else phenotype_input[1]

    adapter = await get_adapter()
    variant_data = await adapter.query(
        "get_variants_for_phenotype",
        phenotype_id=phenotype_id,
        max_p_value=max_p_value,
        source=source,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    variants = _parse_variant_list(variant_data, min_p_value, max_p_value)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=variants,
        total_count=variant_data.get("total_count", len(variants)),
        offset=offset,
        limit=limit,
    )

    return {
        "variants": variants,
        "pagination": pagination.model_dump(),
    }


async def _variant_to_genes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: variant_to_genes - Find nearby genes for a variant."""
    variant = args["variant"]
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    gene_data = await adapter.query(
        "get_genes_for_variant",
        variant_id=variant,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse genes
    genes = _parse_gene_list_for_variant(gene_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=offset,
        limit=limit,
    )

    return {
        "variant": variant,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _variant_to_phenotypes(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: variant_to_phenotypes - Find associated phenotypes for a variant."""
    variant = args["variant"]
    max_p_value = args.get("max_p_value", 0.00001)
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    adapter = await get_adapter()
    phenotype_data = await adapter.query(
        "get_phenotypes_for_variant",
        variant_id=variant,
        max_p_value=max_p_value,
        limit=limit,
        offset=offset,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse phenotypes
    phenotypes = _parse_phenotype_list_for_variant(phenotype_data)

    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=phenotypes,
        total_count=phenotype_data.get("total_count", len(phenotypes)),
        offset=offset,
        limit=limit,
    )

    return {
        "variant": variant,
        "phenotypes": phenotypes,
        "pagination": pagination.model_dump(),
    }


async def _check_variant_association(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_association - Check if variant is associated with disease."""
    variant = args["variant"]
    disease_input = args["disease"]
    max_p_value = args.get("max_p_value", 0.00001)

    # Resolve disease identifier
    resolver = get_resolver()
    disease = await resolver.resolve_disease(disease_input)

    adapter = await get_adapter()
    assoc_data = await adapter.query(
        "is_variant_associated",
        variant_id=variant,
        disease_id=disease.curie,
        max_p_value=max_p_value,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Extract association information
    is_associated = assoc_data.get("is_associated", False) if assoc_data.get("success") else False
    association_strength = assoc_data.get("p_value", None)

    # Get variant details if associated
    variant_info = None
    if is_associated and assoc_data.get("variant"):
        variant_info = _parse_variant_node(assoc_data["variant"])

    return {
        "is_associated": is_associated,
        "association_strength": association_strength,
        "variant": variant_info if variant_info else {"rsid": variant},
        "disease": {
            "name": disease.name,
            "curie": disease.curie,
            "namespace": disease.namespace,
            "identifier": disease.identifier,
        },
    }


# Data parsing helpers for Tool 10
def _parse_variant_node(data: dict[str, Any]) -> dict[str, Any]:
    """Parse single variant from backend response."""
    return {
        "rsid": data.get("rsid", data.get("variant_id", "unknown")),
        "chromosome": str(data.get("chromosome", "unknown")),
        "position": int(data.get("position", 0)),
        "ref_allele": data.get("ref_allele", data.get("reference", "?")),
        "alt_allele": data.get("alt_allele", data.get("alternate", "?")),
        "p_value": float(data.get("p_value", 1.0)),
        "odds_ratio": data.get("odds_ratio"),
        "trait": data.get("trait", data.get("phenotype", "Unknown trait")),
        "study": data.get("study", data.get("study_id", "Unknown study")),
        "source": data.get("source", "unknown"),
    }


def _parse_variant_list(data: dict[str, Any], min_p_value: float | None, max_p_value: float) -> list[dict[str, Any]]:
    """Parse variant list from backend response with p-value filtering."""
    if not data.get("success") or not data.get("records"):
        return []

    variants = []
    for record in data["records"]:
        variant = _parse_variant_node(record)

        # Apply p-value filtering
        if min_p_value is not None and variant["p_value"] < min_p_value:
            continue
        if variant["p_value"] > max_p_value:
            continue

        variants.append(variant)

    return variants


def _parse_phenotype_node_for_variant(data: dict[str, Any]) -> dict[str, Any]:
    """Parse single phenotype from backend response."""
    return {
        "name": data.get("phenotype", data.get("name", "Unknown")),
        "curie": data.get("curie", data.get("phenotype_id", "unknown:unknown")),
        "namespace": data.get("namespace", "hpo"),
        "identifier": data.get("identifier", data.get("phenotype_id", "unknown")),
        "description": data.get("description"),
    }


def _parse_phenotype_list_for_variant(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse phenotype list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    phenotypes = []
    for record in data["records"]:
        phenotypes.append(_parse_phenotype_node_for_variant(record))

    return phenotypes


def _parse_gene_list_for_variant(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append({
            "name": record.get("gene", record.get("name", "Unknown")),
            "curie": record.get("gene_id", record.get("curie", "unknown:unknown")),
            "namespace": "hgnc",
            "identifier": record.get("gene_id", record.get("identifier", "unknown")),
            "description": record.get("description"),
            "synonyms": record.get("synonyms", []),
        })

    return genes



async def _handle_identifier_resolution(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle identifier resolution - Tool 11."""
    try:
        identifiers = args.get("identifiers")
        from_namespace = args.get("from_namespace")
        to_namespace = args.get("to_namespace")
        response_format = args.get("response_format", "markdown")

        # Validate inputs
        if not identifiers:
            return [types.TextContent(
                type="text",
                text="Error: identifiers list cannot be empty"
            )]

        if not from_namespace or not to_namespace:
            return [types.TextContent(
                type="text",
                text="Error: Both from_namespace and to_namespace are required"
            )]

        # Execute conversion
        adapter = await get_adapter()
        result = await _convert_identifiers(
            adapter=adapter,
            identifiers=identifiers,
            from_namespace=from_namespace,
            to_namespace=to_namespace,
        )

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 11 Implementation
async def _convert_identifiers(
    adapter,
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> dict[str, Any]:
    """Convert identifiers between namespaces using appropriate backend endpoint."""
    # Determine which backend endpoint to use
    endpoint, query_params = _select_identifier_endpoint(
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    # Query backend
    conversion_data = await adapter.query(
        endpoint,
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse results
    mappings, unmapped = _parse_conversion_results(
        data=conversion_data,
        identifiers=identifiers,
        from_namespace=from_namespace,
        to_namespace=to_namespace,
    )

    # Build response
    return {
        "mappings": mappings,
        "unmapped": unmapped,
        "statistics": {
            "total_input": len(identifiers),
            "mapped": len(mappings),
            "unmapped": len(unmapped),
            "total_targets": sum(len(m["target_ids"]) for m in mappings),
        },
        "from_namespace": from_namespace,
        "to_namespace": to_namespace,
    }


def _select_identifier_endpoint(
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> tuple[str, dict[str, Any]]:
    """Select appropriate backend endpoint based on namespace pair."""
    from_ns = from_namespace.lower()
    to_ns = to_namespace.lower()

    # Special case: hgnc.symbol → hgnc (symbol to HGNC ID)
    if from_ns == "hgnc.symbol" and to_ns == "hgnc":
        return "symbol_to_hgnc", {
            "symbols": identifiers,
        }

    # Special case: hgnc → uniprot
    if from_ns == "hgnc" and to_ns == "uniprot":
        return "hgnc_to_uniprot", {
            "hgnc_ids": identifiers,
        }

    # Generic case: use general map_identifiers endpoint
    return "map_identifiers", {
        "identifiers": identifiers,
        "from_namespace": from_namespace,
        "to_namespace": to_namespace,
    }


def _parse_conversion_results(
    data: dict[str, Any],
    identifiers: list[str],
    from_namespace: str,
    to_namespace: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse backend conversion results into mappings and unmapped lists."""
    if not data.get("success"):
        logger.warning(f"Backend conversion failed: {data.get('error', 'unknown error')}")
        # Return all as unmapped
        return [], identifiers

    mappings_data = data.get("mappings", {})
    if not mappings_data:
        # No mappings found
        return [], identifiers

    # Build mappings
    mappings: list[dict[str, Any]] = []
    unmapped: list[str] = []

    for source_id in identifiers:
        targets = mappings_data.get(source_id)

        if targets is None or (isinstance(targets, list) and len(targets) == 0):
            # No mapping found for this identifier
            unmapped.append(source_id)
        else:
            # Normalize to list
            if not isinstance(targets, list):
                targets = [targets]

            # Create mapping
            mapping = {
                "source_id": source_id,
                "target_ids": targets,
                "confidence": "exact" if targets else None,
            }
            mappings.append(mapping)

    return mappings, unmapped



async def _handle_relationship_check(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle relationship check - Tool 12."""
    try:
        # Parse params
        from cogex_mcp.schemas import RelationshipQuery, RelationshipType
        params = RelationshipQuery(**args)

        # Route to appropriate handler based on relationship type
        if params.relationship_type == RelationshipType.GENE_IN_PATHWAY:
            result = await _check_gene_in_pathway(params)
        elif params.relationship_type == RelationshipType.DRUG_TARGET:
            result = await _check_drug_target(params)
        elif params.relationship_type == RelationshipType.DRUG_INDICATION:
            result = await _check_drug_indication(params)
        elif params.relationship_type == RelationshipType.DRUG_SIDE_EFFECT:
            result = await _check_drug_side_effect(params)
        elif params.relationship_type == RelationshipType.GENE_DISEASE:
            result = await _check_gene_disease(params)
        elif params.relationship_type == RelationshipType.DISEASE_PHENOTYPE:
            result = await _check_disease_phenotype(params)
        elif params.relationship_type == RelationshipType.GENE_PHENOTYPE:
            result = await _check_gene_phenotype(params)
        elif params.relationship_type == RelationshipType.VARIANT_ASSOCIATION:
            result = await _check_variant_association(params)
        elif params.relationship_type == RelationshipType.CELL_LINE_MUTATION:
            result = await _check_cell_line_mutation(params)
        elif params.relationship_type == RelationshipType.CELL_MARKER:
            result = await _check_cell_marker(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown relationship type '{params.relationship_type}'")]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Relationship Check Implementations

async def _check_gene_in_pathway(params) -> dict[str, Any]:
    """Check if gene is in pathway. entity1: gene, entity2: pathway"""
    resolver = get_resolver()
    gene = await resolver.resolve_gene(params.entity1)

    # Parse pathway identifier
    if isinstance(params.entity2, tuple):
        pathway_id = f"{params.entity2[0]}:{params.entity2[1]}"
    else:
        pathway_id = params.entity2

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_in_pathway",
        gene_id=gene.curie,
        pathway_id=pathway_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_in_pathway",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": pathway_id, "type": "pathway"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_target(params) -> dict[str, Any]:
    """Check if drug targets gene/protein. entity1: drug, entity2: gene"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve target gene
    target = await resolver.resolve_gene(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_drug_target",
        drug_id=drug.curie,
        target_id=target.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("confidence"),
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_target",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": target.name, "curie": target.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_indication(params) -> dict[str, Any]:
    """Check if drug is indicated for disease. entity1: drug, entity2: disease"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "drug_has_indication",
        drug_id=drug.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_indication",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": disease.name, "curie": disease.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_drug_side_effect(params) -> dict[str, Any]:
    """Check if drug causes side effect. entity1: drug, entity2: side effect"""
    resolver = get_resolver()

    # Resolve drug
    drug = await resolver.resolve_drug(params.entity1)

    # Parse side effect
    side_effect_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_side_effect_for_drug",
        drug_id=drug.curie,
        side_effect_id=side_effect_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "drug_side_effect",
        "entity1": {"name": drug.name, "curie": drug.curie},
        "entity2": {"name": side_effect_id, "type": "side_effect"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_gene_disease(params) -> dict[str, Any]:
    """Check if gene is associated with disease. entity1: gene, entity2: disease"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_disease",
        gene_id=gene.curie,
        disease_id=disease.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("score"),  # Use association score as confidence
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_disease",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": disease.name, "curie": disease.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_disease_phenotype(params) -> dict[str, Any]:
    """Check if disease has phenotype. entity1: disease, entity2: phenotype"""
    resolver = get_resolver()

    # Resolve disease
    disease = await resolver.resolve_disease(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "has_phenotype",
        disease_id=disease.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "disease_phenotype",
        "entity1": {"name": disease.name, "curie": disease.curie},
        "entity2": {"name": phenotype_id, "type": "phenotype"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_gene_phenotype(params) -> dict[str, Any]:
    """Check if gene is associated with phenotype. entity1: gene, entity2: phenotype"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse phenotype identifier
    phenotype_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_gene_associated_with_phenotype",
        gene_id=gene.curie,
        phenotype_id=phenotype_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "gene_phenotype",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": phenotype_id, "type": "phenotype"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_variant_association(params) -> dict[str, Any]:
    """Check if variant is associated with trait/disease. entity1: variant (rsID), entity2: trait/disease"""
    # Parse variant rsID
    variant_id = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]
    if not variant_id.startswith("rs"):
        raise ValueError(f"Variant must be an rsID starting with 'rs', got: {variant_id}")

    # Parse trait/disease
    trait_id = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_variant_associated",
        variant_id=variant_id,
        trait_id=trait_id,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("p_value"),  # Use p-value as confidence indicator
            evidence_count=check_data["metadata"].get("study_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "variant_association",
        "entity1": {"name": variant_id, "type": "variant"},
        "entity2": {"name": trait_id, "type": "trait"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_cell_line_mutation(params) -> dict[str, Any]:
    """Check if cell line has mutation in gene. entity1: cell line, entity2: gene"""
    resolver = get_resolver()

    # Parse cell line name
    cell_line = params.entity1 if isinstance(params.entity1, str) else params.entity1[1]

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity2)

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_mutated_in_cell_line",
        cell_line=cell_line,
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            evidence_count=check_data["metadata"].get("mutation_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "cell_line_mutation",
        "entity1": {"name": cell_line, "type": "cell_line"},
        "entity2": {"name": gene.name, "curie": gene.curie},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _check_cell_marker(params) -> dict[str, Any]:
    """Check if gene is a marker for cell type. entity1: gene, entity2: cell type"""
    resolver = get_resolver()

    # Resolve gene
    gene = await resolver.resolve_gene(params.entity1)

    # Parse cell type
    cell_type = params.entity2 if isinstance(params.entity2, str) else params.entity2[1]

    adapter = await get_adapter()
    check_data = await adapter.query(
        "is_cell_marker",
        gene_id=gene.curie,
        cell_type=cell_type,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    exists = check_data.get("result", False) if check_data.get("success") else False

    metadata = None
    if exists and check_data.get("metadata"):
        from cogex_mcp.schemas import RelationshipMetadata
        metadata = RelationshipMetadata(
            confidence=check_data["metadata"].get("marker_confidence"),
            evidence_count=check_data["metadata"].get("evidence_count"),
            sources=check_data["metadata"].get("sources"),
            additional_info=check_data["metadata"].get("additional_info"),
        )

    return {
        "relationship_type": "cell_marker",
        "entity1": {"name": gene.name, "curie": gene.curie},
        "entity2": {"name": cell_type, "type": "cell_type"},
        "exists": exists,
        "metadata": metadata.model_dump() if metadata else None,
    }


async def _handle_ontology_hierarchy(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle ontology hierarchy - Tool 13."""
    try:
        # Parse params
        from cogex_mcp.schemas import OntologyHierarchyQuery, HierarchyDirection
        params = OntologyHierarchyQuery(**args)

        # Route to appropriate handler based on direction
        if params.direction == HierarchyDirection.PARENTS:
            result = await _get_ontology_parents(params)
        elif params.direction == HierarchyDirection.CHILDREN:
            result = await _get_ontology_children(params)
        elif params.direction == HierarchyDirection.BOTH:
            result = await _get_ontology_hierarchy(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown direction '{params.direction}'")]

        # Generate ASCII tree for markdown format
        if params.response_format == ResponseFormat.MARKDOWN:
            result["hierarchy_tree"] = _generate_ascii_tree(
                result.get("root_term"),
                result.get("parents", []),
                result.get("children", []),
                params.direction,
            )

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Ontology Hierarchy Mode Implementations

async def _get_ontology_parents(params) -> dict[str, Any]:
    """Mode: parents - Get parent/ancestor terms in ontology."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    parent_data = await adapter.query(
        "get_ontology_parents",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse parents
    parents = _parse_ontology_terms(parent_data)

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": None,
    }


async def _get_ontology_children(params) -> dict[str, Any]:
    """Mode: children - Get child/descendant terms in ontology."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    child_data = await adapter.query(
        "get_ontology_children",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse children
    children = _parse_ontology_terms(child_data)

    return {
        "root_term": term.model_dump(),
        "parents": None,
        "children": children,
    }


async def _get_ontology_hierarchy(params) -> dict[str, Any]:
    """Mode: both - Get both parents and children in a single query."""
    resolver = get_resolver()
    term = await resolver.resolve_ontology_term(params.term)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "term_id": term.curie,
        "max_depth": params.max_depth,
    }

    hierarchy_data = await adapter.query(
        "get_ontology_hierarchy",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse both parents and children
    parents = _parse_ontology_terms(hierarchy_data.get("parents", {}))
    children = _parse_ontology_terms(hierarchy_data.get("children", {}))

    return {
        "root_term": term.model_dump(),
        "parents": parents,
        "children": children,
    }


def _parse_ontology_terms(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse ontology terms from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    terms = []
    for record in data["records"]:
        terms.append(
            {
                "name": record.get("name", record.get("term", "Unknown")),
                "curie": record.get("curie", record.get("term_id", "unknown:unknown")),
                "namespace": record.get("namespace", "unknown"),
                "definition": record.get("definition"),
                "depth": record.get("depth", 0),
                "relationship": record.get("relationship", "is_a"),
            }
        )

    return terms


def _generate_ascii_tree(
    root_term: dict[str, Any] | None,
    parents: list[dict[str, Any]] | None,
    children: list[dict[str, Any]] | None,
    direction,
) -> str:
    """Generate ASCII tree visualization for markdown output."""
    if not root_term:
        return "No hierarchy data available."

    from cogex_mcp.schemas import HierarchyDirection
    lines = []

    # Build parent tree (bottom-up)
    if parents and direction in (HierarchyDirection.PARENTS, HierarchyDirection.BOTH):
        # Group parents by depth
        parents_by_depth = {}
        for parent in parents:
            depth = parent.get("depth", 1)
            if depth not in parents_by_depth:
                parents_by_depth[depth] = []
            parents_by_depth[depth].append(parent)

        # Sort depths in reverse (farthest first)
        sorted_depths = sorted(parents_by_depth.keys(), reverse=True)

        for depth in sorted_depths:
            indent = "  " * (depth - 1)
            for parent in parents_by_depth[depth]:
                rel = parent.get("relationship", "is_a")
                lines.append(f"{indent}├─ {parent['name']} ({parent['curie']}) [{rel}]")

    # Add root term
    lines.append(f"● {root_term['name']} ({root_term['curie']}) [ROOT]")

    # Build children tree (top-down)
    if children and direction in (HierarchyDirection.CHILDREN, HierarchyDirection.BOTH):
        # Group children by depth
        children_by_depth = {}
        for child in children:
            depth = child.get("depth", 1)
            if depth not in children_by_depth:
                children_by_depth[depth] = []
            children_by_depth[depth].append(child)

        # Sort depths in order (nearest first)
        sorted_depths = sorted(children_by_depth.keys())

        for depth in sorted_depths:
            indent = "  " * depth
            for i, child in enumerate(children_by_depth[depth]):
                rel = child.get("relationship", "is_a")
                # Use different symbol for last child
                is_last = i == len(children_by_depth[depth]) - 1 and depth == max(sorted_depths)
                symbol = "└─" if is_last else "├─"
                lines.append(f"{indent}{symbol} {child['name']} ({child['curie']}) [{rel}]")

    return "\n".join(lines)


async def _handle_cell_markers_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle cell markers query - Tool 14."""
    try:
        # Parse params
        from cogex_mcp.schemas import CellMarkerQuery, CellMarkerMode
        params = CellMarkerQuery(**args)

        # Route to appropriate handler based on mode
        if params.mode == CellMarkerMode.GET_MARKERS:
            result = await _get_markers_for_cell_type(params)
        elif params.mode == CellMarkerMode.GET_CELL_TYPES:
            result = await _get_cell_types_for_marker(params)
        elif params.mode == CellMarkerMode.CHECK_MARKER:
            result = await _check_marker_status(params)
        else:
            return [types.TextContent(type="text", text=f"Error: Unknown query mode '{params.mode}'")]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=params.response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Cell Markers Mode Implementations

async def _get_markers_for_cell_type(params) -> dict[str, Any]:
    """Mode: get_markers - Get marker genes for a specific cell type."""
    if not params.cell_type:
        raise ValueError("cell_type parameter required for get_markers mode")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "cell_type": params.cell_type,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    marker_data = await adapter.query(
        "get_markers_for_cell_type",
        **query_params,
    )

    # Parse cell type metadata
    cell_type_node = _parse_cell_type_node(
        marker_data.get("cell_type", {}),
        params.cell_type,
        params.tissue,
        params.species,
    )

    # Parse marker list
    markers = _parse_marker_list(marker_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=markers,
        total_count=marker_data.get("total_count", len(markers)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "cell_type": cell_type_node,
        "markers": markers,
        "pagination": pagination.model_dump(),
    }


async def _get_cell_types_for_marker(params) -> dict[str, Any]:
    """Mode: get_cell_types - Find cell types that express a specific marker gene."""
    if not params.marker:
        raise ValueError("marker parameter required for get_cell_types mode")

    # Resolve marker gene identifier
    resolver = get_resolver()
    marker_gene = await resolver.resolve_gene(params.marker)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": marker_gene.curie,
        "limit": params.limit,
        "offset": params.offset,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    cell_type_data = await adapter.query(
        "get_cell_types_for_marker",
        **query_params,
    )

    # Parse cell type list
    cell_types = _parse_cell_type_list(cell_type_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=cell_types,
        total_count=cell_type_data.get("total_count", len(cell_types)),
        offset=params.offset,
        limit=params.limit,
    )

    return {
        "marker": marker_gene.model_dump(),
        "cell_types": cell_types,
        "pagination": pagination.model_dump(),
    }


async def _check_marker_status(params) -> dict[str, Any]:
    """Mode: check_marker - Check if a specific gene is a marker for a specific cell type."""
    if not params.cell_type:
        raise ValueError("cell_type parameter required for check_marker mode")
    if not params.marker:
        raise ValueError("marker parameter required for check_marker mode")

    # Resolve marker gene identifier
    resolver = get_resolver()
    marker_gene = await resolver.resolve_gene(params.marker)

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "gene_id": marker_gene.curie,
        "cell_type": params.cell_type,
        "timeout": STANDARD_QUERY_TIMEOUT,
    }

    # Add filters if specified
    if params.tissue:
        query_params["tissue"] = params.tissue
    if params.species:
        query_params["species"] = params.species

    check_data = await adapter.query(
        "is_cell_marker",
        **query_params,
    )

    # Parse result
    is_marker = check_data.get("is_marker", False) if check_data.get("success") else False

    # Parse cell type metadata if available
    cell_type_node = None
    if check_data.get("cell_type"):
        cell_type_node = _parse_cell_type_node(
            check_data["cell_type"],
            params.cell_type,
            params.tissue,
            params.species,
        )
    else:
        # Create basic cell type node
        cell_type_node = {
            "name": params.cell_type,
            "tissue": params.tissue or "unknown",
            "species": params.species or "human",
            "marker_count": 0,
        }

    return {
        "is_marker": is_marker,
        "marker": marker_gene.model_dump(),
        "cell_type": cell_type_node,
    }


def _parse_cell_type_node(
    data: dict[str, Any],
    cell_type_name: str,
    tissue: str | None,
    species: str,
) -> dict[str, Any]:
    """Parse cell type node from backend response."""
    if not data:
        return {
            "name": cell_type_name,
            "tissue": tissue or "unknown",
            "species": species or "human",
            "marker_count": 0,
        }

    return {
        "name": data.get("name", cell_type_name),
        "tissue": data.get("tissue", tissue or "unknown"),
        "species": data.get("species", species or "human"),
        "marker_count": data.get("marker_count", 0),
    }


def _parse_marker_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse marker list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    markers = []
    for record in data["records"]:
        gene_name = record.get("gene", record.get("marker", "Unknown"))
        gene_id = record.get("gene_id", record.get("marker_id", "unknown:unknown"))

        # Extract namespace and identifier from CURIE
        namespace = "hgnc"
        identifier = gene_id
        if ":" in gene_id:
            namespace, identifier = gene_id.split(":", 1)

        markers.append(
            {
                "gene": {
                    "name": gene_name,
                    "curie": gene_id,
                    "namespace": namespace,
                    "identifier": identifier,
                },
                "marker_type": record.get("marker_type", "unknown"),
                "evidence": record.get("evidence", "unknown"),
            }
        )

    return markers


def _parse_cell_type_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse cell type list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    cell_types = []
    for record in data["records"]:
        cell_types.append(
            {
                "name": record.get("cell_type", record.get("name", "Unknown")),
                "tissue": record.get("tissue", "unknown"),
                "species": record.get("species", "human"),
                "marker_count": record.get("marker_count", 0),
            }
        )

    return cell_types


async def _handle_kinase_enrichment(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle kinase enrichment - Tool 15."""
    try:
        # Validate phosphosites
        phosphosites = args.get("phosphosites", [])
        if not phosphosites:
            return [types.TextContent(
                type="text",
                text="Error: phosphosites parameter is required and cannot be empty"
            )]

        # Validate phosphosite format
        pattern = re.compile(r"^[A-Z0-9]+_[STY]\d+$", re.IGNORECASE)
        invalid_sites = [site for site in phosphosites if not pattern.match(site)]
        if invalid_sites:
            return [types.TextContent(
                type="text",
                text=f"Error: Invalid phosphosite format: {', '.join(invalid_sites[:5])}. "
                     f"Expected format: GENE_S123 (serine), GENE_T456 (threonine), or GENE_Y789 (tyrosine)"
            )]

        # Count unique genes in phosphosites
        unique_genes = set(site.split("_")[0] for site in phosphosites)

        # Prepare background phosphosites if provided
        background_sites = args.get("background")
        if background_sites:
            invalid_bg = [site for site in background_sites if not pattern.match(site)]
            if invalid_bg:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Invalid background phosphosite format: {', '.join(invalid_bg[:5])}"
                )]

        # Query backend
        adapter = await get_adapter()

        query_params = {
            "phosphosites": phosphosites,
            "alpha": args.get("alpha", 0.05),
            "correction_method": args.get("correction_method", "fdr_bh"),
            "timeout": ENRICHMENT_TIMEOUT,
        }

        if background_sites:
            query_params["background"] = background_sites

        enrichment_data = await adapter.query("kinase_analysis", **query_params)

        # Parse results
        results = _parse_kinase_results(enrichment_data)
        statistics = _compute_kinase_statistics(results, args, len(unique_genes))

        # Build response
        response_data = {
            "results": [r for r in results],
            "statistics": statistics,
            "total_phosphosites": len(phosphosites),
            "unique_genes": len(unique_genes),
        }

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=response_data,
            format_type=args.get("response_format", "markdown"),
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


def _parse_kinase_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse kinase enrichment results from backend response."""
    if not data.get("success") or not data.get("results"):
        return []

    results = []
    for record in data["results"]:
        # Parse kinase entity
        kinase = {
            "name": record.get("kinase_name", "Unknown"),
            "curie": record.get("kinase_id", "unknown:unknown"),
            "namespace": record.get("kinase_namespace", "hgnc"),
            "identifier": record.get("kinase_identifier", "unknown"),
        }

        # Determine confidence level based on substrate count and evidence
        substrate_count = record.get("substrate_count", 0)
        total_substrates = record.get("total_substrates", 0)
        p_value = record.get("adjusted_p_value", 1.0)

        # Confidence heuristics:
        # - high: 5+ substrates, p < 0.01, or >20% of known substrates
        # - medium: 3-4 substrates, p < 0.05
        # - low: 1-2 substrates
        if (
            substrate_count >= 5
            or p_value < 0.01
            or (total_substrates > 0 and substrate_count / total_substrates > 0.2)
        ):
            confidence = "high"
        elif substrate_count >= 3 and p_value < 0.05:
            confidence = "medium"
        else:
            confidence = "low"

        result = {
            "kinase": kinase,
            "p_value": record.get("p_value", 1.0),
            "adjusted_p_value": record.get("adjusted_p_value", 1.0),
            "substrate_count": substrate_count,
            "total_substrates": total_substrates,
            "phosphosites": record.get("phosphosites", []),
            "prediction_confidence": record.get("confidence", confidence),
        }

        results.append(result)

    # Sort by adjusted p-value (most significant first)
    results.sort(key=lambda x: x["adjusted_p_value"])

    return results


def _compute_kinase_statistics(
    results: list[dict[str, Any]],
    args: dict[str, Any],
    total_genes: int,
) -> dict[str, Any]:
    """Compute overall kinase enrichment statistics."""
    # Count significant results
    alpha = args.get("alpha", 0.05)
    significant_results = sum(1 for r in results if r["adjusted_p_value"] <= alpha)

    return {
        "total_results": len(results),
        "significant_results": significant_results,
        "total_genes_analyzed": total_genes,
        "correction_method": args.get("correction_method", "fdr_bh"),
        "alpha": alpha,
    }


async def _handle_protein_functions_query(args: dict[str, Any]) -> list[types.TextContent]:
    """Handle protein functions query - Tool 16."""
    try:
        mode = args.get("mode")
        response_format = args.get("response_format", "markdown")

        # Route to appropriate handler based on mode
        if mode == "gene_to_activities":
            result = await _get_enzyme_activities(args)
        elif mode == "activity_to_genes":
            result = await _get_genes_for_activity(args)
        elif mode == "check_activity":
            result = await _check_enzyme_activity(args)
        elif mode == "check_function_types":
            result = await _check_function_types(args)
        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown query mode '{mode}'"
            )]

        # Format response
        formatter = get_formatter()
        response = formatter.format_response(
            data=result,
            format_type=response_format,
            max_chars=CHARACTER_LIMIT,
        )

        return [types.TextContent(type="text", text=response)]

    except EntityResolutionError as e:
        logger.warning(f"Entity resolution error: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Tool error: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: Unexpected error occurred. {str(e)}")]


# Tool 16 Mode Handlers
async def _get_enzyme_activities(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: gene_to_activities - Get all enzyme activities for a specific gene."""
    gene_input = args.get("gene")
    if not gene_input:
        raise ValueError("gene parameter required for gene_to_activities mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Fetch enzyme activities from backend
    activity_data = await adapter.query(
        "get_enzyme_activities",
        gene_id=gene.curie,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse activities
    activities = _parse_enzyme_activities(activity_data)

    return {
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
        "activities": activities,
    }


async def _get_genes_for_activity(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: activity_to_genes - Find all genes with a specific enzyme activity."""
    enzyme_activity = args.get("enzyme_activity")
    if not enzyme_activity:
        raise ValueError("enzyme_activity parameter required for activity_to_genes mode")

    adapter = await get_adapter()

    # Build query parameters
    query_params = {
        "activity": enzyme_activity,
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }

    gene_data = await adapter.query(
        "get_genes_for_activity",
        **query_params,
        timeout=STANDARD_QUERY_TIMEOUT,
    )

    # Parse gene list
    genes = _parse_gene_list_protein_function(gene_data)

    # Create pagination metadata
    pagination_service = get_pagination()
    pagination = pagination_service.paginate(
        items=genes,
        total_count=gene_data.get("total_count", len(genes)),
        offset=args.get("offset", 0),
        limit=args.get("limit", 20),
    )

    return {
        "activity": enzyme_activity,
        "genes": genes,
        "pagination": pagination.model_dump(),
    }


async def _check_enzyme_activity(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_activity - Check if a gene has a specific enzyme activity."""
    gene_input = args.get("gene")
    enzyme_activity = args.get("enzyme_activity")

    if not gene_input:
        raise ValueError("gene parameter required for check_activity mode")
    if not enzyme_activity:
        raise ValueError("enzyme_activity parameter required for check_activity mode")

    # Resolve gene identifier
    resolver = get_resolver()
    gene = await resolver.resolve_gene(gene_input)

    adapter = await get_adapter()

    # Check specific activity based on type
    activity_lower = enzyme_activity.lower()

    # Map activity names to backend check functions
    if activity_lower in ["kinase", "protein kinase"]:
        check_data = await adapter.query(
            "is_kinase",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    elif activity_lower in ["phosphatase", "protein phosphatase"]:
        check_data = await adapter.query(
            "is_phosphatase",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    elif activity_lower in ["transcription_factor", "transcription factor", "tf"]:
        check_data = await adapter.query(
            "is_transcription_factor",
            gene_id=gene.curie,
            timeout=STANDARD_QUERY_TIMEOUT,
        )
    else:
        # Generic activity check
        check_data = await adapter.query(
            "has_enzyme_activity",
            gene_id=gene.curie,
            activity=enzyme_activity,
            timeout=STANDARD_QUERY_TIMEOUT,
        )

    has_activity = check_data.get("result", False) if check_data.get("success") else False

    return {
        "has_activity": has_activity,
        "gene": {
            "name": gene.name,
            "curie": gene.curie,
            "namespace": gene.namespace,
            "identifier": gene.identifier,
        },
        "activity": enzyme_activity,
    }


async def _check_function_types(args: dict[str, Any]) -> dict[str, Any]:
    """Mode: check_function_types - Batch check if genes have specific function types."""
    # Determine which genes to check
    genes_to_check = []

    if args.get("genes"):
        genes_to_check = args["genes"]
    elif args.get("gene"):
        genes_to_check = [args["gene"]]
    else:
        raise ValueError("Either gene or genes parameter required for check_function_types mode")

    function_types = args.get("function_types")
    if not function_types:
        raise ValueError("function_types parameter required for check_function_types mode")

    # Resolve all gene identifiers
    resolver = get_resolver()
    resolved_genes = {}

    for gene_input in genes_to_check:
        try:
            gene = await resolver.resolve_gene(gene_input)
            resolved_genes[gene.name] = gene
        except EntityResolutionError as e:
            logger.warning(f"Could not resolve gene '{gene_input}': {e}")
            # Include unresolved genes with None value
            resolved_genes[str(gene_input)] = None

    adapter = await get_adapter()
    function_checks = {}

    # Check each function type for each gene
    for gene_name, gene in resolved_genes.items():
        if gene is None:
            # Gene could not be resolved
            function_checks[gene_name] = dict.fromkeys(function_types, False)
            continue

        gene_results = {}

        for function_type in function_types:
            function_lower = function_type.lower()

            try:
                # Map function type to backend endpoint
                if function_lower in ["kinase", "protein_kinase"]:
                    check_data = await adapter.query(
                        "is_kinase",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                elif function_lower in ["phosphatase", "protein_phosphatase"]:
                    check_data = await adapter.query(
                        "is_phosphatase",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                elif function_lower in ["transcription_factor", "transcription factor", "tf"]:
                    check_data = await adapter.query(
                        "is_transcription_factor",
                        gene_id=gene.curie,
                        timeout=STANDARD_QUERY_TIMEOUT,
                    )
                else:
                    logger.warning(f"Unknown function type: {function_type}")
                    gene_results[function_type] = False
                    continue

                has_function = (
                    check_data.get("result", False) if check_data.get("success") else False
                )
                gene_results[function_type] = has_function

            except Exception as e:
                logger.warning(f"Error checking {function_type} for {gene_name}: {e}")
                gene_results[function_type] = False

        function_checks[gene_name] = gene_results

    return {
        "function_checks": function_checks,
        "genes_checked": len(resolved_genes),
        "function_types": function_types,
    }


# Data parsing helpers for Tool 16
def _parse_enzyme_activities(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse enzyme activities from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    activities = []
    for record in data["records"]:
        activities.append(
            {
                "activity": record.get("activity", "Unknown"),
                "ec_number": record.get("ec_number"),
                "confidence": record.get("confidence", "medium"),
                "evidence_sources": record.get("evidence_sources", []),
            }
        )

    return activities


def _parse_gene_list_protein_function(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse gene list from backend response."""
    if not data.get("success") or not data.get("records"):
        return []

    genes = []
    for record in data["records"]:
        genes.append(
            {
                "name": record.get("gene", record.get("name", "Unknown")),
                "curie": record.get("gene_id", record.get("curie", "unknown:unknown")),
                "namespace": "hgnc",
                "identifier": record.get("gene_id", record.get("identifier", "unknown")),
                "description": record.get("description"),
                "synonyms": record.get("synonyms", []),
            }
        )

    return genes


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("INDRA CoGEx MCP Server (Low-Level) v1.0.0 - All 16 Tools")
    logger.info("=" * 80)
    logger.info("Transport: stdio")
    logger.info(f"Debug mode: {settings.debug_mode}")
    logger.info(f"Character limit: {settings.character_limit:,}")
    logger.info("=" * 80)

    try:
        # Initialize backend
        await initialize_backend()

        # Run server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="cogex_mcp",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await cleanup_backend()


if __name__ == "__main__":
    asyncio.run(main())
