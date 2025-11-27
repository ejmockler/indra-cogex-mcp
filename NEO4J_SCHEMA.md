# INDRA CoGEx Neo4j Schema Documentation

**Last Updated**: 2025-11-25

## Overview

The INDRA CoGEx knowledge graph stores biological entities and relationships in Neo4j. **CRITICAL**: INDRA statements are stored as `indra_rel` relationships between `BioEntity` nodes, NOT as separate Statement nodes.

## Node Labels

Primary node types in the database:

- **BioEntity**: All biological entities (genes, proteins, diseases, drugs, etc.)
- **Evidence**: Evidence supporting relationships
- **Publication**: Scientific publications
- **ClinicalTrial**: Clinical trial records
- **Journal**: Scientific journals
- **Patent**: Patent documents
- **Publisher**: Publication publishers
- **ResearchProject**: Research project metadata
- **Chunk**: Text chunks for embeddings

## BioEntity Properties

BioEntity nodes represent genes, proteins, diseases, drugs, and other biological entities.

### Example: SOD1 Gene
```json
{
  "name": "SOD1",
  "id": "hgnc:11179",
  "type": "human_gene_protein",
  "obsolete": false
}
```

### Key Properties
- `id`: CURIE format identifier (e.g., `hgnc:11179`, `doid:332`, `chembl:CHEMBL123`)
- `name`: Human-readable name
- `type`: Entity type (human_gene_protein, disease, drug, etc.)
- `obsolete`: Boolean flag for deprecated entities

## Relationship Types

### INDRA Relationships: `indra_rel`

**MOST IMPORTANT**: All INDRA statements are stored as `indra_rel` relationships between BioEntity nodes.

#### Properties on `indra_rel` relationships:
- `stmt_type`: Statement type (Complex, Activation, Inhibition, Phosphorylation, etc.)
- `belief`: Float (0-1) representing belief score
- `evidence_count`: Integer count of supporting evidence
- `stmt_hash`: Unique statement identifier (negative integers)
- `stmt_json`: Full INDRA statement JSON with evidence
- `source_counts`: JSON object mapping source to count (e.g., `{"reach": 2, "sparser": 1}`)
- `has_reader_evidence`: Boolean - has machine reading evidence
- `has_database_evidence`: Boolean - has database evidence
- `has_retracted_evidence`: Boolean - has retracted evidence
- `medscan_only`: Boolean - only from MedScan
- `sparser_only`: Boolean - only from Sparser

#### Example Query:
```cypher
MATCH (g1:BioEntity)-[r:indra_rel]->(g2:BioEntity)
WHERE g1.name = 'SOD1'
  AND g2.id STARTS WITH 'hgnc:'
  AND r.belief >= 0.5
  AND r.evidence_count >= 2
RETURN g1.name, r.stmt_type, g2.name, r.belief, r.evidence_count
LIMIT 10
```

#### Common Statement Types:
- `Complex`: Physical protein complex formation
- `Activation`: One entity activates another
- `Inhibition`: One entity inhibits another
- `Phosphorylation`: Phosphorylation modification
- `IncreaseAmount`: Increase in expression/amount
- `DecreaseAmount`: Decrease in expression/amount
- `Acetylation`, `Methylation`, `Ubiquitination`: Post-translational modifications

### Co-dependency: `codependent_with`

Gene pairs that show statistical co-dependency.

**Properties:**
- `logp`: Log p-value of co-dependency (negative values, more negative = stronger)

**Example:**
```cypher
MATCH (g1:BioEntity)-[r:codependent_with]->(g2:BioEntity)
WHERE g1.name = 'SOD1' AND r.logp < -15
RETURN g1.name, g2.name, r.logp
```

### Expression: `expressed_in`

Gene expression in tissues/cell types.

**Example:**
```cypher
MATCH (gene:BioEntity)-[r:expressed_in]->(tissue)
WHERE gene.name = 'SOD1'
RETURN tissue.name
```

### Disease Association: `gene_disease_association`

Links genes to diseases.

**Example:**
```cypher
MATCH (gene:BioEntity)-[r:gene_disease_association]->(disease:BioEntity)
WHERE gene.name = 'SOD1'
RETURN disease.name
```

### Pathway Relationships: `haspart`

**Direction**: Pathway -> Gene (FROM pathway TO gene)

Links pathways to their component genes.

**Example:**
```cypher
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE p.id = 'reactome:R-HSA-212436'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name
```

### Cell Line Relationships: `mutated_in`, `copy_number_altered_in`

**Direction**: Gene -> Cell Line

Links genes to cell lines where they are mutated or copy-number altered.

**Example:**
```cypher
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE c.id = 'ccle:A549_LUNG'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name
```

**Note**: Cell lines use CCLE IDs (e.g., `ccle:A549_LUNG`), not Cellosaurus IDs.

### Variant Relationships: `variant_gene_association`, `variant_disease_association`, `variant_phenotype_association`

**Direction**: Variant -> Gene/Disease/Phenotype

Links genetic variants to associated genes, diseases, and phenotypes.

**Example:**
```cypher
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE v.id = 'dbsnp:rs7412'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name  // Returns: APOE
```

**Note**: Variants use dbSNP namespace (e.g., `dbsnp:rs7412`).

### Other Relationship Types:
- `has_indication`: Drug-disease relationships
- `has_domain`: Protein domains
- `has_clinical_trial`, `has_patent`, `has_publication`: Links to evidence
- `isa`: Ontological is-a relationships
- `has_phenotype`: Phenotype associations
- `has_activity`: Molecular activities
- `published_in`, `published_by`: Publication metadata
- `sensitive_to`: Drug sensitivity
- `phenotype_has_gene`: Phenotype-gene links
- `annotated_with`: Annotations
- `xref`, `replaced_by`, `partof`: Ontology relationships
- `has_side_effect`: Drug side effects
- `tested_in`, `has_trial`: Clinical trial relationships
- `associated_with`: General associations
- `has_citation`: Citation links
- `has_marker`: Cell marker relationships

