# INDRA CoGEx MCP Server

[![CI](https://github.com/ejmockler/indra-cogex-mcp/workflows/CI/badge.svg)](https://github.com/ejmockler/indra-cogex-mcp/actions)
[![codecov](https://codecov.io/gh/ejmockler/indra-cogex-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/ejmockler/indra-cogex-mcp)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Production-grade Model Context Protocol (MCP) server providing unified access to INDRA CoGEx biomedical knowledge graph (28+ databases, 110 API endpoints) through 16 compositional, bidirectional tools.

## Quick Links

- **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** - Complete technical specification and 7-week implementation plan
- **[TOOLS_CATALOG.md](./TOOLS_CATALOG.md)** - Detailed MCP-compliant schemas for all 16 tools
- **Repository**: https://github.com/gyorilab/indra_cogex (INDRA CoGEx source)
- **API Documentation**: https://discovery.indra.bio/apidocs

## Installation

### Install from GitHub

```bash
# Install directly from GitHub
pip install git+https://github.com/ejmockler/indra-cogex-mcp.git

# Or install in editable mode for development
git clone https://github.com/ejmockler/indra-cogex-mcp.git
cd indra-cogex-mcp
pip install -e ".[dev]"
```

### Configure Credentials

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials (see Security section below)
# Option A: Neo4j direct access (recommended)
# Option B: REST API only (public access)
```

### Run the Server

```bash
# Start MCP server
cogex-mcp

# Or run with Python module
python -m cogex_mcp.server
```

See [Security & Credential Management](#security--credential-management) section for detailed credential setup.

### Configure with Claude Desktop

Add to your Claude Desktop MCP settings file:

**macOS/Linux**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "indra-cogex": {
      "command": "cogex-mcp",
      "env": {
        "NEO4J_URL": "bolt://your-server:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password",
        "USE_REST_FALLBACK": "true"
      }
    }
  }
}
```

Or use REST-only mode (no credentials required):

```json
{
  "mcpServers": {
    "indra-cogex": {
      "command": "cogex-mcp",
      "env": {
        "USE_REST_FALLBACK": "true",
        "REST_API_BASE": "https://discovery.indra.bio"
      }
    }
  }
}
```

Restart Claude Desktop to load the server.

## What This Provides

### 16 High-Leverage Tools

**Priority 1 (Core Discovery):**
1. `cogex_query_gene_or_feature` - Bidirectional gene ↔ features (tissues, GO terms, domains, phenotypes)
2. `cogex_extract_subnetwork` - Graph traversal & mechanistic relationships
3. `cogex_enrichment_analysis` - Gene set enrichment (GSEA, pathway analysis)
4. `cogex_query_drug_or_effect` - Bidirectional drug ↔ effects/targets
5. `cogex_query_disease_or_phenotype` - Bidirectional disease ↔ phenotypes

**Priority 2 (Specialized):**
6. `cogex_query_pathway` - Pathway membership & shared pathway analysis
7. `cogex_query_cell_line` - CCLE/DepMap cell line properties
8. `cogex_query_clinical_trials` - ClinicalTrials.gov search
9. `cogex_query_literature` - PubMed/INDRA evidence retrieval
10. `cogex_query_variants` - GWAS & variant associations

**Priority 3 (Utilities & Advanced):**
11. `cogex_resolve_identifiers` - ID system conversion
12. `cogex_check_relationship` - Boolean relationship validation
13. `cogex_get_ontology_hierarchy` - Ontology navigation
14. `cogex_query_cell_markers` - Cell type marker queries
15. `cogex_analyze_kinase_enrichment` - Phosphoproteomics analysis
16. `cogex_query_protein_functions` - Enzyme activities & function types

### Data Coverage

- **28+ Databases**: BGee, GO, Reactome, WikiPathways, ChEMBL, SIDER, DisGeNet, CCLE, DepMap, ClinicalTrials.gov, PubMed, CellMarker, and more
- **100/110 REST Endpoints**: 91% coverage through 16 bidirectional tools
- **Graph Operations**: Subnetwork extraction, path finding, relationship discovery
- **Evidence-Grounded**: Every assertion traceable to publications
- **Bidirectional Architecture**: Forward + reverse lookups (gene→tissue AND tissue→genes)

## Technical Stack

### Dependencies (Latest Versions - 2025-11-24)

```toml
dependencies = [
    "mcp==1.22.0",                    # MCP SDK
    "pydantic==2.12.4",               # Data validation
    "neo4j==6.0.3",                   # Neo4j driver
    "httpx==0.28.1",                  # Async HTTP
    "pydantic-settings==2.7.1",       # Config management
    "cachetools==5.5.0",              # Caching
    "indra-cogex @ git+https://github.com/gyorilab/indra_cogex.git@main",
]

[project.optional-dependencies]
dev = [
    "pytest==9.0.1",
    "pytest-asyncio==0.25.2",
    "pytest-cov==6.0.0",
    "pytest-mock==3.14.0",
    "ruff==0.8.4",
    "mypy==1.13.0",
]
```

**Python**: 3.10+ (Recommended: 3.12)

## Architecture Highlights

### Connection Strategy
- **Primary**: Direct Neo4j access via `indra_cogex.client` (best performance)
- **Fallback**: REST API at discovery.indra.bio (public access)
- **Graceful Degradation**: Automatic fallback if Neo4j unavailable

### Design Principles
- **Compositional Tools**: 16 tools cover 91% of CoGEx capabilities (100/110 endpoints)
- **Bidirectional Architecture**: All relationship tools support forward + reverse queries
- **Workflow-Oriented**: Organized by biological questions, not database schema
- **MCP-Compliant**: Response formats (JSON/Markdown), pagination, tool annotations
- **LLM-Friendly**: Clear semantics, comprehensive descriptions, actionable errors
- **Production-Ready**: Caching, async, error handling, type safety, character limits

### Performance Targets
- Simple queries: <500ms
- Complex analyses: <5s
- Memory footprint: <200MB baseline

## Security & Credential Management

This MCP server follows [MCP security best practices](https://modelcontextprotocol.io) for credential management.

### Setup Credentials

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure your credentials** in `.env`:

   **Option A: Neo4j Direct Access (Recommended for Best Performance)**
   ```bash
   NEO4J_URL=bolt://your-server:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password_here
   USE_REST_FALLBACK=true  # Fallback if Neo4j unavailable
   ```

   **Option B: REST API Only (Public Access)**
   ```bash
   USE_REST_FALLBACK=true
   REST_API_BASE=https://discovery.indra.bio
   ```

3. **Verify security:**
   - Ensure `.env` is listed in `.gitignore` (already configured)
   - NEVER commit `.env` files to version control
   - Use `.env.example` as a template only (no real credentials)

### Credential Loading

The server uses `python-dotenv` for secure environment variable management:

- Credentials loaded from `.env` file in project root
- Falls back to system environment variables
- Validates required credentials on startup
- Provides clear error messages if credentials missing

### Error Messages

If credentials are missing, you'll see helpful error messages:

```
No backend configured for INDRA CoGEx MCP server.

Please configure credentials using ONE of these methods:

Option 1 - Neo4j Direct Access (Best Performance):
  1. Copy .env.example to .env
  2. Set NEO4J_URL=bolt://your-server:7687
  3. Set NEO4J_USER=neo4j
  4. Set NEO4J_PASSWORD=your_password

Option 2 - REST API Fallback (Public Access):
  1. Set USE_REST_FALLBACK=true
  2. Set REST_API_BASE=https://discovery.indra.bio
```

### Security Best Practices

Following MCP security guidelines:

- **API Keys in Environment Variables**: All credentials stored in `.env` files, never in code
- **Validation on Startup**: Server validates credentials before accepting requests
- **Clear Error Messages**: Actionable feedback when authentication fails
- **Input Validation**: Pydantic schemas validate all inputs
- **No Credential Exposure**: Internal errors never expose credentials to clients

## Quick Start (For Agents)

Two authoritative documents provide everything needed for implementation:

### **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** - The Complete Specification

1. **System Architecture** - Component diagrams, connection strategies
2. **Tool Specifications** - All 16 tools with mode parameters
3. **Data Schemas** - Pydantic models for all data types
4. **MCP Compliance** - Response formats, pagination, character limits, annotations
5. **Implementation Guidelines** - 7-week phased plan, project structure
6. **Testing Strategy** - Unit, integration, and evaluation tests
7. **Evaluation Framework** - 10 complex biomedical questions
8. **Deployment Guide** - Local, Docker, Claude configuration

### **[TOOLS_CATALOG.md](./TOOLS_CATALOG.md)** - Copy-Paste-Ready Schemas

- Complete input/output schemas for all 16 tools
- MCP-compliant Pydantic models
- Tool annotations and descriptions
- Backend endpoint mappings
- Implementation checklist per tool

## Implementation Checklist

### Week 1: Foundation
- [ ] Project structure & configuration
- [ ] Client adapter pattern (Neo4j + REST)
- [ ] Entity resolver & caching
- [ ] MCP server scaffold with formatter/pagination services

### Weeks 2-4: Priority 1 Tools (Core Discovery)
- [ ] Tool 1: cogex_query_gene_or_feature (5 modes)
- [ ] Tool 2: cogex_extract_subnetwork (5 modes)
- [ ] Tool 3: cogex_enrichment_analysis (4 modes)
- [ ] Tool 4: cogex_query_drug_or_effect (2 modes)
- [ ] Tool 5: cogex_query_disease_or_phenotype (3 modes)

### Weeks 5-6: Priority 2-3 Tools (Specialized + Utilities)
- [ ] Tools 6-10: Pathway, cell lines, trials, literature, variants
- [ ] Tools 11-16: Identifiers, relationships, ontology, markers, kinases, functions

### Week 7: Integration & Deployment
- [ ] Run evaluation suite (10 questions)
- [ ] Performance optimization & caching
- [ ] Documentation & examples
- [ ] Claude configuration & deployment

**Estimated Timeline**: 7 weeks for full implementation

## Key Features

### For AI Agents
- **Unified Interface**: One MCP server for 28+ biomedical databases
- **Smart Resolution**: Flexible inputs (symbols, IDs, CURIEs)
- **Evidence Tracking**: Every result includes source & evidence counts
- **Error Recovery**: Clear messages with actionable suggestions

### For Researchers
- **Comprehensive**: Gene expression, pathways, diseases, drugs, variants, trials
- **Graph-Native**: Subnetwork extraction, path finding, relationship discovery
- **Statistical**: Enrichment analysis (GSEA, overrepresentation)
- **Production-Grade**: Built on Harvard/Northeastern research infrastructure

## Example Queries

```python
# "What do we know about TP53?"
cogex_query_gene_or_feature(
    mode="gene_to_features",
    gene="TP53",
    include_all=True
)

# "What genes are expressed in brain tissue?"
cogex_query_gene_or_feature(
    mode="tissue_to_genes",
    tissue="brain"
)

# "Find drugs that cause nausea"
cogex_query_drug_or_effect(
    mode="side_effect_to_drugs",
    side_effect="nausea"
)

# "Run GSEA on these 50 differentially expressed genes"
cogex_enrichment_analysis(
    analysis_type="continuous",
    ranked_genes={gene: log_fc for gene, log_fc in results},
    source="reactome"
)

# "Find shared regulators of inflammatory cytokines"
cogex_extract_subnetwork(
    mode="shared_upstream",
    genes=["IL6", "IL1B", "TNF"]
)

# "What kinases phosphorylate these sites?"
cogex_analyze_kinase_enrichment(
    phosphosites=["MAPK1_T185", "MAPK1_Y187", "AKT1_S473"]
)
```

## Success Metrics

- **Coverage**: 16 tools covering 100/110 endpoints (91%)
- **Bidirectionality**: All relationship tools support forward + reverse queries
- **Performance**: Simple <500ms, complex <5s
- **Reliability**: 99%+ uptime, graceful degradation (Neo4j → REST fallback)
- **Evaluation**: 90%+ success on 10 complex test questions
- **Quality**: 90%+ test coverage, full type hints, MCP-compliant

## Documentation Structure

```
/
├── README.md                      # This file - project overview
├── IMPLEMENTATION_GUIDE.md        # Complete technical specification & 7-week plan
├── TOOLS_CATALOG.md               # Copy-paste-ready MCP schemas for all 16 tools
├── pyproject.toml                 # Dependencies & configuration
├── .env.example                   # Environment template
├── archive/                       # Superseded analysis documents
│   ├── IMPLEMENTATION_SPEC.md     # Original spec (replaced by IMPLEMENTATION_GUIDE)
│   ├── COMPLETE_COVERAGE_PLAN.md  # Bidirectional redesign analysis
│   ├── MISSING_CAPABILITIES.md    # Gap analysis
│   └── MCP_BUILDER_ASSESSMENT.md  # MCP compliance assessment
├── src/cogex_mcp/                # Implementation
├── tests/                         # Unit, integration, eval tests
└── docs/                          # Additional documentation
```

## License

This project: MIT License (or your choice)

INDRA CoGEx: BSD-2-Clause License
- Repository: https://github.com/gyorilab/indra_cogex
- Maintained by: Gyori Lab, Northeastern University

## Citation

If you use INDRA CoGEx, please cite:

> Gyori BM, et al. (2023). INDRA CoGEx: An automatically assembled biomedical knowledge graph integrating causal mechanisms with non-causal contextual relations. *bioRxiv*.

## Next Steps

1. **Read** [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) for 7-week implementation plan
2. **Reference** [TOOLS_CATALOG.md](./TOOLS_CATALOG.md) for copy-paste-ready schemas
3. **Set up** Python 3.12 environment
4. **Install** dependencies: `mcp==1.22.0`, `pydantic==2.12.4`, `indra_cogex`
5. **Implement** Week 1 foundation, then Priority 1 tools (weeks 2-4)
6. **Test** against evaluation questions (week 7)
7. **Deploy** with Claude or other MCP clients

---

**Status**: Implementation-ready specification with complete MCP-compliant schemas
**Version**: 2.0.0 (Bidirectional Architecture)
**Last Updated**: 2025-11-24
**Coverage**: 100/110 endpoints (91%) via 16 tools

For detailed schemas and implementation guidance, see [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md) and [TOOLS_CATALOG.md](./TOOLS_CATALOG.md).
