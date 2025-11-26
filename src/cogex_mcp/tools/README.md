# CoGEx MCP Tools

This directory contains the 16 compositional MCP tools that provide comprehensive access to the INDRA CoGEx knowledge graph.

## Purpose

These tool modules serve two critical purposes:

1. **Production Tool Handlers**: Each module contains the actual tool handler functions that are registered with the MCP server via `@mcp.tool()` decorators
2. **Test Fixtures**: Integration tests import these tool functions directly to validate end-to-end functionality

## Architecture

```
tools/
├── __init__.py              # Tool module registry
├── gene_feature.py          # Tool 1: Gene/Feature bidirectional queries
├── subnetwork.py            # Tool 2: Mechanistic subnetwork extraction
├── enrichment.py            # Tool 3: Gene set enrichment analysis
├── drug_effect.py           # Tool 4: Drug/side effect queries
├── disease_phenotype.py     # Tool 5: Disease/phenotype queries
├── pathway.py               # Tool 6: Pathway membership queries
├── cell_line.py             # Tool 7: Cell line data queries
├── clinical_trials.py       # Tool 8: Clinical trial queries
├── literature.py            # Tool 9: Literature/evidence queries
├── variants.py              # Tool 10: Genetic variant queries
├── identifier.py            # Tool 11: Identifier resolution
├── relationship.py          # Tool 12: Relationship checking
├── ontology.py              # Tool 13: Ontology hierarchy navigation
├── cell_marker.py           # Tool 14: Cell marker queries
├── kinase.py                # Tool 15: Kinase enrichment analysis
└── protein_function.py      # Tool 16: Protein function queries
```

## Tool Pattern

Each tool module follows a consistent pattern:

```python
from cogex_mcp.server import mcp
from cogex_mcp.schemas import ToolInputSchema
from cogex_mcp.adapters import get_adapter

@mcp.tool()
async def cogex_tool_name(query: ToolInputSchema) -> str:
    \"\"\"Tool description for LLM.\"\"\"

    # 1. Entity resolution (if needed)
    # 2. Backend query via adapter
    # 3. Response formatting (markdown/JSON)
    # 4. Error handling

    return formatted_response
```

## Integration with Server

The main server (`src/cogex_mcp/server.py`) imports this module, which triggers:

1. Tool module imports in `__init__.py`
2. `@mcp.tool()` decorators register handlers with FastMCP
3. Tools become available via MCP protocol

## Usage in Tests

Integration tests import tool functions directly:

```python
from cogex_mcp.tools.gene_feature import cogex_query_gene_or_feature

async def test_gene_query():
    query = GeneFeatureQuery(mode="gene_to_features", gene="TP53")
    result = await cogex_query_gene_or_feature(query)
    assert "TP53" in result
```

This allows end-to-end testing of:
- Tool input validation (Pydantic schemas)
- Entity resolution logic
- Backend adapter calls
- Response formatting
- Error handling

## Dependencies

Each tool depends on:
- **Schemas** (`cogex_mcp.schemas`): Input validation and type safety
- **Adapters** (`cogex_mcp.adapters`): Neo4j/REST backend abstraction
- **Entity Resolution** (`cogex_mcp.entity_resolution`): ID normalization
- **Formatters** (`cogex_mcp.formatters`): Response rendering

## Coverage

These 16 tools provide **91% coverage** of CoGEx capabilities:
- **Priority 1** (Tools 1-5): Core gene/disease/drug queries - 50% coverage
- **Priority 2** (Tools 6-10): Pathway/cell/literature queries - 25% coverage
- **Priority 3** (Tools 11-16): Utilities/specialized queries - 16% coverage

## Development Notes

### Adding a New Tool

1. Create `new_tool.py` in this directory
2. Implement handler with `@mcp.tool()` decorator
3. Add to `__init__.py` imports and `__all__`
4. Create schema in `schemas.py`
5. Add integration tests in `tests/integration/`

### Tool Testing Strategy

- **Unit tests**: Mock backend, test logic (not yet implemented)
- **Integration tests**: Real backends, validate E2E flow (in `tests/integration/`)
- **Manual testing**: Claude Desktop, test UX

### Known Issues

- Tests currently import tool functions directly (not via MCP protocol)
- This tests tool logic but not MCP serialization/deserialization
- Future: Add MCP client-based tests for protocol validation

## Historical Context

This tools directory was created during Phase 1-7 implementation to organize the 16 compositional tools. Previously, tool handlers were embedded directly in server files, making testing difficult.

The current structure enables:
- Clean separation of concerns
- Easy testing of individual tools
- Reusable tool handlers across server implementations
- Clear API boundaries

## Migration Notes

If you're updating old code:
- Old pattern: Tools embedded in `server.py`
- New pattern: Tools in separate modules with `@mcp.tool()` decorators
- All functionality preserved, just reorganized

Last updated: 2025-11-25
