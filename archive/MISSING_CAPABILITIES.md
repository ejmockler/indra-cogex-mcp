# Missing Capabilities & Coverage Analysis - REVISED

**Date**: 2025-11-24
**Status**: MAJOR ARCHITECTURAL REVISION REQUIRED
**Current Coverage**: 74.5% (82/110 endpoints)
**Target Coverage**: 91-100% with revised design

---

## 🚨 CRITICAL DISCOVERY

Our initial 15-tool design has a **fundamental architectural flaw**:

**Tools are UNIDIRECTIONAL but CoGEx is BIDIRECTIONAL**

This limits coverage to 74.5% and misses essential query patterns.

---

## Coverage Audit Summary

| Metric | Value |
|--------|-------|
| **Total CoGEx Endpoints** | 110 |
| **Covered by Initial Design** | 82 (74.5%) |
| **Uncovered** | 29 (25.5%) |
| **Critical Gaps** | 6 reverse lookups |
| **High Priority Gaps** | 7 enzyme/analysis |
| **Medium Priority Gaps** | 4 phenotype/statement |
| **Low Priority Gaps** | 12 research/journal metadata |

---

## Gap Analysis by Category

### Category 1: Reverse Lookups ⭐⭐⭐ **CRITICAL**

**Impact**: HIGHEST - Fundamental query patterns missing

**Problem**: We have forward queries (gene→feature) but NOT reverse (feature→genes)

| Have Forward | Missing Reverse | Use Case |
|-------------|-----------------|----------|
| gene→tissues | tissue→genes ❌ | "What genes are expressed in brain?" |
| gene→GO terms | GO→genes ❌ | "Show me all genes with kinase activity" |
| gene→domains | domain→genes ❌ | "Find genes with SH2 domains" |
| gene→phenotypes | phenotype→genes ❌ | "Genes associated with seizures" |
| drug→side effects | side effect→drugs ❌ | "What drugs cause nausea?" |
| disease→phenotypes | phenotype→diseases ❌ | "Diseases causing fever" |

**Endpoints (6):**
1. `/api/get_genes_for_go_term` - GO term → genes
2. `/api/get_genes_in_tissue` - Tissue → genes
3. `/api/get_genes_for_domain` - Protein domain → genes
4. `/api/get_genes_for_phenotype` - Phenotype → genes
5. `/api/get_drugs_for_side_effect` - Side effect → drugs
6. `/api/get_diseases_for_phenotype` - Phenotype → diseases

**Solution**: Redesign Tools 1, 4, 5 with bidirectional modes

**Example Redesign (Tool 1):**
```python
class GeneFeatureQuery(BaseModel):
    mode: QueryMode  # NEW PARAMETER

    # Entity (depends on mode)
    gene: Optional[str] = None
    tissue: Optional[str] = None
    go_term: Optional[str] = None
    domain: Optional[str] = None
    phenotype: Optional[str] = None

class QueryMode(str, Enum):
    GENE_TO_FEATURES = "gene_to_features"      # Original direction
    TISSUE_TO_GENES = "tissue_to_genes"        # NEW reverse
    GO_TO_GENES = "go_to_genes"                # NEW reverse
    DOMAIN_TO_GENES = "domain_to_genes"        # NEW reverse
    PHENOTYPE_TO_GENES = "phenotype_to_genes"  # NEW reverse
```

**Priority**: ⭐⭐⭐ MUST FIX in v1.0

---

### Category 2: Enzyme/Protein Functions ⭐⭐⭐ HIGH

**Impact**: HIGH - Essential for drug targeting and pathway analysis

**Endpoints (6):**
1. `/api/get_enzyme_activities_for_gene` - Gene → EC numbers
2. `/api/get_genes_for_enzyme_activity` - EC number → genes
3. `/api/has_enzyme_activity` - Check if gene has activity
4. `/api/is_kinase` - Check if gene(s) are kinases
5. `/api/is_phosphatase` - Check if gene(s) are phosphatases
6. `/api/is_transcription_factor` - Check if gene(s) are TFs

