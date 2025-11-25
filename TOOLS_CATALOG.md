# CoGEx MCP Tools Catalog

**Version**: 1.0.0
**Total Tools**: 16
**Coverage**: 100/110 endpoints (91%)

This is the definitive catalog of all MCP tools with complete, MCP-compliant schemas ready for implementation.

---

## Tool Index

**Priority 1: Core Discovery**
1. [cogex_query_gene_or_feature](#1-cogex_query_gene_or_feature) - Bidirectional gene ↔ features
2. [cogex_extract_subnetwork](#2-cogex_extract_subnetwork) - Graph traversal & mechanisms
3. [cogex_enrichment_analysis](#3-cogex_enrichment_analysis) - GSEA, pathway enrichment
4. [cogex_query_drug_or_effect](#4-cogex_query_drug_or_effect) - Bidirectional drug ↔ effects
5. [cogex_query_disease_or_phenotype](#5-cogex_query_disease_or_phenotype) - Bidirectional disease ↔ phenotypes

**Priority 2: Specialized**
6. [cogex_query_pathway](#6-cogex_query_pathway) - Pathway operations
7. [cogex_query_cell_line](#7-cogex_query_cell_line) - CCLE/DepMap data
8. [cogex_query_clinical_trials](#8-cogex_query_clinical_trials) - ClinicalTrials.gov
9. [cogex_query_literature](#9-cogex_query_literature) - PubMed/evidence
10. [cogex_query_variants](#10-cogex_query_variants) - GWAS, genetic variants

**Priority 3: Utilities & Advanced**
11. [cogex_resolve_identifiers](#11-cogex_resolve_identifiers) - ID conversion
12. [cogex_check_relationship](#12-cogex_check_relationship) - Boolean validators
13. [cogex_get_ontology_hierarchy](#13-cogex_get_ontology_hierarchy) - Ontology navigation
14. [cogex_query_cell_markers](#14-cogex_query_cell_markers) - Cell type markers
15. [cogex_analyze_kinase_enrichment](#15-cogex_analyze_kinase_enrichment) - Phosphoproteomics
16. [cogex_query_protein_functions](#16-cogex_query_protein_functions) - Enzyme activities

---

## Common Schemas

### Shared Types

```python
from enum import Enum
from typing import Optional, List, Tuple, Dict, Any
from pydantic import BaseModel, Field

# Response format (required for all tools)
class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

# Entity reference (used throughout)
class EntityRef(BaseModel):
    name: str
    curie: str
    namespace: str
    identifier: str

# Pagination (for list-returning tools)
class PaginatedResponse(BaseModel):
    total_count: int
    count: int
    offset: int
    limit: int
    has_more: bool
    next_offset: Optional[int] = None

# Standard annotations (customize per tool)
READONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

---

## 1. cogex_query_gene_or_feature

**Purpose**: Bidirectional queries between genes and their features (tissues, GO terms, domains, phenotypes)

**Modes**: 5 (gene→features, tissue→genes, GO→genes, domain→genes, phenotype→genes)

**Coverage**: 8 endpoints

### Input Schema

```python
class QueryMode(str, Enum):
    GENE_TO_FEATURES = "gene_to_features"
    TISSUE_TO_GENES = "tissue_to_genes"
    GO_TO_GENES = "go_to_genes"
    DOMAIN_TO_GENES = "domain_to_genes"
    PHENOTYPE_TO_GENES = "phenotype_to_genes"

class GeneFeatureQuery(BaseModel):
    mode: QueryMode
    """Query direction"""

    # Entity (depends on mode)
    gene: Optional[str | Tuple[str, str]] = None
    tissue: Optional[str | Tuple[str, str]] = None
    go_term: Optional[str | Tuple[str, str]] = None
    domain: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None

    # Options (for gene_to_features)
    include_expression: bool = True
    include_go_terms: bool = True
    include_pathways: bool = True
    include_diseases: bool = True
    include_domains: bool = False
    include_variants: bool = False
    include_phenotypes: bool = False
    include_codependencies: bool = False

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class GeneFeatureResponse(BaseModel):
    # For gene_to_features mode
    gene: Optional[GeneNode]
    expression: Optional[List[ExpressionData]]
    go_terms: Optional[List[GOAnnotation]]
    pathways: Optional[List[PathwayMembership]]
    diseases: Optional[List[DiseaseAssociation]]
    domains: Optional[List[ProteinDomain]]
    variants: Optional[List[GeneticVariant]]
    phenotypes: Optional[List[PhenotypeAssociation]]
    codependencies: Optional[List[GeneCodependent]]

    # For reverse modes (tissue/GO/domain/phenotype → genes)
    genes: Optional[List[GeneNode]]

    # Pagination (if genes list)
    pagination: Optional[PaginatedResponse]

class GeneNode(BaseModel):
    name: str
    curie: str
    description: Optional[str] = None
    synonyms: List[str] = []

class ExpressionData(BaseModel):
    tissue: EntityRef
    confidence: str  # "gold", "silver", "bronze"
    evidence_count: int

class GOAnnotation(BaseModel):
    go_term: EntityRef
    aspect: str  # "biological_process", "molecular_function", "cellular_component"
    evidence_code: str

class PathwayMembership(BaseModel):
    pathway: EntityRef
    source: str  # "reactome", "wikipathways"

class DiseaseAssociation(BaseModel):
    disease: EntityRef
    score: float
    evidence_count: int
    sources: List[str]
```

### Tool Description

```
Comprehensive bidirectional queries between genes and their features.

Modes:
- gene_to_features: Gene → tissues, GO terms, pathways, diseases, etc.
- tissue_to_genes: Tissue → genes expressed in that tissue
- go_to_genes: GO term → genes annotated with that term
- domain_to_genes: Protein domain → genes containing that domain
- phenotype_to_genes: Phenotype → genes associated with that phenotype

Use when:
- "What does TP53 do?" (gene_to_features)
- "What genes are expressed in brain?" (tissue_to_genes)
- "Show me all kinases" (go_to_genes with GO:0016301)
- "Genes with SH2 domains" (domain_to_genes)

Returns:
- Markdown: Human-readable report with sections
- JSON: Structured data with complete metadata

Supports pagination for large gene lists.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_tissues_for_gene` (gene→tissues)
- `get_genes_in_tissue` (tissue→genes)
- `get_go_terms_for_gene` (gene→GO)
- `get_genes_for_go_term` (GO→genes)
- `get_domains_for_gene` (gene→domains)
- `get_genes_for_domain` (domain→genes)
- `get_phenotypes_for_gene` (gene→phenotypes)
- `get_genes_for_phenotype` (phenotype→genes)

---

## 2. cogex_extract_subnetwork

**Purpose**: Graph traversal and mechanistic relationship discovery

**Modes**: 5 (direct, mediated, shared_upstream, shared_downstream, source_to_targets)

**Coverage**: 8 endpoints

### Input Schema

```python
class SubnetworkMode(str, Enum):
    DIRECT = "direct"
    MEDIATED = "mediated"
    SHARED_UPSTREAM = "shared_upstream"
    SHARED_DOWNSTREAM = "shared_downstream"
    SOURCE_TO_TARGETS = "source_to_targets"

class SubnetworkQuery(BaseModel):
    mode: SubnetworkMode

    # For most modes
    genes: Optional[List[str]] = None

    # For source_to_targets mode
    source_gene: Optional[str] = None
    target_genes: Optional[List[str]] = None

    # Filters
    tissue_filter: Optional[str] = None
    go_filter: Optional[str] = None

    # Evidence options
    include_evidence: bool = False
    max_evidence_per_statement: int = Field(default=5, le=10)

    # Statement filters
    statement_types: Optional[List[str]] = None
    min_evidence_count: int = 1
    min_belief_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Limits
    max_statements: int = Field(default=100, le=500)

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class SubnetworkResponse(BaseModel):
    nodes: List[GeneNode]
    statements: List[IndraStatement]
    statistics: NetworkStatistics

class IndraStatement(BaseModel):
    stmt_hash: str
    stmt_type: str  # "Phosphorylation", "Activation", etc.
    subject: EntityRef
    object: EntityRef
    residue: Optional[str] = None  # For modifications
    position: Optional[str] = None
    evidence_count: int
    belief_score: float
    sources: List[str]
    evidence: Optional[List[Evidence]] = None

class Evidence(BaseModel):
    text: str
    pmid: Optional[str] = None
    source_api: str

class NetworkStatistics(BaseModel):
    node_count: int
    edge_count: int
    statement_types: Dict[str, int]
    avg_evidence_per_statement: float
    avg_belief_score: float
```

### Tool Description

```
Extract mechanistic subnetworks from INDRA knowledge graph.

Modes:
- direct: Direct edges between specified genes (A→B)
- mediated: Two-hop paths with intermediates (A→X→B)
- shared_upstream: Shared regulators (A←X→B)
- shared_downstream: Shared targets (A→X←B)
- source_to_targets: One gene regulating multiple targets

Filters:
- tissue_filter: Restrict to genes expressed in tissue
- go_filter: Restrict to genes with GO term
- statement_types: Filter by mechanism type

Use when:
- "How do TP53 and MDM2 interact?" (direct)
- "What connects BRCA1 to DNA repair genes?" (mediated)
- "Shared regulators of inflammatory cytokines" (shared_upstream)

Returns:
- Markdown: Network summary with grouped statements
- JSON: Complete graph with nodes, edges, evidence

Evidence inclusion is optional (adds significant size).
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `indra_subnetwork`
- `indra_mediated_subnetwork`
- `indra_shared_upstream_subnetwork` (implied)
- `indra_shared_downstream_subnetwork` (implied)
- `indra_subnetwork_tissue`
- `indra_subnetwork_go`
- `source_target_analysis`
- `get_network` / `get_network_for_statements`

---

## 3. cogex_enrichment_analysis

**Purpose**: Statistical gene set and pathway enrichment analysis

**Modes**: 4 (discrete, continuous, signed, metabolite)

**Coverage**: 4 endpoints

### Input Schema

```python
class EnrichmentType(str, Enum):
    DISCRETE = "discrete"
    CONTINUOUS = "continuous"
    SIGNED = "signed"
    METABOLITE = "metabolite"

class EnrichmentSource(str, Enum):
    GO = "go"
    REACTOME = "reactome"
    WIKIPATHWAYS = "wikipathways"
    INDRA_UPSTREAM = "indra-upstream"
    INDRA_DOWNSTREAM = "indra-downstream"
    PHENOTYPE = "phenotype"

class EnrichmentQuery(BaseModel):
    analysis_type: EnrichmentType

    # For discrete
    gene_list: Optional[List[str]] = None
    background_genes: Optional[List[str]] = None

    # For continuous/signed
    ranked_genes: Optional[Dict[str, float]] = None
    """Gene → log fold change or rank score"""

    # Analysis parameters
    source: EnrichmentSource = EnrichmentSource.GO
    alpha: float = Field(default=0.05, gt=0, le=1)
    correction_method: str = "fdr_bh"
    keep_insignificant: bool = False

    # For INDRA sources
    min_evidence_count: int = 1
    min_belief_score: float = 0.0

    # For continuous
    permutations: int = Field(default=1000, ge=100, le=10000)

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class EnrichmentResponse(BaseModel):
    results: List[EnrichmentResult]
    statistics: EnrichmentStatistics

class EnrichmentResult(BaseModel):
    term: EntityRef
    term_name: str
    p_value: float
    adjusted_p_value: float
    enrichment_score: Optional[float] = None  # For GSEA
    normalized_enrichment_score: Optional[float] = None
    gene_count: int
    term_size: int
    genes: List[str]
    background_count: Optional[int] = None

class EnrichmentStatistics(BaseModel):
    total_results: int
    significant_results: int
    total_genes_analyzed: int
    correction_method: str
    alpha: float
```

### Tool Description

```
Perform gene set enrichment analysis (GSEA) and pathway analysis.

Analysis types:
- discrete: Overrepresentation (Fisher's exact test)
- continuous: GSEA with ranked gene list
- signed: Directional enrichment (up/down regulation)
- metabolite: Metabolite set enrichment

Sources:
- go: Gene Ontology terms
- reactome: Reactome pathways
- wikipathways: WikiPathways
- indra-upstream: Upstream regulators from INDRA
- indra-downstream: Downstream targets from INDRA
- phenotype: HPO phenotypes

Use when:
- "What pathways are enriched in these DE genes?" (discrete, reactome)
- "Run GSEA on this ranked list" (continuous, go)
- "Find upstream regulators" (discrete, indra-upstream)

Returns:
- Markdown: Ranked table of enriched terms
- JSON: Complete results with statistics

Supports background gene sets for custom enrichment.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,  # Statistical computation may vary slightly
    "openWorldHint": True,
}
```

### Backend Endpoints

- `/api/discrete_analysis`
- `/api/continuous_analysis`
- `/api/signed_analysis`
- `/api/metabolite_discrete_analysis`

---

## 4. cogex_query_drug_or_effect

**Purpose**: Bidirectional queries between drugs and their effects/properties

**Modes**: 2 (drug_to_profile, side_effect_to_drugs)

**Coverage**: 13 endpoints

### Input Schema

```python
class DrugQueryMode(str, Enum):
    DRUG_TO_PROFILE = "drug_to_profile"
    SIDE_EFFECT_TO_DRUGS = "side_effect_to_drugs"

class DrugEffectQuery(BaseModel):
    mode: DrugQueryMode

    # Entity (depends on mode)
    drug: Optional[str | Tuple[str, str]] = None
    side_effect: Optional[str | Tuple[str, str]] = None

    # Options (for drug_to_profile)
    include_targets: bool = True
    include_indications: bool = True
    include_side_effects: bool = True
    include_trials: bool = True
    include_cell_lines: bool = False

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class DrugProfileResponse(BaseModel):
    # For drug_to_profile
    drug: Optional[DrugNode]
    targets: Optional[List[DrugTarget]]
    indications: Optional[List[DrugIndication]]
    side_effects: Optional[List[SideEffect]]
    trials: Optional[List[ClinicalTrial]]
    cell_lines: Optional[List[CellLineSensitivity]]

    # For side_effect_to_drugs
    drugs: Optional[List[DrugNode]]

    # Pagination (if drugs list)
    pagination: Optional[PaginatedResponse]

class DrugNode(BaseModel):
    name: str
    curie: str
    synonyms: List[str] = []
    drug_type: Optional[str] = None

class DrugTarget(BaseModel):
    target: EntityRef
    action_type: Optional[str] = None  # "INHIBITOR", "AGONIST"
    evidence_count: int

class DrugIndication(BaseModel):
    disease: EntityRef
    indication_type: str
    max_phase: Optional[int] = None

class SideEffect(BaseModel):
    effect: EntityRef
    frequency: Optional[str] = None
```

### Tool Description

```
Comprehensive drug characterization and reverse lookup by side effects.

Modes:
- drug_to_profile: Drug → targets, indications, side effects, trials
- side_effect_to_drugs: Side effect → drugs causing that effect

Use when:
- "What does imatinib target?" (drug_to_profile)
- "Side effects of aspirin?" (drug_to_profile)
- "What drugs cause nausea?" (side_effect_to_drugs)
- "Clinical trials for pembrolizumab?" (drug_to_profile)

Returns:
- Markdown: Organized drug profile or drug list
- JSON: Complete structured data

Cell line sensitivities are optional (large data).
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_targets_for_drug` / `get_targets_for_drugs`
- `get_indications_for_drug`
- `get_side_effects_for_drug`
- `get_drugs_for_side_effect`
- `get_trials_for_drug`
- `get_sensitive_cell_lines_for_drug`
- `is_drug_target`
- `drug_has_indication`
- `is_side_effect_for_drug`
- Plus related check/list endpoints

---

## 5. cogex_query_disease_or_phenotype

**Purpose**: Bidirectional queries between diseases and phenotypes/mechanisms

**Modes**: 3 (disease_to_mechanisms, phenotype_to_diseases, check_phenotype)

**Coverage**: 9 endpoints

### Input Schema

```python
class DiseaseQueryMode(str, Enum):
    DISEASE_TO_MECHANISMS = "disease_to_mechanisms"
    PHENOTYPE_TO_DISEASES = "phenotype_to_diseases"
    CHECK_PHENOTYPE = "check_phenotype"

class DiseasePhenotypeQuery(BaseModel):
    mode: DiseaseQueryMode

    # Entity (depends on mode)
    disease: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None

    # Options (for disease_to_mechanisms)
    include_genes: bool = True
    include_variants: bool = True
    include_phenotypes: bool = True
    include_drugs: bool = True
    include_trials: bool = True

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class DiseaseMechanismsResponse(BaseModel):
    # For disease_to_mechanisms
    disease: Optional[DiseaseNode]
    genes: Optional[List[GeneAssociation]]
    variants: Optional[List[VariantAssociation]]
    phenotypes: Optional[List[PhenotypeAssociation]]
    drugs: Optional[List[DrugTherapy]]
    trials: Optional[List[ClinicalTrial]]

    # For phenotype_to_diseases
    diseases: Optional[List[DiseaseNode]]

    # For check_phenotype
    has_phenotype: Optional[bool]

    # Pagination (if diseases list)
    pagination: Optional[PaginatedResponse]
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_genes_for_disease`
- `get_diseases_for_phenotype`
- `get_phenotypes_for_disease`
- `get_variants_for_disease`
- `get_drugs_for_indication`
- `get_trials_for_disease`
- `has_phenotype`
- Plus related association checks

---

## 6. cogex_query_pathway

**Purpose**: Pathway membership queries and shared pathway analysis

**Modes**: 4 (get_genes, get_pathways, find_shared, check_membership)

**Coverage**: 4 endpoints

### Input Schema

```python
class PathwayQueryMode(str, Enum):
    GET_GENES = "get_genes"
    GET_PATHWAYS = "get_pathways"
    FIND_SHARED = "find_shared"
    CHECK_MEMBERSHIP = "check_membership"

class PathwayQuery(BaseModel):
    mode: PathwayQueryMode

    # For get_genes, check_membership
    pathway: Optional[str | Tuple[str, str]] = None

    # For get_pathways
    gene: Optional[str | Tuple[str, str]] = None

    # For find_shared
    genes: Optional[List[str]] = None

    # Filters
    pathway_source: Optional[str] = None  # "reactome", "wikipathways"

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class PathwayQueryResponse(BaseModel):
    # For get_genes
    pathway: Optional[PathwayNode]
    genes: Optional[List[GeneNode]]

    # For get_pathways, find_shared
    pathways: Optional[List[PathwayNode]]

    # For check_membership
    is_member: Optional[bool]

    # Pagination
    pagination: Optional[PaginatedResponse]

class PathwayNode(BaseModel):
    name: str
    curie: str
    source: str  # "reactome", "wikipathways"
    description: Optional[str] = None
    gene_count: int
    url: Optional[str] = None
```

### Tool Description

```
Query pathway memberships and find shared pathways.

Modes:
- get_genes: Pathway → genes in pathway
- get_pathways: Gene → pathways containing gene
- find_shared: Genes → pathways containing all genes
- check_membership: Check if gene is in pathway

Use when:
- "What genes are in the MAPK signaling pathway?"
- "What pathways contain TP53?"
- "Shared pathways for these genes?"

Returns:
- Markdown: Pathway/gene lists with source info
- JSON: Complete pathway metadata

Supports filtering by pathway source (Reactome, WikiPathways).
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_genes_in_pathway`
- `get_pathways_for_gene`
- `get_shared_pathways_for_genes`
- `is_gene_in_pathway`

---

## 7. cogex_query_cell_line

**Purpose**: CCLE/DepMap cell line data and mutation profiles

**Modes**: 4 (get_properties, get_mutated_genes, get_cell_lines_with_mutation, check_mutation)

**Coverage**: 8 endpoints

### Input Schema

```python
class CellLineQueryMode(str, Enum):
    GET_PROPERTIES = "get_properties"
    GET_MUTATED_GENES = "get_mutated_genes"
    GET_CELL_LINES_WITH_MUTATION = "get_cell_lines_with_mutation"
    CHECK_MUTATION = "check_mutation"

class CellLineQuery(BaseModel):
    mode: CellLineQueryMode

    # For get_properties, get_mutated_genes, check_mutation
    cell_line: Optional[str] = None

    # For get_cell_lines_with_mutation, check_mutation
    gene: Optional[str | Tuple[str, str]] = None

    # Options
    include_mutations: bool = True
    include_copy_number: bool = True
    include_dependencies: bool = False
    include_expression: bool = False

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class CellLineResponse(BaseModel):
    # For get_properties
    cell_line: Optional[CellLineNode]
    mutations: Optional[List[GeneMutation]]
    copy_number_alterations: Optional[List[CopyNumberEvent]]
    dependencies: Optional[List[GeneDependency]]
    expression: Optional[List[GeneExpression]]

    # For get_mutated_genes
    genes: Optional[List[GeneNode]]

    # For get_cell_lines_with_mutation
    cell_lines: Optional[List[CellLineNode]]

    # For check_mutation
    has_mutation: Optional[bool]

    # Pagination
    pagination: Optional[PaginatedResponse]

class CellLineNode(BaseModel):
    name: str
    ccle_id: str
    depmap_id: str
    tissue: Optional[str] = None
    disease: Optional[str] = None

class GeneMutation(BaseModel):
    gene: EntityRef
    mutation_type: str  # "missense", "nonsense", etc.
    protein_change: Optional[str] = None
    is_driver: bool

class GeneDependency(BaseModel):
    gene: EntityRef
    dependency_score: float
    """Lower = more essential"""
```

### Tool Description

```
Access Cancer Cell Line Encyclopedia (CCLE) and DepMap data.

Modes:
- get_properties: Cell line → mutations, CNAs, dependencies
- get_mutated_genes: Cell line → mutated genes
- get_cell_lines_with_mutation: Gene → cell lines with mutation
- check_mutation: Check if gene is mutated in cell line

Use when:
- "What mutations does A549 have?"
- "Cell lines with KRAS mutations?"
- "Essential genes in HeLa cells?"

Returns:
- Markdown: Cell line profiles or gene lists
- JSON: Complete mutation/dependency data

Dependencies and expression are optional (large datasets).
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_mutations_for_cell_line`
- `get_cell_lines_for_mutation`
- `is_mutated_in_cell_line`
- `get_copy_number_for_cell_line`
- `get_dependencies_for_cell_line`
- `get_expression_for_cell_line`
- Plus related endpoints

---

## 8. cogex_query_clinical_trials

**Purpose**: ClinicalTrials.gov data for drugs and diseases

**Modes**: 3 (get_for_drug, get_for_disease, get_by_id)

**Coverage**: 4 endpoints

### Input Schema

```python
class ClinicalTrialsMode(str, Enum):
    GET_FOR_DRUG = "get_for_drug"
    GET_FOR_DISEASE = "get_for_disease"
    GET_BY_ID = "get_by_id"

class ClinicalTrialsQuery(BaseModel):
    mode: ClinicalTrialsMode

    # Entity (depends on mode)
    drug: Optional[str | Tuple[str, str]] = None
    disease: Optional[str | Tuple[str, str]] = None
    trial_id: Optional[str] = None  # NCT ID

    # Filters
    phase: Optional[List[int]] = None  # [1, 2, 3, 4]
    status: Optional[str] = None  # "recruiting", "completed", etc.

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class ClinicalTrialsResponse(BaseModel):
    trials: List[ClinicalTrial]
    pagination: PaginatedResponse

class ClinicalTrial(BaseModel):
    nct_id: str
    title: str
    phase: Optional[int] = None
    status: str
    conditions: List[str]
    interventions: List[str]
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    enrollment: Optional[int] = None
    sponsor: Optional[str] = None
    url: str
```

### Tool Description

```
Access ClinicalTrials.gov data for drugs and diseases.

Modes:
- get_for_drug: Drug → clinical trials
- get_for_disease: Disease → clinical trials
- get_by_id: Retrieve trial by NCT ID

Filters:
- phase: Filter by trial phase (1, 2, 3, 4)
- status: Filter by recruitment status

Use when:
- "Clinical trials for pembrolizumab?"
- "Active trials for Alzheimer's disease?"
- "Details for NCT12345678?"

Returns:
- Markdown: Trial summaries with key info
- JSON: Complete trial metadata

NCT IDs link to ClinicalTrials.gov.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_trials_for_drug`
- `get_trials_for_disease`
- `get_trial_by_id`
- `search_trials`

---

## 9. cogex_query_literature

**Purpose**: PubMed literature and INDRA statement evidence

**Modes**: 4 (get_statements_for_pmid, get_evidence_for_statement, search_by_mesh, get_statements_by_hashes)

**Coverage**: 13 endpoints

### Input Schema

```python
class LiteratureQueryMode(str, Enum):
    GET_STATEMENTS_FOR_PMID = "get_statements_for_pmid"
    GET_EVIDENCE_FOR_STATEMENT = "get_evidence_for_statement"
    SEARCH_BY_MESH = "search_by_mesh"
    GET_STATEMENTS_BY_HASHES = "get_statements_by_hashes"

class LiteratureQuery(BaseModel):
    mode: LiteratureQueryMode

    # For get_statements_for_pmid
    pmid: Optional[str] = None

    # For get_evidence_for_statement
    statement_hash: Optional[str] = None

    # For search_by_mesh
    mesh_terms: Optional[List[str]] = None

    # For get_statements_by_hashes
    statement_hashes: Optional[List[str]] = None

    # Options
    include_evidence_text: bool = True
    max_evidence_per_statement: int = Field(default=5, le=20)

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class LiteratureResponse(BaseModel):
    # For get_statements_for_pmid, get_statements_by_hashes
    statements: Optional[List[IndraStatement]]

    # For get_evidence_for_statement
    evidence: Optional[List[Evidence]]

    # For search_by_mesh
    publications: Optional[List[Publication]]

    # Pagination
    pagination: Optional[PaginatedResponse]

class Publication(BaseModel):
    pmid: str
    title: str
    authors: List[str]
    journal: str
    year: int
    abstract: Optional[str] = None
    mesh_terms: List[str]
    url: str
```

### Tool Description

```
Access PubMed literature and INDRA statement evidence.

Modes:
- get_statements_for_pmid: PMID → INDRA statements
- get_evidence_for_statement: Statement hash → evidence texts
- search_by_mesh: MeSH terms → publications
- get_statements_by_hashes: Batch retrieve statements

Use when:
- "What statements come from PMID 12345678?"
- "Evidence for this phosphorylation?"
- "Papers about 'autophagy' and 'cancer'?"

Returns:
- Markdown: Statements with evidence snippets
- JSON: Complete statement/evidence data

Evidence text inclusion is optional.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_statements_for_paper`
- `get_evidence_for_mesh`
- `get_evidences_for_stmt_hash`
- `get_stmts_for_stmt_hashes`
- Plus related literature endpoints (13 total)

---

## 10. cogex_query_variants

**Purpose**: Genetic variants from GWAS and disease associations

**Modes**: 6 (get_for_gene, get_for_disease, get_for_phenotype, variant_to_genes, variant_to_phenotypes, check_association)

**Coverage**: 7 endpoints

### Input Schema

```python
class VariantQueryMode(str, Enum):
    GET_FOR_GENE = "get_for_gene"
    GET_FOR_DISEASE = "get_for_disease"
    GET_FOR_PHENOTYPE = "get_for_phenotype"
    VARIANT_TO_GENES = "variant_to_genes"
    VARIANT_TO_PHENOTYPES = "variant_to_phenotypes"
    CHECK_ASSOCIATION = "check_association"

class VariantQuery(BaseModel):
    mode: VariantQueryMode

    # Entity (depends on mode)
    gene: Optional[str | Tuple[str, str]] = None
    disease: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None
    variant: Optional[str] = None  # rsID

    # Filters
    min_p_value: Optional[float] = None
    max_p_value: float = Field(default=1e-5, le=1.0)
    source: Optional[str] = None  # "gwas_catalog", "disgenet"

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class VariantResponse(BaseModel):
    # For get_for_* modes
    variants: Optional[List[VariantNode]]

    # For variant_to_genes
    genes: Optional[List[GeneNode]]

    # For variant_to_phenotypes
    phenotypes: Optional[List[PhenotypeNode]]

    # For check_association
    is_associated: Optional[bool]
    association_strength: Optional[float] = None

    # Pagination
    pagination: Optional[PaginatedResponse]

class VariantNode(BaseModel):
    rsid: str
    chromosome: str
    position: int
    ref_allele: str
    alt_allele: str
    p_value: float
    odds_ratio: Optional[float] = None
    trait: str
    study: str
    source: str
```

### Tool Description

```
Query genetic variants from GWAS Catalog and DisGeNet.

Modes:
- get_for_gene: Gene → variants in/near gene
- get_for_disease: Disease → associated variants
- get_for_phenotype: Phenotype → GWAS hits
- variant_to_genes: Variant (rsID) → nearby genes
- variant_to_phenotypes: Variant → associated phenotypes
- check_association: Check variant-disease association

Use when:
- "GWAS hits for APOE?"
- "Variants associated with Alzheimer's?"
- "What genes are near rs7412?"

Returns:
- Markdown: Variant table with p-values, traits
- JSON: Complete GWAS data

Supports p-value filtering (default: < 1e-5).
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_variants_for_gene`
- `get_variants_for_disease`
- `get_variants_for_phenotype`
- `get_genes_for_variant`
- `get_phenotypes_for_variant`
- `is_variant_associated`
- Plus related endpoints

---

## 11. cogex_resolve_identifiers

**Purpose**: Identifier conversion between namespaces

**Modes**: Flexible namespace mapping

**Coverage**: 3 endpoints

### Input Schema

```python
class IdentifierQuery(BaseModel):
    identifiers: List[str]
    """List of identifiers to convert"""

    from_namespace: str
    """Source namespace: hgnc, hgnc.symbol, uniprot, etc."""

    to_namespace: str
    """Target namespace: hgnc, hgnc.symbol, uniprot, etc."""

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class IdentifierResponse(BaseModel):
    mappings: List[IdentifierMapping]
    unmapped: List[str]
    """Identifiers that couldn't be mapped"""

class IdentifierMapping(BaseModel):
    source_id: str
    target_ids: List[str]
    """Multiple targets possible for 1:many mappings"""
    confidence: Optional[str] = None
```

### Tool Description

```
Convert identifiers between namespaces (HGNC, UniProt, etc.).

Common conversions:
- hgnc.symbol ↔ hgnc (gene symbol ↔ HGNC ID)
- hgnc ↔ uniprot (HGNC ID ↔ UniProt ID)
- ensembl ↔ hgnc (Ensembl gene ↔ HGNC ID)

Use when:
- "Convert TP53 to HGNC ID"
- "Get UniProt IDs for these HGNC IDs"
- "Map gene symbols to Ensembl"

Returns:
- Markdown: Table of mappings
- JSON: Structured mapping list

Returns unmapped IDs separately.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,  # Uses internal mappings
}
```

### Backend Endpoints

- `map_identifiers`
- `hgnc_to_uniprot`
- `symbol_to_hgnc`

---

## 12. cogex_check_relationship

**Purpose**: Boolean validators for entity relationships

**Modes**: 10 relationship types

**Coverage**: 15 endpoints

### Input Schema

```python
class RelationshipType(str, Enum):
    GENE_IN_PATHWAY = "gene_in_pathway"
    DRUG_TARGET = "drug_target"
    DRUG_INDICATION = "drug_indication"
    DRUG_SIDE_EFFECT = "drug_side_effect"
    GENE_DISEASE = "gene_disease"
    DISEASE_PHENOTYPE = "disease_phenotype"
    GENE_PHENOTYPE = "gene_phenotype"
    VARIANT_ASSOCIATION = "variant_association"
    CELL_LINE_MUTATION = "cell_line_mutation"
    CELL_MARKER = "cell_marker"

class RelationshipQuery(BaseModel):
    relationship_type: RelationshipType

    entity1: str | Tuple[str, str]
    """First entity (gene/drug/disease/etc.)"""

    entity2: str | Tuple[str, str]
    """Second entity (pathway/target/phenotype/etc.)"""

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class RelationshipResponse(BaseModel):
    exists: bool
    metadata: Optional[RelationshipMetadata] = None

class RelationshipMetadata(BaseModel):
    """Type-specific metadata"""
    confidence: Optional[float] = None
    evidence_count: Optional[int] = None
    sources: Optional[List[str]] = None
    additional_info: Optional[Dict[str, Any]] = None
```

### Tool Description

```
Check existence of specific relationships between entities.

Relationship types:
- gene_in_pathway: Is gene in pathway?
- drug_target: Does drug target gene/protein?
- drug_indication: Is drug indicated for disease?
- drug_side_effect: Does drug cause side effect?
- gene_disease: Is gene associated with disease?
- disease_phenotype: Does disease have phenotype?
- gene_phenotype: Is gene associated with phenotype?
- variant_association: Is variant associated with trait?
- cell_line_mutation: Does cell line have mutation?
- cell_marker: Is gene a marker for cell type?

Use when:
- "Is TP53 in the p53 pathway?"
- "Does imatinib target BCR-ABL?"
- Quick validation checks

Returns:
- Markdown: Boolean + metadata summary
- JSON: Structured result with evidence

More efficient than full queries for yes/no questions.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

All `is_*` and `has_*` endpoints (15 total)

---

## 13. cogex_get_ontology_hierarchy

**Purpose**: Navigate ontology parent/child relationships

**Modes**: 3 (parents, children, both)

**Coverage**: 3 endpoints

### Input Schema

```python
class HierarchyDirection(str, Enum):
    PARENTS = "parents"
    CHILDREN = "children"
    BOTH = "both"

class OntologyHierarchyQuery(BaseModel):
    term: str | Tuple[str, str]
    """Ontology term (GO, HPO, MONDO, etc.)"""

    direction: HierarchyDirection

    max_depth: int = Field(default=2, ge=1, le=5)
    """Maximum levels to traverse"""

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class OntologyHierarchyResponse(BaseModel):
    root_term: OntologyTerm
    parents: Optional[List[OntologyTerm]] = None
    children: Optional[List[OntologyTerm]] = None
    hierarchy_tree: Optional[str] = None
    """ASCII tree visualization (Markdown only)"""

class OntologyTerm(BaseModel):
    name: str
    curie: str
    namespace: str
    definition: Optional[str] = None
    depth: int
    """Distance from root term"""
    relationship: Optional[str] = None
    """is_a, part_of, etc."""
```

### Tool Description

```
Navigate ontology hierarchies (GO, HPO, MONDO, etc.).

Directions:
- parents: Get parent/ancestor terms
- children: Get child/descendant terms
- both: Get both parents and children

Use when:
- "What are the parent terms of GO:0006915?"
- "Show me the apoptosis hierarchy"
- "Child terms of 'cellular process'"

Returns:
- Markdown: ASCII tree visualization
- JSON: Structured hierarchy with depths

Max depth prevents excessive traversal.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,  # Internal ontology data
}
```

### Backend Endpoints

- `get_ontology_parents`
- `get_ontology_children`
- `get_ontology_hierarchy`

---

## 14. cogex_query_cell_markers

**Purpose**: CellMarker database queries for cell type markers

**Modes**: 3 (get_markers, get_cell_types, check_marker)

**Coverage**: 3 endpoints

### Input Schema

```python
class CellMarkerMode(str, Enum):
    GET_MARKERS = "get_markers"
    GET_CELL_TYPES = "get_cell_types"
    CHECK_MARKER = "check_marker"

class CellMarkerQuery(BaseModel):
    mode: CellMarkerMode

    # Entity (depends on mode)
    cell_type: Optional[str] = None
    marker: Optional[str | Tuple[str, str]] = None

    # Filters
    tissue: Optional[str] = None
    species: str = "human"

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class CellMarkerResponse(BaseModel):
    # For get_markers
    markers: Optional[List[CellMarker]]

    # For get_cell_types
    cell_types: Optional[List[CellTypeNode]]

    # For check_marker
    is_marker: Optional[bool]

    # Pagination
    pagination: Optional[PaginatedResponse]

class CellMarker(BaseModel):
    gene: EntityRef
    marker_type: str  # "canonical", "putative"
    evidence: str

class CellTypeNode(BaseModel):
    name: str
    tissue: str
    species: str
    marker_count: int
```

### Tool Description

```
Query CellMarker database for cell type markers.

Modes:
- get_markers: Cell type → marker genes
- get_cell_types: Marker gene → cell types
- check_marker: Is gene a marker for cell type?

Use when:
- "What are markers for T cells?"
- "What cell types express CD4?"
- "Is CD8A a T cell marker?"

Returns:
- Markdown: Marker/cell type lists
- JSON: Complete marker metadata

Supports tissue and species filtering.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_markers_for_cell_type`
- `get_cell_types_for_marker`
- `is_cell_marker`

---

## 15. cogex_analyze_kinase_enrichment

**Purpose**: Kinase enrichment from phosphoproteomics data

**Modes**: 1 (enrichment analysis)

**Coverage**: 1 endpoint

### Input Schema

```python
class KinaseEnrichmentQuery(BaseModel):
    phosphosites: List[str]
    """List of phosphosites (format: 'GENE_S123' or 'GENE_T456')"""

    background: Optional[List[str]] = None
    """Optional background phosphosites for normalization"""

    # Analysis parameters
    alpha: float = Field(default=0.05, gt=0, le=1)
    correction_method: str = "fdr_bh"

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

### Output Schema

```python
class KinaseEnrichmentResponse(BaseModel):
    results: List[KinaseEnrichmentResult]
    statistics: EnrichmentStatistics

class KinaseEnrichmentResult(BaseModel):
    kinase: EntityRef
    p_value: float
    adjusted_p_value: float
    substrate_count: int
    """Number of input phosphosites predicted for this kinase"""
    total_substrates: int
    """Total known substrates for this kinase"""
    phosphosites: List[str]
    """Input phosphosites attributed to this kinase"""
    prediction_confidence: str
    """high, medium, low"""
```

### Tool Description

```
Predict upstream kinases from phosphoproteomics data.

Use when:
- "What kinases phosphorylate these sites?"
- "Kinase enrichment from mass spec data"
- "Predict upstream kinases for phosphopeptides"

Input format:
- GENE_S123 (serine 123)
- GENE_T456 (threonine 456)
- GENE_Y789 (tyrosine 789)

Returns:
- Markdown: Ranked kinase table with p-values
- JSON: Complete enrichment results

Uses PhosphoSitePlus and other kinase databases.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": False,  # Statistical computation
    "openWorldHint": True,
}
```

### Backend Endpoints

- `/api/kinase_analysis`

---

## 16. cogex_query_protein_functions

**Purpose**: Enzyme activities and protein function classifications

**Modes**: 4 (gene_to_activities, activity_to_genes, check_activity, check_function_types)

**Coverage**: 6 endpoints

### Input Schema

```python
class ProteinFunctionMode(str, Enum):
    GENE_TO_ACTIVITIES = "gene_to_activities"
    ACTIVITY_TO_GENES = "activity_to_genes"
    CHECK_ACTIVITY = "check_activity"
    CHECK_FUNCTION_TYPES = "check_function_types"

class ProteinFunctionQuery(BaseModel):
    mode: ProteinFunctionMode

    # Entity (depends on mode)
    gene: Optional[str | Tuple[str, str]] = None
    genes: Optional[List[str]] = None  # For batch check_function_types
    enzyme_activity: Optional[str] = None

    # For check_function_types
    function_types: Optional[List[str]] = None
    """Options: kinase, phosphatase, transcription_factor"""

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
```

### Output Schema

```python
class ProteinFunctionResponse(BaseModel):
    # For gene_to_activities
    activities: Optional[List[EnzymeActivity]]

    # For activity_to_genes
    genes: Optional[List[GeneNode]]

    # For check_activity
    has_activity: Optional[bool]

    # For check_function_types
    function_checks: Optional[Dict[str, bool]]
    """function_type → boolean"""

    # Pagination
    pagination: Optional[PaginatedResponse]

class EnzymeActivity(BaseModel):
    activity: str
    ec_number: Optional[str] = None
    confidence: str
    evidence_sources: List[str]
```

### Tool Description

```
Query enzyme activities and protein function types.

Modes:
- gene_to_activities: Gene → enzyme activities
- activity_to_genes: Activity → genes with that activity
- check_activity: Does gene have specific activity?
- check_function_types: Batch check kinase/phosphatase/TF

Function types:
- kinase: Is this gene a kinase?
- phosphatase: Is this gene a phosphatase?
- transcription_factor: Is this gene a TF?

Use when:
- "What enzyme activities does EGFR have?"
- "All kinases in this gene list?"
- "Is TP53 a transcription factor?"

Returns:
- Markdown: Activity lists or function classifications
- JSON: Complete enzyme data

Batch mode efficient for large gene lists.
```

### Annotations

```python
{
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### Backend Endpoints

- `get_enzyme_activities`
- `get_genes_for_activity`
- `is_kinase`
- `is_phosphatase`
- `is_transcription_factor`
- Plus related endpoints

---

## Implementation Checklist Per Tool

For each tool, ensure:

- [ ] Input schema with all required fields
- [ ] Response format parameter (MARKDOWN/JSON)
- [ ] Pagination parameters (limit/offset) where applicable
- [ ] Tool annotations (readOnlyHint, destructiveHint, etc.)
- [ ] Output schema for both formats
- [ ] CHARACTER_LIMIT check and truncation
- [ ] Error handling with actionable messages
- [ ] Unit tests (happy path, errors, pagination)
- [ ] Integration test (live backend)
- [ ] Documentation with examples

---

**This catalog provides complete, copy-paste-ready schemas for all 16 tools. Use as reference during implementation.**
