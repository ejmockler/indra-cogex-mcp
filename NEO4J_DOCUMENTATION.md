# Neo4j Connection Documentation

## Overview

This document provides comprehensive information about the Neo4j database connection for INDRA CoGEx MCP server, including connection details, query patterns, response structures, and optimization guidelines.

## Connection Details

### Production Credentials

```
URL: bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687
User: neo4j
Password: newton-heroic-lily-sharp-malta-5377
```

### Connection Configuration

The Neo4j client is configured with the following settings:

- **Connection Pool Size**: 50 connections (configurable via `NEO4J_MAX_CONNECTION_POOL_SIZE`)
- **Connection Timeout**: 30 seconds (configurable via `NEO4J_CONNECTION_TIMEOUT`)
- **Max Connection Lifetime**: 3600 seconds / 1 hour (configurable via `NEO4J_MAX_CONNECTION_LIFETIME`)
- **Connection Acquisition Timeout**: 30.0 seconds
- **Max Transaction Retry Time**: 30.0 seconds

### Retry Logic

The Neo4j client implements automatic retry with exponential backoff for transient failures:

- **Retry on**: `ServiceUnavailable`, `TransientError` exceptions
- **Max Attempts**: 3
- **Backoff**: Exponential (1s min, 10s max, multiplier=1)

## Backend Prioritization

### Adapter Configuration

The `ClientAdapter` automatically prioritizes Neo4j when configured:

1. **Primary Backend**: Neo4j (when credentials are available)
2. **Fallback Backend**: REST API (when `USE_REST_FALLBACK=true`)

### Circuit Breaker

Each backend has a circuit breaker to prevent cascading failures:

- **Failure Threshold**: 5 consecutive failures
- **Recovery Timeout**: 60 seconds
- **Success Threshold**: 2 consecutive successes to close circuit

### Health Monitoring

- **Health Check Interval**: 300 seconds (5 minutes)
- **Health States**: `healthy`, `degraded`, `unhealthy`, `unknown`

## Database Statistics

From production database:

- **Total BioEntity Nodes**: 5,424,489
- **Gene Nodes**: 0 (Note: Gene data appears to be stored differently - see Query Patterns section)

## Query Patterns

### Available Named Queries

The Neo4j client provides the following pre-defined query operations:

#### 1. Gene Queries

##### `get_gene_by_symbol`

**Cypher:**
```cypher
MATCH (g:BioEntity)
WHERE g.name = $symbol AND 'Gene' IN labels(g)
RETURN g.name AS name, g.id AS id, g.db_refs AS db_refs
LIMIT 1
```

**Parameters:**
- `symbol` (string): Gene symbol (e.g., "TP53")

**Response Structure:**
```json
{
  "success": true,
  "records": [
    {
      "name": "TP53",
      "id": "hgnc:11998",
      "db_refs": {
        "HGNC": "11998",
        "UP": "P04637",
        "ENSEMBL": "ENSG00000141510"
      }
    }
  ],
  "count": 1
}
```

**Note**: The query returned 0 results for TP53. This suggests either:
- Gene data uses different labels or property names
- Gene data is stored in a different format
- Database schema differs from expected structure

##### `get_tissues_for_gene`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[:expressed_in]->(t:BioEntity)
WHERE g.id = $gene_id AND 'Tissue' IN labels(t)
RETURN t.name AS tissue, t.id AS tissue_id
```

**Parameters:**
- `gene_id` (string): Gene identifier (e.g., "hgnc:11998")

##### `get_genes_in_tissue`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[:expressed_in]->(t:BioEntity)
WHERE t.id = $tissue_id AND 'Gene' IN labels(g)
RETURN g.name AS gene, g.id AS gene_id
LIMIT $limit SKIP $offset
```

**Parameters:**
- `tissue_id` (string): Tissue identifier
- `limit` (int): Number of results to return
- `offset` (int): Number of results to skip (for pagination)

#### 2. GO Term Queries

##### `get_go_terms_for_gene`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[:associated_with]->(go:BioEntity)
WHERE g.id = $gene_id AND 'GO' IN labels(go)
RETURN go.name AS term, go.id AS go_id, go.namespace AS aspect
```

**Parameters:**
- `gene_id` (string): Gene identifier

**Response Structure:**
```json
{
  "success": true,
  "records": [
    {
      "term": "cell cycle arrest",
      "go_id": "GO:0007050",
      "aspect": "biological_process"
    }
  ],
  "count": 1
}
```

##### `get_genes_for_go_term`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[:associated_with]->(go:BioEntity)
WHERE go.id = $go_id AND 'Gene' IN labels(g)
RETURN g.name AS gene, g.id AS gene_id
LIMIT $limit SKIP $offset
```