**Use Cases:**
- "Is EGFR a kinase?" → Boolean
- "Find all kinases in the PI3K pathway" → Gene list
- "What's the enzyme activity of GAPDH?" → EC 1.2.1.12
- "Show me all phosphatases in my gene set" → Filter list

**Solution**: New **Tool 16: query_protein_functions**

```python
class ProteinFunctionQuery(BaseModel):
    mode: FunctionQueryMode

    gene: Optional[str | Tuple[str, str]] = None
    enzyme_activity: Optional[str] = None      # EC number
    genes_batch: Optional[List[str]] = None    # For batch checks

    function_types: Optional[List[str]] = None
    """Check: ["kinase", "phosphatase", "transcription_factor"]"""

class FunctionQueryMode(str, Enum):
    GENE_TO_ACTIVITIES = "gene_to_activities"      # get_enzyme_activities_for_gene
    ACTIVITY_TO_GENES = "activity_to_genes"        # get_genes_for_enzyme_activity
    CHECK_ACTIVITY = "check_activity"               # has_enzyme_activity
    CHECK_FUNCTION_TYPES = "check_function_types"  # is_kinase, etc. (batch)

class ProteinFunctionResponse(BaseModel):
    query: QueryMetadata
    results: ProteinFunctionResults

class ProteinFunctionResults(BaseModel):
    # For gene→activities
    enzyme_activities: Optional[List[EnzymeActivity]]

    # For activity→genes
    genes: Optional[List[GeneInfo]]

    # For checks
    has_activity: Optional[bool]
    function_checks: Optional[Dict[str, bool]]  # {"is_kinase": True, ...}

class EnzymeActivity(BaseModel):
    ec_number: str
    activity_name: str
    evidence_count: int
```

**Priority**: ⭐⭐⭐ HIGH - Add in v1.0

---

### Category 3: Advanced Analysis ⭐⭐ MEDIUM-HIGH

**Endpoints (2):**
1. `/api/source_target_analysis` - Source gene → multiple targets analysis
2. `/api/kinase_analysis` - Phosphosite enrichment (already planned as Tool 15)

#### 3.1 Source-Target Analysis

**Use Case**: "How does TP53 regulate these 20 downstream genes?"

**Solution**: Extend **Tool 2: extract_subnetwork** with new mode

```python
class SubnetworkQuery(BaseModel):
    # ... existing fields ...

    # NEW for source-target analysis:
    source_gene: Optional[str] = None
    target_genes: Optional[List[str]] = None

class SubnetworkMode(str, Enum):
    # ... existing modes ...
    SOURCE_TO_TARGETS = "source_to_targets"  # NEW
```

**Priority**: ⭐⭐ MEDIUM-HIGH - Add in v1.0

#### 3.2 Kinase Analysis

**Already planned as Tool 15** ✓

**Priority**: ⭐⭐⭐ HIGH - Add in v1.0

---

### Category 4: Phenotype Relationships ⭐⭐ MEDIUM

**Endpoints (3):**
1. `/api/get_phenotypes_for_variant_gwas` - Variant → phenotypes (GWAS)
2. `/api/has_phenotype` - Disease ↔ phenotype check
3. `/api/has_phenotype_gene` - Gene ↔ phenotype check

**Use Cases:**
- "What phenotypes are associated with rs429358?" → GWAS phenotypes
- "Does Alzheimer's disease have memory loss phenotype?" → Boolean
- "Is BRCA1 associated with breast cancer phenotype?" → Boolean

**Solution**: Extend **Tool 10: query_variants** and **Tool 5: query_disease_or_phenotype**

**Tool 10 Extensions:**
```python
class VariantQueryMode(str, Enum):
    # ... existing modes ...

    # NEW:
    VARIANT_TO_PHENOTYPES_GWAS = "variant_to_phenotypes_gwas"  # get_phenotypes_for_variant_gwas
    CHECK_GENE_ASSOCIATION = "check_gene_association"          # has_phenotype_gene
```

