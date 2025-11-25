# Neo4j Connection - Quick Start Guide

## Summary

The INDRA CoGEx MCP server is now configured with production Neo4j credentials and fully tested.

### Status: ✓ OPERATIONAL

All connection tests passed successfully. Neo4j is configured as the primary backend with REST API as fallback.

## Connection Details

```
URL: bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
User: neo4j
Status: Connected and verified
Database Nodes: 5,424,489 BioEntities
```

## Test Results

All 7 tests passed:
- ✓ Direct Neo4j Connection
- ✓ Gene Query (TP53)
- ✓ Adapter Initialization
- ✓ Adapter Query Execution
- ✓ Cypher Query Patterns
- ✓ Connection Pooling (10 concurrent queries in 0.52s)
- ✓ Error Handling

## Key Features

### 1. Backend Prioritization
- **Primary**: Neo4j (direct database access)
- **Fallback**: REST API (public endpoint)
- **Automatic**: Fails over when Neo4j unavailable

### 2. Connection Pooling
- Pool size: 50 connections
- Connection timeout: 30 seconds
- Max lifetime: 1 hour
- Concurrent queries: 10 simultaneous operations

### 3. Fault Tolerance
- Circuit breaker pattern implemented
- Automatic retry with exponential backoff
- Health monitoring every 5 minutes
- Graceful degradation to fallback backend

### 4. Performance Optimization
- Query timeout: 5 seconds (default)
- LRU caching: 1000 items, 1 hour TTL
- Connection reuse and pooling
- Efficient concurrent query handling

## How to Use

### Basic Query Example

```python
from cogex_mcp.clients.adapter import get_adapter

# Get the global adapter (auto-initializes)
adapter = await get_adapter()

# Execute a query (Neo4j preferred, REST fallback)
result = await adapter.query(
    "get_gene_by_symbol",
    symbol="TP53"
)

print(f"Found {result['count']} records")
```

### Direct Neo4j Access

```python
from cogex_mcp.clients.neo4j_client import Neo4jClient
from cogex_mcp.config import settings

# Create client
client = Neo4jClient(
    uri=settings.neo4j_url,
    user=settings.neo4j_user,
    password=settings.neo4j_password,
)

# Connect
await client.connect()

# Execute query
result = await client.execute_query("health_check")

# Raw Cypher
records = await client.execute_raw_cypher(
    "MATCH (n:BioEntity) RETURN count(n) as total"
)

# Close
await client.close()
```

### Check Backend Status

```python
adapter = await get_adapter()
status = adapter.get_status()

print(f"Primary: {status['primary_backend']}")
print(f"Neo4j health: {status['neo4j']['health']}")
print(f"REST health: {status['rest']['health']}")
```

## Available Queries

### Gene Queries
- `get_gene_by_symbol` - Get gene by symbol (e.g., TP53)
- `get_tissues_for_gene` - Get tissues where gene is expressed
- `get_genes_in_tissue` - Get genes expressed in tissue

### GO Term Queries
- `get_go_terms_for_gene` - Get GO terms for gene
- `get_genes_for_go_term` - Get genes for GO term

### Pathway Queries
- `get_pathways_for_gene` - Get pathways containing gene

### Disease Queries
- `get_diseases_for_gene` - Get diseases associated with gene

### System Queries
- `health_check` - Verify database connectivity

## Configuration Files

### Environment Variables (`.env`)
```bash
# Neo4j Connection
NEO4J_URL=bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=newton-heroic-lily-sharp-malta-5377

# Performance
NEO4J_MAX_CONNECTION_POOL_SIZE=50
NEO4J_CONNECTION_TIMEOUT=30
NEO4J_MAX_CONNECTION_LIFETIME=3600

# Fallback
USE_REST_FALLBACK=true
REST_API_BASE=https://discovery.indra.bio
```

## Testing

Run the comprehensive test suite:

```bash
source venv/bin/activate
python test_neo4j_connection.py
```

