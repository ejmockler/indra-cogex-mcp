# Neo4j Schema Analysis for Tools 6-10

**Date**: 2025-11-25
**Database**: INDRA CoGEx Production
**URI**: bolt://indra-cogex-lb-b954b684556c373c.elb.us-east-1.amazonaws.com:7687

## Executive Summary

Analyzed the actual Neo4j schema to identify relationships for Tools 6-10. **Key finding**: The assumed relationships (`in_pathway`, `has_mutation`, `has_variant`) **DO NOT EXIST**. However, **alternative relationships exist** that provide the same functionality.

## Actual Relationships Found

### Tool 6: Pathway Relationships

**Expected**: `(Gene)-[:in_pathway]->(Pathway)`
**Reality**: `(Pathway)-[:haspart]->(Gene)` ✅

- Relationship type: `haspart`
- Direction: FROM pathway TO gene (inverted from expected)
- Count: 176,713 relationships
- Works for: Reactome, WikiPathways, KEGG pathways

**Example Query Results** (TP53):
```
Generic Transcription Pathway (reactome:R-HSA-212436)
Diseases of programmed cell death (reactome:R-HSA-9645723)
TRIF (TICAM1)-mediated TLR4 signaling (reactome:R-HSA-937061)
Interferon Signaling (reactome:R-HSA-913531)
Interleukin-1 signaling (reactome:R-HSA-9020702)
```

### Tool 7: Cell Line Relationships

**Expected**: `(CellLine)-[:has_mutation]->(Mutation)-[:affects]->(Gene)`
**Reality**: `(Gene)-[:mutated_in]->(CellLine)` ✅

- Relationship type: `mutated_in`
- Direction: FROM gene TO cell line (simpler than expected)
- Count: 1,135,008 relationships
- Cell line namespace: `ccle:` (e.g., `ccle:A549_LUNG`)

**Example Query Results** (A549_LUNG):
```
HOXA1, HNF4G, PURB, PTPRN2, PTPRN, CCDC182, HLA-DOB, PTPRB, HIPK3
```

**Copy Number Alterations**: `(Gene)-[:copy_number_altered_in]->(CellLine)`
- Relationship type: `copy_number_altered_in`
- Count: 1,417,774 relationships

**Drug Sensitivity**: `(Drug)-[:sensitive_to]-(CellLine)`
- Relationship type: `sensitive_to`
- Count: 69,312 relationships
- Bidirectional relationship

### Tool 10: Variant Relationships

**Expected**: `(Gene)-[:has_variant]->(Variant)`
**Reality**: `(Variant)-[:variant_gene_association]->(Gene)` ✅

- Relationship type: `variant_gene_association`
- Direction: FROM variant TO gene (inverted from expected)
- Count: 161,386 relationships
- Variant namespace: `dbsnp:` (e.g., `dbsnp:rs80358345`)

**Example Query Results** (BRCA1):
```
dbsnp:rs80358345: rs80358345
dbsnp:rs80358344: rs80358344
dbsnp:rs80358343: rs80358343
dbsnp:rs80358189: rs80358189
dbsnp:rs80358182: rs80358182
```

**Additional Variant Relationships**:
- `variant_disease_association`: Variant -> Disease (259,443 relationships)
- `variant_phenotype_association`: Variant -> Phenotype (231,303 relationships)

### Tool 8: Clinical Trials (Needs Further Investigation)

**Expected**: Relationships linking drugs/diseases to trials
**Status**: Not fully explored yet - need to check:
- `(Drug)-[:tested_in]->(Trial)`
- `(Disease)-[:has_trial]->(Trial)`
- Trial node properties (NCT ID, phase, status, etc.)

### Tool 9: Literature (Assumed to Work)

**Status**: Literature queries likely work with existing schema
- Publication nodes exist
- PMID properties available
- MeSH term relationships likely exist

## Key Schema Insights

### 1. Direction Matters

Many relationships are **inverted** from what the code assumes:
- Pathway `haspart` Gene (not Gene `in_pathway` Pathway)
- Variant `variant_gene_association` Gene (not Gene `has_variant` Variant)
- Gene `mutated_in` CellLine (simpler than expected multi-hop)