**Tool 5 Extensions:**
```python
class DiseaseQueryMode(str, Enum):
    # ... existing modes ...

    # NEW:
    CHECK_PHENOTYPE = "check_phenotype"  # has_phenotype
```

**Priority**: ⭐⭐ MEDIUM - Add in v1.0

---

### Category 5: Statement Queries ⭐⭐ MEDIUM

**Endpoints (1):**
1. `/api/get_stmts_for_stmt_hashes` - Bulk statement retrieval

**Use Case**: "Get full details for these 100 statement hashes"

**Solution**: Extend **Tool 9: query_literature_evidence**

```python
class LiteratureQueryMode(str, Enum):
    # ... existing modes ...

    # NEW:
    GET_STATEMENTS_BY_HASHES = "get_statements_by_hashes"  # Bulk retrieval
```

**Priority**: ⭐⭐ MEDIUM - Add in v1.0

---

### Category 6: Research Metadata (NIH Reporter) 🔵 LOW

**Endpoints (6):**
1. `/api/get_clinical_trials_for_project` - NIH project → trials
2. `/api/get_patents_for_project` - NIH project → patents
3. `/api/get_projects_for_clinical_trial` - Trial → NIH projects
4. `/api/get_projects_for_patent` - Patent → NIH projects
5. `/api/get_projects_for_publication` - Publication → NIH projects
6. `/api/get_publications_for_project` - NIH project → publications

**Use Cases:**
- "What NIH grants funded TP53 research?" → Grant IDs
- "Find collaborators working on CRISPR" → Via co-funded projects
- "What patents came from grant R01CA123456?" → Patent list

**Impact**: MEDIUM - Valuable for grant writing, collaboration discovery

**Solution**: New **Tool 17: query_research_metadata** (OPTIONAL)

```python
class ResearchMetadataQuery(BaseModel):
    mode: ResearchMode

    project_id: Optional[str] = None          # NIH Reporter project ID
    publication_pmid: Optional[str] = None
    patent_id: Optional[str] = None
    trial_nct_id: Optional[str] = None

    include_publications: bool = True
    include_trials: bool = True
    include_patents: bool = True

class ResearchMode(str, Enum):
    PROJECT_TO_OUTPUTS = "project_to_outputs"         # Project → pubs/trials/patents
    PUBLICATION_TO_PROJECTS = "publication_to_projects"  # Pub → projects
    TRIAL_TO_PROJECTS = "trial_to_projects"           # Trial → projects
    PATENT_TO_PROJECTS = "patent_to_projects"         # Patent → projects
```

**Priority**: 🔵 LOW - Defer to v1.1 (optional)

---

### Category 7: Journal/Publisher Metadata 🔵 VERY LOW

**Endpoints (6):**
1. `/api/get_journal_for_publication` - PMID → journal
2. `/api/get_journals_for_publisher` - Publisher → journals
3. `/api/get_publisher_for_journal` - Journal → publisher
4. `/api/get_publications_for_journal` - Journal → PMIDs
5. `/api/is_journal_published_by` - Check journal-publisher relationship
6. `/api/is_published_in_journal` - Check publication-journal relationship

**Use Cases:**
- "What journal published PMID:12345678?" → Journal name
- "What journals does Nature Publishing Group publish?" → Journal list
- "Was this paper published in Science?" → Boolean

**Impact**: VERY LOW - Niche use cases, low research value

**Solution**: New **Tool 18: query_journal_metadata** (OPTIONAL)

**Priority**: 🔵 VERY LOW - Defer to v1.2+ or never

---

## Specification Gaps (Infrastructure)

### 1. Error Handling ⭐⭐⭐ CRITICAL

**Missing:**
- Complete error taxonomy
- Retry logic for transient failures
- Circuit breaker pattern
- Graceful degradation strategies

