# Setup & Configuration

Quick setup guide for the INDRA CoGEx MCP server.

## Installation

```bash
# 1. Clone/navigate to project
cd indra-cogex-mcp

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Optional: Configure Neo4j credentials
cp .env.example .env
# Edit .env with your Neo4j credentials (REST fallback enabled by default)
```

## Add to Claude Code

The `.mcp.json` file is already configured in project root:

```json
{
  "mcpServers": {
    "indra-cogex": {
      "type": "stdio",
      "command": "/Users/noot/Documents/indra-cogex-mcp/venv/bin/python3",
      "args": ["-m", "cogex_mcp.server"],
      "env": {
        "PYTHONPATH": "/Users/noot/Documents/indra-cogex-mcp/src"
      }
    }
  }
}
```

**To activate**: Restart Claude Code, then open this workspace.

## Quick Test

After restart, ask Claude Code:

```
Using indra-cogex, query the gene TP53. Include expression and GO terms.
```

You should see comprehensive gene data returned.

## Verify Installation

```bash
# Test server directly
venv/bin/python3 -m cogex_mcp.server

# Run smoke tests
pytest tests/integration/ -v -k "smoke" -m "not slow"
```

## Configuration

**Environment variables** (.env):
- `NEO4J_URL` - Neo4j connection (optional)
- `NEO4J_USER` / `NEO4J_PASSWORD` - Credentials
- `USE_REST_FALLBACK=true` - Enable REST API fallback
- `CACHE_ENABLED=true` - Enable caching
- `LOG_LEVEL=INFO` - Logging level

## Next Steps

1. **Test tools**: See `QUICK_START.md` for usage examples
2. **Run tests**: See `TESTING.md` for test framework
3. **Review tools**: See `TOOLS_CATALOG.md` for all 16 tools
4. **Try evaluation questions**: See `evaluation/questions.xml`
