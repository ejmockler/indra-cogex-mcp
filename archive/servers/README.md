# Archived Server Files

This directory contains legacy server implementations that have been superseded by the current production server.

## Files

### `server_lowlevel.py`
- **Status**: Archived (2025-11-25)
- **Description**: Early low-level MCP server implementation using `mcp.server.lowlevel`
- **Why archived**: Replaced by FastMCP-based implementation in `server.py`
- **Historical value**: Shows initial MCP integration approach

### `server_fastmcp_backup.py`
- **Status**: Archived (2025-11-25)
- **Description**: Backup of early FastMCP server implementation
- **Why archived**: Server architecture evolved significantly; backup preserved for reference
- **Historical value**: Early attempt at FastMCP integration

### `server.py.backup_1764079708`
- **Status**: Archived (2025-11-25)
- **Description**: Timestamped backup of server.py from intermediate development phase
- **Why archived**: Historical checkpoint during major refactoring
- **Timestamp**: 1764079708 (Unix epoch)

## Current Server

The production MCP server is located at:
```
src/cogex_mcp/server.py
```

This server uses FastMCP and provides all 16 tools with proper:
- Entity resolution
- Neo4j/REST backend adapter
- Error handling
- Progress reporting
- Response formatting (markdown/JSON)

## Migration Notes

If you need to reference old server code:
1. These files are for reference only - DO NOT import or use in production
2. The current server (src/cogex_mcp/server.py) is the source of truth
3. All functionality from these old servers has been migrated to the current implementation

## Cleanup History

- **2025-11-25**: Initial archive creation during Phase 7 cleanup
  - Moved from `src/cogex_mcp/` to `archive/servers/`
  - Part of legacy code consolidation effort