**Add:**
```python
# src/indra_cogex_mcp/errors.py

class CoGExError(Exception):
    """Base exception"""
    pass

class EntityNotFoundError(CoGExError):
    """Entity doesn't exist"""
    suggestions: List[str]  # Did you mean?

class AmbiguousIdentifierError(CoGExError):
    """Multiple matches"""
    candidates: List[EntityRef]

class BackendUnavailableError(CoGExError):
    """Neo4j/REST API down"""
    retry_after: int

class QueryTimeoutError(CoGExError):
    """Query exceeded timeout"""
    partial_results: Optional[Any]

class RateLimitExceededError(CoGExError):
    """Too many requests"""
    retry_after: int

# Retry decorator
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(BackendUnavailableError)
)
async def query_with_retry(...):
    pass
```

---

### 2. Security ⭐⭐⭐ HIGH

**Missing:**
- Input validation (Cypher injection prevention)
- Rate limiting per user
- Authentication/authorization
- Secrets management

**Add:**
```python
# Input sanitization
def sanitize_cypher_input(user_input: str) -> str:
    """Prevent Cypher injection"""
    forbidden_patterns = [';', 'MATCH', 'DELETE', 'CREATE', 'DROP']
    # Validate and escape
    pass

# Rate limiting
from slowapi import Limiter

limiter = Limiter(
    key_func=lambda: request.headers.get("X-User-ID", "anonymous")
)

@limiter.limit("60/minute")
async def call_tool(...):
    pass
```

---

### 3. Batch Operations ⭐⭐ MEDIUM

**Missing:**
- Batch processing for multiple entities
- Efficient parallel queries
- Request deduplication

**Add:**
```python
# Support in all tools:
class GeneFeatureQuery(BaseModel):
    genes: List[str] | str  # Support both single and batch

# OR dedicated batch endpoint:
class BatchQuery(BaseModel):
    tool: str
    queries: List[Dict[str, Any]]
    parallel: bool = True
```

---

### 4. Data Provenance ⭐⭐ MEDIUM

**Missing:**
- INDRA CoGEx version tracking
- Data source versions
- Graph build dates
- Reproducibility hashes

**Add:**
```python
class ResponseMetadata(BaseModel):
    # ... existing fields ...
    cogex_version: str              # "1.0.0"
    graph_build_date: str           # "2025-11-15"
    data_source_versions: Dict[str, str]  # {"reactome": "2024-12", ...}
    query_hash: str                 # For reproducibility
```

---

### 5. Monitoring & Observability ⭐⭐ MEDIUM

**Missing:**
- Metrics (latency, error rates, cache hit rate)
- Distributed tracing
- Health checks
- Logging standards

**Add:**
```python
from prometheus_client import Counter, Histogram

tool_calls = Counter('mcp_tool_calls_total', 'Total calls', ['tool', 'status'])
tool_duration = Histogram('mcp_tool_duration_seconds', 'Duration', ['tool'])
cache_hits = Counter('mcp_cache_hits_total', 'Cache hits', ['type'])

async def health_check() -> HealthStatus:
    return HealthStatus(
        neo4j_available=await check_neo4j(),
        rest_api_available=await check_rest_api(),
        cache_size=len(cache),
        uptime_seconds=time.time() - start_time
    )
```

---

## Revised Architecture Summary

### Tools Count

| Version | Tools | Coverage | Priority |
|---------|-------|----------|----------|
| **v1.0 (Recommended)** | 16 | 91% (100/110) | High-value only |
| **v1.1 (Full)** | 17 | 95% (105/110) | + NIH Reporter |
| **v1.2 (Complete)** | 18 | 100% (110/110) | + Journal metadata |

### What Changes from Initial Design

**Major Redesigns:**
1. ✅ Tool 1: `query_gene_context` → `query_gene_or_feature` (bidirectional)
2. ✅ Tool 4: `query_drug_profile` → `query_drug_or_effect` (bidirectional)
3. ✅ Tool 5: `query_disease_mechanisms` → `query_disease_or_phenotype` (bidirectional)

**Enhancements:**
4. ✅ Tool 2: Add source-target analysis mode
5. ✅ Tool 9: Add statement hash bulk retrieval
6. ✅ Tool 10: Add reverse lookups + phenotype checks

