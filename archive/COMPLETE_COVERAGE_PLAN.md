# Complete CoGEx Coverage Plan - Revised Architecture

**Date**: 2025-11-24
**Status**: MAJOR REVISION - Bidirectional Design
**Coverage Target**: 100% (110/110 endpoints)

---

## Executive Summary

**Critical Discovery**: Our initial 15-tool design achieved only 74.5% coverage because tools were UNIDIRECTIONAL but CoGEx is BIDIRECTIONAL.

**Solution**: Redesign tools with bidirectional modes to achieve 95-100% coverage.

---

## Coverage Analysis

### Current State (Initial Design)
- **Tools**: 15 (13 original + 2 additions)
- **Endpoints Covered**: 82/110 (74.5%)
- **Endpoints Uncovered**: 29

### Target State (Revised Design)
- **Tools**: 16-17 (with bidirectional modes)
- **Endpoints Covered**: 100-105/110 (91-95%)
- **Endpoints Uncovered**: 5-10 (low-priority journal metadata)

---

## Gap Categories

### Category 1: Reverse Lookups (6 endpoints) ⭐ **CRITICAL**

**Impact**: HIGH - Fundamental query patterns

**Missing Endpoints:**
1. `get_genes_for_go_term` - GO term → genes
2. `get_genes_in_tissue` - Tissue → genes
3. `get_genes_for_domain` - Domain → genes
4. `get_genes_for_phenotype` - Phenotype → genes
5. `get_drugs_for_side_effect` - Side effect → drugs
6. `get_diseases_for_phenotype` - Phenotype → diseases

**Use Cases:**
- "What genes are expressed in brain?" (tissue→genes)
- "Show me all genes with kinase activity" (GO→genes)
- "Find genes with SH2 domains" (domain→genes)
- "What drugs cause nausea?" (side effect→drugs)
- "Genes associated with seizures" (phenotype→genes)

**Solution**: Make tools BIDIRECTIONAL

---

### Category 2: Enzyme/Protein Functions (6 endpoints) ⭐ HIGH

**Missing Endpoints:**
1. `get_enzyme_activities_for_gene`
2. `get_genes_for_enzyme_activity`
3. `has_enzyme_activity`
4. `is_kinase`
5. `is_phosphatase`
6. `is_transcription_factor`

**Use Cases:**
- "Is EGFR a kinase?"
- "Find all phosphatases in my gene set"
- "What's the EC number for this gene?"

**Solution**: New Tool 16 or extend Tool 1

---

### Category 3: Phenotype Relationships (3 endpoints) ⭐ MEDIUM

**Missing Endpoints:**
1. `get_phenotypes_for_variant_gwas` - Variant → phenotypes
2. `has_phenotype` - Disease ↔ phenotype check
3. `has_phenotype_gene` - Gene ↔ phenotype check

**Solution**: Extend Tools 5 & 10

---

### Category 4: Statement Queries (1 endpoint) ⭐ HIGH

**Missing Endpoints:**
1. `get_stmts_for_stmt_hashes` - Bulk statement retrieval

**Use Cases:**
- "Get full details for these 100 statement hashes"
- Batch evidence retrieval

**Solution**: Extend Tool 9

---

### Category 5: Advanced Analysis (1 endpoint) ⭐ MEDIUM

**Missing Endpoints:**
1. `source_target_analysis` - Source → multiple targets analysis

**Use Cases:**
- "How does TP53 regulate these 20 genes?"

**Solution**: Extend Tool 2 or new mode

---

### Category 6: Research Metadata (6 endpoints) 🔵 LOW

**Missing Endpoints:**
1. `get_clinical_trials_for_project`
2. `get_patents_for_project`
3. `get_projects_for_clinical_trial`
4. `get_projects_for_patent`
5. `get_projects_for_publication`
6. `get_publications_for_project`

**Solution**: Tool 17 (optional, defer to v1.1)

---

### Category 7: Journal Metadata (6 endpoints) 🔵 VERY LOW

**Missing Endpoints:**
1. `get_journal_for_publication`
2. `get_journals_for_publisher`
3. `get_publisher_for_journal`
4. `get_publications_for_journal`
5. `is_journal_published_by`
6. `is_published_in_journal`

**Solution**: Tool 18 (optional, defer to v1.2+)

---

## Revised Tool Architecture

### 🔄 Redesign for Bidirectionality

#### **Tool 1: query_gene_context** → **query_gene_or_feature**

**OLD**: Gene-centric only
**NEW**: Bidirectional gene ↔ feature queries

