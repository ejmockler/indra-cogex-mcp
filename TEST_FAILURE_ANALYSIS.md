# Test Failure Analysis - INDRA CoGEx MCP

**Date**: 2025-11-25
**Test Results**: 233 passed, 55 failed

## Summary by Tool

| Tool | Total Tests | Passing | Failing | Status |
|------|-------------|---------|---------|--------|
| 1 | 16 | 16 | 0 | ✅ PRODUCTION READY |
| MCP | 18 | 18 | 0 | ✅ PRODUCTION READY |
| 6 | 9 | 5 | 4 | ⚠️ Entity resolution |
| 7 | 9 | 8 | 1 | ⚠️ Minor fix needed |
| 8 | 10 | 5 | 5 | ⚠️ Entity resolution |
| 9 | 10 | 8 | 2 | ⚠️ Backend method |
| 10 | 11 | 8 | 3 | ⚠️ Type error |
| 11 | 21 | 14 | 7 | ⚠️ Empty results |
| 12 | 20 | 14 | 6 | ⚠️ Empty results |
| 13 | 16 | 8 | 8 | ❌ Missing adapter query |
| 14 | 22 | 19 | 3 | ⚠️ Validation issues |
| 15 | 17 | 11 | 6 | ⚠️ Empty results |
| 16 | 19 | 9 | 10 | ❌ REST API 404 |

## Critical Issues

### Issue #1: Tool 13 - Missing Adapter Query
**Severity**: HIGH
**Affected Tests**: 8 failures

**Error**:
```
Error: Failed to resolve ontology term: Unknown query: get_ontology_term
```

**Root Cause**: The adapter doesn't have a `get_ontology_term` query registered.

**Fix Required**:
1. Add `get_ontology_term` to Neo4j client queries
2. Register query in adapter
3. Implement ontology term resolution

**Estimated Fix Time**: 30 minutes

### Issue #2: Tool 16 - REST API 404
**Severity**: HIGH
**Affected Tests**: 10 failures

**Error**:
```
Client error '404 NOT FOUND' for url 'https://discovery.indra.bio/api/get_enzyme_activities'
```

**Root Cause**: REST API endpoint doesn't exist or has been renamed.

**Fix Required**:
1. Check INDRA REST API documentation for correct endpoint
2. Either:
   - Update endpoint URL in REST client
   - Implement Neo4j-based alternative
   - Mark as known limitation if endpoint removed

**Estimated Fix Time**: 1 hour (if endpoint exists), 2+ hours (if needs Neo4j implementation)

### Issue #3: Tool 10 - Type Error
**Severity**: MEDIUM
**Affected Tests**: 1 failure

**Error**:
```
int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
```

**Root Cause**: Code expects integer but receives None.

**Fix Required**:
1. Add None check before int() conversion
2. Provide default value or skip field

**Estimated Fix Time**: 15 minutes

## Tool-Specific Analysis

### Tool 6: Pathway Queries (4 failures)

**Failures**:
1. `test_get_genes_p53_pathway` - Empty results
2. `test_check_membership_tp53_in_p53_pathway` - Returns false when should be true
3. `test_unknown_pathway_error` - Should error but returns empty
4. `test_pathway_source_filter` - Returns 'unknown' instead of 'reactome'

**Pattern**: Pathway entity resolution issues

**Fix Priority**: MEDIUM
**Estimated Fix Time**: 1 hour

**Recommended Fix**:
- Update entity resolver to handle pathway names
- Convert pathway names to CURIEs (e.g., "p53 pathway" → "reactome:R-HSA-109581")

### Tool 7: Cell Line Queries (1 failure)

**Failures**:
1. `test_get_mutated_genes_mcf7` - Empty results

**Pattern**: Cell line entity resolution

**Fix Priority**: LOW
**Estimated Fix Time**: 30 minutes

**Recommended Fix**:
- Update entity resolver to handle cell line names
- Convert names to CCLE CURIEs (e.g., "MCF7" → "ccle:MCF7_BREAST")

### Tool 8: Clinical Trials (5 failures)

**Failures**:
1. `test_get_for_drug_pembrolizumab` - Empty results
2. `test_get_for_disease_diabetes` - Empty results
3. `test_get_by_id_specific_trial` - Returns 'unknown' ID
4. `test_pagination_trials` - Empty results
5. (Another pagination test)

**Pattern**: All queries return empty

**Fix Priority**: MEDIUM
**Estimated Fix Time**: 1 hour

**Recommended Fix**:
- Verify clinical trial data exists in Neo4j (we know 11,395 trials exist)
- Fix entity resolution for drugs/diseases
- Fix trial ID lookup

### Tool 9: Literature (2 failures)

**Failures**:
1. `test_search_by_mesh_autophagy_cancer` - Empty results
2. `test_pagination_publications` - Empty results

**Pattern**: Backend method not implemented

**Fix Priority**: LOW
**Estimated Fix Time**: 1 hour

**Recommended Fix**:
- Implement literature search in Neo4j client
- Or mark as known limitation if data not in Neo4j

### Tool 10: Variants (3 failures)

**Failures**:
1. `test_get_for_gene_brca1` - Type error (int/None)
2. `test_get_for_disease_alzheimer` - Empty results
3. `test_variant_to_genes_apoe` - Empty results

**Pattern**: Type error + empty results

**Fix Priority**: MEDIUM
**Estimated Fix Time**: 1 hour

**Recommended Fix**:
- Fix int/None type error
- Verify variant data exists (we know 161K+ variants in database)
- Fix entity resolution for variants

