# INDRA CoGEx MCP Server - Quick Start

**Status**: ✅ Phase 5 Complete - All 16 Tools Implemented (16/16)
**Version**: 2.0.0
**Date**: 2025-11-24
**Test Coverage**: 20/20 passing ✅
**Tool Coverage**: 100% (16/16 tools) - COMPLETE IMPLEMENTATION

## What's Implemented

### ✅ Complete Infrastructure
- **FastMCP Server** with lifespan management
- **Client Adapter** with circuit breaker and automatic fallback
- **Neo4j Client** with connection pooling (50 connections)
- **REST Client** with exponential backoff
- **Services Layer**: Cache, Entity Resolver, Formatter, Pagination

### ✅ Priority 1 Tools - Complete (5/5)

#### Tool 1: cogex_query_gene_or_feature
**5 Bidirectional Modes:**
1. `gene_to_features` - Gene → complete profile
2. `tissue_to_genes` - Tissue → genes expressed
3. `go_to_genes` - GO term → annotated genes
4. `domain_to_genes` - Protein domain → genes
5. `phenotype_to_genes` - Phenotype → associated genes

#### Tool 2: cogex_extract_subnetwork
**5 Graph Traversal Modes:**
1. `direct` - Direct edges (A→B)
2. `mediated` - Two-hop paths (A→X→B)
3. `shared_upstream` - Shared regulators (A←X→B)
4. `shared_downstream` - Shared targets (A→X←B)
5. `source_to_targets` - One source → multiple targets

#### Tool 3: cogex_enrichment_analysis
**4 Analysis Types:**
1. `discrete` - Fisher's exact test (overrepresentation)
2. `continuous` - GSEA with ranked genes
3. `signed` - Directional enrichment (up/down)
4. `metabolite` - Metabolite set enrichment

**6 Sources:** GO, Reactome, WikiPathways, INDRA-upstream/downstream, phenotype

#### Tool 4: cogex_query_drug_or_effect
**2 Bidirectional Modes:**
1. `drug_to_profile` - Drug → targets, indications, side effects, trials
2. `side_effect_to_drugs` - Side effect → drugs causing it

**Coverage:** 13 backend endpoints

#### Tool 5: cogex_query_disease_or_phenotype
**3 Query Modes:**
1. `disease_to_mechanisms` - Disease → genes, variants, phenotypes, drugs, trials
2. `phenotype_to_diseases` - Phenotype → associated diseases
3. `check_phenotype` - Boolean disease-phenotype check

**Coverage:** 9 backend endpoints

### ✅ Priority 2 Tools - Complete (5/5)

#### Tool 6: cogex_query_pathway
**4 Bidirectional Modes:**
1. `get_genes` - Pathway → genes in pathway
2. `get_pathways` - Gene → pathways containing gene
3. `find_shared` - Find shared pathways between genes
4. `check_membership` - Check if gene is in pathway

**Coverage:** Reactome, WikiPathways

#### Tool 7: cogex_query_cell_line
**4 Query Modes:**
1. `get_properties` - Cell line → mutations, CNAs, dependencies, expression
2. `get_mutated_genes` - Cell line → all mutated genes
3. `get_cell_lines_with_mutation` - Gene → cell lines with mutation
4. `check_mutation` - Check if gene is mutated in cell line

**Coverage:** CCLE, DepMap data

#### Tool 8: cogex_query_clinical_trials
**3 Query Modes:**
1. `get_for_drug` - Drug → clinical trials testing it
2. `get_for_disease` - Disease → clinical trials for condition
3. `get_by_id` - NCT ID → trial details

**Coverage:** ClinicalTrials.gov data

#### Tool 9: cogex_query_literature
**4 Query Modes:**
1. `get_statements_for_pmid` - PubMed ID → INDRA statements
2. `get_evidence_for_statement` - Statement hash → evidence snippets
3. `search_by_mesh` - MeSH terms → relevant statements
4. `get_statements_by_hashes` - Multiple hashes → statements

**Coverage:** PubMed, INDRA evidence

#### Tool 10: cogex_query_variants
**6 Query Modes:**
1. `get_for_gene` - Gene → associated variants (GWAS)
2. `get_for_disease` - Disease → associated variants
3. `get_for_phenotype` - Phenotype → associated variants
4. `variant_to_genes` - Variant (rsID) → associated genes
5. `variant_to_phenotypes` - Variant → associated phenotypes
6. `check_association` - Check if variant associated with gene/disease

**Coverage:** GWAS Catalog, DisGeNet

### ✅ Priority 3 Tools - Complete (6/6)

#### Tool 11: cogex_resolve_identifiers
**Purpose**: Identifier conversion between namespaces
- Convert between HGNC, UniProt, Ensembl, etc.
- Supports 1:many mappings
- Returns unmapped IDs separately

