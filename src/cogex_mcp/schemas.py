"""
Pydantic schemas for all data structures.

Includes input schemas for tools and output schemas for responses.
All schemas are MCP-compliant with proper validation.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cogex_mcp.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    ResponseFormat,
)

# ============================================================================
# Base Models
# ============================================================================


class BaseToolInput(BaseModel):
    """Base class for all tool input schemas."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",  # Reject unknown fields
    )

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' (human-readable) or 'json' (machine-readable)",
    )


class PaginatedToolInput(BaseToolInput):
    """Base class for tools that support pagination."""

    limit: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=MIN_PAGE_SIZE,
        le=MAX_PAGE_SIZE,
        description=f"Maximum results to return ({MIN_PAGE_SIZE}-{MAX_PAGE_SIZE})",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    )


# ============================================================================
# Common Entity Types
# ============================================================================


class EntityRef(BaseModel):
    """Reference to a biomedical entity."""

    name: str = Field(..., description="Human-readable name")
    curie: str = Field(..., description="Compact URI (namespace:identifier)")
    namespace: str = Field(..., description="Identifier namespace (e.g., 'hgnc', 'chembl')")
    identifier: str = Field(..., description="Entity identifier")


class GeneNode(BaseModel):
    """Gene entity with metadata."""

    name: str = Field(..., description="Gene symbol (e.g., 'TP53')")
    curie: str = Field(..., description="CURIE (e.g., 'hgnc:11998')")
    namespace: str = Field(default="hgnc", description="Namespace")
    identifier: str = Field(..., description="Identifier")
    description: str | None = Field(None, description="Gene description")
    synonyms: list[str] = Field(default_factory=list, description="Alternative gene symbols")


class DrugNode(BaseModel):
    """Drug entity with metadata."""

    name: str = Field(..., description="Drug name")
    curie: str = Field(..., description="CURIE (e.g., 'chembl:CHEMBL1')")
    namespace: str = Field(default="chembl", description="Namespace")
    identifier: str = Field(..., description="Identifier")
    synonyms: list[str] = Field(default_factory=list, description="Alternative names")
    drug_type: str | None = Field(None, description="Drug type (small molecule, antibody, etc.)")


class DiseaseNode(BaseModel):
    """Disease entity with metadata."""

    name: str = Field(..., description="Disease name")
    curie: str = Field(..., description="CURIE")
    namespace: str = Field(default="mondo", description="Namespace")
    identifier: str = Field(..., description="Identifier")
    description: str | None = Field(None, description="Disease description")


class PathwayNode(BaseModel):
    """Pathway entity with metadata."""

    name: str = Field(..., description="Pathway name")
    curie: str = Field(..., description="CURIE")
    source: str = Field(..., description="Source database (reactome, wikipathways)")
    description: str | None = Field(None, description="Pathway description")
    gene_count: int = Field(..., description="Number of genes in pathway")
    url: str | None = Field(None, description="External URL")


# ============================================================================
# Pagination Response
# ============================================================================


class PaginatedResponse(BaseModel):
    """Standard pagination metadata."""

    total_count: int = Field(..., description="Total number of results")
    count: int = Field(..., description="Number of results in this response")
    offset: int = Field(..., description="Current pagination offset")
    limit: int = Field(..., description="Maximum results requested")
    has_more: bool = Field(..., description="Whether more results available")
    next_offset: int | None = Field(None, description="Offset for next page (if has_more)")


# ============================================================================
# Tool 1: Gene/Feature Query Schemas
# ============================================================================


class QueryMode(str, Enum):
    """Query direction modes for gene/feature queries."""

    GENE_TO_FEATURES = "gene_to_features"
    TISSUE_TO_GENES = "tissue_to_genes"
    GO_TO_GENES = "go_to_genes"
    DOMAIN_TO_GENES = "domain_to_genes"
    PHENOTYPE_TO_GENES = "phenotype_to_genes"