```python
class GeneFeatureQuery(BaseModel):
    mode: QueryMode  # NEW PARAMETER

    # Entity specification (depends on mode)
    gene: Optional[str | Tuple[str, str]] = None
    tissue: Optional[str | Tuple[str, str]] = None
    go_term: Optional[str | Tuple[str, str]] = None
    domain: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None

    # Options
    include_expression: bool = True
    include_go_terms: bool = True
    include_pathways: bool = True
    include_diseases: bool = True
    include_domains: bool = False
    include_variants: bool = False
    include_phenotypes: bool = False

class QueryMode(str, Enum):
    # Forward: Gene → features
    GENE_TO_FEATURES = "gene_to_features"

    # Reverse: Feature → genes
    TISSUE_TO_GENES = "tissue_to_genes"
    GO_TO_GENES = "go_to_genes"
    DOMAIN_TO_GENES = "domain_to_genes"
    PHENOTYPE_TO_GENES = "phenotype_to_genes"
```

**Coverage Added**: +4 endpoints (tissue→genes, GO→genes, domain→genes, phenotype→genes)

---

#### **Tool 4: query_drug_profile** → **query_drug_or_effect**

**OLD**: Drug-centric only
**NEW**: Bidirectional drug ↔ effect queries

```python
class DrugEffectQuery(BaseModel):
    mode: DrugQueryMode

    drug: Optional[str | Tuple[str, str]] = None
    side_effect: Optional[str | Tuple[str, str]] = None

    include_targets: bool = True
    include_indications: bool = True
    include_side_effects: bool = True
    include_trials: bool = True

class DrugQueryMode(str, Enum):
    DRUG_TO_PROFILE = "drug_to_profile"          # Drug → all info
    SIDE_EFFECT_TO_DRUGS = "side_effect_to_drugs"  # Side effect → drugs
```

**Coverage Added**: +1 endpoint (side_effect→drugs)

---

#### **Tool 5: query_disease_mechanisms** → **query_disease_or_phenotype**

**OLD**: Disease-centric only
**NEW**: Bidirectional disease ↔ phenotype queries

```python
class DiseasePhenotypeQuery(BaseModel):
    mode: DiseaseQueryMode

    disease: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None

    include_genes: bool = True
    include_variants: bool = True
    include_phenotypes: bool = True
    include_drugs: bool = True

class DiseaseQueryMode(str, Enum):
    DISEASE_TO_MECHANISMS = "disease_to_mechanisms"
    PHENOTYPE_TO_DISEASES = "phenotype_to_diseases"
    CHECK_PHENOTYPE = "check_phenotype"  # has_phenotype
```

**Coverage Added**: +2 endpoints (phenotype→diseases, has_phenotype)

---

#### **Tool 9: query_literature_evidence** → Enhanced

**ADD**: Statement hash bulk retrieval

```python
class LiteratureQuery(BaseModel):
    mode: LiteratureQueryMode

    # ... existing fields ...
    statement_hashes: Optional[List[str]] = None  # NEW

class LiteratureQueryMode(str, Enum):
    # ... existing modes ...
    GET_STATEMENTS_BY_HASHES = "get_statements_by_hashes"  # NEW
```

**Coverage Added**: +1 endpoint (get_stmts_for_stmt_hashes)

---

#### **Tool 10: query_variants** → Enhanced

**ADD**: Reverse lookups and phenotype checks

```python
class VariantQuery(BaseModel):
    mode: VariantQueryMode

    gene: Optional[str | Tuple[str, str]] = None
    disease: Optional[str | Tuple[str, str]] = None
    phenotype: Optional[str | Tuple[str, str]] = None
    variant: Optional[str | Tuple[str, str]] = None  # NEW

class VariantQueryMode(str, Enum):
    GET_FOR_GENE = "get_for_gene"
    GET_FOR_DISEASE = "get_for_disease"
    GET_FOR_PHENOTYPE = "get_for_phenotype"

    # NEW reverse lookups:
    VARIANT_TO_GENES = "variant_to_genes"
    VARIANT_TO_PHENOTYPES = "variant_to_phenotypes"

    # NEW checks:
    CHECK_GENE_ASSOCIATION = "check_gene_association"     # has_variant_gene_association
    CHECK_PHENOTYPE_ASSOCIATION = "check_phenotype_association"  # has_phenotype_gene
```

**Coverage Added**: +3 endpoints (variant→genes, variant→phenotypes, has_phenotype_gene)

---

#### **Tool 2: extract_subnetwork** → Enhanced

**ADD**: Source-target analysis mode