**Coverage:** 3 endpoints

#### Tool 12: cogex_check_relationship
**10 Relationship Types:**
1. gene_in_pathway - Is gene in pathway?
2. drug_target - Does drug target gene/protein?
3. drug_indication - Is drug indicated for disease?
4. drug_side_effect - Does drug cause side effect?
5. gene_disease - Is gene associated with disease?
6. disease_phenotype - Does disease have phenotype?
7. gene_phenotype - Is gene associated with phenotype?
8. variant_association - Is variant associated with trait?
9. cell_line_mutation - Does cell line have mutation?
10. cell_marker - Is gene a marker for cell type?

**Coverage:** 15 boolean validation endpoints

#### Tool 13: cogex_get_ontology_hierarchy
**3 Query Modes:**
1. parents - Navigate up ontology (ancestors)
2. children - Navigate down ontology (descendants)
3. both - Get complete hierarchy

**Features:** ASCII tree visualization, max depth control (1-5 levels)
**Coverage:** GO, HPO, MONDO ontologies

#### Tool 14: cogex_query_cell_markers
**3 Query Modes:**
1. get_markers - Cell type → marker genes
2. get_cell_types - Marker gene → cell types
3. check_marker - Boolean validation

**Coverage:** CellMarker database, tissue and species filters

#### Tool 15: cogex_analyze_kinase_enrichment
**Purpose**: Kinase enrichment from phosphoproteomics data
- Input: Phosphosite list (GENE_S123, GENE_T456, etc.)
- Output: Ranked kinases with p-values, substrates
- Statistical: Fisher's exact test with FDR correction

**Coverage:** PhosphoSitePlus, kinase substrate databases

#### Tool 16: cogex_query_protein_functions
**4 Query Modes:**
1. gene_to_activities - Gene → enzyme activities
2. activity_to_genes - Activity → genes (paginated)
3. check_activity - Boolean check for activity
4. check_function_types - Batch check kinase/phosphatase/TF

**Coverage:** EC numbers, enzyme classifications, function types

### 🎯 Common Features Across All Tools
- Dual format support (JSON/Markdown)
- Pagination (limit/offset)
- Character limit enforcement (25,000)
- Progress reporting
- Comprehensive error handling
- MCP-compliant annotations
- Entity resolution with caching

## Installation

### Prerequisites
- Python 3.10+ (recommended: 3.12)
- Optional: Neo4j with INDRA CoGEx data

### Setup

```bash
# 1. Navigate to project
cd indra-cogex-mcp

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env if you have Neo4j access
# Otherwise, REST fallback is enabled by default
```

## Running the Server

### stdio Mode (Default - for MCP clients)

```bash
# Run directly
python -m cogex_mcp.server

# Or using the installed command
cogex-mcp
```

### HTTP Mode (for testing/deployment)

```bash
# Set transport in .env:
# TRANSPORT=http
# HTTP_PORT=8000

python -m cogex_mcp.server
```

## Testing

### Run Unit Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_server.py -v

# With coverage
pytest tests/ --cov=cogex_mcp --cov-report=html
```

### Test with MCP Inspector

```bash
# Run inspector (automatically uses npx to install if needed)
npx @modelcontextprotocol/inspector venv/bin/python3 -m cogex_mcp.server

# Or with system Python
npx @modelcontextprotocol/inspector python3 -m cogex_mcp.server
```

This will:
1. Start the MCP Inspector proxy server on `http://localhost:6274`
2. Connect to your cogex-mcp server via stdio
3. Open your browser to test tools interactively
4. Display connection details including auth token

**Note**: The inspector provides a web UI to test all 5 query modes of Tool 1.

## Using Tool 1

### Example 1: Get Gene Profile (gene_to_features)

```json
{
  "mode": "gene_to_features",
  "gene": "TP53",
  "include_expression": true,
  "include_go_terms": true,
  "include_pathways": true,
  "include_diseases": true,
  "response_format": "markdown",
  "limit": 20,
  "offset": 0
}
```

**Expected Response:** Markdown-formatted gene profile with expression, GO terms, pathways, and disease associations.

### Example 2: Find Brain-Expressed Genes (tissue_to_genes)

```json
{
  "mode": "tissue_to_genes",
  "tissue": "brain",
  "response_format": "json",
  "limit": 50,
  "offset": 0
}
```

**Expected Response:** JSON list of genes with pagination metadata.

### Example 3: Find Kinase Genes (go_to_genes)

```json
{
  "mode": "go_to_genes",
  "go_term": "GO:0016301",
  "response_format": "markdown",
  "limit": 100,
  "offset": 0
}
```

**Expected Response:** Markdown list of genes annotated with "kinase activity".

## Architecture Highlights