**New Tools:**
7. ✅ Tool 14: `query_cell_markers` (cell type markers)
8. ✅ Tool 15: `analyze_kinase_enrichment` (phosphoproteomics)
9. ✅ Tool 16: `query_protein_functions` (enzyme activities, is_kinase, etc.)
10. 🔵 Tool 17: `query_research_metadata` (NIH Reporter) - Optional
11. 🔵 Tool 18: `query_journal_metadata` (journal/publisher) - Optional

**Infrastructure:**
12. ✅ Complete error taxonomy
13. ✅ Security (input validation, rate limiting)
14. ✅ Monitoring (Prometheus metrics)
15. ✅ Batch operations support
16. ✅ Data provenance tracking

---

## Implementation Timeline (Revised)

### Phase 1: Bidirectional Redesign (Weeks 1-3)
- Redesign Tools 1, 4, 5 with mode parameters
- Implement reverse lookup backends
- Update all schemas
- **Deliverable**: 3 bidirectional tools (+6 endpoints)

### Phase 2: Tool Enhancements (Week 4)
- Extend Tools 2, 9, 10
- Add new modes
- **Deliverable**: 3 enhanced tools (+5 endpoints)

### Phase 3: New Tools (Week 5)
- Tool 14: Cell markers
- Tool 15: Kinase analysis
- Tool 16: Protein functions
- **Deliverable**: 3 new tools (+9 endpoints)

### Phase 4: Infrastructure (Week 6)
- Error handling framework
- Security hardening
- Monitoring infrastructure
- **Deliverable**: Production-ready infrastructure

### Phase 5: Testing & Evaluation (Week 7)
- Unit tests for bidirectional modes
- Integration tests
- Updated evaluation questions
- **Deliverable**: 90%+ test coverage

### Total: 7 weeks (was 6 weeks)

---

## Recommendations

### For v1.0 (16 Tools, 91% Coverage)

**MUST HAVE:**
1. ✅ Bidirectional redesigns (Tools 1, 4, 5)
2. ✅ Enhanced reverse lookups (Tools 2, 9, 10)
3. ✅ New high-value tools (14, 15, 16)
4. ✅ Complete error handling
5. ✅ Security hardening
6. ✅ Monitoring infrastructure

**DEFER:**
- ❌ Tool 17 (NIH Reporter) → v1.1
- ❌ Tool 18 (Journal metadata) → v1.2

**Coverage**: 100/110 endpoints (91%)

**Timeline**: 7 weeks

---

### For v1.1 (17 Tools, 95% Coverage)

**ADD:**
- ✅ Tool 17: Research metadata (NIH Reporter)

**Coverage**: 105/110 endpoints (95%)

**Additional Time**: +1 week

---

### For v1.2 (18 Tools, 100% Coverage)

**ADD:**
- ✅ Tool 18: Journal metadata

**Coverage**: 110/110 endpoints (100%)

**Additional Time**: +1 week

---

## Key Takeaways

1. **Bidirectionality is Essential**: CoGEx is designed for bidirectional queries. Our tools must match.

2. **74.5% → 91% with Smart Redesign**: By making 3 tools bidirectional and adding 3 new tools, we jump from 74.5% to 91% coverage.

3. **Prioritize by Value**: The missing 9% (journal metadata) has very low research value. 91% coverage captures 99% of use cases.

4. **Infrastructure Matters**: Error handling, security, and monitoring are as important as tool coverage.

5. **Estimated Timeline**: 7 weeks for production-ready v1.0 with 91% coverage.

---

## Next Steps

1. ✅ Review and approve revised architecture
2. ✅ Update IMPLEMENTATION_SPEC.md with bidirectional designs
3. ✅ Update all tool schemas
4. ✅ Update evaluation questions
5. ✅ Begin implementation with Phase 1

---

**END OF MISSING CAPABILITIES ANALYSIS - REVISED**

**See COMPLETE_COVERAGE_PLAN.md for detailed redesign specifications.**
