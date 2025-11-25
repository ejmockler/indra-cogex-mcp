# INDRA CoGEx MCP Server

[![CI](https://github.com/ejmockler/indra-cogex-mcp/workflows/CI/badge.svg)](https://github.com/ejmockler/indra-cogex-mcp/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Model Context Protocol server providing unified access to the INDRA CoGEx biomedical knowledge graph—28+ databases, 110 API endpoints, accessible through 16 compositional, bidirectional tools.

## Overview

**What it does**: Connects AI agents to comprehensive biomedical knowledge spanning genes, diseases, drugs, pathways, variants, and clinical trials.

**Why it matters**: Instead of querying 28+ databases separately, use one MCP server with intelligent entity resolution, automatic fallback, and evidence-grounded results.

**How it works**: Dual backend (Neo4j + REST), bidirectional queries (gene→tissue AND tissue→genes), automatic caching, production-grade reliability.

## Installation

### Quick Start

```bash
# Install from GitHub
pip install git+https://github.com/ejmockler/indra-cogex-mcp.git

# Configure credentials
cp .env.example .env
# Edit .env - see Security section below

# Start server
cogex-mcp
```

## MCP Client Integration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Restart Claude Desktop. For Neo4j access (better performance), add `NEO4J_URL`, `NEO4J_USER`, `NEO4J_PASSWORD` to `env`.

### Cline (VSCode Extension)

Cline has built-in MCP support. Add to VSCode settings or Cline config:

```json
{
  "cline.mcpServers": {
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

**Use case**: Scientific literature review, drug discovery workflows, analyzing gene expression datasets during development.

### Zed Editor

Add to Zed's MCP settings (`~/.config/zed/settings.json`):

```json
{
  "context_servers": {
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

**Use case**: Real-time biomedical context while editing research code, inline pathway/disease queries.

### Cursor

Cursor supports MCP through its configuration. Add to Cursor settings:

```json
{
  "mcp": {
    "servers": {
      "indra-cogex": {
        "command": "cogex-mcp",
        "env": {
          "USE_REST_FALLBACK": "true",
          "REST_API_BASE": "https://discovery.indra.bio"
        }
      }
    }
  }
}
```

**Use case**: AI-assisted bioinformatics development, automated gene annotation in code comments.

### Continue.dev

Add to Continue config (`~/.continue/config.json`):

```json
{
  "mcpServers": [
    {
      "name": "indra-cogex",
      "command": "cogex-mcp",
      "env": {
        "USE_REST_FALLBACK": "true",
        "REST_API_BASE": "https://discovery.indra.bio"
      }
    }
  ]
}
```

**Use case**: Inline documentation generation with biomedical context, research code autocompletion.

### Local LLMs (Ollama + Python)

Use with any local LLM via Python:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Connect to MCP server
server_params = StdioServerParameters(
    command="cogex-mcp",
    env={
        "USE_REST_FALLBACK": "true",
        "REST_API_BASE": "https://discovery.indra.bio"
    }
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # Initialize
        await session.initialize()

        # List available tools
        tools = await session.list_tools()

        # Call tool
        result = await session.call_tool(
            "cogex_query_gene_or_feature",
            arguments={
                "mode": "gene_to_features",
                "gene": "TP53",
                "response_format": "json"
            }
        )
```

**Use case**: Custom research pipelines, automated hypothesis generation, local-first biomedical analysis.

### Why Use This MCP for Biomedical Research

**Most powerful for**:
- **Drug discovery AI agents**: Query drug-target-disease relationships across 28+ databases in one call
- **Scientific writing assistants**: Evidence-grounded citations, automated literature synthesis
- **Bioinformatics workflows**: Gene set enrichment, pathway analysis, variant interpretation integrated into code editors
- **Research automation**: Systematic reviews, hypothesis generation, dataset annotation
- **Local LLM research**: Privacy-preserving biomedical queries, offline analysis, custom research tools

**Key advantage**: Bidirectional queries mean you can start from any entity (gene, disease, drug, phenotype) and traverse the knowledge graph in both directions—forward and reverse lookups in one unified interface.

## Available Tools

### Core Discovery
| Tool | Function | Bidirectional |
|------|----------|---------------|
| `cogex_query_gene_or_feature` | Gene ↔ tissues, GO terms, domains, phenotypes | ✓ |
| `cogex_extract_subnetwork` | Graph traversal, mechanistic relationships, shared regulators | ✓ |
| `cogex_enrichment_analysis` | GSEA, pathway overrepresentation analysis | ✓ |
| `cogex_query_drug_or_effect` | Drug ↔ side effects, targets, indications | ✓ |
| `cogex_query_disease_or_phenotype` | Disease ↔ phenotypes, associated genes | ✓ |

### Specialized Queries
| Tool | Function |
|------|----------|
| `cogex_query_pathway` | Pathway membership & shared pathway discovery |
| `cogex_query_cell_line` | CCLE/DepMap cell line properties |
| `cogex_query_clinical_trials` | ClinicalTrials.gov search by disease/drug/gene |
| `cogex_query_literature` | PubMed/INDRA evidence retrieval |
| `cogex_query_variants` | GWAS catalog & DisGeNet variant associations |

### Utilities
| Tool | Function |
|------|----------|
| `cogex_resolve_identifiers` | Convert between ID systems (HGNC, Entrez, Ensembl, etc.) |
| `cogex_check_relationship` | Boolean validation of entity relationships |
| `cogex_get_ontology_hierarchy` | Navigate GO/Disease/Phenotype ontologies |
| `cogex_query_cell_markers` | Cell type marker gene discovery |
| `cogex_analyze_kinase_enrichment` | Phosphoproteomics kinase-substrate analysis |
| `cogex_query_protein_functions` | Enzyme activities & molecular function annotations |

**Coverage**: 100/110 API endpoints (91%) • All relationship tools support forward + reverse queries

## Example Usage

```python
# Comprehensive gene profile
cogex_query_gene_or_feature(mode="gene_to_features", gene="TP53", include_all=True)

# Tissue expression query (reverse direction)
cogex_query_gene_or_feature(mode="tissue_to_genes", tissue="brain")

# Drug side effect discovery
cogex_query_drug_or_effect(mode="side_effect_to_drugs", side_effect="nausea")

# Gene set enrichment
cogex_enrichment_analysis(
    analysis_type="continuous",
    ranked_genes={"BRCA1": 3.2, "TP53": 2.8, ...},
    source="reactome"
)

# Network analysis - find shared regulators
cogex_extract_subnetwork(mode="shared_upstream", genes=["IL6", "IL1B", "TNF"])

# Phosphoproteomics analysis
cogex_analyze_kinase_enrichment(phosphosites=["MAPK1_T185", "MAPK1_Y187"])
```

## Architecture

### Data Sources
28+ integrated databases: BGee, GO, Reactome, WikiPathways, ChEMBL, SIDER, DisGeNet, CCLE, DepMap, ClinicalTrials.gov, PubMed, CellMarker, GWAS Catalog, and more.

### Connection Strategy
- **Primary**: Direct Neo4j access via `indra_cogex.client` (<500ms simple queries)
- **Fallback**: REST API at discovery.indra.bio (public access, no credentials)
- **Automatic**: Graceful degradation, circuit breakers, intelligent caching

### Design Philosophy
- **Compositional**: 16 tools, not 110 endpoints—organized by biological questions
- **Bidirectional**: All relationship tools support forward + reverse queries
- **Evidence-grounded**: Every result traceable to source publications
- **LLM-optimized**: Clear semantics, actionable errors, character-limited responses
- **Production-ready**: Async, type-safe, cached, monitored

## Security

### Credential Configuration

Create `.env` from template:
```bash
cp .env.example .env
```

**Option A**: Neo4j + REST fallback (recommended)
```bash
NEO4J_URL=bolt://your-server:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
USE_REST_FALLBACK=true
```

**Option B**: REST only (no credentials needed)
```bash
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
```

The server validates credentials on startup and provides actionable error messages. Credentials never exposed in logs or errors.

## Development

### Requirements
- Python 3.10+ (3.12 recommended)
- Dependencies: `mcp==1.22.0`, `pydantic==2.12.4`, `neo4j==6.0.3`, `httpx==0.28.1`

### Development Setup
```bash
git clone https://github.com/ejmockler/indra-cogex-mcp.git
cd indra-cogex-mcp
pip install -e ".[dev]"

# Run tests
pytest tests/unit -v
pytest tests/integration -v  # Requires Neo4j credentials

# Run linting
ruff check src tests
ruff format src tests
mypy src
```

### CI/CD
- Multi-Python testing (3.10, 3.11, 3.12)
- 80% coverage target (Codecov)
- Security scanning (Bandit + Safety)
- Automated distribution builds

## Documentation

- **[IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)** - Complete technical specification, architecture, 7-week implementation plan
- **[TOOLS_CATALOG.md](./TOOLS_CATALOG.md)** - Copy-paste-ready MCP schemas for all 16 tools
- **[INDRA CoGEx Docs](https://github.com/gyorilab/indra_cogex)** - Upstream knowledge graph source
- **[API Reference](https://discovery.indra.bio/apidocs)** - REST API documentation

## Performance

- Simple queries: <500ms
- Complex analyses: <5s
- Memory baseline: <200MB
- Uptime: 99%+

## Citation

If you use INDRA CoGEx, please cite:

> Gyori BM, et al. (2023). INDRA CoGEx: An automatically assembled biomedical knowledge graph integrating causal mechanisms with non-causal contextual relations. *bioRxiv*.

## License

**This MCP Server**: MIT License

**INDRA CoGEx**: BSD-2-Clause License (Gyori Lab, Northeastern University)

---

**Version**: 2.0.0 • **Status**: Production-ready • **Coverage**: 91% (100/110 endpoints)