class GeneFeatureQuery(PaginatedToolInput):
    """
    Input for cogex_query_gene_or_feature tool.

    Supports bidirectional queries between genes and their features.
    """

    mode: QueryMode = Field(..., description="Query direction mode")

    # Entity fields (depends on mode)
    gene: str | tuple[str, str] | None = Field(
        None,
        description="Gene symbol or (namespace, id) tuple (e.g., 'TP53' or ('hgnc', '11998'))",
    )
    tissue: str | tuple[str, str] | None = Field(
        None,
        description="Tissue name or CURIE",
    )
    go_term: str | tuple[str, str] | None = Field(
        None,
        description="GO term name or CURIE (e.g., 'GO:0006915' or 'apoptosis')",
    )
    domain: str | tuple[str, str] | None = Field(
        None,
        description="Protein domain name or identifier",
    )
    phenotype: str | tuple[str, str] | None = Field(
        None,
        description="Phenotype term or CURIE",
    )

    # Options for gene_to_features mode
    include_expression: bool = Field(
        True,
        description="Include tissue expression data",
    )
    include_go_terms: bool = Field(
        True,
        description="Include Gene Ontology annotations",
    )
    include_pathways: bool = Field(
        True,
        description="Include pathway memberships",
    )
    include_diseases: bool = Field(
        True,
        description="Include disease associations",
    )
    include_domains: bool = Field(
        False,
        description="Include protein domains",
    )
    include_variants: bool = Field(
        False,
        description="Include genetic variants",
    )
    include_phenotypes: bool = Field(
        False,
        description="Include phenotype associations",
    )
    include_codependencies: bool = Field(
        False,
        description="Include gene codependencies (CRISPR screens)",
    )

    @field_validator("gene", "tissue", "go_term", "domain", "phenotype")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class ExpressionData(BaseModel):
    """Gene expression in specific tissue."""

    tissue: EntityRef
    confidence: str = Field(..., description="Evidence confidence: gold, silver, bronze")
    evidence_count: int = Field(..., description="Number of supporting evidences")


class GOAnnotation(BaseModel):
    """Gene Ontology annotation."""

    go_term: EntityRef
    aspect: str = Field(
        ...,
        description="GO aspect: biological_process, molecular_function, cellular_component",
    )
    evidence_code: str = Field(..., description="Evidence code (e.g., 'IDA', 'IEA')")


class PathwayMembership(BaseModel):
    """Pathway membership information."""

    pathway: EntityRef
    source: str = Field(..., description="Source database (reactome, wikipathways)")


class DiseaseAssociation(BaseModel):
    """Gene-disease association."""

    disease: EntityRef
    score: float = Field(..., ge=0.0, le=1.0, description="Association score (0-1)")
    evidence_count: int = Field(..., description="Number of supporting evidences")
    sources: list[str] = Field(..., description="Source databases")


class ProteinDomain(BaseModel):
    """Protein domain information."""

    domain: EntityRef
    start: int | None = Field(None, description="Domain start position")
    end: int | None = Field(None, description="Domain end position")


class GeneticVariant(BaseModel):
    """Genetic variant information."""

    rsid: str = Field(..., description="dbSNP rsID (e.g., 'rs7412')")
    chromosome: str = Field(..., description="Chromosome")
    position: int = Field(..., description="Genomic position")
    ref_allele: str = Field(..., description="Reference allele")
    alt_allele: str = Field(..., description="Alternate allele")
    p_value: float | None = Field(None, description="GWAS p-value")
    trait: str | None = Field(None, description="Associated trait/disease")


class PhenotypeAssociation(BaseModel):
    """Gene-phenotype association."""

    phenotype: EntityRef
    frequency: str | None = Field(None, description="Phenotype frequency")
    evidence_count: int = Field(..., description="Number of supporting evidences")


class GeneCodependent(BaseModel):
    """Gene codependency from CRISPR screens."""

    gene: EntityRef
    correlation: float = Field(..., ge=-1.0, le=1.0, description="Correlation coefficient")
    source: str = Field(..., description="Source (e.g., 'depmap')")


# ============================================================================
# Tool 2: Subnetwork Extraction Schemas
# ============================================================================


class SubnetworkMode(str, Enum):
    """Modes for subnetwork extraction."""

    DIRECT = "direct"  # Direct edges A→B
    MEDIATED = "mediated"  # Two-hop paths A→X→B
    SHARED_UPSTREAM = "shared_upstream"  # Shared regulators A←X→B
    SHARED_DOWNSTREAM = "shared_downstream"  # Shared targets A→X←B
    SOURCE_TO_TARGETS = "source_to_targets"  # One source → multiple targets