```python
class SubnetworkQuery(BaseModel):
    genes: List[str]
    mode: SubnetworkMode

    # NEW for source-target analysis:
    source_gene: Optional[str] = None
    target_genes: Optional[List[str]] = None

class SubnetworkMode(str, Enum):
    DIRECT = "direct"
    MEDIATED = "mediated"
    SHARED_UPSTREAM = "shared_upstream"
    SHARED_DOWNSTREAM = "shared_downstream"

    # NEW:
    SOURCE_TO_TARGETS = "source_to_targets"  # source_target_analysis
```

**Coverage Added**: +1 endpoint (source_target_analysis)

---

### ➕ New Tools

#### **Tool 16: query_protein_functions**

**Purpose**: Enzyme activity and protein function classification

```python
class ProteinFunctionQuery(BaseModel):
    mode: FunctionQueryMode

    gene: Optional[str | Tuple[str, str]] = None
    enzyme_activity: Optional[str] = None  # EC number
    genes_batch: Optional[List[str]] = None  # For is_kinase, etc.

    function_types: Optional[List[str]] = None
    """Check: ["kinase", "phosphatase", "transcription_factor"]"""

class FunctionQueryMode(str, Enum):
    GENE_TO_ACTIVITIES = "gene_to_activities"      # get_enzyme_activities_for_gene
    ACTIVITY_TO_GENES = "activity_to_genes"        # get_genes_for_enzyme_activity
    CHECK_ACTIVITY = "check_activity"               # has_enzyme_activity
    CHECK_FUNCTION_TYPES = "check_function_types"  # is_kinase, is_phosphatase, is_tf
```

**Coverage Added**: +6 endpoints (all enzyme/function endpoints)

---

#### **Tool 17: query_research_metadata** (OPTIONAL)

**Purpose**: NIH Reporter integration

```python
class ResearchMetadataQuery(BaseModel):
    mode: ResearchMode

    project_id: Optional[str] = None
    publication_pmid: Optional[str] = None
    patent_id: Optional[str] = None
    trial_nct_id: Optional[str] = None

class ResearchMode(str, Enum):
    PROJECT_TO_OUTPUTS = "project_to_outputs"
    PUBLICATION_TO_PROJECTS = "publication_to_projects"
    TRIAL_TO_PROJECTS = "trial_to_projects"
    PATENT_TO_PROJECTS = "patent_to_projects"
```

**Coverage Added**: +6 endpoints (all NIH Reporter endpoints)

---

#### **Tool 18: query_journal_metadata** (OPTIONAL)

**Purpose**: Journal/publisher relationships

**Recommendation**: DEFER to v1.2+ (very low priority)

**Coverage Added**: +6 endpoints (all journal metadata endpoints)

---

## Revised Tool Summary

| # | Tool Name | Type | Coverage | Priority |
|---|-----------|------|----------|----------|
| 1 | query_gene_or_feature | Bidirectional | +4 | ⭐ CRITICAL |
| 2 | extract_subnetwork | Enhanced | +1 | ⭐ HIGH |
| 3 | enrichment_analysis | Unchanged | ✓ | ⭐ HIGH |
| 4 | query_drug_or_effect | Bidirectional | +1 | ⭐ HIGH |
| 5 | query_disease_or_phenotype | Bidirectional | +2 | ⭐ HIGH |
| 6 | query_pathway | Unchanged | ✓ | ⭐ HIGH |
| 7 | query_cell_line | Unchanged | ✓ | MEDIUM |
| 8 | query_clinical_trials | Unchanged | ✓ | MEDIUM |
| 9 | query_literature_evidence | Enhanced | +1 | ⭐ HIGH |
| 10 | query_variants | Enhanced | +3 | MEDIUM |
| 11 | resolve_identifiers | Unchanged | ✓ | LOW |
| 12 | check_relationship | Unchanged | ✓ | LOW |
| 13 | get_ontology_hierarchy | Unchanged | ✓ | LOW |
| 14 | query_cell_markers | New | ✓ | ⭐ HIGH |
| 15 | analyze_kinase_enrichment | New | ✓ | ⭐ HIGH |
| 16 | query_protein_functions | New | +6 | ⭐ HIGH |
| 17 | query_research_metadata | Optional | +6 | 🔵 LOW |
| 18 | query_journal_metadata | Optional | +6 | 🔵 VERY LOW |

---

## Coverage Breakdown

### With Tools 1-16 (Recommended v1.0)

**Endpoints Covered**: 100/110 (91%)
**Endpoints Uncovered**: 10 (6 journal + 4 minor)

**Uncovered Endpoints:**
- All journal/publisher metadata (6 endpoints) - defer
- Minor omissions if any

### With Tools 1-17 (Full v1.0)

