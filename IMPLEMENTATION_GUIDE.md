# INDRA CoGEx MCP Server - Implementation Guide

**Version**: 2.0.0-mcp-compliant
**Date**: 2025-11-24
**Status**: ✅ READY FOR IMPLEMENTATION
**Language**: Python 3.10+ with FastMCP
**Transport**: stdio (primary), Streamable HTTP (optional)

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/gyorilab/indra_cogex.git
cd indra_cogex && pip install -e . && cd ..

# Create project
mkdir cogex_mcp && cd cogex_mcp
pip install mcp pydantic neo4j httpx cachetools

# Run
python src/cogex_mcp/server.py
```

---

## Project Overview

### What We're Building

A production-grade MCP server exposing INDRA CoGEx (28+ biomedical databases, 110 REST endpoints) through **16 compositional, bidirectional tools** achieving **91% API coverage**.

### Why This Design

**Bidirectional Architecture**: CoGEx is inherently bidirectional (gene↔tissues, drug↔effects). Our tools match this design through mode parameters.

**Compositional over Comprehensive**: 16 well-designed tools beat 110 endpoint wrappers. Agents compose operations. Coverage: 100/110 endpoints (91%).

**Evidence-Grounded**: Every result traceable to publications. PubMed integration throughout.

### Success Metrics

- **Coverage**: 91% (100/110 endpoints) with 16 tools
- **Performance**: Simple queries <500ms, complex <5s
- **Evaluation**: 90%+ success on 10 biomedical questions
- **Quality**: 90%+ test coverage, full type hints

---

## Architecture

```
Claude/MCP Client
    ↓ MCP Protocol (JSON-RPC)
┌───────────────────────────────────────┐
│   CoGEx MCP Server (Python)           │
│                                       │
│  ┌─────────────────────────────────┐ │
│  │ Tools (16 compositional)        │ │
│  │ - Bidirectional modes           │ │
│  │ - Response formats (JSON/MD)    │ │
│  │ - Pagination & truncation       │ │
│  └──────────────┬──────────────────┘ │
│  ┌──────────────▼──────────────────┐ │
│  │ Services Layer                  │ │
│  │ - Entity resolution             │ │
│  │ - Response formatting           │ │
│  │ - Caching (LRU)                 │ │
│  └──────────────┬──────────────────┘ │
│  ┌──────────────▼──────────────────┐ │
│  │ Client Adapter                  │ │
│  │ Primary: indra_cogex.client     │ │
│  │ Fallback: REST API              │ │
│  └──────────────┬──────────────────┘ │
└─────────────────┼───────────────────┘
                  │
      ┌───────────┴──────────┐
      │                      │
   Neo4j DB          REST API
  (optimal)      (public fallback)
```

---

## Tech Stack

### Core Dependencies (Latest Versions)

```toml
[project]
name = "cogex-mcp"
version = "1.0.0"
requires-python = ">=3.10"

dependencies = [
    "mcp==1.22.0",                    # MCP SDK
    "pydantic==2.12.4",               # Validation
    "neo4j==6.0.3",                   # Neo4j driver
    "httpx==0.28.1",                  # Async HTTP
    "pydantic-settings==2.7.1",       # Config
    "cachetools==5.5.0",              # LRU cache
    "indra-cogex @ git+https://github.com/gyorilab/indra_cogex.git@main",
]

