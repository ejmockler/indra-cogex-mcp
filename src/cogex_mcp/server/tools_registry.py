"""
Tool Registry - All 16 MCP Tool Definitions

This module contains the tool definitions (schemas and descriptions)
for all 16 INDRA CoGEx MCP tools.
"""

import mcp.types as types


def get_all_tools() -> list[types.Tool]:
    """Return list of all tool definitions."""
    return TOOL_DEFINITIONS


# All 16 tool definitions
TOOL_DEFINITIONS = [
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