class SubnetworkQuery(BaseToolInput):
    """Input for cogex_extract_subnetwork tool."""

    mode: SubnetworkMode = Field(..., description="Subnetwork extraction mode")

    # Entity specification
    genes: list[str] | None = Field(
        None,
        description="List of gene symbols or CURIEs",
    )
    source_gene: str | None = Field(
        None,
        description="Source gene for source_to_targets mode",
    )
    target_genes: list[str] | None = Field(
        None,
        description="Target genes for source_to_targets mode",
    )

    # Filters
    tissue_filter: str | None = Field(
        None,
        description="Restrict to genes expressed in tissue",
    )
    go_filter: str | None = Field(
        None,
        description="Restrict to genes with GO term",
    )

    # Evidence options
    include_evidence: bool = Field(
        False,
        description="Include evidence text (increases response size)",
    )
    max_evidence_per_statement: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum evidence per statement",
    )

    # Statement filters
    statement_types: list[str] | None = Field(
        None,
        description="Filter by statement types (e.g., ['Phosphorylation', 'Activation'])",
    )
    min_evidence_count: int = Field(
        default=1,
        ge=1,
        description="Minimum evidence count per statement",
    )
    min_belief_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum belief score (0-1)",
    )

    # Limits
    max_statements: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum statements to return",
    )


class IndraStatement(BaseModel):
    """INDRA mechanistic statement."""

    stmt_hash: str = Field(..., description="Unique statement hash")
    stmt_type: str = Field(..., description="Statement type (e.g., 'Phosphorylation')")
    subject: EntityRef = Field(..., description="Subject entity")
    object: EntityRef = Field(..., description="Object entity")
    residue: str | None = Field(None, description="Modified residue (for PTMs)")
    position: str | None = Field(None, description="Position (for PTMs)")
    evidence_count: int = Field(..., description="Number of evidences")
    belief_score: float = Field(..., ge=0.0, le=1.0, description="Belief score (0-1)")
    sources: list[str] = Field(..., description="Source databases")
    evidence: list[dict[str, Any]] | None = Field(
        None,
        description="Evidence snippets (if include_evidence=True)",
    )


class NetworkStatistics(BaseModel):
    """Network-level statistics."""

    node_count: int = Field(..., description="Number of nodes")
    edge_count: int = Field(..., description="Number of edges")
    statement_types: dict[str, int] = Field(..., description="Counts by statement type")
    avg_evidence_per_statement: float = Field(..., description="Average evidence count")
    avg_belief_score: float = Field(..., description="Average belief score")


# ============================================================================
# Tool 3: Enrichment Analysis Schemas
# ============================================================================


class EnrichmentType(str, Enum):
    """Enrichment analysis types."""

    DISCRETE = "discrete"  # Overrepresentation (Fisher's exact)
    CONTINUOUS = "continuous"  # GSEA with ranked list
    SIGNED = "signed"  # Directional enrichment
    METABOLITE = "metabolite"  # Metabolite set enrichment


class EnrichmentSource(str, Enum):
    """Enrichment analysis sources."""

    GO = "go"
    REACTOME = "reactome"
    WIKIPATHWAYS = "wikipathways"
    INDRA_UPSTREAM = "indra-upstream"
    INDRA_DOWNSTREAM = "indra-downstream"
    PHENOTYPE = "phenotype"


class EnrichmentQuery(BaseToolInput):
    """Input for cogex_enrichment_analysis tool."""

    analysis_type: EnrichmentType = Field(..., description="Analysis type")

    # For discrete enrichment
    gene_list: list[str] | None = Field(
        None,
        description="List of genes for discrete analysis",
    )
    background_genes: list[str] | None = Field(
        None,
        description="Background gene set (optional)",
    )

    # For continuous/signed enrichment
    ranked_genes: dict[str, float] | None = Field(
        None,
        description="Gene → score mapping for continuous analysis (e.g., log fold change)",
    )

    # Analysis parameters
    source: EnrichmentSource = Field(
        default=EnrichmentSource.GO,
        description="Enrichment source database",
    )
    alpha: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description="Significance threshold",
    )
    correction_method: str = Field(
        default="fdr_bh",
        description="Multiple testing correction (fdr_bh, bonferroni)",
    )
    keep_insignificant: bool = Field(
        default=False,
        description="Include non-significant results",
    )

    # For INDRA sources
    min_evidence_count: int = Field(
        default=1,
        ge=1,
        description="Minimum evidence count (INDRA sources)",
    )
    min_belief_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum belief score (INDRA sources)",
    )

    # For continuous methods
    permutations: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Number of permutations for GSEA",
    )


class EnrichmentResult(BaseModel):
    """Single enrichment result."""

    term: EntityRef = Field(..., description="Enriched term")
    term_name: str = Field(..., description="Human-readable term name")
    p_value: float = Field(..., description="Raw p-value")
    adjusted_p_value: float = Field(..., description="Adjusted p-value")
    enrichment_score: float | None = Field(None, description="Enrichment score (GSEA)")
    normalized_enrichment_score: float | None = Field(
        None,
        description="Normalized enrichment score (GSEA)",
    )
    gene_count: int = Field(..., description="Genes in query overlapping term")
    term_size: int = Field(..., description="Total genes in term")
    genes: list[str] = Field(..., description="Overlapping genes")
    background_count: int | None = Field(None, description="Background gene count")