[project.optional-dependencies]
dev = [
    "pytest==9.0.1",
    "pytest-asyncio==0.25.2",
    "pytest-cov==6.0.0",
    "ruff==0.8.4",
    "mypy==1.13.0",
]
```

### Project Structure

```
cogex_mcp/
├── pyproject.toml
├── README.md
├── LICENSE
├── .env.example
├── src/
│   └── cogex_mcp/
│       ├── __init__.py
│       ├── server.py              # MCP server entry point
│       ├── config.py               # Settings
│       ├── constants.py            # CHARACTER_LIMIT, etc.
│       ├── schemas.py              # Pydantic models
│       ├── tools/                  # Tool implementations (16 files)
│       │   ├── gene_feature.py     # Tool 1: bidirectional gene queries
│       │   ├── subnetwork.py       # Tool 2: graph traversal
│       │   ├── enrichment.py       # Tool 3: GSEA
│       │   └── ...
│       ├── services/
│       │   ├── entity_resolver.py  # ID resolution
│       │   ├── formatter.py        # JSON/Markdown formatting
│       │   ├── pagination.py       # Pagination helpers
│       │   └── cache.py            # LRU caching
│       └── clients/
│           ├── adapter.py          # Unified interface
│           ├── neo4j_client.py     # Primary backend
│           └── rest_client.py      # Fallback backend
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluations/
│       └── qa_pairs.xml
└── docs/
```

---

## The 16 Tools (MCP-Compliant)

### Tool Naming Convention

**Format**: `cogex_{action}_{resource}`
**Examples**: `cogex_query_gene_context`, `cogex_extract_subnetwork`

**Rationale**: Prefix prevents conflicts with other bio MCP servers.

### Tool Categories

**Priority 1: Core Discovery (5 tools)**
1. `cogex_query_gene_or_feature` - Bidirectional gene↔feature queries
2. `cogex_extract_subnetwork` - Graph traversal & mechanisms
3. `cogex_enrichment_analysis` - GSEA, pathway enrichment
4. `cogex_query_drug_or_effect` - Bidirectional drug↔effect queries
5. `cogex_query_disease_or_phenotype` - Bidirectional disease↔phenotype

**Priority 2: Specialized (5 tools)**
6. `cogex_query_pathway` - Pathway membership
7. `cogex_query_cell_line` - CCLE/DepMap data
8. `cogex_query_clinical_trials` - ClinicalTrials.gov
9. `cogex_query_literature` - PubMed/evidence
10. `cogex_query_variants` - GWAS, genetic variants

**Priority 3: Utilities & Advanced (6 tools)**
11. `cogex_resolve_identifiers` - ID conversion
12. `cogex_check_relationship` - Boolean validators
13. `cogex_get_ontology_hierarchy` - Ontology navigation
14. `cogex_query_cell_markers` - Cell type markers
15. `cogex_analyze_kinase_enrichment` - Phosphoproteomics
16. `cogex_query_protein_functions` - Enzyme activities, is_kinase, etc.

**Coverage**: 100/110 endpoints (91%)

---

## MCP-Specific Requirements

### 1. Response Format Support ⭐ CRITICAL

**All tools must support dual formats:**

```python
class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"  # Human-readable (default)
    JSON = "json"          # Machine-readable

# Add to every tool schema:
response_format: ResponseFormat = ResponseFormat.MARKDOWN
```

**Markdown format**:
- Headers, lists, formatting
- Human-readable timestamps
- Display names with IDs in parentheses
- Omit verbose metadata

**JSON format**:
- Complete structured data
- All fields and metadata
- Consistent field names

**Implementation**:
```python
if params.response_format == ResponseFormat.MARKDOWN:
    return format_as_markdown(data)
else:
    return json.dumps(data, indent=2)
```

### 2. Character Limits ⭐ CRITICAL

```python
# constants.py
CHARACTER_LIMIT = 25000  # Max response size

# In every tool:
if len(response_text) > CHARACTER_LIMIT:
    response_text = truncate_intelligently(response_text)
    response_text += "\n\n⚠️ Response truncated. Use pagination or filters."
```

### 3. Pagination Metadata ⭐ HIGH

```python
class PaginatedResponse(BaseModel):
    items: List[Any]
    total_count: int
    count: int              # Items in this response
    offset: int
    limit: int
    has_more: bool
    next_offset: Optional[int]  # Only if has_more
```

### 4. Tool Annotations ⭐ HIGH

```python
# Every tool must specify:
annotations = {
    "readOnlyHint": bool,      # Doesn't modify data
    "destructiveHint": bool,   # May perform destructive updates
    "idempotentHint": bool,    # Same input → same output
    "openWorldHint": bool,     # Interacts with external entities
}