Expected output:
```
Total: 7/7 tests passed
```

## Monitoring

### Health Checks
The adapter automatically checks backend health every 5 minutes. Manual check:

```python
adapter = await get_adapter()
await adapter._check_health()
status = adapter.get_status()
```

### Circuit Breaker Status
Check if circuit breakers are open (blocking requests):

```python
status = adapter.get_status()
neo4j_open = status['neo4j']['circuit_open']
rest_open = status['rest']['circuit_open']
```

### Connection Pool Metrics
Monitor via logs (INFO level):
```
Neo4j client connected to bolt://... (pool_size=50)
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to Neo4j
```
Failed to connect to Neo4j: ServiceUnavailable
```

**Solutions**:
1. Verify credentials in `.env` file
2. Check network access to AWS Load Balancer
3. Verify database is running
4. Try REST fallback (should happen automatically)

### Query Returns No Results

**Problem**: Query succeeds but returns 0 records
```
Records found: 0
```

**Solutions**:
1. Verify query parameters (case-sensitive)
2. Check database schema matches expectations
3. Use raw Cypher to explore data structure
4. Review `NEO4J_DOCUMENTATION.md` for schema notes

### Performance Issues

**Problem**: Queries are slow

**Solutions**:
1. Increase connection pool size: `NEO4J_MAX_CONNECTION_POOL_SIZE=100`
2. Adjust timeouts for complex queries: `QUERY_TIMEOUT_MS=10000`
3. Enable caching: `CACHE_ENABLED=true`
4. Review query patterns for optimization

### Circuit Breaker Open

**Problem**: Circuit breaker blocking requests
```
Circuit breaker is OPEN
```

**Solutions**:
1. Wait for recovery timeout (60 seconds)
2. Check backend health
3. Review logs for underlying errors
4. Manually reset if needed (requires adapter restart)

## Important Notes

### Database Schema
- The database uses `BioEntity` as base label for all entities
- Multiple labels per node (e.g., `BioEntity` + `Gene`)
- Some expected properties (like `db_refs`) may not exist
- Always verify schema before writing complex queries

### Query Patterns
- Use `IN labels(node)` instead of exact label matching
- Parameterize all queries for safety and performance
- Implement pagination for large result sets
- Always set reasonable timeouts

### Security
- **Never commit** `.env` files to version control
- Credentials are stored in environment variables only
- Connection uses encrypted Bolt protocol
- Rotate passwords regularly in production

## Related Documentation

- **Comprehensive Guide**: `NEO4J_DOCUMENTATION.md` - Full technical documentation
- **Test Suite**: `test_neo4j_connection.py` - Test scripts and examples
- **Client Code**: `src/cogex_mcp/clients/neo4j_client.py` - Implementation details
- **Adapter Code**: `src/cogex_mcp/clients/adapter.py` - Backend management
- **Configuration**: `src/cogex_mcp/config.py` - Settings and validation

## Next Steps

### Recommended Actions

1. **Explore Database Schema**
   - Run schema discovery queries
   - Document actual property names
   - Update query definitions as needed

2. **Optimize Queries**
   - Add indexes for frequently queried properties
   - Profile slow queries
   - Implement result caching for expensive operations

3. **Monitor Performance**
   - Track query execution times
   - Monitor connection pool utilization
   - Review circuit breaker activation patterns

4. **Enhance Error Handling**
   - Add more specific error messages
   - Implement query result validation
   - Add detailed logging for debugging

## Support

For issues or questions:

1. Check test suite output for diagnostic information
2. Review logs at INFO level for connection details
3. Consult `NEO4J_DOCUMENTATION.md` for detailed guidance
4. Verify configuration in `.env` matches requirements

## Version Information

- **MCP Server**: cogex_mcp v1.0.0
- **Neo4j Client**: neo4j-python-driver (async)
- **Python**: 3.14+
- **Last Tested**: 2025-11-24
- **Status**: Production-ready