**Endpoints Covered**: 105/110 (95%)
**Endpoints Uncovered**: 5 (journal metadata only)

### With Tools 1-18 (Complete)

**Endpoints Covered**: 110/110 (100%)

---

## Implementation Strategy

### Phase 1: Core Bidirectional Redesign (Weeks 1-3)

**Priority**: ⭐ CRITICAL

1. **Redesign Tool 1** (gene ↔ features)
   - Add 4 reverse lookup modes
   - Test bidirectional queries
   - Update schema

2. **Redesign Tool 4** (drug ↔ effects)
   - Add side effect → drugs mode
   - Integrate with existing

3. **Redesign Tool 5** (disease ↔ phenotypes)
   - Add phenotype → diseases mode
   - Add phenotype checks

4. **Enhance Tool 2** (subnetworks)
   - Add source-target analysis mode

5. **Enhance Tool 9** (literature)
   - Add statement hash bulk retrieval

6. **Enhance Tool 10** (variants)
   - Add reverse lookups
   - Add phenotype checks

---

### Phase 2: New High-Value Tools (Week 4)

**Priority**: ⭐ HIGH

1. **Tool 14**: query_cell_markers
2. **Tool 15**: analyze_kinase_enrichment
3. **Tool 16**: query_protein_functions

---

### Phase 3: Testing & Evaluation (Week 5)

- Unit tests for all bidirectional modes
- Integration tests
- Update evaluation questions

---

### Phase 4: Optional Extensions (v1.1+)

**Priority**: 🔵 LOW

1. **Tool 17**: query_research_metadata (NIH Reporter)
2. **Tool 18**: query_journal_metadata (defer to v1.2)

---

## Key Design Principles

### 1. Bidirectional by Default

All entity-relationship tools should support BOTH directions:
- Forward: entity → related entities
- Reverse: related entity → entities

### 2. Mode Parameter Pattern

```python
class Query(BaseModel):
    mode: QueryMode  # Always specify direction
    entity: Optional[...] = None
    # ... other params
```

### 3. Consistent Naming

- Forward: `{ENTITY}_TO_{FEATURES}`
- Reverse: `{FEATURE}_TO_{ENTITIES}`
- Check: `CHECK_{RELATIONSHIP}`

### 4. Backward Compatibility

Existing queries without `mode` default to forward direction:
```python
# OLD (still works):
query_gene_context(gene="TP53")

# NEW (explicit):
query_gene_or_feature(mode="gene_to_features", gene="TP53")
```

---

## Comparison: Old vs New

| Metric | Initial Design | Revised Design |
|--------|---------------|----------------|
| **Tools** | 15 | 16-17 |
| **Coverage** | 74.5% (82/110) | 91-95% (100-105/110) |
| **Bidirectional** | No | Yes |
| **Missing Critical** | 6 reverse lookups | 0 |
| **Extensibility** | Low | High |

---

## Benefits of Revised Architecture

### 1. Complete Coverage
- 91% with 16 tools (v1.0)
- 95% with 17 tools (v1.1)
- 100% with 18 tools (v1.2)

### 2. Better User Experience
- "What genes are in brain tissue?" → Now supported
- "What drugs cause nausea?" → Now supported
- "Genes with SH2 domains?" → Now supported

### 3. Architectural Consistency
- All relationship tools are bidirectional
- Predictable mode patterns
- Easy to extend

### 4. Flexibility
- Users can query from either direction
- No need to know "which entity is primary"
- Matches mental models better

---

## Migration Path

### From Initial Spec → Revised Spec

**Step 1**: Update tool schemas with `mode` parameter

**Step 2**: Implement reverse lookup backends

**Step 3**: Update tests for bidirectionality

**Step 4**: Update documentation with mode examples

**Step 5**: Add new Tools 16-18

---

## Recommendation

**For v1.0**: Implement Tools 1-16 (16 tools, 91% coverage)

This includes:
- ✅ All bidirectional redesigns
- ✅ All high-priority new tools
- ✅ Complete enzyme/protein functions
- ✅ Cell markers & kinase analysis
- ❌ NIH Reporter (defer to v1.1)
- ❌ Journal metadata (defer to v1.2)

**Estimated Timeline**: 5-6 weeks (1 week longer due to redesign)

**Coverage**: 100/110 endpoints (91%)

**Uncovered**: Only low-priority journal/publisher metadata

---

## Next Steps

1. ✅ Update IMPLEMENTATION_SPEC.md with bidirectional designs
2. ✅ Update all tool schemas
3. ✅ Update evaluation questions to test reverse lookups
4. ✅ Begin implementation with revised architecture

---

**END OF COMPLETE COVERAGE PLAN**