# Example for query_gene_or_feature:
annotations = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
```

### 5. Error Messages ⭐ HIGH

**Actionable, not exposing internals:**

```python
# Good:
"Gene 'TP' matches multiple: TP53 (hgnc:11998), TP63 (hgnc:15979).
Specify using format 'hgnc:ID'."

# Bad:
"AmbiguousIdentifierError: Multiple matches in database query"
```

**With next-step suggestions:**

```python
"No variants found for gene 'BRCA1'.
Try:
- Verify gene exists: cogex_query_gene_context(gene='BRCA1')
- Check spelling
- Use HGNC ID: ('hgnc', '1100')"
```

---

## Bidirectional Tool Pattern

### Example: Tool 1 (Gene ↔ Features)

```python
class GeneFeatureQuery(BaseModel):
    mode: QueryMode  # Determines direction

    # Entity (depends on mode)
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

    # MCP-required
    response_format: ResponseFormat = ResponseFormat.MARKDOWN
    limit: int = 20
    offset: int = 0

class QueryMode(str, Enum):
    GENE_TO_FEATURES = "gene_to_features"      # Forward: gene → all features
    TISSUE_TO_GENES = "tissue_to_genes"        # Reverse: tissue → genes
    GO_TO_GENES = "go_to_genes"                # Reverse: GO term → genes
    DOMAIN_TO_GENES = "domain_to_genes"        # Reverse: domain → genes
    PHENOTYPE_TO_GENES = "phenotype_to_genes"  # Reverse: phenotype → genes

# Tool registration:
@mcp.tool(annotations={...})
async def cogex_query_gene_or_feature(params: GeneFeatureQuery) -> str:
    if params.mode == QueryMode.GENE_TO_FEATURES:
        return await gene_to_features(params)
    elif params.mode == QueryMode.TISSUE_TO_GENES:
        return await tissue_to_genes(params)
    # ... etc
```

**Why Bidirectional?**
- CoGEx is natively bidirectional
- Covers 6 endpoints with 1 tool (DRY)
- Natural user queries ("genes in brain", "tissues for TP53")
- Consistent interface pattern

---

## Implementation Phases

### Week 0: Pre-Implementation (NEW)
**Deliverables**: Updated specs, finalized decisions

- [ ] Finalize server naming: `cogex_mcp`
- [ ] Finalize tool prefix: `cogex_` (all tools)
- [ ] Finalize transport: Streamable HTTP (primary)
- [ ] Create shared formatters (JSON/Markdown)
- [ ] Create pagination builders
- [ ] Create truncation utilities
- [ ] Update all tool schemas with MCP features
- [ ] Document tool annotations (all 16 tools)

### Week 1: Foundation
**Deliverables**: Working server skeleton, infrastructure

- [ ] Project setup (pyproject.toml, structure)
- [ ] Configuration management (Pydantic Settings)
- [ ] Client adapter (Neo4j primary, REST fallback)
- [ ] Entity resolver (ID conversion)
- [ ] Caching layer (LRU)
- [ ] Shared formatters (JSON/Markdown)
- [ ] Pagination helpers
- [ ] Truncation logic (CHARACTER_LIMIT)
- [ ] MCP server scaffold (empty tool registry)
- [ ] Basic error taxonomy

### Weeks 2-3: Priority 1 Tools (Core Discovery)
**Deliverables**: 5 essential tools, 60% coverage

**Tool 1**: `cogex_query_gene_or_feature` (bidirectional)
- [ ] 5 modes implemented
- [ ] Response formats (JSON/Markdown)
- [ ] Pagination
- [ ] Annotations
- [ ] Unit tests

**Tool 2**: `cogex_extract_subnetwork`
- [ ] 5 modes (direct, mediated, shared_up, shared_down, source_to_targets)
- [ ] Evidence inclusion
- [ ] Tissue/GO filters
- [ ] Unit tests

**Tool 3**: `cogex_enrichment_analysis`
- [ ] 4 analysis types (discrete, continuous, signed, metabolite)
- [ ] Multiple sources (GO, Reactome, INDRA)
- [ ] Background gene support
- [ ] Unit tests

**Tool 4**: `cogex_query_drug_or_effect` (bidirectional)
- [ ] 2 modes (drug_to_profile, side_effect_to_drugs)
- [ ] Complete drug profiles
- [ ] Unit tests

**Tool 5**: `cogex_query_disease_or_phenotype` (bidirectional)
- [ ] 3 modes (disease_to_mechanisms, phenotype_to_diseases, check_phenotype)
- [ ] Comprehensive disease data
- [ ] Unit tests

### Week 4: Priority 2 Tools (Specialized)
**Deliverables**: 5 specialized tools, 80% coverage

**Tools 6-10**: Pathway, Cell Line, Trials, Literature, Variants
- [ ] All with response formats
- [ ] All with pagination
- [ ] All with annotations
- [ ] Integration tests

### Week 5: Priority 3 Tools (Utilities & Advanced)
**Deliverables**: 6 utility/advanced tools, 91% coverage

**Tools 11-16**: Identifiers, Relationships, Ontology, Cell Markers, Kinase, Protein Functions
- [ ] All MCP-compliant
- [ ] Full test coverage

### Week 6: Testing & Polish
**Deliverables**: Production-ready server

- [ ] Integration tests (Neo4j + REST)
- [ ] Error handling refinement
- [ ] Performance optimization
- [ ] Security hardening (input validation, rate limiting)
- [ ] Documentation

### Week 7: Evaluation
**Deliverables**: Validated server, evaluation results

- [ ] Create 10 qa_pair evaluations (XML format)
- [ ] Run evaluation suite
- [ ] Achieve 90%+ success rate
- [ ] Performance benchmarking
- [ ] Final polish

**Total: 7 weeks + 1 week buffer = 8 weeks to production**

---

## Configuration

### Environment Variables

```bash
# .env
# Neo4j (optional, best performance)
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