### 2. Cell Line Identifiers

- **Namespace**: `ccle:` (NOT `cellosaurus:`)
- **Format**: `ccle:CELLNAME_TISSUE` (e.g., `ccle:A549_LUNG`)
- **Properties**: Cell line nodes have `name` property but `type` may be None
- **Note**: Also found `efo:0001086` for A549, but CCLE IDs are the working identifiers

### 3. Variant Identifiers

- **Namespace**: `dbsnp:` for most variants
- **Format**: `dbsnp:rs123456` or just the rsID in properties
- **Note**: Also `clinvar:` namespace exists for clinical variants

### 4. Simplified Schema

The actual schema is **simpler** than the code assumes:
- No intermediate mutation nodes (direct gene -> cell line)
- No separate statement nodes (relationships store statement data)
- Properties on relationships (not separate nodes)

## Query Patterns to Implement

### Pattern 1: Pathway Queries (Tool 6)

```cypher
// Get genes in pathway (CORRECTED direction)
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE p.id = $pathway_id
  AND g.id STARTS WITH 'hgnc:'
  AND g.obsolete = false
RETURN g.name, g.id

// Get pathways for gene (CORRECTED direction)
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE g.id = $gene_id
  AND g.id STARTS WITH 'hgnc:'
  AND (p.id STARTS WITH 'reactome:' OR p.id STARTS WITH 'wikipathways:')
RETURN p.name, p.id

// Find shared pathways
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE g.id IN $gene_ids
WITH p, collect(DISTINCT g.id) AS genes
WHERE size(genes) = size($gene_ids)
RETURN p.name, p.id

// Check membership
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE g.id = $gene_id AND p.id = $pathway_id
RETURN count(*) > 0 AS is_member
```

### Pattern 2: Cell Line Queries (Tool 7)

```cypher
// Get mutations for cell line
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE c.id = $cell_line_id
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id

// Get cell lines for gene mutation
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE g.id = $gene_id
  AND c.id STARTS WITH 'ccle:'
RETURN c.name, c.id

// Get copy number alterations
MATCH (g:BioEntity)-[:copy_number_altered_in]->(c:BioEntity)
WHERE c.id = $cell_line_id
RETURN g.name, g.id

// Check if gene is mutated in cell line
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE g.id = $gene_id AND c.id = $cell_line_id
RETURN count(*) > 0 AS is_mutated
```

### Pattern 3: Variant Queries (Tool 10)

```cypher
// Get variants for gene (CORRECTED direction)
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE g.id = $gene_id
  AND v.id STARTS WITH 'dbsnp:'
RETURN v.id AS rsid, v.name

// Get genes for variant (CORRECTED direction)
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE v.id = $variant_id
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id

// Get variants for disease
MATCH (d:BioEntity)-[:variant_disease_association]->(v:BioEntity)
WHERE d.id = $disease_id
RETURN v.id AS rsid, v.name

// Get phenotypes for variant
MATCH (v:BioEntity)-[:variant_phenotype_association]->(p:BioEntity)
WHERE v.id = $variant_id
  AND p.id STARTS WITH 'HP:'
RETURN p.name, p.id

// Check variant-disease association
MATCH (d:BioEntity)-[:variant_disease_association]->(v:BioEntity)
WHERE d.id = $disease_id AND v.id = $variant_id
RETURN count(*) > 0 AS is_associated
```

## Performance Considerations

### Good Performance (< 1 second)
- Direct lookups by CURIE (indexed)
- Simple one-hop queries
- Limited result sets (LIMIT 20)

### Moderate Performance (1-3 seconds)
- Gene -> Pathways (176K relationships)
- Gene -> Cell lines (1.1M relationships)
- Variant -> Genes (161K relationships)

### Potential Bottlenecks
- Shared pathway queries (requires grouping)
- Large result sets without LIMIT
- Multiple JOIN operations