class EnrichmentStatistics(BaseModel):
    """Overall enrichment statistics."""

    total_results: int = Field(..., description="Total results tested")
    significant_results: int = Field(..., description="Significant results")
    total_genes_analyzed: int = Field(..., description="Genes in analysis")
    correction_method: str = Field(..., description="Correction method used")
    alpha: float = Field(..., description="Significance threshold")


# ============================================================================
# Tool 4: Drug/Effect Query Schemas
# ============================================================================


class DrugQueryMode(str, Enum):
    """Query modes for drug/effect queries."""

    DRUG_TO_PROFILE = "drug_to_profile"
    SIDE_EFFECT_TO_DRUGS = "side_effect_to_drugs"


class DrugEffectQuery(PaginatedToolInput):
    """Input for cogex_query_drug_or_effect tool."""

    mode: DrugQueryMode = Field(..., description="Query mode")

    # Entity fields
    drug: str | tuple[str, str] | None = Field(
        None,
        description="Drug name or (namespace, id) tuple (e.g., 'aspirin' or ('chembl', 'CHEMBL25'))",
    )
    side_effect: str | tuple[str, str] | None = Field(
        None,
        description="Side effect term or (namespace, id) tuple",
    )

    # Options for drug_to_profile
    include_targets: bool = Field(True, description="Include drug targets")
    include_indications: bool = Field(True, description="Include disease indications")
    include_side_effects: bool = Field(True, description="Include side effects")
    include_trials: bool = Field(True, description="Include clinical trials")
    include_cell_lines: bool = Field(False, description="Include cell line sensitivity data")

    @field_validator("drug", "side_effect")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class DrugTarget(BaseModel):
    """Drug target information."""

    target: EntityRef
    action_type: str | None = Field(None, description="Action type (INHIBITOR, AGONIST, etc.)")
    evidence_count: int = Field(..., description="Number of supporting evidences")


class DrugIndication(BaseModel):
    """Drug indication for disease."""

    disease: EntityRef
    indication_type: str = Field(..., description="Indication type")
    max_phase: int | None = Field(None, description="Max clinical trial phase (1-4)")


class SideEffect(BaseModel):
    """Drug side effect."""

    effect: EntityRef
    frequency: str | None = Field(None, description="Frequency category (common, rare, etc.)")


class ClinicalTrial(BaseModel):
    """Clinical trial information."""

    nct_id: str = Field(..., description="ClinicalTrials.gov NCT ID")
    title: str = Field(..., description="Trial title")
    phase: int | None = Field(None, description="Trial phase (1-4)")
    status: str = Field(..., description="Trial status (recruiting, completed, etc.)")
    conditions: list[str] = Field(default_factory=list, description="Conditions studied")
    interventions: list[str] = Field(default_factory=list, description="Interventions")
    url: str = Field(..., description="ClinicalTrials.gov URL")


class CellLineSensitivity(BaseModel):
    """Cell line sensitivity data."""

    cell_line: str = Field(..., description="Cell line name")
    sensitivity_score: float = Field(..., description="Sensitivity score (lower = more sensitive)")


# ============================================================================
# Tool 5: Disease/Phenotype Query Schemas
# ============================================================================


class DiseaseQueryMode(str, Enum):
    """Query modes for disease/phenotype queries."""

    DISEASE_TO_MECHANISMS = "disease_to_mechanisms"
    PHENOTYPE_TO_DISEASES = "phenotype_to_diseases"
    CHECK_PHENOTYPE = "check_phenotype"


class DiseasePhenotypeQuery(PaginatedToolInput):
    """Input for cogex_query_disease_or_phenotype tool."""

    mode: DiseaseQueryMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    disease: str | tuple[str, str] | None = Field(
        None,
        description="Disease name or CURIE (e.g., 'diabetes' or ('mondo', 'MONDO:0005015'))",
    )
    phenotype: str | tuple[str, str] | None = Field(
        None,
        description="Phenotype term or CURIE (e.g., 'HP:0001250' or 'seizures')",
    )

    # Options for disease_to_mechanisms mode
    include_genes: bool = Field(
        True,
        description="Include associated genes",
    )
    include_variants: bool = Field(
        True,
        description="Include genetic variants",
    )
    include_phenotypes: bool = Field(
        True,
        description="Include phenotypes",
    )
    include_drugs: bool = Field(
        True,
        description="Include drug therapies",
    )
    include_trials: bool = Field(
        True,
        description="Include clinical trials",
    )

    @field_validator("disease", "phenotype")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class GeneAssociation(BaseModel):
    """Gene-disease association."""

    gene: EntityRef
    score: float = Field(..., ge=0.0, le=1.0, description="Association score (0-1)")
    evidence_count: int = Field(..., description="Number of supporting evidences")
    sources: list[str] = Field(..., description="Source databases")


