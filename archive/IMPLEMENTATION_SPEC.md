# INDRA CoGEx MCP Server - Implementation Specification

**Version:** 1.0.0
**Date:** 2025-11-24
**Status:** Implementation Ready
**Target Audience:** Software Engineering Agents & Distinguished Developers

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technical Stack](#technical-stack)
4. [Tool Specifications](#tool-specifications)
5. [Data Schemas](#data-schemas)
6. [Implementation Guidelines](#implementation-guidelines)
7. [Testing Strategy](#testing-strategy)
8. [Evaluation Framework](#evaluation-framework)
9. [Deployment Guide](#deployment-guide)
10. [Examples & Use Cases](#examples--use-cases)

---

## Executive Summary

### Project Goal

Create a production-grade Model Context Protocol (MCP) server that exposes INDRA CoGEx biomedical knowledge graph capabilities to AI agents. The server provides unified access to 28+ biomedical databases through compositional, workflow-oriented tools.

### Key Differentiators

- **Unified Knowledge Access**: Single interface to 28+ biomedical databases
- **Graph-Native Operations**: Subnetwork extraction, path finding, relationship discovery
- **Evidence-Grounded**: Every assertion traceable to source publications
- **Production-Ready**: Built on Harvard/Northeastern research infrastructure

### Design Philosophy

**Compositional Tools > API Mirroring**

Rather than creating 110 MCP tools (one per REST endpoint), we design 13 high-leverage compositional tools organized by biological workflow, not database schema.

### Success Metrics

- **Tool Coverage**: 13 tools covering 90%+ of biomedical query patterns
- **Performance**: Simple queries <500ms, complex analyses <5s
- **Reliability**: 99%+ uptime with graceful degradation
- **Usability**: LLM agents successfully complete 90%+ of evaluation questions

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client (Claude)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ MCP Protocol
                            │ (JSON-RPC over stdio)
┌───────────────────────────┴─────────────────────────────────┐
│                   INDRA CoGEx MCP Server                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Tool Layer (13 Compositional Tools)        │   │
│  └────────────────────┬─────────────────────────────────┘   │
│  ┌────────────────────┴─────────────────────────────────┐   │
│  │         Service Layer (Business Logic)               │   │
│  │  - Entity Resolution   - Response Formatting         │   │
│  │  - Caching            - Error Handling               │   │
│  └────────────────────┬─────────────────────────────────┘   │
│  ┌────────────────────┴─────────────────────────────────┐   │
│  │    Client Adapter Layer (Primary/Fallback)           │   │
│  │  ┌──────────────────┐   ┌────────────────────────┐  │   │
│  │  │ Python Client    │   │  REST Client (Backup)  │  │   │
│  │  │ (indra_cogex)    │   │  (discovery.indra.bio) │  │   │
│  │  └────────┬─────────┘   └───────────┬────────────┘  │   │
│  └───────────┴─────────────────────────┴───────────────┘   │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
    ┌───────────▼────────┐  ┌──────────▼──────────┐
    │   Neo4j Database   │  │   REST API          │
    │   (Primary Store)  │  │   (Public Fallback) │
    └────────────────────┘  └─────────────────────┘
```

### Component Responsibilities

#### 1. Tool Layer
- Exposes 13 MCP tools with clear semantic boundaries
- Handles parameter validation using Pydantic
- Constructs service layer calls
- Formats responses for MCP clients

#### 2. Service Layer
- **Entity Resolution**: Converts flexible inputs (symbols, IDs, CURIEs) to canonical forms
- **Query Orchestration**: Composes multiple backend queries
- **Response Formatting**: Standardizes output schemas
- **Caching**: LRU cache for frequently accessed entities
- **Error Handling**: Translates exceptions to actionable messages

#### 3. Client Adapter Layer
- **Primary**: Python client (`indra_cogex.client`) for direct Neo4j access
- **Fallback**: REST client wrapper for public API when Neo4j unavailable
- Adapter pattern ensures consistent interface regardless of backend

#### 4. Data Layer
- **Neo4j**: Primary graph database (local/remote)
- **REST API**: Public endpoint at discovery.indra.bio

### Connection Strategy

**Priority Cascade:**
1. Local Neo4j (if configured)
2. Remote Neo4j (if credentials provided)
3. REST API fallback (public access)

**Configuration:**
```python
# Option 1: Neo4j (best performance)
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>

# Option 2: REST Fallback (no configuration needed)
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
```

---

## Technical Stack

### Core Dependencies

**Required (pinned versions):**

```toml
[project]
name = "indra-cogex-mcp"
version = "1.0.0"
requires-python = ">=3.10"

dependencies = [
    "mcp==1.22.0",                    # MCP SDK
    "pydantic==2.12.4",               # Data validation
    "neo4j==6.0.3",                   # Neo4j driver
    "httpx==0.28.1",                  # Async HTTP client
    "pydantic-settings==2.7.1",       # Environment config
    "cachetools==5.5.0",              # LRU caching
]

[project.optional-dependencies]
dev = [
    "pytest==9.0.1",                  # Testing framework
    "pytest-asyncio==0.25.2",         # Async test support
    "pytest-cov==6.0.0",              # Coverage reporting
    "pytest-mock==3.14.0",            # Mocking utilities
    "ruff==0.8.4",                    # Linting & formatting
    "mypy==1.13.0",                   # Type checking
]

[project.scripts]
indra-cogex-mcp = "indra_cogex_mcp.server:main"
```

### INDRA CoGEx Installation

**Not on PyPI - Install from GitHub:**

```bash
# Clone the repository
git clone https://github.com/gyorilab/indra_cogex.git
cd indra_cogex

# Install in editable mode
pip install -e .
```

**Or add to pyproject.toml:**
```toml
dependencies = [
    # ... other deps
    "indra-cogex @ git+https://github.com/gyorilab/indra_cogex.git@main",
]
```

### Python Version Requirements

- **Minimum**: Python 3.10
- **Recommended**: Python 3.12
- **Maximum Tested**: Python 3.13

### Development Tools

```bash
# Linting & Formatting
ruff check .
ruff format .

# Type Checking
mypy src/

# Testing
pytest tests/ -v --cov=src/indra_cogex_mcp

# Security Scanning
pip-audit
```

---

## Tool Specifications

### Priority 1: Core Discovery Tools (Implement First)

#### Tool 1: `query_gene_context`

**Purpose**: Comprehensive gene information retrieval across multiple data domains

**Use Cases:**
- "What do we know about TP53?"
- "Where is BRCA1 expressed and what pathways is it in?"
- "Give me a complete profile for EGFR"

**Input Schema:**
```python
class GeneContextQuery(BaseModel):
    gene: str | Tuple[str, str]
    """Gene identifier - accepts:
    - HGNC symbol: "TP53", "EGFR"
    - CURIE: "hgnc:11998"
    - Tuple: ("hgnc", "11998")
    """

    include_expression: bool = True
    """Tissue/cell-type expression data (BGee)"""

    include_go_terms: bool = True
    """Gene Ontology annotations"""

    include_pathways: bool = True
    """Reactome & WikiPathways memberships"""

    include_diseases: bool = True
    """DisGeNet disease associations"""

    include_domains: bool = False
    """InterPro protein domains"""

    include_variants: bool = False
    """Known genetic variants"""

    include_codependencies: bool = False
    """DepMap gene co-dependencies"""

    max_results_per_category: int = 50
    """Limit results per data type"""
```

**Output Schema:**
```python
class GeneContextResponse(BaseModel):
    query: QueryMetadata
    gene: GeneNode
    expression: Optional[List[ExpressionData]]
    go_terms: Optional[List[GOAnnotation]]
    pathways: Optional[List[PathwayMembership]]
    diseases: Optional[List[DiseaseAssociation]]
    domains: Optional[List[ProteinDomain]]
    variants: Optional[List[GeneticVariant]]
    codependencies: Optional[List[GeneCodependent]]
    metadata: ResponseMetadata

class GeneNode(BaseModel):
    name: str                    # HGNC symbol
    curie: str                   # "hgnc:11998"
    description: Optional[str]   # Gene description
    synonyms: List[str]          # Alternative names

class ExpressionData(BaseModel):
    tissue: EntityRef
    confidence: str              # "gold", "silver", "bronze"
    evidence_count: int

class GOAnnotation(BaseModel):
    go_term: EntityRef
    aspect: str                  # "biological_process", "molecular_function", "cellular_component"
    evidence_code: str           # "IDA", "IEA", etc.

class PathwayMembership(BaseModel):
    pathway: EntityRef
    source: str                  # "reactome", "wikipathways"

class DiseaseAssociation(BaseModel):
    disease: EntityRef
    score: float                 # DisGeNet score
    evidence_count: int
    sources: List[str]           # ["befree", "curated", ...]
```

**Backend Queries:**
```python
# Implementation pseudo-code
async def query_gene_context(params: GeneContextQuery) -> GeneContextResponse:
    # 1. Resolve gene identifier
    gene_node = await resolve_gene(params.gene)

    # 2. Parallel data fetching
    tasks = []
    if params.include_expression:
        tasks.append(client.get_tissues_for_gene(gene_node))
    if params.include_go_terms:
        tasks.append(client.get_go_terms_for_gene(gene_node))
    # ... more tasks

    results = await asyncio.gather(*tasks)

    # 3. Format and return
    return format_gene_context_response(gene_node, results)
```

**Error Handling:**
```python
# Ambiguous identifier
"Gene 'TP' matches multiple entries: TP53 (hgnc:11998), TP63 (hgnc:15979). Please specify."

# Not found
"Gene 'FAKEGEN' not found in HGNC. Did you mean: TP53, TP63?"

# Partial failure
"Retrieved expression and pathways successfully. GO term query timed out (retry recommended)."
```

---

#### Tool 2: `extract_subnetwork`

**Purpose**: Graph traversal and mechanistic relationship discovery

**Use Cases:**
- "What are the direct interactions between TP53, MDM2, and ATM?"
- "Find genes that mediate between BRCA1 and DNA repair pathway members"
- "Show me shared upstream regulators of inflammatory cytokines"

**Input Schema:**
```python
class SubnetworkQuery(BaseModel):
    genes: List[str]
    """List of gene identifiers (symbols or CURIEs)"""

    mode: SubnetworkMode
    """Subnetwork extraction strategy"""

    tissue_filter: Optional[str] = None
    """Restrict to genes expressed in tissue"""

    go_filter: Optional[str] = None
    """Restrict to genes with GO term"""

    include_evidence: bool = False
    """Include supporting evidence for statements"""

    max_statements: int = 100
    """Maximum INDRA statements to return"""

    statement_types: Optional[List[str]] = None
    """Filter by type: ["Activation", "Inhibition", "Phosphorylation", ...]"""

    min_evidence_count: int = 1
    """Minimum evidence per statement"""

    min_belief_score: float = 0.0
    """Minimum belief score (0.0-1.0)"""

class SubnetworkMode(str, Enum):
    DIRECT = "direct"                    # A→B direct edges
    MEDIATED = "mediated"                # A→X→B paths
    SHARED_UPSTREAM = "shared_upstream"  # A←X→B patterns
    SHARED_DOWNSTREAM = "shared_downstream"  # A→X←B patterns
```

**Output Schema:**
```python
class SubnetworkResponse(BaseModel):
    query: QueryMetadata
    nodes: List[GeneNode]              # All genes in subnetwork
    statements: List[IndraStatement]   # Mechanistic relationships
    statistics: NetworkStatistics
    metadata: ResponseMetadata

class IndraStatement(BaseModel):
    stmt_hash: str                     # Unique statement identifier
    stmt_type: str                     # "Phosphorylation", "Activation", etc.
    subject: EntityRef
    object: EntityRef
    residue: Optional[str]             # For modifications: "S", "T", "Y"
    position: Optional[str]            # Amino acid position
    evidence_count: int
    belief_score: float
    sources: List[str]                 # ["reach", "sparser", "signor", ...]
    evidence: Optional[List[Evidence]] # If include_evidence=True

class Evidence(BaseModel):
    text: str                          # Evidence sentence
    pmid: Optional[str]                # PubMed ID
    source_api: str                    # Extraction system
    epistemics: Dict[str, Any]         # Negation, hypothesis, etc.

class NetworkStatistics(BaseModel):
    node_count: int
    edge_count: int
    statement_types: Dict[str, int]    # Count per type
    avg_evidence_per_statement: float
    avg_belief_score: float
```

**Backend Implementation:**
```python
async def extract_subnetwork(params: SubnetworkQuery) -> SubnetworkResponse:
    # 1. Resolve all gene identifiers
    gene_nodes = await asyncio.gather(*[
        resolve_gene(g) for g in params.genes
    ])

    # 2. Choose extraction method
    if params.mode == SubnetworkMode.DIRECT:
        if params.tissue_filter:
            stmts = await client.indra_subnetwork_tissue(
                gene_nodes, params.tissue_filter
            )
        elif params.go_filter:
            stmts = await client.indra_subnetwork_go(
                gene_nodes, params.go_filter
            )
        else:
            stmts = await client.indra_subnetwork(
                gene_nodes,
                include_evidence=params.include_evidence
            )

    elif params.mode == SubnetworkMode.MEDIATED:
        stmts = await client.indra_mediated_subnetwork(gene_nodes)

    # ... other modes

    # 3. Apply filters
    filtered = filter_statements(
        stmts,
        types=params.statement_types,
        min_evidence=params.min_evidence_count,
        min_belief=params.min_belief_score
    )

    # 4. Limit and format
    limited = filtered[:params.max_statements]
    return format_subnetwork_response(gene_nodes, limited)
```

---

#### Tool 3: `enrichment_analysis`

**Purpose**: Statistical gene set and pathway enrichment analysis

**Use Cases:**
- "What pathways are enriched in these 50 differentially expressed genes?"
- "Run GSEA on this ranked gene list"
- "Find upstream regulators enriched in my gene set"

**Input Schema:**
```python
class EnrichmentQuery(BaseModel):
    analysis_type: EnrichmentType

    # For discrete analysis
    gene_list: Optional[List[str]] = None
    background_genes: Optional[List[str]] = None

    # For continuous/signed analysis
    ranked_genes: Optional[Dict[str, float]] = None
    """Gene -> log fold change or rank score"""

    source: EnrichmentSource = EnrichmentSource.GO
    """Database to test against"""

    alpha: float = 0.05
    """Significance threshold"""

    correction_method: str = "fdr_bh"
    """Multiple testing correction: fdr_bh, bonferroni, etc."""

    keep_insignificant: bool = False
    """Include non-significant results"""

    min_evidence_count: int = 1
    """For INDRA sources: minimum evidence"""

    min_belief_score: float = 0.0
    """For INDRA sources: minimum belief"""

    permutations: int = 1000
    """For continuous analysis: permutation count"""

class EnrichmentType(str, Enum):
    DISCRETE = "discrete"          # Overrepresentation (Fisher's exact)
    CONTINUOUS = "continuous"      # GSEA with log fold changes
    SIGNED = "signed"              # Directional enrichment
    METABOLITE = "metabolite"      # Metabolite set enrichment

class EnrichmentSource(str, Enum):
    GO = "go"                      # Gene Ontology
    REACTOME = "reactome"          # Reactome pathways
    WIKIPATHWAYS = "wikipathways"  # WikiPathways
    INDRA_UPSTREAM = "indra-upstream"    # Upstream regulators
    INDRA_DOWNSTREAM = "indra-downstream" # Downstream targets
    PHENOTYPE = "phenotype"        # HPO phenotypes
```

**Output Schema:**
```python
class EnrichmentResponse(BaseModel):
    query: QueryMetadata
    results: List[EnrichmentResult]
    statistics: EnrichmentStatistics
    metadata: ResponseMetadata

class EnrichmentResult(BaseModel):
    term: EntityRef                # GO term, pathway, etc.
    term_name: str
    p_value: float
    adjusted_p_value: float
    enrichment_score: Optional[float]  # For GSEA
    normalized_enrichment_score: Optional[float]
    gene_count: int                # Genes from query in term
    term_size: int                 # Total genes in term
    genes: List[str]               # Overlapping genes
    background_count: Optional[int]

class EnrichmentStatistics(BaseModel):
    total_results: int
    significant_results: int
    total_genes_analyzed: int
    correction_method: str
    alpha: float
```

**Backend Implementation:**
```python
async def enrichment_analysis(params: EnrichmentQuery) -> EnrichmentResponse:
    # 1. Prepare payload for REST API (currently no Python client method)
    if params.analysis_type == EnrichmentType.DISCRETE:
        payload = {
            "gene_list": params.gene_list,
            "background_gene_list": params.background_genes,
            "alpha": params.alpha,
            "method": params.correction_method,
            "keep_insignificant": params.keep_insignificant,
            "minimum_evidence_count": params.min_evidence_count,
            "minimum_belief": params.min_belief_score,
        }
        endpoint = "/api/discrete_analysis"

    elif params.analysis_type == EnrichmentType.CONTINUOUS:
        payload = {
            "gene_names": list(params.ranked_genes.keys()),
            "log_fold_change": list(params.ranked_genes.values()),
            "source": params.source.value,
            "permutations": params.permutations,
            "alpha": params.alpha,
            # ...
        }
        endpoint = "/api/continuous_analysis"

    # 2. Call REST API
    response = await rest_client.post(endpoint, json=payload)

    # 3. Parse and format
    return format_enrichment_response(response.json())
```

---

#### Tool 4: `query_drug_profile`

**Purpose**: Comprehensive drug characterization

**Use Cases:**
- "What does aspirin target and what are its side effects?"
- "Find clinical trials for pembrolizumab"
- "What cell lines are sensitive to imatinib?"

**Input Schema:**
```python
class DrugProfileQuery(BaseModel):
    drug: str | Tuple[str, str]
    """Drug identifier - accepts:
    - Common name: "aspirin", "imatinib"
    - ChEMBL ID: "CHEMBL25"
    - CURIE: "chebi:15365"
    - Tuple: ("chebi", "15365")
    """

    include_targets: bool = True
    """Known protein targets"""

    include_indications: bool = True
    """Disease indications from ChEMBL"""

    include_side_effects: bool = True
    """Adverse effects from SIDER"""

    include_trials: bool = True
    """Active clinical trials"""

    include_cell_lines: bool = False
    """CCLE cell line sensitivities"""

    max_results_per_category: int = 50
```

**Output Schema:**
```python
class DrugProfileResponse(BaseModel):
    query: QueryMetadata
    drug: DrugNode
    targets: Optional[List[DrugTarget]]
    indications: Optional[List[DrugIndication]]
    side_effects: Optional[List[SideEffect]]
    trials: Optional[List[ClinicalTrial]]
    cell_lines: Optional[List[CellLineSensitivity]]
    metadata: ResponseMetadata

class DrugNode(BaseModel):
    name: str
    curie: str
    synonyms: List[str]
    drug_type: Optional[str]

class DrugTarget(BaseModel):
    target: EntityRef            # Gene
    action_type: Optional[str]   # "INHIBITOR", "AGONIST", etc.
    evidence_count: int
    sources: List[str]

class DrugIndication(BaseModel):
    disease: EntityRef
    indication_type: str         # "approved", "clinical_trial"
    max_phase: Optional[int]     # Clinical trial phase

class SideEffect(BaseModel):
    effect: EntityRef            # MedDRA term
    frequency: Optional[str]     # "common", "rare", etc.

class ClinicalTrial(BaseModel):
    trial_id: str                # NCT identifier
    title: str
    phase: Optional[str]
    status: str
    conditions: List[str]
```

---

#### Tool 5: `query_disease_mechanisms`

**Purpose**: Disease-centric mechanistic information

**Use Cases:**
- "What genes are associated with Alzheimer's disease?"
- "Find druggable targets for breast cancer"
- "What genetic variants increase risk for diabetes?"

**Input Schema:**
```python
class DiseaseMechanismsQuery(BaseModel):
    disease: str | Tuple[str, str]
    """Disease identifier - accepts:
    - Common name: "Alzheimer's disease"
    - DOID: "DOID:10652"
    - MeSH: "D000544"
    - CURIE: "doid:10652"
    - Tuple: ("doid", "10652")
    """

    include_genes: bool = True
    """Associated genes from DisGeNet"""

    include_variants: bool = True
    """Genetic variants from GWAS"""

    include_phenotypes: bool = True
    """Clinical phenotypes"""

    include_drugs: bool = True
    """Available therapies"""

    include_trials: bool = True
    """Active clinical trials"""

    max_results_per_category: int = 50
```

**Output Schema:**
```python
class DiseaseMechanismsResponse(BaseModel):
    query: QueryMetadata
    disease: DiseaseNode
    genes: Optional[List[GeneAssociation]]
    variants: Optional[List[VariantAssociation]]
    phenotypes: Optional[List[PhenotypeAssociation]]
    drugs: Optional[List[DrugTherapy]]
    trials: Optional[List[ClinicalTrial]]
    metadata: ResponseMetadata

class DiseaseNode(BaseModel):
    name: str
    curie: str
    synonyms: List[str]
    description: Optional[str]

class GeneAssociation(BaseModel):
    gene: EntityRef
    score: float                 # DisGeNet score
    evidence_count: int
    sources: List[str]

class VariantAssociation(BaseModel):
    variant: EntityRef
    rsid: Optional[str]
    p_value: Optional[float]
    odds_ratio: Optional[float]
    source: str                  # "gwas", "disgenet"
```

---

### Priority 2: Specialized Query Tools

#### Tool 6: `query_pathway`

**Purpose**: Pathway membership and gene set analysis

**Input Schema:**
```python
class PathwayQuery(BaseModel):
    mode: PathwayQueryMode

    # For pathway lookup
    pathway: Optional[str | Tuple[str, str]] = None

    # For shared pathway analysis
    genes: Optional[List[str]] = None

    source: PathwaySource = PathwaySource.ALL

    include_descriptions: bool = True

class PathwayQueryMode(str, Enum):
    GET_GENES = "get_genes"              # Pathway → genes
    GET_PATHWAYS = "get_pathways"        # Gene → pathways
    FIND_SHARED = "find_shared"          # Genes → shared pathways
    CHECK_MEMBERSHIP = "check_membership" # Gene + Pathway → bool

class PathwaySource(str, Enum):
    ALL = "all"
    REACTOME = "reactome"
    WIKIPATHWAYS = "wikipathways"
```

**Output Schema:**
```python
class PathwayResponse(BaseModel):
    query: QueryMetadata
    results: PathwayResults
    metadata: ResponseMetadata

class PathwayResults(BaseModel):
    # Different fields populated based on mode
    pathways: Optional[List[PathwayInfo]]
    genes: Optional[List[GeneInfo]]
    is_member: Optional[bool]
    shared_pathways: Optional[List[SharedPathway]]

class PathwayInfo(BaseModel):
    pathway: EntityRef
    source: str
    description: Optional[str]
    gene_count: int

class SharedPathway(BaseModel):
    pathway: EntityRef
    source: str
    shared_genes: List[str]
    shared_count: int
    total_genes: int
```

---

#### Tool 7: `query_cell_line`

**Purpose**: Cancer cell line properties from CCLE and DepMap

**Input Schema:**
```python
class CellLineQuery(BaseModel):
    mode: CellLineQueryMode

    # For cell line lookup
    cell_line: Optional[str | Tuple[str, str]] = None

    # For gene/drug lookup
    gene: Optional[str | Tuple[str, str]] = None
    drug: Optional[str | Tuple[str, str]] = None

    include_mutations: bool = True
    include_cna: bool = True
    include_dependencies: bool = False
    include_drug_sensitivity: bool = False

class CellLineQueryMode(str, Enum):
    GET_PROPERTIES = "get_properties"        # Cell line → all data
    GET_MUTATED_GENES = "get_mutated_genes"  # Cell line → genes
    GET_CELL_LINES_WITH_MUTATION = "get_cell_lines_with_mutation"  # Gene → cell lines
    CHECK_MUTATION = "check_mutation"        # Cell line + Gene → bool
```

**Output Schema:**
```python
class CellLineResponse(BaseModel):
    query: QueryMetadata
    results: CellLineResults
    metadata: ResponseMetadata

class CellLineResults(BaseModel):
    cell_lines: Optional[List[CellLineInfo]]
    genes: Optional[List[GeneInfo]]
    is_mutated: Optional[bool]
    is_sensitive: Optional[bool]

class CellLineInfo(BaseModel):
    cell_line: EntityRef
    tissue: str
    mutations: Optional[List[GeneMutation]]
    cna: Optional[List[CopyNumberAlteration]]
    dependencies: Optional[List[GeneDependency]]
    sensitivities: Optional[List[DrugSensitivity]]

class GeneMutation(BaseModel):
    gene: EntityRef
    mutation_type: str

class DrugSensitivity(BaseModel):
    drug: EntityRef
    ic50: Optional[float]
    auc: Optional[float]
```

---

#### Tool 8: `query_clinical_trials`

**Purpose**: ClinicalTrials.gov data access

**Input Schema:**
```python
class ClinicalTrialsQuery(BaseModel):
    mode: TrialQueryMode

    drug: Optional[str | Tuple[str, str]] = None
    disease: Optional[str | Tuple[str, str]] = None
    trial_id: Optional[str] = None

    status_filter: Optional[List[str]] = None
    """["recruiting", "active", "completed", ...]"""

    phase_filter: Optional[List[str]] = None
    """["phase1", "phase2", "phase3", "phase4"]"""

    max_results: int = 50

class TrialQueryMode(str, Enum):
    GET_FOR_DRUG = "get_for_drug"
    GET_FOR_DISEASE = "get_for_disease"
    GET_BY_ID = "get_by_id"
```

**Output Schema:**
```python
class ClinicalTrialsResponse(BaseModel):
    query: QueryMetadata
    trials: List[ClinicalTrial]
    statistics: TrialStatistics
    metadata: ResponseMetadata

class ClinicalTrial(BaseModel):
    trial_id: str
    nct_id: str
    title: str
    status: str
    phase: Optional[str]
    conditions: List[str]
    interventions: List[str]
    sponsor: Optional[str]
    start_date: Optional[str]
    completion_date: Optional[str]

class TrialStatistics(BaseModel):
    total_trials: int
    by_phase: Dict[str, int]
    by_status: Dict[str, int]
```

---

#### Tool 9: `query_literature_evidence`

**Purpose**: PubMed and evidence retrieval

**Input Schema:**
```python
class LiteratureQuery(BaseModel):
    mode: LiteratureQueryMode

    # For paper lookup
    pmid: Optional[str | List[str]] = None

    # For MeSH-based search
    mesh_terms: Optional[List[str]] = None

    # For statement evidence
    statement_hash: Optional[str | List[str]] = None

    include_full_text: bool = False
    max_results: int = 50

class LiteratureQueryMode(str, Enum):
    GET_STATEMENTS_FOR_PMID = "get_statements_for_pmid"
    GET_EVIDENCE_FOR_STATEMENT = "get_evidence_for_statement"
    SEARCH_BY_MESH = "search_by_mesh"
```

**Output Schema:**
```python
class LiteratureResponse(BaseModel):
    query: QueryMetadata
    results: LiteratureResults
    metadata: ResponseMetadata

class LiteratureResults(BaseModel):
    statements: Optional[List[IndraStatement]]
    evidence: Optional[List[Evidence]]
    publications: Optional[List[Publication]]

class Publication(BaseModel):
    pmid: str
    title: str
    authors: List[str]
    journal: str
    year: int
    mesh_terms: List[str]
```

---

#### Tool 10: `query_variants`

**Purpose**: Genetic variant associations

**Input Schema:**
```python
class VariantQuery(BaseModel):
    mode: VariantQueryMode

    gene: Optional[str | Tuple[str, str]] = None
    disease: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None
    variant: Optional[str | Tuple[str, str]] = None

    include_gwas: bool = True
    include_disgenet: bool = True
    min_p_value: Optional[float] = None

class VariantQueryMode(str, Enum):
    GET_FOR_GENE = "get_for_gene"
    GET_FOR_DISEASE = "get_for_disease"
    GET_FOR_PHENOTYPE = "get_for_phenotype"
    CHECK_ASSOCIATION = "check_association"
```

**Output Schema:**
```python
class VariantResponse(BaseModel):
    query: QueryMetadata
    variants: List[VariantInfo]
    metadata: ResponseMetadata

class VariantInfo(BaseModel):
    variant: EntityRef
    rsid: Optional[str]
    gene: Optional[EntityRef]
    disease: Optional[EntityRef]
    phenotype: Optional[EntityRef]
    p_value: Optional[float]
    odds_ratio: Optional[float]
    source: str
```

---

### Priority 3: Utility Tools

#### Tool 11: `resolve_identifiers`

**Purpose**: Convert between biological identifier systems

**Input Schema:**
```python
class IdentifierQuery(BaseModel):
    identifiers: List[str]
    from_namespace: str
    to_namespace: str

# Supported conversions:
# - hgnc_id <-> hgnc_symbol
# - hgnc <-> uniprot
# - hgnc <-> entrez
```

#### Tool 12: `check_relationship`

**Purpose**: Boolean validation of relationships

**Input Schema:**
```python
class RelationshipQuery(BaseModel):
    relationship_type: RelationshipType
    entity1: str | Tuple[str, str]
    entity2: str | Tuple[str, str]

class RelationshipType(str, Enum):
    GENE_IN_PATHWAY = "gene_in_pathway"
    GENE_IN_TISSUE = "gene_in_tissue"
    DRUG_TARGET = "drug_target"
    DRUG_INDICATION = "drug_indication"
    # ... etc
```

#### Tool 13: `get_ontology_hierarchy`

**Purpose**: Navigate ontological relationships

**Input Schema:**
```python
class OntologyQuery(BaseModel):
    term: str | Tuple[str, str]
    direction: OntologyDirection
    max_depth: int = 5

class OntologyDirection(str, Enum):
    PARENTS = "parents"      # isa/partof ancestors
    CHILDREN = "children"    # isa/partof descendants
    BOTH = "both"
```

---

## Data Schemas

### Common Types

```python
# All schemas in indra_cogex_mcp/schemas.py

from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field, validator
from datetime import datetime

class EntityRef(BaseModel):
    """Standardized entity reference"""
    name: str
    curie: str
    namespace: str
    identifier: str

    @classmethod
    def from_curie(cls, curie: str):
        namespace, identifier = curie.split(":", 1)
        return cls(
            name="",  # Populated later
            curie=curie,
            namespace=namespace,
            identifier=identifier
        )

class QueryMetadata(BaseModel):
    """Query tracking information"""
    tool: str
    parameters: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str

class ResponseMetadata(BaseModel):
    """Response metadata"""
    result_count: int
    sources: List[str]              # Data sources consulted
    execution_time_ms: int
    cached: bool = False
    warnings: List[str] = []

class ErrorResponse(BaseModel):
    """Standard error format"""
    error: str
    error_type: str                 # "ValidationError", "NotFound", etc.
    details: Optional[Dict[str, Any]] = None
    suggestions: List[str] = []
    request_id: str
```

---

## Implementation Guidelines

### Project Structure

```
indra-cogex-mcp/
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_SPEC.md          # This document
├── LICENSE
├── .gitignore
├── .env.example
├── src/
│   └── indra_cogex_mcp/
│       ├── __init__.py
│       ├── server.py               # MCP server entry point
│       ├── config.py                # Configuration management
│       ├── schemas.py               # Pydantic models
│       ├── tools/                   # Tool implementations
│       │   ├── __init__.py
│       │   ├── gene.py              # Tool 1: query_gene_context
│       │   ├── subnetwork.py        # Tool 2: extract_subnetwork
│       │   ├── enrichment.py        # Tool 3: enrichment_analysis
│       │   ├── drug.py              # Tool 4: query_drug_profile
│       │   ├── disease.py           # Tool 5: query_disease_mechanisms
│       │   ├── pathway.py           # Tool 6: query_pathway
│       │   ├── cell_line.py         # Tool 7: query_cell_line
│       │   ├── trials.py            # Tool 8: query_clinical_trials
│       │   ├── literature.py        # Tool 9: query_literature_evidence
│       │   ├── variants.py          # Tool 10: query_variants
│       │   ├── identifiers.py       # Tool 11: resolve_identifiers
│       │   ├── relationships.py     # Tool 12: check_relationship
│       │   └── ontology.py          # Tool 13: get_ontology_hierarchy
│       ├── services/                # Business logic layer
│       │   ├── __init__.py
│       │   ├── entity_resolver.py  # ID resolution
│       │   ├── cache.py             # Caching layer
│       │   └── formatter.py         # Response formatting
│       └── clients/                 # Backend adapters
│           ├── __init__.py
│           ├── neo4j_client.py      # Primary client
│           ├── rest_client.py       # Fallback client
│           └── adapter.py           # Unified interface
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── test_tools/
│   │   ├── test_services/
│   │   └── test_clients/
│   ├── integration/
│   │   ├── test_neo4j_integration.py
│   │   └── test_rest_integration.py
│   └── evaluations/
│       ├── eval_questions.xml       # 10 complex questions
│       └── run_evaluation.py
└── docs/
    ├── architecture.md
    ├── tools_reference.md
    └── examples/
        ├── basic_usage.md
        └── advanced_workflows.md
```

### Configuration Management

```python
# src/indra_cogex_mcp/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )

    # Connection settings
    neo4j_url: Optional[str] = None
    neo4j_user: str = "neo4j"
    neo4j_password: Optional[str] = None

    # Fallback REST API
    use_rest_fallback: bool = True
    rest_api_base: str = "https://discovery.indra.bio"
    rest_timeout_seconds: int = 30

    # Performance
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate limiting
    rate_limit_enabled: bool = True
    max_requests_per_minute: int = 60

    def has_neo4j_config(self) -> bool:
        return bool(self.neo4j_url and self.neo4j_password)

# Global instance
settings = Settings()
```

### Server Implementation

```python
# src/indra_cogex_mcp/server.py

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .config import settings
from .clients.adapter import get_client
from .tools import (
    query_gene_context,
    extract_subnetwork,
    enrichment_analysis,
    # ... import all tools
)

logger = logging.getLogger(__name__)

# Initialize MCP server
app = Server("indra-cogex-mcp")

# Tool registry
TOOLS = {
    "query_gene_context": query_gene_context,
    "extract_subnetwork": extract_subnetwork,
    "enrichment_analysis": enrichment_analysis,
    "query_drug_profile": query_drug_profile,
    "query_disease_mechanisms": query_disease_mechanisms,
    "query_pathway": query_pathway,
    "query_cell_line": query_cell_line,
    "query_clinical_trials": query_clinical_trials,
    "query_literature_evidence": query_literature_evidence,
    "query_variants": query_variants,
    "resolve_identifiers": resolve_identifiers,
    "check_relationship": check_relationship,
    "get_ontology_hierarchy": get_ontology_hierarchy,
}

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name=name,
            description=tool.description,
            inputSchema=tool.input_schema,
        )
        for name, tool in TOOLS.items()
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute tool"""
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")

    tool = TOOLS[name]

    try:
        # Execute tool
        result = await tool.execute(arguments)

        # Format response
        return [TextContent(
            type="text",
            text=result.model_dump_json(indent=2)
        )]

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

async def main():
    """Run server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### Client Adapter Pattern

```python
# src/indra_cogex_mcp/clients/adapter.py

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..schemas import EntityRef, IndraStatement

class CoGExClientAdapter(ABC):
    """Abstract interface for INDRA CoGEx backends"""

    @abstractmethod
    async def get_tissues_for_gene(self, gene: EntityRef) -> List[Dict]:
        pass

    @abstractmethod
    async def get_go_terms_for_gene(self, gene: EntityRef) -> List[Dict]:
        pass

    # ... declare all needed methods

class Neo4jClientAdapter(CoGExClientAdapter):
    """Primary: Direct Neo4j access via indra_cogex Python client"""

    def __init__(self, url: str, user: str, password: str):
        from indra_cogex.client import Neo4jClient
        self.client = Neo4jClient(url=url, auth=(user, password))

    async def get_tissues_for_gene(self, gene: EntityRef) -> List[Dict]:
        # Call indra_cogex.client.queries.get_tissues_for_gene
        return await asyncio.to_thread(
            self.client.get_tissues_for_gene,
            (gene.namespace, gene.identifier)
        )

    # ... implement all methods

class RESTClientAdapter(CoGExClientAdapter):
    """Fallback: REST API access"""

    def __init__(self, base_url: str, timeout: int = 30):
        import httpx
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout
        )

    async def get_tissues_for_gene(self, gene: EntityRef) -> List[Dict]:
        response = await self.client.post(
            "/api/get_tissues_for_gene",
            json={"gene": [gene.namespace, gene.identifier]}
        )
        response.raise_for_status()
        return response.json()

    # ... implement all methods

def get_client() -> CoGExClientAdapter:
    """Factory: Return configured client"""
    from ..config import settings

    if settings.has_neo4j_config():
        return Neo4jClientAdapter(
            url=settings.neo4j_url,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
    elif settings.use_rest_fallback:
        return RESTClientAdapter(
            base_url=settings.rest_api_base,
            timeout=settings.rest_timeout_seconds
        )
    else:
        raise ValueError("No backend configured")
```

### Entity Resolution Service

```python
# src/indra_cogex_mcp/services/entity_resolver.py

from typing import Tuple, List, Optional
from ..schemas import EntityRef
from ..clients.adapter import CoGExClientAdapter

class EntityResolver:
    """Resolve flexible identifier inputs to canonical EntityRefs"""

    def __init__(self, client: CoGExClientAdapter):
        self.client = client

    async def resolve_gene(
        self,
        identifier: str | Tuple[str, str]
    ) -> EntityRef:
        """
        Resolve gene from:
        - HGNC symbol: "TP53"
        - CURIE: "hgnc:11998"
        - Tuple: ("hgnc", "11998")
        """
        if isinstance(identifier, tuple):
            namespace, id = identifier
            return EntityRef(
                name="",  # Fetch from DB
                curie=f"{namespace}:{id}",
                namespace=namespace,
                identifier=id
            )

        elif ":" in identifier:
            # CURIE format
            return EntityRef.from_curie(identifier)

        else:
            # Assume HGNC symbol, resolve to ID
            # Call client to lookup
            result = await self.client.get_hgnc_id_from_symbol(identifier)

            if not result:
                raise ValueError(
                    f"Gene '{identifier}' not found. "
                    "Please provide HGNC symbol, ID, or CURIE."
                )

            if len(result) > 1:
                options = ", ".join([r['symbol'] for r in result])
                raise ValueError(
                    f"Ambiguous gene '{identifier}'. "
                    f"Multiple matches: {options}"
                )

            return EntityRef(
                name=result[0]['symbol'],
                curie=f"hgnc:{result[0]['id']}",
                namespace="hgnc",
                identifier=result[0]['id']
            )

    async def resolve_drug(self, identifier: str | Tuple[str, str]) -> EntityRef:
        # Similar logic for drugs
        pass

    async def resolve_disease(self, identifier: str | Tuple[str, str]) -> EntityRef:
        # Similar logic for diseases
        pass
```

### Caching Layer

```python
# src/indra_cogex_mcp/services/cache.py

from functools import wraps
from cachetools import TTLCache
from typing import Callable, Any
import hashlib
import json

class ResponseCache:
    """LRU cache with TTL for expensive queries"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)

    def cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Generate deterministic cache key"""
        key_data = {
            "func": func_name,
            "args": args,
            "kwargs": kwargs
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()

    def cached(self, func: Callable) -> Callable:
        """Decorator for cacheable functions"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = self.cache_key(func.__name__, args, kwargs)

            if key in self.cache:
                return self.cache[key]

            result = await func(*args, **kwargs)
            self.cache[key] = result
            return result

        return wrapper

# Global cache instance
cache = ResponseCache()
```

### Tool Implementation Template

```python
# src/indra_cogex_mcp/tools/gene.py

from typing import Any, Dict
from ..schemas import GeneContextQuery, GeneContextResponse
from ..clients.adapter import get_client
from ..services.entity_resolver import EntityResolver
from ..services.cache import cache

class GeneContextTool:
    """Tool 1: query_gene_context"""

    name = "query_gene_context"
    description = """
    Retrieve comprehensive gene information across multiple data domains.

    Use this tool when you need:
    - Complete gene profile
    - Expression patterns
    - Pathway memberships
    - Disease associations
    - Protein domains
    - Known variants

    Example queries:
    - "What do we know about TP53?"
    - "Where is BRCA1 expressed?"
    - "What pathways contain EGFR?"
    """

    input_schema = GeneContextQuery.model_json_schema()

    def __init__(self):
        self.client = get_client()
        self.resolver = EntityResolver(self.client)

    @cache.cached
    async def execute(self, params: Dict[str, Any]) -> GeneContextResponse:
        """Execute tool"""
        # 1. Validate input
        query = GeneContextQuery(**params)

        # 2. Resolve gene
        gene_ref = await self.resolver.resolve_gene(query.gene)

        # 3. Fetch data in parallel
        import asyncio
        tasks = []

        if query.include_expression:
            tasks.append(self._get_expression(gene_ref))
        if query.include_go_terms:
            tasks.append(self._get_go_terms(gene_ref))
        if query.include_pathways:
            tasks.append(self._get_pathways(gene_ref))
        # ... more tasks

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. Format response
        return self._format_response(gene_ref, results, query)

    async def _get_expression(self, gene: EntityRef) -> List[Dict]:
        """Fetch tissue expression data"""
        return await self.client.get_tissues_for_gene(gene)

    async def _get_go_terms(self, gene: EntityRef) -> List[Dict]:
        """Fetch GO annotations"""
        return await self.client.get_go_terms_for_gene(gene)

    # ... more helper methods

    def _format_response(
        self,
        gene: EntityRef,
        results: List[Any],
        query: GeneContextQuery
    ) -> GeneContextResponse:
        """Format collected data into response"""
        # Parse results, handle errors, format
        pass

# Export tool instance
query_gene_context = GeneContextTool()
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_tools/test_gene.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from indra_cogex_mcp.tools.gene import GeneContextTool
from indra_cogex_mcp.schemas import GeneContextQuery

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_tissues_for_gene.return_value = [
        {"tissue": {"name": "brain", "curie": "uberon:0000955"}}
    ]
    client.get_go_terms_for_gene.return_value = [
        {"go_term": {"name": "apoptosis", "curie": "go:0006915"}}
    ]
    return client

@pytest.mark.asyncio
async def test_query_gene_context_basic(mock_client):
    """Test basic gene context query"""
    tool = GeneContextTool()
    tool.client = mock_client

    params = {
        "gene": "TP53",
        "include_expression": True,
        "include_go_terms": True
    }

    response = await tool.execute(params)

    assert response.gene.name == "TP53"
    assert len(response.expression) > 0
    assert len(response.go_terms) > 0

@pytest.mark.asyncio
async def test_query_gene_context_invalid_gene(mock_client):
    """Test error handling for invalid gene"""
    tool = GeneContextTool()
    tool.client = mock_client
    tool.client.get_hgnc_id_from_symbol.return_value = []

    params = {"gene": "FAKEGENE"}

    with pytest.raises(ValueError, match="not found"):
        await tool.execute(params)
```

### Integration Tests

```python
# tests/integration/test_neo4j_integration.py

import pytest
import os
from indra_cogex_mcp.clients.neo4j_client import Neo4jClientAdapter
from indra_cogex_mcp.schemas import EntityRef

# Skip if no Neo4j configured
pytestmark = pytest.mark.skipif(
    not os.getenv("NEO4J_URL"),
    reason="Neo4j not configured"
)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tissues_for_tp53():
    """Integration test: Fetch TP53 expression"""
    client = Neo4jClientAdapter(
        url=os.getenv("NEO4J_URL"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )

    tp53 = EntityRef.from_curie("hgnc:11998")
    tissues = await client.get_tissues_for_gene(tp53)

    assert len(tissues) > 0
    assert any(t['tissue']['name'] == 'brain' for t in tissues)
```

### Test Coverage Requirements

- **Unit Tests**: 90%+ coverage
- **Integration Tests**: All priority 1 tools
- **End-to-End Tests**: MCP protocol communication

---

## Evaluation Framework

### Evaluation Questions (eval_questions.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<evaluations>
  <evaluation id="1" complexity="high">
    <question>
      What genes are mutated in lung cancer cell lines (CCLE) and what drugs
      currently target those genes?
    </question>
    <expected_tools>
      <tool>query_cell_line</tool>
      <tool>query_drug_profile</tool>
    </expected_tools>
    <success_criteria>
      - Identifies multiple lung cancer cell lines
      - Lists mutated genes (e.g., EGFR, KRAS, TP53)
      - Maps genes to targeting drugs (e.g., EGFR → erlotinib)
      - Provides evidence counts
    </success_criteria>
  </evaluation>

  <evaluation id="2" complexity="high">
    <question>
      Find shared pathways between BRCA1, BRCA2, and PALB2. Then identify
      other genes in those pathways that are also associated with breast cancer.
    </question>
    <expected_tools>
      <tool>query_pathway</tool>
      <tool>query_disease_mechanisms</tool>
      <tool>extract_subnetwork</tool>
    </expected_tools>
    <success_criteria>
      - Identifies DNA repair pathways (e.g., Reactome DNA repair)
      - Lists other pathway members
      - Filters for breast cancer associations
      - Provides DisGeNet scores
    </success_criteria>
  </evaluation>

  <evaluation id="3" complexity="high">
    <question>
      What tissues express genes in the p53 signaling pathway? For those genes
      expressed in brain tissue, what are their known functions (GO terms)?
    </question>
    <expected_tools>
      <tool>query_pathway</tool>
      <tool>query_gene_context</tool>
    </expected_tools>
    <success_criteria>
      - Retrieves p53 pathway genes
      - Checks expression for each gene
      - Filters for brain-expressed genes
      - Provides GO annotations for filtered genes
    </success_criteria>
  </evaluation>

  <evaluation id="4" complexity="medium">
    <question>
      Which drugs targeting EGFR are currently in clinical trials for
      non-small cell lung cancer?
    </question>
    <expected_tools>
      <tool>query_drug_profile</tool>
      <tool>query_clinical_trials</tool>
    </expected_tools>
    <success_criteria>
      - Identifies EGFR-targeting drugs
      - Finds relevant clinical trials
      - Filters by disease indication
      - Provides trial IDs and phases
    </success_criteria>
  </evaluation>

  <evaluation id="5" complexity="high">
    <question>
      Perform gene set enrichment analysis on these differentially expressed
      genes [AKT1, PIK3CA, MTOR, RPS6KB1, EIF4EBP1] and identify the enriched
      pathways. Then find what drugs target genes in the top enriched pathway.
    </question>
    <expected_tools>
      <tool>enrichment_analysis</tool>
      <tool>query_pathway</tool>
      <tool>query_drug_profile</tool>
    </expected_tools>
    <success_criteria>
      - Runs discrete enrichment (or provides instruction)
      - Identifies PI3K-AKT signaling pathway
      - Retrieves pathway member genes
      - Maps genes to targeting drugs
    </success_criteria>
  </evaluation>

  <evaluation id="6" complexity="medium">
    <question>
      What are the most common side effects of imatinib and what is its
      mechanism of action (targets)?
    </question>
    <expected_tools>
      <tool>query_drug_profile</tool>
    </expected_tools>
    <success_criteria>
      - Identifies imatinib (CHEMBL941)
      - Lists targets (BCR-ABL, KIT, PDGFR)
      - Provides side effects from SIDER
      - Includes frequency/severity if available
    </success_criteria>
  </evaluation>

  <evaluation id="7" complexity="high">
    <question>
      Find genes that are codependent with KRAS in DepMap data, then identify
      which of those genes have drug targets.
    </question>
    <expected_tools>
      <tool>query_gene_context</tool>
      <tool>query_drug_profile</tool>
    </expected_tools>
    <success_criteria>
      - Retrieves KRAS codependencies
      - For each codependent gene, checks druggability
      - Provides drug names and target info
      - Explains significance
    </success_criteria>
  </evaluation>

  <evaluation id="8" complexity="medium">
    <question>
      What genetic variants (SNPs) are associated with Alzheimer's disease
      according to GWAS studies? For the most significant variants, what genes
      do they affect?
    </question>
    <expected_tools>
      <tool>query_variants</tool>
      <tool>query_disease_mechanisms</tool>
    </expected_tools>
    <success_criteria>
      - Retrieves GWAS variants for Alzheimer's
      - Provides p-values and rsIDs
      - Maps variants to genes (e.g., APOE)
      - Ranks by significance
    </success_criteria>
  </evaluation>

  <evaluation id="9" complexity="high">
    <question>
      Find the mechanistic subnetwork connecting TP53, MDM2, and ATM. What types
      of interactions exist between these genes and what is the evidence supporting
      each interaction?
    </question>
    <expected_tools>
      <tool>extract_subnetwork</tool>
    </expected_tools>
    <success_criteria>
      - Retrieves direct INDRA statements
      - Identifies statement types (activation, inhibition, ubiquitination)
      - Provides evidence counts and belief scores
      - Optionally includes evidence text and PMIDs
    </success_criteria>
  </evaluation>

  <evaluation id="10" complexity="medium">
    <question>
      Which cell markers distinguish CD4+ T cells from CD8+ T cells, and are
      any of these markers druggable?
    </question>
    <expected_tools>
      <tool>query_cell_line</tool>
      <tool>query_drug_profile</tool>
    </expected_tools>
    <success_criteria>
      - Retrieves cell type markers
      - Identifies CD4/CD8 markers
      - Checks if markers are drug targets
      - Provides targeting drugs if available
    </success_criteria>
  </evaluation>
</evaluations>
```

### Running Evaluations

```python
# tests/evaluations/run_evaluation.py

import asyncio
import xml.etree.ElementTree as ET
from indra_cogex_mcp.server import TOOLS

async def run_evaluation(eval_xml: str):
    """Run evaluation suite"""
    tree = ET.parse(eval_xml)
    root = tree.getroot()

    results = []

    for eval in root.findall('evaluation'):
        eval_id = eval.get('id')
        question = eval.find('question').text

        print(f"\n[Evaluation {eval_id}]")
        print(f"Question: {question}")

        # Here you would:
        # 1. Send question to Claude with MCP tools available
        # 2. Capture tool calls and responses
        # 3. Evaluate against success criteria
        # 4. Score the result

        # For now, placeholder
        result = {
            "id": eval_id,
            "question": question,
            "success": True,  # Determine programmatically
            "tool_calls": [],
            "reasoning": ""
        }

        results.append(result)

    # Generate report
    success_rate = sum(r['success'] for r in results) / len(results)
    print(f"\n✓ Success Rate: {success_rate * 100:.1f}%")

    return results

if __name__ == "__main__":
    asyncio.run(run_evaluation("eval_questions.xml"))
```

---

## Deployment Guide

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/yourusername/indra-cogex-mcp.git
cd indra-cogex-mcp

# 2. Set up Python environment
python3.12 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 3. Install indra_cogex from GitHub
git clone https://github.com/gyorilab/indra_cogex.git
cd indra_cogex
pip install -e .
cd ..

# 4. Install project dependencies
pip install -e ".[dev]"

# 5. Configure environment
cp .env.example .env
# Edit .env with your Neo4j credentials or use REST fallback

# 6. Run tests
pytest tests/ -v

# 7. Start server
indra-cogex-mcp
```

### Environment Configuration

```bash
# .env.example

# Neo4j Connection (optional - for best performance)
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# REST API Fallback (enabled by default)
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
REST_TIMEOUT_SECONDS=30

# Caching
CACHE_ENABLED=true
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=1000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Rate Limiting
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=60
```

### Claude Configuration

```json
// claude_desktop_config.json

{
  "mcpServers": {
    "indra-cogex": {
      "command": "/path/to/venv/bin/indra-cogex-mcp",
      "args": [],
      "env": {
        "NEO4J_URL": "bolt://localhost:7687",
        "NEO4J_PASSWORD": "your_password",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Docker Deployment

```dockerfile
# Dockerfile

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and install indra_cogex
RUN git clone https://github.com/gyorilab/indra_cogex.git && \
    cd indra_cogex && \
    pip install -e .

# Copy application
COPY pyproject.toml .
COPY src/ src/

# Install application
RUN pip install -e .

# Run server
CMD ["indra-cogex-mcp"]
```

```yaml
# docker-compose.yml

services:
  indra-cogex-mcp:
    build: .
    environment:
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - USE_REST_FALLBACK=true
    depends_on:
      - neo4j

  neo4j:
    image: neo4j:5-enterprise
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    volumes:
      - neo4j_data:/data

volumes:
  neo4j_data:
```

---

## Examples & Use Cases

### Example 1: Gene Discovery Workflow

**Scenario**: Researcher wants to understand TP53 biology

```python
# User question to Claude:
"Tell me everything you can find about TP53 - where it's expressed,
what pathways it's in, what diseases it's associated with, and what
interacts with it."

# Claude's tool calls:

# 1. Get comprehensive gene context
query_gene_context({
  "gene": "TP53",
  "include_expression": true,
  "include_pathways": true,
  "include_diseases": true,
  "include_go_terms": true
})

# Response shows:
# - Expressed in 50+ tissues (ubiquitous)
# - In pathways: p53 signaling, apoptosis, DNA damage response
# - Associated with: Li-Fraumeni syndrome, various cancers
# - GO terms: transcription factor, tumor suppressor

# 2. Get interaction network
extract_subnetwork({
  "genes": ["TP53"],
  "mode": "direct",
  "max_statements": 50,
  "include_evidence": true
})

# Response shows:
# - MDM2 ubiquitinates TP53
# - ATM phosphorylates TP53
# - TP53 activates CDKN1A
# - Evidence: 100+ papers per interaction
```

### Example 2: Drug Repurposing Analysis

**Scenario**: Find alternative indications for imatinib

```python
# User question:
"What does imatinib target, what is it approved for, and are there
clinical trials testing it for other diseases?"

# Tool calls:

# 1. Get drug profile
query_drug_profile({
  "drug": "imatinib",
  "include_targets": true,
  "include_indications": true,
  "include_trials": true,
  "include_side_effects": true
})

# Response:
# Targets: BCR-ABL, KIT, PDGFR
# Approved: CML, GIST
# Trials: Testing for glioblastoma, dermatofibrosarcoma
# Side effects: Nausea, edema, muscle cramps

# 2. Find other diseases with same targets
query_disease_mechanisms({
  "disease": "glioblastoma",
  "include_genes": true
})

# Check if PDGFR is implicated → Yes, overexpressed in glioblastoma
```

### Example 3: Pathway Enrichment Analysis

**Scenario**: Analyze RNA-seq results

```python
# User provides:
"I have these upregulated genes from my RNA-seq experiment: AKT1,
PIK3CA, MTOR, RPS6KB1, EIF4EBP1, GSK3B, FOXO1. What pathways are enriched?"

# Tool call:
enrichment_analysis({
  "analysis_type": "discrete",
  "gene_list": ["AKT1", "PIK3CA", "MTOR", "RPS6KB1", "EIF4EBP1", "GSK3B", "FOXO1"],
  "source": "reactome",
  "alpha": 0.05
})

# Response:
# Top enriched pathways:
# 1. PI3K-AKT signaling (p=1.2e-8)
# 2. mTOR signaling (p=3.4e-7)
# 3. Insulin signaling (p=5.6e-6)

# Follow-up question:
"What drugs target genes in the PI3K-AKT pathway?"

# Get pathway members
query_pathway({
  "mode": "get_genes",
  "pathway": "reactome:R-HSA-5205685"  # PI3K-AKT
})

# For each gene, check druggability
query_drug_profile({
  "mode": "get_drugs_for_targets",
  "targets": ["PIK3CA", "AKT1", "MTOR"]
})

# Response:
# PIK3CA → alpelisib, pictilisib
# AKT1 → ipatasertib, capivasertib
# MTOR → everolimus, temsirolimus
```

### Example 4: Disease Mechanism Investigation

**Scenario**: Understand Alzheimer's disease genetics

```python
# Question:
"What genes and variants are associated with Alzheimer's disease?
Focus on the most significant GWAS hits."

# Tool call:
query_disease_mechanisms({
  "disease": "Alzheimer's disease",
  "include_genes": true,
  "include_variants": true
})

# Response:
# Top genes:
# - APOE (score: 0.85)
# - APP (score: 0.72)
# - PSEN1 (score: 0.68)

# Top variants:
# - rs429358 (APOE, p=1e-200)
# - rs7412 (APOE, p=1e-50)

# Follow-up:
"What do these genes do and how do they interact?"

# Get gene functions
query_gene_context({
  "gene": "APOE",
  "include_go_terms": true,
  "include_pathways": true
})

# Get interactions
extract_subnetwork({
  "genes": ["APOE", "APP", "PSEN1"],
  "mode": "direct",
  "include_evidence": true
})
```

---

## Implementation Checklist

### Phase 1: Foundation (Week 1)
- [ ] Set up project structure
- [ ] Implement configuration management
- [ ] Create client adapter pattern
- [ ] Implement entity resolver
- [ ] Set up caching layer
- [ ] Configure logging
- [ ] Write basic MCP server scaffold

### Phase 2: Priority 1 Tools (Week 2-3)
- [ ] Tool 1: query_gene_context
- [ ] Tool 2: extract_subnetwork
- [ ] Tool 3: enrichment_analysis
- [ ] Tool 4: query_drug_profile
- [ ] Tool 5: query_disease_mechanisms
- [ ] Unit tests for all Priority 1 tools
- [ ] Integration tests with Neo4j/REST

### Phase 3: Priority 2 Tools (Week 4)
- [ ] Tool 6: query_pathway
- [ ] Tool 7: query_cell_line
- [ ] Tool 8: query_clinical_trials
- [ ] Tool 9: query_literature_evidence
- [ ] Tool 10: query_variants
- [ ] Unit tests for Priority 2 tools

### Phase 4: Priority 3 Utilities (Week 4-5)
- [ ] Tool 11: resolve_identifiers
- [ ] Tool 12: check_relationship
- [ ] Tool 13: get_ontology_hierarchy
- [ ] Unit tests for utilities

### Phase 5: Evaluation & Refinement (Week 5-6)
- [ ] Create 10 evaluation questions
- [ ] Run evaluation suite
- [ ] Analyze failures
- [ ] Refine tool descriptions
- [ ] Optimize performance
- [ ] Add error recovery

### Phase 6: Documentation & Deployment (Week 6)
- [ ] Complete API reference
- [ ] Write usage examples
- [ ] Create Docker setup
- [ ] CI/CD pipeline
- [ ] Security audit
- [ ] Performance benchmarking

---

## Success Criteria

### Functional Requirements
✓ All 13 tools implemented and tested
✓ 90%+ success rate on evaluation suite
✓ Both Neo4j and REST backend support
✓ Comprehensive error handling

### Performance Requirements
✓ Simple queries < 500ms
✓ Complex queries < 5s
✓ Memory usage < 200MB baseline
✓ 99%+ uptime in production

### Quality Requirements
✓ 90%+ test coverage
✓ Type hints on all functions
✓ No critical security vulnerabilities
✓ Comprehensive documentation

---

## Maintenance & Evolution

### Version Strategy
- **v1.0.0**: Priority 1 & 2 tools, production-ready
- **v1.1.0**: Priority 3 tools, enhanced caching
- **v1.2.0**: Advanced graph algorithms (shortest path, centrality)
- **v2.0.0**: Real-time updates, GraphQL support

### Monitoring
- Request latency per tool
- Cache hit rates
- Error rates by type
- Backend availability
- Token usage (for LLM clients)

### Future Enhancements
1. **Graph Algorithms**: PageRank, betweenness centrality
2. **Batch Operations**: Multiple genes/drugs in single request
3. **Streaming Responses**: For large subnetworks
4. **Custom Filters**: User-defined evidence thresholds
5. **Visualization**: Network diagrams, pathway maps
6. **Alerts**: Gene/drug monitoring, literature updates

---

## Contact & Support

**Repository**: https://github.com/yourusername/indra-cogex-mcp
**Documentation**: https://indra-cogex-mcp.readthedocs.io
**Issues**: https://github.com/yourusername/indra-cogex-mcp/issues

**INDRA CoGEx**: https://github.com/gyorilab/indra_cogex
**MCP Protocol**: https://modelcontextprotocol.io

---

**End of Specification**

This document provides complete implementation context for distinguished software engineering agents. All technical decisions are justified, all schemas are defined, and all implementation patterns are specified. No ambiguity remains.