# MCP Server
MCP_SERVER_NAME=cogex_mcp
TRANSPORT=http              # "http" or "stdio"
HTTP_HOST=0.0.0.0
HTTP_PORT=3000

# Performance
CHARACTER_LIMIT=25000
QUERY_TIMEOUT_MS=5000

# Logging
LOG_LEVEL=INFO
```

### Transport Configuration

**stdio (Recommended - Primary):**
```python
# For local integration with MCP clients
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cogex_mcp")

# ... register tools ...

if __name__ == "__main__":
    mcp.run()  # Default: stdio transport
```

**Streamable HTTP (Optional - Deployment):**
```python
# For production web deployment
if __name__ == "__main__":
    mcp.run(transport="streamable_http", port=8000)

# Or configure in environment:
# TRANSPORT=http
# HTTP_PORT=8000
```

---

## Code Quality Standards

### Composability & Reusability

**Extract common patterns:**

```python
# services/formatter.py
def format_gene_info(gene: GeneNode, format: ResponseFormat) -> str:
    """Shared formatter used by multiple tools"""
    if format == ResponseFormat.MARKDOWN:
        return f"## {gene.name} ({gene.curie})\n{gene.description}"
    else:
        return gene.model_dump_json(indent=2)

# services/pagination.py
def paginate_response(items, total, offset, limit):
    """Shared pagination wrapper"""
    return PaginatedResponse(
        items=items,
        total_count=total,
        count=len(items),
        offset=offset,
        limit=limit,
        has_more=total > offset + len(items),
        next_offset=offset + len(items) if total > offset + len(items) else None
    )
```

**Never duplicate code** - If logic appears twice, extract it.

### Type Safety

```python
# Use Pydantic everywhere
class GeneNode(BaseModel):
    name: str
    curie: str
    namespace: str
    identifier: str
    description: Optional[str] = None

# Explicit return types
async def resolve_gene(identifier: str | Tuple[str, str]) -> GeneNode:
    ...
```

### Error Handling

```python
class CoGExError(Exception):
    """Base for all errors"""
    pass