class VariantAssociation(BaseModel):
    """Variant-disease association."""

    variant: str = Field(..., description="Variant rsID (e.g., 'rs7412')")
    gene: EntityRef = Field(..., description="Gene containing variant")
    p_value: float | None = Field(None, description="GWAS p-value")
    odds_ratio: float | None = Field(None, description="Odds ratio")
    trait: str | None = Field(None, description="Associated trait/phenotype")


class DrugTherapy(BaseModel):
    """Drug therapy for disease."""

    drug: EntityRef
    indication_type: str = Field(..., description="Indication type")
    max_phase: int | None = Field(None, description="Maximum clinical trial phase (1-4)")
    status: str | None = Field(None, description="Development status")


# Note: ClinicalTrial schema is defined in Tool 4 section above
# Note: PhenotypeAssociation schema is defined in Tool 1 section above


# ============================================================================
# Tool 6: Pathway Query Schemas
# ============================================================================


class PathwayQueryMode(str, Enum):
    """Query modes for pathway queries."""

    GET_GENES = "get_genes"
    GET_PATHWAYS = "get_pathways"
    FIND_SHARED = "find_shared"
    CHECK_MEMBERSHIP = "check_membership"


class PathwayQuery(PaginatedToolInput):
    """Input for cogex_query_pathway tool."""

    mode: PathwayQueryMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    pathway: str | tuple[str, str] | None = Field(
        None,
        description="Pathway name or CURIE (e.g., 'MAPK signaling' or ('reactome', 'R-HSA-5683057'))",
    )
    gene: str | tuple[str, str] | None = Field(
        None,
        description="Gene symbol or CURIE",
    )
    genes: list[str] | None = Field(
        None,
        description="List of genes for find_shared mode",
    )

    # Filters
    pathway_source: str | None = Field(
        None,
        description="Filter by pathway source (reactome, wikipathways)",
    )

    @field_validator("pathway", "gene")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


# ============================================================================
# Tool 7: Cell Line Query Schemas
# ============================================================================


class CellLineQueryMode(str, Enum):
    """Query modes for cell line queries."""

    GET_PROPERTIES = "get_properties"
    GET_MUTATED_GENES = "get_mutated_genes"
    GET_CELL_LINES_WITH_MUTATION = "get_cell_lines_with_mutation"
    CHECK_MUTATION = "check_mutation"


class CellLineQuery(PaginatedToolInput):
    """Input for cogex_query_cell_line tool."""

    mode: CellLineQueryMode = Field(..., description="Query mode")

    # Entity fields
    cell_line: str | None = Field(
        None,
        description="Cell line name (e.g., 'A549', 'HeLa')",
    )
    gene: str | tuple[str, str] | None = Field(
        None,
        description="Gene symbol or CURIE",
    )

    # Options for get_properties
    include_mutations: bool = Field(True, description="Include mutation data")
    include_copy_number: bool = Field(True, description="Include copy number alterations")
    include_dependencies: bool = Field(False, description="Include gene dependencies (DepMap)")
    include_expression: bool = Field(False, description="Include expression data")

    @field_validator("gene")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class CellLineNode(BaseModel):
    """Cell line entity."""

    name: str = Field(..., description="Cell line name")
    ccle_id: str = Field(..., description="CCLE identifier")
    depmap_id: str = Field(..., description="DepMap identifier")
    tissue: str | None = Field(None, description="Tissue of origin")
    disease: str | None = Field(None, description="Disease type")


class GeneMutation(BaseModel):
    """Gene mutation in cell line."""

    gene: EntityRef
    mutation_type: str = Field(..., description="Mutation type (missense, nonsense, etc.)")
    protein_change: str | None = Field(None, description="Protein change notation")
    is_driver: bool = Field(..., description="Is this a driver mutation?")


class CopyNumberEvent(BaseModel):
    """Copy number alteration."""

    gene: EntityRef
    copy_number: float = Field(..., description="Copy number value")
    alteration_type: str = Field(..., description="amplification, deletion, or neutral")


class GeneDependency(BaseModel):
    """Gene dependency from DepMap."""

    gene: EntityRef
    dependency_score: float = Field(..., description="Dependency score (lower = more essential)")
    percentile: float | None = Field(None, description="Percentile rank")