## Common Query Patterns

### 1. Get Gene by Symbol
```cypher
MATCH (g:BioEntity)
WHERE g.name = 'SOD1' AND g.id STARTS WITH 'hgnc:'
RETURN g
```

### 2. Get Gene-Gene INDRA Relationships (Subnetwork)
```cypher
MATCH (g1:BioEntity)-[r:indra_rel]-(g2:BioEntity)
WHERE g1.id IN ['hgnc:11179', 'hgnc:11571']  // SOD1, TARDBP
  AND g2.id IN ['hgnc:11179', 'hgnc:11571']
  AND r.belief >= 0.5
  AND r.evidence_count >= 2
RETURN g1.name AS source,
       r.stmt_type AS type,
       g2.name AS target,
       r.belief,
       r.evidence_count
```

### 3. Get All Genes Related to a Gene
```cypher
MATCH (gene:BioEntity {name: 'SOD1'})-[r:indra_rel]-(related:BioEntity)
WHERE related.id STARTS WITH 'hgnc:'
  AND r.belief >= 0.4
RETURN related.name, r.stmt_type, r.belief, r.evidence_count
ORDER BY r.belief DESC
LIMIT 50
```

### 4. Get Tissue Expression
```cypher
MATCH (gene:BioEntity {name: 'SOD1'})-[:expressed_in]->(tissue)
RETURN tissue.name
```

### 5. Get Disease Associations
```cypher
MATCH (gene:BioEntity)-[r:gene_disease_association]->(disease:BioEntity)
WHERE gene.name = 'SOD1'
RETURN disease.name, disease.id
```

## ALS Gene Examples

### ALS-Related Genes and Their `indra_rel` Counts:
- **SOD1** (hgnc:11179): ~1,000 indra_rel relationships
- **TARDBP** (hgnc:11571): 3,786 indra_rel relationships
- **FUS** (hgnc:4010): 4,234 indra_rel relationships
- **C9orf72** (hgnc:28337): 3,122 indra_rel relationships

### Example SOD1 Relationships:
```
SOD1 -[Complex]-> BCL2 (belief: 0.457, evidence: 2)
SOD1 -[Activation]-> BCL2 (belief: 0.376, evidence: 2)
SOD1 -[Activation]-> RELA (belief: 0.367, evidence: 2)
SOD1 -[Acetylation]-> RELA (belief: 0.469, evidence: 1)
```

## Performance Notes

1. **Index on BioEntity.id**: Very fast lookups by CURIE
2. **Index on BioEntity.name**: Fast symbol-based queries
3. **Relationship property filters**: Apply early for better performance
4. **Limit results**: Always use LIMIT for exploratory queries
5. **Use parameters**: Parameterized queries are cached and faster

## Query Patterns for Tools 6-10

### Tool 6: Pathway Queries

**Get pathways for gene**:
```cypher
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE g.id = 'hgnc:11998'
  AND (p.id STARTS WITH 'reactome:' OR p.id STARTS WITH 'wikipathways:')
RETURN p.name, p.id
```

**Get genes in pathway**:
```cypher
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)
WHERE p.id = 'reactome:R-HSA-212436'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id
```

### Tool 7: Cell Line Queries

**Get mutations for cell line**:
```cypher
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE c.id = 'ccle:A549_LUNG'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id
```

**Get cell lines with mutation**:
```cypher
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
WHERE g.id = 'hgnc:3236'  // KRAS
  AND c.id STARTS WITH 'ccle:'
RETURN c.name, c.id
```

### Tool 10: Variant Queries

**Get variants for gene**:
```cypher
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE g.id = 'hgnc:1100'  // BRCA1
  AND v.id STARTS WITH 'dbsnp:'
RETURN v.id, v.name
```

**Get genes for variant**:
```cypher
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)
WHERE v.id = 'dbsnp:rs7412'
  AND g.id STARTS WITH 'hgnc:'
RETURN g.name, g.id  // Returns: APOE
```

## CRITICAL: What NOT to Do

❌ **DO NOT** use `in_pathway` (use `haspart`):
```cypher
// WRONG - Relationship doesn't exist
MATCH (g:BioEntity)-[:in_pathway]->(p:BioEntity)
```

❌ **DO NOT** use `has_variant` (use `variant_gene_association`):
```cypher
// WRONG - Relationship doesn't exist
MATCH (g:BioEntity)-[:has_variant]->(v:BioEntity)
```

❌ **DO NOT** use multi-hop for cell line mutations (direct relationship exists):
```cypher
// WRONG - Unnecessarily complex
MATCH (c:BioEntity)-[:has_mutation]->(m)-[:affects]->(g:BioEntity)
```

✅ **CORRECT** relationship patterns:
```cypher
// RIGHT - Pathway to gene
MATCH (p:BioEntity)-[:haspart]->(g:BioEntity)

// RIGHT - Variant to gene
MATCH (v:BioEntity)-[:variant_gene_association]->(g:BioEntity)

// RIGHT - Gene to cell line
MATCH (g:BioEntity)-[:mutated_in]->(c:BioEntity)
```

## Validation Status

**Last Validated**: 2025-11-25

All queries for Tools 6-10 have been validated against the production database:
- ✅ Tool 6: Pathway queries (3/3 tests passed)
- ✅ Tool 7: Cell line queries (4/4 tests passed)
- ✅ Tool 10: Variant queries (3/3 tests passed)

See `NEO4J_SCHEMA_ANALYSIS.md` for detailed findings and `scripts/validate_neo4j_queries.py` for validation tests.
