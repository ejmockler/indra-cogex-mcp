# Subnetwork Extraction Guide

Complete guide to extracting mechanistic networks from INDRA CoGEx using the `cogex_extract_subnetwork` tool.

## Table of Contents

1. [Introduction](#introduction)
2. [Conceptual Overview](#conceptual-overview)
3. [Query Modes](#query-modes)
4. [Parameters Reference](#parameters-reference)
5. [Common Workflows](#common-workflows)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Introduction

### What is Subnetwork Extraction?

Subnetwork extraction allows you to discover mechanistic relationships between genes by traversing the INDRA knowledge graph. Unlike simple gene-disease associations, this tool returns **mechanistic statements** like:

- "MAPK1 phosphorylates ELK1 at Serine 383"
- "TP53 activates BAX"
- "MDM2 ubiquitinates TP53"

These mechanistic relationships are extracted from literature using natural language processing and curated from pathway databases.

### When to Use This Tool

**Use subnetwork extraction when you need to:**
- Understand how specific genes interact mechanistically
- Find pathways connecting disease genes
- Discover master regulators of a gene set
- Identify shared targets of multiple proteins
- Build tissue-specific or pathway-specific networks

**Don't use subnetwork extraction for:**
- Simple gene expression queries (use `cogex_query_gene_or_feature` instead)
- Gene set enrichment analysis (use `cogex_enrichment_analysis` instead)
- Finding genes associated with a disease (use `cogex_query_disease_or_phenotype` instead)

### Key Concepts

**Nodes**: Genes or proteins (e.g., TP53, MDM2)

**Edges/Statements**: Mechanistic relationships between nodes (e.g., phosphorylation, activation)

**Evidence**: Literature citations supporting each statement

**Belief Score**: Confidence score (0-1) based on evidence quality and quantity

**Statement Types**: Categories of mechanisms (Phosphorylation, Activation, Inhibition, Ubiquitination, etc.)

---

## Conceptual Overview

### How INDRA CoGEx Represents Biology

INDRA CoGEx integrates mechanistic knowledge from:
- **Literature**: Automated reading of PubMed articles (REACH, Sparser)
- **Pathway databases**: Reactome, WikiPathways, KEGG
- **Protein databases**: UniProt, PhosphoSitePlus

Each mechanistic relationship is stored as an **INDRA Statement** with:
- Subject (the agent performing the action)
- Object (the target of the action)
- Type (the mechanism: Phosphorylation, Activation, etc.)
- Evidence (supporting citations and database entries)
- Belief score (confidence based on evidence)

### Graph Traversal Modes

Think of the knowledge graph as a network where:
- Nodes = Genes/Proteins
- Edges = Mechanistic relationships

Different modes traverse this graph in different ways:

```
DIRECT MODE (A→B)
  TP53 --activates--> BAX
  TP53 --phosphorylates--> MDM2

MEDIATED MODE (A→X→B)
  BRCA1 --binds--> RAD51 --activates--> DNA_REPAIR

SHARED UPSTREAM (A←X→B)
  JAK1 <--phosphorylates-- SRC
  STAT3 <--phosphorylates-- SRC
  (SRC is shared regulator)

SHARED DOWNSTREAM (A→X←B)
  TP53 --activates--> BAX
  BCL2 --inhibits--> BAX
  (BAX is shared target)

SOURCE TO TARGETS (S→[T1,T2,T3])
  MAPK1 --phosphorylates--> FOS
  MAPK1 --phosphorylates--> JUN
  MAPK1 --phosphorylates--> ELK1
```

---

## Query Modes

### Mode 1: Direct

**Purpose**: Find direct mechanistic edges between specified genes

**Pattern**: A→B (one-hop relationships)

**Use when**:
- You know genes interact and want to know *how*
- Validating known protein-protein interactions
- Finding specific mechanisms (e.g., phosphorylation sites)

**Example**:
```json
{
  "mode": "direct",
  "genes": ["TP53", "MDM2"],
  "min_evidence_count": 2,
  "response_format": "json"
}
```

**Expected output**:
- Direct phosphorylation, ubiquitination, activation events
- Specific residues and positions (e.g., S15, Y394)
- 5-50 statements depending on gene pair

**Strengths**:
- Most specific and reliable
- Includes mechanistic details (residues, positions)
- High-confidence results

**Limitations**:
- Won't find indirect connections
- May miss relevant biology if genes don't interact directly

---

### Mode 2: Mediated

**Purpose**: Find two-hop paths connecting genes through intermediates

**Pattern**: A→X→B (intermediary mechanisms)

**Use when**:
- Genes don't interact directly but you suspect a connection
- Building pathway models
- Discovering potential drug targets (intermediaries)

**Example**:
```json
{
  "mode": "mediated",
  "genes": ["BRCA1", "RAD51"],
  "max_statements": 100,
  "response_format": "json"
}
```

**Expected output**:
- Two-hop paths: BRCA1→PALB2→RAD51
- Intermediary proteins (potential drug targets)
- 20-100+ statements depending on connectivity

**Strengths**:
- Discovers indirect connections
- Identifies pathway intermediaries
- Useful for hypothesis generation

**Limitations**:
- More results to sift through
- Lower specificity than direct mode
- May include spurious connections

---

### Mode 3: Shared Upstream

**Purpose**: Find shared regulatory inputs (master regulators)

**Pattern**: A←X→B (common regulators)

**Use when**:
- Looking for master regulators
- Understanding coordinated gene expression
- Finding upstream control points for drug targeting

**Example**:
```json
{
  "mode": "shared_upstream",
  "genes": ["BAX", "BCL2", "CASP3"],
  "statement_types": ["Activation", "Inhibition"],
  "response_format": "json"
}
```

**Expected output**:
- Kinases phosphorylating multiple targets
- Transcription factors regulating gene sets
- Upstream signaling molecules

**Strengths**:
- Identifies master control points
- Good for understanding regulation
- Useful for drug target discovery

**Limitations**:
- Backend implementation may be limited (check for "not yet implemented" message)
- May return many regulators (use filters)

---

### Mode 4: Shared Downstream

**Purpose**: Find shared regulatory targets

**Pattern**: A→X←B (common targets)

**Use when**:
- Looking for convergence points
- Understanding pathway crosstalk
- Finding genes regulated by multiple inputs

**Example**:
```json
{
  "mode": "shared_downstream",
  "genes": ["TP53", "MYC", "RB1"],
  "min_evidence_count": 3,
  "response_format": "json"
}
```

**Expected output**:
- Genes regulated by multiple transcription factors
- Proteins phosphorylated by multiple kinases
- Convergence points in signaling

**Strengths**:
- Reveals pathway crosstalk
- Identifies integration points
- Good for systems biology

**Limitations**:
- Backend implementation may be limited
- Can be computationally expensive

---

### Mode 5: Source to Targets

**Purpose**: Find all downstream targets of a source gene

**Pattern**: Source→[Targets] (one-to-many)

**Use when**:
- Exploring a kinase's substrates
- Finding transcription factor targets
- Building gene regulatory networks

**Example**:
```json
{
  "mode": "source_to_targets",
  "source_gene": "MAPK1",
  "target_genes": ["FOS", "JUN", "ELK1", "MYC"],
  "statement_types": ["Phosphorylation"],
  "response_format": "json"
}
```

**Expected output**:
- All confirmed phosphorylation events
- Specific sites (e.g., FOS S362, JUN S73)
- Evidence counts and sources

**Strengths**:
- Comprehensive downstream view
- Can optionally filter to specific targets
- Good for kinase-substrate analysis

**Limitations**:
- Can return many results (use max_statements limit)
- May need additional filtering

---

## Parameters Reference

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `mode` | string | Query mode (see above) | `"direct"` |
| `genes` | list[str] | Gene list (for modes 1-4) | `["TP53", "MDM2"]` |
| `source_gene` | string | Source gene (mode 5 only) | `"MAPK1"` |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_genes` | list[str] | `null` | Target genes for mode 5 |
| `statement_types` | list[str] | `null` | Filter by mechanism (e.g., `["Phosphorylation"]`) |
| `min_evidence_count` | int | `1` | Minimum supporting evidences |
| `min_belief_score` | float | `0.0` | Minimum confidence (0-1) |
| `max_statements` | int | `100` | Maximum results (1-500) |
| `tissue_filter` | string | `null` | Tissue context (e.g., `"brain"`) |
| `go_filter` | string | `null` | GO term filter (e.g., `"GO:0006915"`) |
| `include_evidence` | bool | `false` | Include evidence text |
| `max_evidence_per_statement` | int | `5` | Max evidences when include_evidence=true |
| `response_format` | string | `"markdown"` | Output format (`"markdown"` or `"json"`) |

### Statement Types

Common statement types you can filter by:

- **Phosphorylation**: Kinase-substrate relationships
- **Activation**: Positive regulation
- **Inhibition**: Negative regulation
- **Ubiquitination**: E3 ligase-substrate
- **IncreaseAmount**: Transcriptional activation
- **DecreaseAmount**: Transcriptional repression
- **Complex**: Protein complex formation
- **Translocation**: Cellular localization changes

See INDRA documentation for full list: https://indra.readthedocs.io/

---

## Common Workflows

### Workflow 1: Drug Discovery

**Goal**: Find druggable targets in a disease pathway

**Steps**:
1. Start with disease genes (e.g., ALS: SOD1, TARDBP, FUS)
2. Use **mediated mode** to find connecting pathways
3. Filter for kinases (statement_type: Phosphorylation)
4. Identify intermediary kinases as drug targets

**Example**:
```json
{
  "mode": "mediated",
  "genes": ["SOD1", "TARDBP", "FUS"],
  "statement_types": ["Phosphorylation"],
  "min_evidence_count": 3,
  "max_statements": 100
}
```

**Analysis**:
- Extract intermediary nodes (not in original gene list)
- Prioritize by connectivity (hub nodes)
- Check for existing kinase inhibitors

---

### Workflow 2: Pathway Reconstruction

**Goal**: Build a complete pathway model

**Steps**:
1. Identify core pathway genes (e.g., MAPK cascade)
2. Use **direct mode** for core interactions
3. Use **shared_upstream** for input signals
4. Use **shared_downstream** for outputs

**Example sequence**:
```json
// Step 1: Core pathway
{
  "mode": "direct",
  "genes": ["MAPK1", "MAP2K1", "RAF1", "KRAS"],
  "min_evidence_count": 2
}

// Step 2: Upstream regulators
{
  "mode": "shared_upstream",
  "genes": ["RAF1", "KRAS"],
  "statement_types": ["Activation", "Phosphorylation"]
}

// Step 3: Downstream targets
{
  "mode": "shared_downstream",
  "genes": ["MAPK1", "MAPK3"],
  "statement_types": ["Phosphorylation"]
}
```

---

### Workflow 3: Disease Mechanism Research

**Goal**: Understand how disease mutations affect signaling

**Steps**:
1. Identify disease genes from GWAS/sequencing
2. Use **direct mode** to see normal interactions
3. Apply **tissue filter** for disease-relevant tissue
4. Cross-reference with mutation data

**Example**:
```json
{
  "mode": "direct",
  "genes": ["APP", "PSEN1", "MAPT"],
  "tissue_filter": "brain",
  "min_evidence_count": 2,
  "include_evidence": true
}
```

**Analysis**:
- Check if mutations affect phosphorylation sites
- Identify altered protein-protein interactions
- Look for tissue-specific mechanisms

---

### Workflow 4: Kinase-Substrate Discovery

**Goal**: Find all substrates of a specific kinase

**Steps**:
1. Use **source_to_targets** mode with kinase as source
2. Filter to Phosphorylation statements only
3. Extract phosphorylation sites
4. Validate with PhosphoSitePlus data

**Example**:
```json
{
  "mode": "source_to_targets",
  "source_gene": "MAPK1",
  "statement_types": ["Phosphorylation"],
  "min_evidence_count": 2,
  "max_statements": 200
}
```

**Analysis**:
- Group by substrate
- Identify consensus motifs
- Prioritize by evidence count

---

## Best Practices

### 1. Start Broad, Then Filter

**Don't**: Immediately apply strict filters
```json
// Too restrictive - may miss biology
{
  "mode": "direct",
  "genes": ["GENE1", "GENE2"],
  "min_evidence_count": 10,
  "min_belief_score": 0.95,
  "statement_types": ["Phosphorylation"]
}
```

**Do**: Start broad, examine results, then refine
```json
// First query - explore the landscape
{
  "mode": "direct",
  "genes": ["GENE1", "GENE2"],
  "max_statements": 100
}

// Second query - refined based on first results
{
  "mode": "direct",
  "genes": ["GENE1", "GENE2"],
  "statement_types": ["Phosphorylation", "Activation"],
  "min_evidence_count": 3
}
```

### 2. Use Appropriate Evidence Thresholds

| Research Stage | min_evidence_count | min_belief_score |
|----------------|-------------------|------------------|
| Hypothesis generation | 1 | 0.0 |
| Literature review | 2 | 0.5 |
| Experimental design | 3 | 0.7 |
| High-confidence only | 5+ | 0.8+ |

### 3. Combine Multiple Queries

Don't rely on a single query mode. Build complete models by combining:
- **Direct**: Core interactions
- **Mediated**: Pathway context
- **Shared upstream/downstream**: Regulatory control

### 4. Leverage Filters Strategically

**Tissue filters**: Use when disease/phenotype is tissue-specific
```json
// Alzheimer's research - brain only
{"tissue_filter": "brain"}
```

**GO filters**: Use to focus on specific processes
```json
// Autophagy research
{"go_filter": "GO:0006914"}
```

**Statement type filters**: Use when mechanism is important
```json
// Phosphoproteomics analysis
{"statement_types": ["Phosphorylation"]}
```

### 5. Handle Large Result Sets

If you get too many results:
1. Increase `min_evidence_count`
2. Increase `min_belief_score`
3. Add `statement_types` filter
4. Use `max_statements` limit
5. Apply tissue or GO filters

### 6. Include Evidence When Needed

**Default** (include_evidence=false):
- Faster queries
- Smaller responses
- Good for initial exploration

**With evidence** (include_evidence=true):
- Slower queries
- Larger responses
- Necessary for validation
- Good for final verification

---

## Troubleshooting

### Problem: No Results Returned

**Possible causes**:
1. Genes don't interact (expected for some pairs)
2. Filters too strict
3. Gene names not recognized

**Solutions**:
```json
// Try removing filters
{
  "mode": "direct",
  "genes": ["GENE1", "GENE2"],
  "min_evidence_count": 1,  // Lower threshold
  "min_belief_score": 0.0    // No belief filter
}

// Try mediated mode instead
{
  "mode": "mediated",  // Finds indirect connections
  "genes": ["GENE1", "GENE2"]
}

// Verify gene names
// Use cogex_query_gene_or_feature to check
```

### Problem: Too Many Results

**Solutions**:
```json
// Increase evidence threshold
{"min_evidence_count": 5}

// Add belief filter
{"min_belief_score": 0.7}

// Filter by mechanism
{"statement_types": ["Phosphorylation"]}

// Limit results
{"max_statements": 50}
```

### Problem: "Not Yet Implemented" Message

**Cause**: Backend doesn't support this mode yet (shared_upstream, shared_downstream)

**Solution**: Wait for future release or use alternative approaches:
```json
// Instead of shared_upstream, use source_to_targets multiple times
{
  "mode": "source_to_targets",
  "source_gene": "POTENTIAL_REGULATOR",
  "target_genes": ["GENE1", "GENE2", "GENE3"]
}
```

### Problem: Gene Name Not Recognized

**Error**: "Could not resolve gene: XYZ"

**Solutions**:
1. Try alternative gene symbols (HGNC vs common names)
2. Use gene ID (HGNC:12345)
3. Check for typos
4. Verify gene exists in human genome

**Examples**:
```json
// Try different identifiers
{"genes": ["TP53"]}      // HGNC symbol ✓
{"genes": ["p53"]}       // Common name (may work)
{"genes": ["hgnc:11998"]} // HGNC ID (most reliable)
```

### Problem: Response Too Large / Truncated

**Cause**: Results exceed character limit (90,000 chars)

**Solutions**:
1. Use JSON format (more compact than Markdown)
2. Reduce max_statements
3. Apply stricter filters
4. Don't include evidence text
5. Query in batches (subset of genes)

---

## FAQ

### Q: What's the difference between direct and mediated mode?

**A**:
- **Direct**: One-hop (A→B). Use when you know genes interact.
- **Mediated**: Two-hop (A→X→B). Use to discover pathways connecting genes.

### Q: How do I choose the right min_evidence_count?

**A**:
- **1-2**: Exploratory research, hypothesis generation
- **3-5**: Literature review, pathway building
- **5+**: High-confidence, experimental validation

Higher is better for reliability, but you may miss real biology.

### Q: Should I use tissue_filter or go_filter?

**A**:
- **tissue_filter**: When disease/phenotype is tissue-specific (e.g., brain for neurodegeneration)
- **go_filter**: When focusing on a biological process (e.g., autophagy, apoptosis)
- **Both**: Can be combined for maximum specificity

### Q: What are good gene sets to start with?

**A**: Try these well-studied examples:
- **TP53-MDM2**: Classic feedback loop
- **MAPK pathway**: MAPK1, MAP2K1, RAF1, KRAS
- **Apoptosis**: BAX, BCL2, CASP3, TP53
- **ALS genes**: SOD1, TARDBP, FUS, C9orf72

### Q: How do I interpret belief scores?

**A**:
- **0.9-1.0**: Very high confidence, multiple independent sources
- **0.7-0.9**: High confidence, well-supported
- **0.5-0.7**: Moderate confidence
- **< 0.5**: Low confidence, may need validation

Belief scores combine evidence count, source quality, and consistency.

### Q: Can I export results for visualization?

**A**: Yes! Use `response_format: "json"` and export to:
- **Cytoscape**: Import nodes and edges JSON
- **NetworkX**: Parse JSON in Python
- **Gephi**: Convert to GEXF/GraphML format
- **R/igraph**: Read JSON in R

### Q: What's the maximum number of genes I can query?

**A**:
- **Recommended**: 2-10 genes for focused analysis
- **Maximum**: No hard limit, but more genes = more results = slower queries
- **Best practice**: If you have >20 genes, use enrichment analysis instead

### Q: How current is the data?

**A**: INDRA CoGEx is updated regularly from:
- PubMed (continuously, with some lag)
- Pathway databases (quarterly)
- Protein databases (quarterly)

Check the INDRA CoGEx repository for latest update information.

### Q: Can I query non-human genes?

**A**: Currently, INDRA CoGEx focuses on human biology. For model organisms, results may be limited. Check gene resolution first.

### Q: What if my genes are isoform-specific?

**A**: INDRA typically aggregates to gene level. Isoform-specific statements may be available in evidence text but not separated in the primary results.

---

## Additional Resources

### Documentation
- **INDRA Documentation**: https://indra.readthedocs.io/
- **INDRA CoGEx GitHub**: https://github.com/gyorilab/indra_cogex
- **MCP Server README**: [README.md](../README.md)

### Examples
- **Code Examples**: [examples/subnetwork_extraction.py](../examples/subnetwork_extraction.py)
- **Integration Tests**: [tests/integration/test_tool02_subnetwork_integration.py](../tests/integration/test_tool02_subnetwork_integration.py)

### Related Tools
- **Gene Features**: `cogex_query_gene_or_feature` - For gene expression, GO terms, domains
- **Enrichment**: `cogex_enrichment_analysis` - For pathway enrichment analysis
- **Disease**: `cogex_query_disease_or_phenotype` - For disease-gene associations

### Publications
- Gyori et al. (2017). "From word models to executable models of signaling networks using automated assembly." Molecular Systems Biology.
- Gyori et al. (2023). "INDRA CoGEx: An automatically assembled biomedical knowledge graph." bioRxiv.

---

**Last Updated**: 2025-01-26
**Version**: 2.0.0