class GeneExpression(BaseModel):
    """Gene expression in cell line."""

    gene: EntityRef
    expression_value: float
    unit: str = Field(default="TPM", description="Expression unit")


# ============================================================================
# Tool 8: Clinical Trials Query Schemas
# ============================================================================


class ClinicalTrialsMode(str, Enum):
    """Query modes for clinical trials."""

    GET_FOR_DRUG = "get_for_drug"
    GET_FOR_DISEASE = "get_for_disease"
    GET_BY_ID = "get_by_id"


class ClinicalTrialsQuery(PaginatedToolInput):
    """Input for cogex_query_clinical_trials tool."""

    mode: ClinicalTrialsMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    drug: str | tuple[str, str] | None = Field(
        None,
        description="Drug name or CURIE (e.g., 'pembrolizumab' or ('chembl', 'CHEMBL1201585'))",
    )
    disease: str | tuple[str, str] | None = Field(
        None,
        description="Disease name or CURIE (e.g., 'diabetes' or ('mondo', 'MONDO:0005015'))",
    )
    trial_id: str | None = Field(
        None,
        description="NCT ID (e.g., 'NCT12345678')",
    )

    # Filters
    phase: list[int] | None = Field(
        None,
        description="Filter by trial phase (1, 2, 3, 4)",
    )
    status: str | None = Field(
        None,
        description="Filter by status (recruiting, completed, terminated, etc.)",
    )

    @field_validator("trial_id")
    @classmethod
    def validate_nct_id(cls, v: str | None) -> str | None:
        """Validate NCT ID format."""
        if v is not None and not v.upper().startswith("NCT"):
            raise ValueError("Trial ID must start with 'NCT'")
        return v.upper() if v else None

    @field_validator("drug", "disease")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


# ============================================================================
# Tool 9: Literature Query Schemas
# ============================================================================


class LiteratureQueryMode(str, Enum):
    """Query modes for literature queries."""

    GET_STATEMENTS_FOR_PMID = "get_statements_for_pmid"
    GET_EVIDENCE_FOR_STATEMENT = "get_evidence_for_statement"
    SEARCH_BY_MESH = "search_by_mesh"
    GET_STATEMENTS_BY_HASHES = "get_statements_by_hashes"


class LiteratureQuery(PaginatedToolInput):
    """Input for cogex_query_literature tool."""

    mode: LiteratureQueryMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    pmid: str | None = Field(None, description="PubMed ID (e.g., '12345678')")
    statement_hash: str | None = Field(None, description="INDRA statement hash")
    mesh_terms: list[str] | None = Field(None, description="MeSH terms for search")
    statement_hashes: list[str] | None = Field(None, description="List of statement hashes")

    # Options
    include_evidence_text: bool = Field(
        True,
        description="Include evidence text snippets",
    )
    max_evidence_per_statement: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum evidence per statement",
    )


class Publication(BaseModel):
    """PubMed publication."""

    pmid: str = Field(..., description="PubMed ID")
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str
    year: int
    abstract: str | None = None
    mesh_terms: list[str] = Field(default_factory=list)
    url: str = Field(..., description="PubMed URL")


class Evidence(BaseModel):
    """INDRA evidence snippet."""

    text: str = Field(..., description="Evidence text")
    pmid: str | None = Field(None, description="PubMed ID")
    source_api: str = Field(..., description="Source API (reach, sparser, etc.)")
    annotations: dict[str, Any] | None = Field(None, description="Additional annotations")


# Note: IndraStatement schema already exists in Tool 2 section (lines 375-391)


# Continue with remaining tool schemas in next file...
# This file is getting large, so we'll create additional schema files for remaining tools


# ============================================================================
# Tool 10: Variant Query Schemas
# ============================================================================


class VariantQueryMode(str, Enum):
    """Query modes for variant queries."""

    GET_FOR_GENE = "get_for_gene"
    GET_FOR_DISEASE = "get_for_disease"
    GET_FOR_PHENOTYPE = "get_for_phenotype"
    VARIANT_TO_GENES = "variant_to_genes"
    VARIANT_TO_PHENOTYPES = "variant_to_phenotypes"
    CHECK_ASSOCIATION = "check_association"