### Tool 11: Identifier Mapping (7 failures)

**Failures**:
1. `test_tp53_symbol_to_hgnc` - Empty results
2. `test_multiple_symbols_to_hgnc` - Empty results
3. `test_tp53_hgnc_to_uniprot` - Empty results
4. `test_multiple_hgnc_to_uniprot` - Empty results
5. `test_hgnc_to_symbol` - Empty results
6. `test_empty_identifier_list` - Validation error
7. `test_mixed_valid_invalid_identifiers` - Empty results

**Pattern**: All identifier mappings return empty

**Fix Priority**: HIGH
**Estimated Fix Time**: 2 hours

**Recommended Fix**:
- Implement identifier mapping in Neo4j client
- Query BioEntity nodes for xrefs
- Map between namespaces (hgnc ↔ symbol ↔ uniprot)

### Tool 12: Pathway Hierarchy (6 failures)

**Failures**:
1. `test_pathway_source_filter` - Returns 'unknown'
2. `test_p53_pathway_genes` - Empty results
3. `test_apoptosis_pathway_genes` - Empty results
4. `test_tp53_in_p53_pathway` - Returns false
5. `test_pathway_metadata_completeness` - Gene count = 0

**Pattern**: Similar to Tool 6 (pathway issues)

**Fix Priority**: MEDIUM
**Estimated Fix Time**: 1 hour

**Note**: Pathway hierarchy relationships may not exist in database (known limitation from NEO4J_SCHEMA.md)

### Tool 13: Ontology (8 failures)

**All failures due to missing adapter query `get_ontology_term`**

**Fix Priority**: HIGH
**Estimated Fix Time**: 30 minutes

### Tool 14: Relationships (3 failures)

**Failures**:
1. `test_imatinib_targets_abl1` - Returns false
2. `test_brca1_breast_cancer` - Returns false
3. `test_unknown_entity2` - Should error but returns false

**Pattern**: Relationship checks return false instead of true/error

**Fix Priority**: MEDIUM
**Estimated Fix Time**: 1 hour

**Recommended Fix**:
- Verify relationship checking logic
- Fix entity resolution for drugs/genes/diseases
- Add proper error handling for unknown entities

### Tool 15: Clinical Trials (6 failures)

**Same as Tool 8** - appears to be duplicate functionality

**Fix Priority**: MEDIUM
**Estimated Fix Time**: Same as Tool 8

### Tool 16: Protein Functions (10 failures)

**All failures due to REST API 404**

**Fix Priority**: HIGH
**Estimated Fix Time**: 1-2 hours

## Common Patterns

### Pattern #1: Empty Results (24 failures)
**Cause**: Entity resolution or query issues
**Solution**:
- Fix entity resolver to handle names → CURIEs
- Verify Neo4j queries return data
- Add logging to see what's being queried

### Pattern #2: Missing Backend Queries (8 failures)
**Cause**: Adapter queries not registered
**Solution**:
- Add missing queries to Neo4j client
- Register in adapter

### Pattern #3: REST API Issues (10 failures)
**Cause**: REST endpoints missing or changed
**Solution**:
- Update endpoint URLs
- Or implement Neo4j alternatives

### Pattern #4: Type Errors (1 failure)
**Cause**: None values not handled
**Solution**:
- Add None checks
- Provide defaults

## Recommended Fix Order

### Phase 1: Quick Wins (2-3 hours)
1. ✅ Fix Tool 13 missing adapter query (30 min)
2. ✅ Fix Tool 10 type error (15 min)
3. ✅ Fix Tool 11 identifier mapping (2 hours)

**Impact**: 16 test failures → ~8 failures

### Phase 2: Entity Resolution (3-4 hours)
4. ✅ Fix pathway entity resolution (affects Tools 6, 12) (1 hour)
5. ✅ Fix clinical trial entity resolution (affects Tools 8, 15) (1 hour)
6. ✅ Fix cell line entity resolution (Tool 7) (30 min)
7. ✅ Fix variant entity resolution (Tool 10) (1 hour)
8. ✅ Fix relationship entity resolution (Tool 14) (1 hour)

**Impact**: 8 failures → ~3 failures

### Phase 3: REST API / Backend (2-4 hours)
9. ✅ Fix Tool 16 REST API or implement Neo4j alternative (2 hours)
10. ✅ Fix Tool 9 literature search (1 hour)

**Impact**: 3 failures → 0 failures ✅

**Total Estimated Time**: 7-11 hours to fix all 55 failures

## Success Metrics

### Current
- 233/344 tests passing (67.7%)
- 1/16 tools production ready (Tool 1)
- MCP infrastructure production ready

### After Phase 1
- ~248/344 tests passing (72.1%)
- 2/16 tools production ready

### After Phase 2
- ~341/344 tests passing (99.1%)
- 10-12/16 tools production ready

### After Phase 3
- 344/344 tests passing (100%) ✅
- 16/16 tools production ready ✅

## Notes

1. **Database Validation**: We've confirmed data exists in Neo4j:
   - 11,395 clinical trials
   - 161K+ variants
   - 176K+ pathways
   - 1.1M+ mutations

2. **Test Quality**: Tests are properly validating data exists, which is why they're failing when queries return empty.

3. **Infrastructure Solid**: The failures are in business logic (queries, entity resolution), not infrastructure.

4. **Easy Fixes**: Most fixes are straightforward:
   - Add missing adapter queries
   - Fix entity resolution
   - Add None checks
   - Update REST endpoints