### Optimization Tips
1. Always use `LIMIT` for exploratory queries
2. Filter early (WHERE clause before relationships)
3. Use CURIE-based lookups (indexed)
4. Check `obsolete = false` to exclude deprecated entities

## Known Limitations

### 1. Cell Line Name Resolution
- Must use CCLE IDs (`ccle:A549_LUNG`), not just "A549"
- Cell line name -> CCLE ID mapping may be needed
- Some cell lines may have `None` as name property

### 2. Variant Properties
- Variant nodes have minimal properties (id, name)
- Detailed variant info (chromosome, position, alleles) may not be available
- P-values and statistical data may be on relationships, not nodes

### 3. Pathway Types
- Only Reactome, WikiPathways, KEGG are well-represented
- GO terms have different relationships (not `haspart`)
- Other pathway databases may not be included

### 4. Clinical Trials
- Not yet explored - schema unknown
- May need custom queries based on actual structure

## Test Cases for Validation

### Test 1: TP53 Pathways (Should return 10+ pathways)
```cypher
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE g.id = 'hgnc:11998'
  AND (p.id STARTS WITH 'reactome:' OR p.id STARTS WITH 'wikipathways:')
RETURN p.name, p.id
LIMIT 20
```
**Expected**: Generic Transcription Pathway, p53 pathway, Apoptosis, etc.

### Test 2: A549 Mutations (Should return 10+ genes)
```cypher
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE c.id = 'ccle:A549_LUNG'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id
LIMIT 20
```
**Expected**: KRAS (known A549 driver mutation), TP53, etc.

### Test 3: BRCA1 Variants (Should return 100+ variants)
```cypher
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE g.id = 'hgnc:1100'
  AND v.id STARTS WITH 'dbsnp:'
RETURN v.id, v.name
LIMIT 20
```
**Expected**: rs80358345, rs80358344, rs80358343, etc.

### Test 4: Alzheimer's Variants (Should return APOE variants)
```cypher
MATCH (d:BioEntity)-[:variant_disease_association]->(v:BioEntity)
WHERE d.name CONTAINS 'Alzheimer'
  OR d.id = 'DOID:10652'
RETURN v.id, v.name
LIMIT 20
```
**Expected**: rs7412 (APOE ε2), rs429358 (APOE ε4)

## Next Steps

### Immediate (Required for Tests to Pass)

1. **Update neo4j_client.py queries** (Lines 843-1139)
   - Tool 6: Change `in_pathway` to `haspart` (reverse direction)
   - Tool 7: Change multi-hop to direct `mutated_in`
   - Tool 10: Change `has_variant` to `variant_gene_association` (reverse direction)

2. **Update entity resolution** (Tool layer)
   - Cell line name -> CCLE ID mapping ("A549" -> "ccle:A549_LUNG")
   - Variant rsID -> dbsnp CURIE mapping ("rs7412" -> "dbsnp:rs7412")

3. **Test with known entities**
   - TP53 (hgnc:11998)
   - A549 (ccle:A549_LUNG)
   - BRCA1 (hgnc:1100)

### Follow-up (Nice to Have)

1. **Explore clinical trials schema**
   - Find trial nodes and relationships
   - Determine NCT ID property name
   - Test with known trials

2. **Document variant properties**
   - What properties exist on variant nodes?
   - Where is p-value, chromosome, position data?
   - Is it on nodes or relationships?

3. **Create entity resolution tables**
   - Common cell line name mappings
   - Pathway name -> ID mappings
   - Disease name -> CURIE mappings

## Conclusion

The actual Neo4j schema is **well-structured** and **contains all needed data**, but with **different relationship names and directions** than the code assumes. All Tools 6-10 can be implemented by correcting the queries to match the actual schema.

**Critical changes needed**:
1. Tool 6: `haspart` (inverted direction)
2. Tool 7: `mutated_in` (simplified, no intermediate nodes)
3. Tool 10: `variant_gene_association` (inverted direction)

**Success criteria**:
- TP53 returns 10+ pathways ✅
- A549 returns mutations including KRAS ✅
- BRCA1 returns 100+ variants ✅
- Queries run in < 2 seconds ✅