class VariantQuery(PaginatedToolInput):
    """Input for cogex_query_variants tool."""

    mode: VariantQueryMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    gene: str | tuple[str, str] | None = Field(
        None,
        description="Gene symbol or CURIE",
    )
    disease: str | tuple[str, str] | None = Field(
        None,
        description="Disease name or CURIE",
    )
    phenotype: str | tuple[str, str] | None = Field(
        None,
        description="Phenotype term or CURIE",
    )
    variant: str | None = Field(
        None,
        description="Variant rsID (e.g., 'rs7412')",
    )

    # Filters
    min_p_value: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum p-value",
    )
    max_p_value: float = Field(
        default=1e-5,
        ge=0.0,
        le=1.0,
        description="Maximum p-value threshold",
    )
    source: str | None = Field(
        None,
        description="Data source (gwas_catalog, disgenet)",
    )

    @field_validator("variant")
    @classmethod
    def validate_rsid(cls, v: str | None) -> str | None:
        """Validate variant rsID format."""
        if v is not None and not v.startswith("rs"):
            raise ValueError("Variant ID must be an rsID starting with 'rs'")
        return v

    @field_validator("gene", "disease", "phenotype")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


# Tool 10 output schemas (previously in schemas_tool10.py, now consolidated)


class VariantNode(BaseModel):
    """Genetic variant from GWAS."""

    rsid: str = Field(..., description="dbSNP rsID")
    chromosome: str
    position: int
    ref_allele: str = Field(..., description="Reference allele")
    alt_allele: str = Field(..., description="Alternate allele")
    p_value: float = Field(..., description="GWAS p-value")
    odds_ratio: float | None = None
    trait: str = Field(..., description="Associated trait or phenotype")
    study: str = Field(..., description="GWAS study identifier")
    source: str = Field(..., description="Data source (gwas_catalog, disgenet)")


class PhenotypeNode(BaseModel):
    """Phenotype entity."""

    name: str
    curie: str
    namespace: str = Field(default="hpo", description="Typically HPO")
    identifier: str
    description: str | None = None


# ============================================================================
# Tool 11: Identifier Resolution Schemas
# ============================================================================


class IdentifierQuery(BaseToolInput):
    """Input for cogex_resolve_identifiers tool."""

    identifiers: list[str] = Field(
        ...,
        min_length=1,
        description="List of identifiers to convert (e.g., ['TP53', 'BRCA1'])",
    )

    from_namespace: str = Field(
        ...,
        min_length=1,
        description="Source namespace (e.g., 'hgnc.symbol', 'hgnc', 'uniprot', 'ensembl')",
    )

    to_namespace: str = Field(
        ...,
        min_length=1,
        description="Target namespace (e.g., 'hgnc', 'hgnc.symbol', 'uniprot', 'ensembl')",
    )


class IdentifierMapping(BaseModel):
    """Single identifier mapping result."""

    source_id: str = Field(..., description="Source identifier")
    target_ids: list[str] = Field(..., description="Target identifier(s) (1:many supported)")
    confidence: str | None = Field(None, description="Mapping confidence (exact, inferred, etc.)")


# ============================================================================
# Tool 14: Cell Marker Query Schemas
# ============================================================================


class CellMarkerMode(str, Enum):
    """Query modes for cell marker queries."""

    GET_MARKERS = "get_markers"
    GET_CELL_TYPES = "get_cell_types"
    CHECK_MARKER = "check_marker"


class CellMarkerQuery(PaginatedToolInput):
    """Input for cogex_query_cell_markers tool."""

    mode: CellMarkerMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    cell_type: str | None = Field(
        None,
        description="Cell type name (e.g., 'T cell', 'NK cell')",
    )
    marker: str | tuple[str, str] | None = Field(
        None,
        description="Marker gene symbol or CURIE (e.g., 'CD4' or ('hgnc', '1678'))",
    )

    # Filters
    tissue: str | None = Field(
        None,
        description="Filter by tissue (e.g., 'blood', 'brain')",
    )
    species: str = Field(
        default="human",
        description="Filter by species (default: 'human')",
    )

    @field_validator("marker")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class CellMarkerNode(BaseModel):
    """Cell marker information."""

    gene: EntityRef = Field(..., description="Marker gene")
    marker_type: str = Field(..., description="Marker type (canonical, putative, etc.)")
    evidence: str = Field(..., description="Evidence source/method")


class CellTypeNode(BaseModel):
    """Cell type information."""

    name: str = Field(..., description="Cell type name")
    tissue: str = Field(..., description="Tissue where cell type is found")
    species: str = Field(..., description="Species")
    marker_count: int = Field(..., description="Number of known markers")


# ============================================================================
# Tool 12: Relationship Check Schemas
# ============================================================================


class RelationshipType(str, Enum):
    """Types of biological relationships to check."""

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