### Connection Flow
```
MCP Client (Claude)
    ↓ stdio/HTTP
FastMCP Server
    ↓
Tool 1 (gene_feature.py)
    ↓
Entity Resolver → Cache → Client Adapter
    ↓
Circuit Breaker
    ↓
Neo4j (primary) ←→ REST API (fallback)
```

### Performance Features
- **Concurrent Queries**: Up to 10 simultaneous
- **Connection Pooling**: 50 Neo4j connections
- **LRU Cache**: 1000 entries, 1-hour TTL
- **Intelligent Truncation**: 25,000 character limit
- **Health Monitoring**: 5-minute intervals

## Configuration

### Key Environment Variables

```bash
# Backend Selection
NEO4J_URL=bolt://localhost:7687     # Optional: for best performance
NEO4J_PASSWORD=your_password        # Optional
USE_REST_FALLBACK=true              # Always available

# Performance
NEO4J_MAX_CONNECTION_POOL_SIZE=50
CACHE_ENABLED=true
CACHE_MAX_SIZE=1000
CHARACTER_LIMIT=25000

# Logging
LOG_LEVEL=INFO                      # DEBUG for development
LOG_FORMAT=json                     # or "text"
```

## Troubleshooting

### Server won't start

```bash
# Check Python version
python --version  # Should be 3.10+

# Reinstall dependencies
pip install -e ".[dev]" --force-reinstall

# Check logs
LOG_LEVEL=DEBUG python -m cogex_mcp.server
```

### "No backend available" error

**Solution:** Enable REST fallback in `.env`:
```bash
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
```

### Tests fail

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests individually
pytest tests/test_server.py::test_server_exists -v
```

## Next Steps

### Immediate
1. Test with MCP Inspector: `npx @modelcontextprotocol/inspector venv/bin/python3 -m cogex_mcp.server`
2. Verify all 16 tools function correctly with sample queries
3. Run integration tests against live backend

### Phase 6 (Evaluation & Optimization)
- Create comprehensive evaluation suite (10 complex questions)
- Performance profiling and optimization
- Load testing with concurrent queries
- Cache effectiveness analysis
- Documentation improvements
- Production deployment guide

## Development

### Code Structure

```
src/cogex_mcp/
├── server.py              # FastMCP server entry point
├── config.py              # Configuration management
├── constants.py           # Constants and enums
├── schemas.py             # Pydantic models (all 16 tools - 1,349 lines)
├── clients/
│   ├── adapter.py         # Unified client with fallback
│   ├── neo4j_client.py    # Neo4j connection pool
│   └── rest_client.py     # REST API client
├── services/
│   ├── cache.py           # LRU cache with TTL
│   ├── entity_resolver.py # Entity resolution
│   ├── formatter.py       # Response formatting
│   └── pagination.py      # Pagination helpers
└── tools/
    ├── gene_feature.py    # Tool 1 (5 modes) - Gene/feature queries
    ├── subnetwork.py      # Tool 2 (5 modes) - Graph traversal
    ├── enrichment.py      # Tool 3 (4 types) - GSEA
    ├── drug_effect.py     # Tool 4 (2 modes) - Drug queries
    ├── disease_phenotype.py  # Tool 5 (3 modes) - Disease queries
    ├── pathway.py         # Tool 6 (4 modes) - Pathway queries
    ├── cell_line.py       # Tool 7 (4 modes) - CCLE/DepMap
    ├── clinical_trials.py # Tool 8 (3 modes) - ClinicalTrials.gov
    ├── literature.py      # Tool 9 (4 modes) - PubMed/INDRA
    ├── variants.py        # Tool 10 (6 modes) - GWAS data
    ├── identifier.py      # Tool 11 - ID conversion
    ├── relationship.py    # Tool 12 (10 types) - Boolean checks
    ├── ontology.py        # Tool 13 (3 modes) - Hierarchy navigation
    ├── cell_marker.py     # Tool 14 (3 modes) - Cell markers
    ├── kinase.py          # Tool 15 - Kinase enrichment
    └── protein_function.py # Tool 16 (4 modes) - Enzyme activities
```

### Adding New Tools

1. Create `src/cogex_mcp/tools/your_tool.py`
2. Import from `cogex_mcp.server import mcp`
3. Decorate function with `@mcp.tool()`
4. Import in `server.py`
5. Add tests in `tests/`

## Support

- **Documentation**: See `IMPLEMENTATION_GUIDE.md` and `TOOLS_CATALOG.md`
- **Specifications**: Complete tool schemas in `TOOLS_CATALOG.md`
- **Architecture**: Detailed design in `IMPLEMENTATION_GUIDE.md`

## License

MIT License - See LICENSE file

---

**Built with engineering distinction**: Circuit breakers, connection pooling, intelligent caching, comprehensive error handling, and full MCP compliance.