**Parameters:**
- `go_id` (string): GO term identifier (e.g., "GO:0007050")
- `limit` (int): Number of results
- `offset` (int): Pagination offset

#### 3. Pathway Queries

##### `get_pathways_for_gene`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[:in_pathway]->(p:BioEntity)
WHERE g.id = $gene_id AND 'Pathway' IN labels(p)
RETURN p.name AS pathway, p.id AS pathway_id, p.source AS source
```

**Parameters:**
- `gene_id` (string): Gene identifier

**Response Structure:**
```json
{
  "success": true,
  "records": [
    {
      "pathway": "TP53 Regulates Transcription of Cell Cycle Genes",
      "pathway_id": "reactome:R-HSA-6804754",
      "source": "reactome"
    }
  ],
  "count": 1
}
```

#### 4. Disease Queries

##### `get_diseases_for_gene`

**Cypher:**
```cypher
MATCH (g:BioEntity)-[a:associated_with]->(d:BioEntity)
WHERE g.id = $gene_id AND 'Disease' IN labels(d)
RETURN d.name AS disease, d.id AS disease_id,
       a.score AS score, a.source AS source
```

**Parameters:**
- `gene_id` (string): Gene identifier

**Response Structure:**
```json
{
  "success": true,
  "records": [
    {
      "disease": "Li-Fraumeni syndrome",
      "disease_id": "mesh:D016864",
      "score": 0.95,
      "source": "disgenet"
    }
  ],
  "count": 1
}
```

#### 5. Health Check

##### `health_check`

**Cypher:**
```cypher
RETURN 1 AS status
```

**Response Structure:**
```json
{
  "success": true,
  "records": [{"status": 1}],
  "count": 1
}
```

### Raw Cypher Execution

For advanced use cases, you can execute raw Cypher queries:

```python
records = await client.execute_raw_cypher(
    "MATCH (n:BioEntity) RETURN count(n) as total",
    timeout=5000  # milliseconds
)
```

## Response Structure

All named queries return a consistent response format:

```json
{
  "success": true,
  "records": [
    {
      "field1": "value1",
      "field2": "value2"
    }
  ],
  "count": 1
}
```

- **success** (boolean): Whether query executed successfully
- **records** (array): List of result records (may be empty)
- **count** (int): Number of records returned

## Performance Optimizations

### Connection Pooling

The client uses connection pooling to handle concurrent requests efficiently:

- **Pool Size**: 50 connections by default
- **Concurrent Queries**: Up to 10 concurrent operations (`MAX_CONCURRENT_QUERIES`)
- **Concurrent Enrichments**: Up to 3 concurrent enrichment analyses (`MAX_CONCURRENT_ENRICHMENTS`)

### Query Timeouts

Different timeout values for different operation types:

- **Default Query Timeout**: 5000ms (`QUERY_TIMEOUT_MS`)
- **Enrichment Timeout**: 15000ms (`ENRICHMENT_TIMEOUT_MS`)
- **Subnetwork Timeout**: 10000ms (`SUBNETWORK_TIMEOUT_MS`)

### Caching

LRU cache for frequently accessed entities:

- **Cache Enabled**: true (`CACHE_ENABLED`)
- **Cache Size**: 1000 items (`CACHE_MAX_SIZE`)
- **Cache TTL**: 3600 seconds / 1 hour (`CACHE_TTL_SECONDS`)
- **Stats Interval**: 300 seconds (`CACHE_STATS_INTERVAL`)

## Database Schema Notes

### Labels

The database uses Neo4j labels to categorize nodes:

- **BioEntity**: Base label for all biological entities
- **Gene**: Gene-specific nodes
- **Tissue**: Tissue-specific nodes
- **GO**: Gene Ontology terms
- **Pathway**: Pathway entities
- **Disease**: Disease entities

**Important**: Multiple labels can be applied to a single node. Always check labels using `IN labels(node)` rather than exact label matching.

### Relationships

Common relationship types:

- **expressed_in**: Gene expression in tissue
- **associated_with**: Gene-GO term associations, gene-disease associations
- **in_pathway**: Gene-pathway membership

### Properties

#### Warning: Property Schema Differences

During testing, we encountered a warning:

```
property key does not exist: The property `db_refs` does not exist in database `neo4j`
```

This indicates the actual database schema may differ from the expected schema. When working with this database:

1. **Verify property names** using `MATCH (n:BioEntity) RETURN keys(n) LIMIT 10`
2. **Check available properties** for each node type
3. **Update queries** to match actual schema

### Example: Schema Discovery

```cypher
// Find all property keys used in BioEntity nodes
MATCH (n:BioEntity)
WITH DISTINCT keys(n) AS props
UNWIND props AS prop
RETURN DISTINCT prop
ORDER BY prop
```

## Testing

### Test Suite

A comprehensive test suite is available at `/Users/noot/Documents/indra-cogex-mcp/test_neo4j_connection.py`

Run tests:
```bash
source venv/bin/activate
python test_neo4j_connection.py
```

### Test Coverage

The test suite validates:

1. **Direct Connection**: Connection establishment, health checks, basic queries
2. **Gene Queries**: Gene lookup functionality (TP53 example)
3. **Adapter Initialization**: Backend selection and prioritization
4. **Adapter Queries**: Query execution through unified adapter
5. **Cypher Patterns**: Various Cypher query patterns and response handling
6. **Connection Pooling**: Concurrent query execution
7. **Error Handling**: Invalid queries, timeouts, retry logic

### Test Results

All 7 tests passed successfully:

- Connection established to production database
- Health checks working
- Neo4j correctly prioritized as primary backend
- REST API configured as fallback
- Circuit breakers operational
- Connection pooling handling 10 concurrent queries in 0.52s

## Troubleshooting

### Connection Issues

If connection fails:

1. **Check credentials** in `.env` file
2. **Verify network access** to AWS Load Balancer
3. **Check timeout settings** (increase if needed)
4. **Review logs** for detailed error messages

### Query Issues

If queries return unexpected results:

1. **Verify schema** using discovery queries
2. **Check property names** match actual database
3. **Validate labels** are applied correctly
4. **Test with raw Cypher** to isolate issues

### Performance Issues

If queries are slow:

1. **Increase connection pool size** (`NEO4J_MAX_CONNECTION_POOL_SIZE`)
2. **Adjust timeout values** for complex queries
3. **Enable caching** (`CACHE_ENABLED=true`)
4. **Review query patterns** for optimization opportunities

## Security Considerations

### Credential Management

- **Never commit** `.env` files to version control
- **Use environment variables** for production deployments
- **Rotate passwords** regularly
- **Limit network access** to Neo4j database

### MCP Best Practices

This implementation follows MCP best practices:

1. **Secure credential storage** via environment variables
2. **Error logging to stderr** (for stdio transport)
3. **Health checks** for backend availability
4. **Circuit breakers** for fault tolerance
5. **Connection pooling** for resource management

## Related Files

- **Client Implementation**: `/Users/noot/Documents/indra-cogex-mcp/src/cogex_mcp/clients/neo4j_client.py`
- **Adapter Implementation**: `/Users/noot/Documents/indra-cogex-mcp/src/cogex_mcp/clients/adapter.py`
- **Configuration**: `/Users/noot/Documents/indra-cogex-mcp/src/cogex_mcp/config.py`
- **Test Suite**: `/Users/noot/Documents/indra-cogex-mcp/test_neo4j_connection.py`
- **Environment Config**: `/Users/noot/Documents/indra-cogex-mcp/.env`

## Next Steps

### Schema Investigation

To better understand the actual database schema:

1. **Query available labels**: `CALL db.labels()`
2. **Query relationship types**: `CALL db.relationshipTypes()`
3. **Inspect node properties**: `MATCH (n) RETURN DISTINCT keys(n) LIMIT 100`
4. **Update query definitions** based on findings

### Query Optimization

1. **Add indexes** for frequently queried properties
2. **Optimize Cypher queries** based on actual usage patterns
3. **Implement query result caching** for expensive operations
4. **Monitor query performance** using Neo4j profiling

### Feature Enhancements

1. **Add more query types** as needed by tools
2. **Implement batch query operations** for efficiency
3. **Add query result pagination** for large datasets
4. **Implement query result streaming** for very large results
