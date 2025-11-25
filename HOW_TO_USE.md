# How to Use the INDRA CoGEx MCP Server

## ✅ Current Status

The MCP server is **configured and ready** in this workspace!

### Known Issue
Project-scoped MCP servers don't appear in `claude mcp list` due to a [known CLI bug](https://github.com/anthropics/claude-code/issues/5963), but **they work functionally**. The runtime loads them correctly when you try to use them.

### Verification
```bash
# Server is in .mcp.json:
$ jq -r '.mcpServers | keys[]' .mcp.json
indra-cogex

# Server starts correctly:
$ venv/bin/python3 -m cogex_mcp.server
✓ All 16 tools register successfully
```

---

## 🧪 Test It Now

Ask Claude Code (in this chat or a new one):

### Simple Test
```
Use the cogex_query_gene_or_feature tool to query the gene TP53.
Include expression data and GO terms. Use markdown format.
```

**Expected**: 
- First time: Approval prompt to connect to "indra-cogex"
- After approval: Returns comprehensive TP53 profile

### Evaluation Question (Easy)
```
Using indra-cogex tools, convert these HGNC IDs to gene symbols and UniProt IDs:
- HGNC:11998
- HGNC:1100
- HGNC:3467

Then find tissue expression for the gene starting with 'T'.
```

**Expected**: Multi-tool workflow using identifier resolution and gene queries

---

## 📚 Available Tools (16)

1. **cogex_query_gene_or_feature** - Gene profiles, expression, GO terms
2. **cogex_extract_subnetwork** - Graph traversal, regulatory networks
3. **cogex_enrichment_analysis** - GSEA, pathway enrichment
4. **cogex_query_drug_or_effect** - Drug targets, side effects
5. **cogex_query_disease_or_phenotype** - Disease mechanisms
6. **cogex_query_pathway** - Pathway membership
7. **cogex_query_cell_line** - CCLE mutations
8. **cogex_query_clinical_trials** - ClinicalTrials.gov
9. **cogex_query_literature** - PubMed evidence
10. **cogex_query_variants** - GWAS variants
11. **cogex_resolve_identifiers** - ID conversion
12. **cogex_check_relationship** - Boolean validation
13. **cogex_get_ontology_hierarchy** - GO/HPO navigation
14. **cogex_query_cell_markers** - CellMarker queries
15. **cogex_analyze_kinase_enrichment** - Phosphoproteomics
16. **cogex_query_protein_functions** - Enzyme activities

**Full specs**: See `TOOLS_CATALOG.md`

---

## 📋 Evaluation Questions

10 complex questions ready in `evaluation/questions.xml`:
- Q1: Drug-Target-Pathway (imatinib)
- Q2: Alzheimer's genetics
- Q6: Identifier resolution (easiest)
- Q10: Ontology navigation

**See**: `evaluation/README.md` for details

---

## 🔧 Troubleshooting

**Tools not working?**
1. Verify server starts: `venv/bin/python3 -m cogex_mcp.server`
2. Check approval prompt appeared and you accepted
3. Check Claude Code output panel for errors

**Need to reload?**
- Close and reopen this workspace folder
- Or restart Claude Code

---

## 📖 Documentation

- `QUICK_START.md` - Usage examples
- `TOOLS_CATALOG.md` - Complete tool specifications  
- `TESTING.md` - Test framework (203 tests)
- `evaluation/README.md` - Evaluation suite guide

**Status**: ✅ Ready to use - just ask Claude to use the tools!