class EntityNotFoundError(CoGExError):
    def __init__(self, entity: str, suggestions: List[str]):
        self.entity = entity
        self.suggestions = suggestions
        super().__init__(self._message())

    def _message(self) -> str:
        msg = f"Entity '{self.entity}' not found."
        if self.suggestions:
            msg += f" Did you mean: {', '.join(self.suggestions)}?"
        return msg
```

---

## Evaluation Format

**qa_pair XML (MCP-Builder Standard):**

```xml
<evaluation>
  <qa_pair>
    <question>What genes are mutated in lung cancer cell lines (CCLE) and what drugs target the top 3 most mutated genes? List drug names only, comma-separated, alphabetically.</question>
    <answer>afatinib, erlotinib, gefitinib, osimertinib, trametinib</answer>
  </qa_pair>

  <qa_pair>
    <question>How many pathways are shared by all three genes: BRCA1, BRCA2, PALB2?</question>
    <answer>12</answer>
  </qa_pair>

  <!-- 8 more qa_pairs -->
</evaluation>
```

**Requirements:**
- Read-only operations only
- Single, verifiable answer
- Complex (multi-tool) questions
- Deterministic (stable over time)

---

## Key Design Decisions

### 1. Python over TypeScript
**Rationale**: Direct access to `indra_cogex.client` library. Neo4j performance benefits. Team familiarity.

### 2. stdio Primary Transport
**Rationale**: Server accesses CoGEx via Python library (local), not remote HTTP API. stdio is appropriate for library-based integrations. Streamable HTTP available for deployment flexibility.

### 3. 16 Tools over 110
**Rationale**: Compositional > comprehensive. Agents compose operations. Better discoverability.

### 4. Bidirectional Architecture
**Rationale**: Matches CoGEx design. Covers 6 endpoints per tool. Natural query patterns.

### 5. Neo4j Primary, REST Fallback
**Rationale**: Performance + public access. Graceful degradation. Flexible deployment.

---

## Success Criteria

### Functional
- ✅ All 16 tools implemented and tested
- ✅ 90%+ success on evaluation suite (10 questions)
- ✅ Both Neo4j and REST backends work
- ✅ All MCP features (response formats, pagination, annotations)

### Performance
- ✅ Simple queries < 500ms
- ✅ Complex queries < 5s
- ✅ Memory < 200MB baseline
- ✅ No responses exceed CHARACTER_LIMIT

### Quality
- ✅ 90%+ test coverage
- ✅ Full type hints (mypy passes)
- ✅ No critical security vulnerabilities
- ✅ Comprehensive documentation

---

## Common Patterns

### Entity Resolution
```python
# Accept flexible inputs
"TP53"                   → resolve_gene() → GeneNode
"hgnc:11998"            → resolve_gene() → GeneNode
("hgnc", "11998")       → resolve_gene() → GeneNode
```

### Response Formatting
```python
# Always support both formats
data = fetch_data()
if params.response_format == ResponseFormat.MARKDOWN:
    return format_markdown(data)
else:
    return json.dumps(data, indent=2)
```

### Pagination
```python
# Always include metadata
return paginate_response(
    items=results[:params.limit],
    total=total_count,
    offset=params.offset,
    limit=params.limit
)
```

### Truncation
```python
# Always check CHARACTER_LIMIT
response = generate_response(data)
if len(response) > CHARACTER_LIMIT:
    response = truncate_with_message(response)
```

---

## Next Steps

1. **Review this guide** - Ensure alignment with team
2. **Set up development environment** - Python 3.10+, dependencies
3. **Week 0 tasks** - Finalize naming, create shared utilities
4. **Begin Week 1** - Foundation implementation
5. **Weekly reviews** - Track progress against timeline

---

## Resources

- **INDRA CoGEx**: https://github.com/gyorilab/indra_cogex
- **MCP Protocol**: https://modelcontextprotocol.io
- **API Docs**: https://discovery.indra.bio/apidocs
- **This Repo**: Tools catalog, evaluation questions, examples

---

**This is your single source of truth for implementation. All decisions justified. All patterns specified. Ready to build.**