class RelationshipQuery(BaseToolInput):
    """Input for cogex_check_relationship tool."""

    relationship_type: RelationshipType = Field(..., description="Type of relationship to check")

    entity1: str | tuple[str, str] = Field(
        ...,
        description="First entity (gene/drug/disease/etc.) as name or (namespace, id) tuple",
    )

    entity2: str | tuple[str, str] = Field(
        ...,
        description="Second entity (pathway/target/phenotype/etc.) as name or (namespace, id) tuple",
    )

    @field_validator("entity1", "entity2")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str]) -> str | tuple[str, str]:
        """Validate entity input format."""
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class RelationshipMetadata(BaseModel):
    """Metadata about a relationship check."""

    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence score (0-1)")
    evidence_count: int | None = Field(None, description="Number of supporting evidences")
    sources: list[str] | None = Field(None, description="Source databases")
    additional_info: dict[str, Any] | None = Field(None, description="Type-specific metadata")


class RelationshipResponse(BaseModel):
    """Response from relationship check."""

    exists: bool = Field(..., description="Whether the relationship exists")
    metadata: RelationshipMetadata | None = Field(
        None, description="Additional relationship metadata"
    )


# ============================================================================
# Tool 13: Ontology Hierarchy Schemas
# ============================================================================


class HierarchyDirection(str, Enum):
    """Ontology hierarchy query directions."""

    PARENTS = "parents"
    CHILDREN = "children"
    BOTH = "both"


class OntologyHierarchyQuery(BaseToolInput):
    """Input for cogex_get_ontology_hierarchy tool."""

    term: str | tuple[str, str] = Field(
        ...,
        description="Ontology term (GO, HPO, MONDO, etc.) as name, CURIE, or (namespace, id) tuple",
    )

    direction: HierarchyDirection = Field(
        ...,
        description="Query direction: parents (ancestors), children (descendants), or both",
    )

    max_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum levels to traverse in the ontology hierarchy",
    )

    @field_validator("term")
    @classmethod
    def validate_term_input(cls, v: str | tuple[str, str]) -> str | tuple[str, str]:
        """Validate term input format."""
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class OntologyTerm(BaseModel):
    """Ontology term with hierarchy metadata."""

    name: str = Field(..., description="Term name (e.g., 'apoptotic process')")
    curie: str = Field(..., description="CURIE (e.g., 'GO:0006915')")
    namespace: str = Field(..., description="Ontology namespace (go, hpo, mondo, etc.)")
    definition: str | None = Field(None, description="Term definition/description")
    depth: int = Field(..., description="Distance from root term in hierarchy traversal")
    relationship: str | None = Field(
        None,
        description="Relationship type to parent/child (is_a, part_of, etc.)",
    )


# ============================================================================
# Tool 16: Protein Function Query Schemas
# ============================================================================


class ProteinFunctionMode(str, Enum):
    """Query modes for protein function queries."""

    GENE_TO_ACTIVITIES = "gene_to_activities"
    ACTIVITY_TO_GENES = "activity_to_genes"
    CHECK_ACTIVITY = "check_activity"
    CHECK_FUNCTION_TYPES = "check_function_types"


class ProteinFunctionQuery(PaginatedToolInput):
    """Input for cogex_query_protein_functions tool."""

    mode: ProteinFunctionMode = Field(..., description="Query mode")

    # Entity fields (depends on mode)
    gene: str | tuple[str, str] | None = Field(
        None,
        description="Gene symbol or CURIE for gene_to_activities and check_activity modes",
    )
    genes: list[str] | None = Field(
        None,
        description="List of genes for batch check_function_types mode",
    )
    enzyme_activity: str | None = Field(
        None,
        description="Enzyme activity name for activity_to_genes and check_activity modes",
    )

    # For check_function_types
    function_types: list[str] | None = Field(
        None,
        description="Function types to check: kinase, phosphatase, transcription_factor",
    )

    @field_validator("gene")
    @classmethod
    def validate_entity_input(cls, v: str | tuple[str, str] | None) -> str | tuple[str, str] | None:
        """Validate entity input format."""
        if v is None:
            return None
        if isinstance(v, tuple):
            if len(v) != 2:
                raise ValueError("Tuple must have exactly 2 elements: (namespace, identifier)")
            if not all(isinstance(x, str) for x in v):
                raise ValueError("Tuple elements must be strings")
        return v


class EnzymeActivity(BaseModel):
    """Enzyme activity information."""

    activity: str = Field(..., description="Activity name (e.g., 'kinase', 'phosphorylation')")
    ec_number: str | None = Field(None, description="EC number (e.g., 'EC:2.7.11.1')")
    confidence: str = Field(..., description="Confidence level (high, medium, low)")
    evidence_sources: list[str] = Field(..., description="Evidence source databases")
