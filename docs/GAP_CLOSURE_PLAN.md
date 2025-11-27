# MCP Test Gap Closure Plan

Date: 2025-11-27  
Owners: QA/Tools (primary), Backend (support), DevEx (CI)

## Objectives
- Enforce data-realism: every “integration” test must prove that the backend returns non-empty, correctly shaped data for known-good entities.
- Align tests with production code paths: cover MCP server JSON-RPC → handlers → adapter → backends for all 16 tools.
- Eliminate blind spots from mocks by adding at least one live check per client/tool and resolving the Tool 16 xfail.
- Keep CI practical: fast smoke profile (<10 min) and nightly/full profile (20–30 min).

## Current State (snapshot)
- Integration tests hit live Neo4j/REST via `integration_adapter`; all 16 tools have at least a smoke case.
- MCP server path is only partially covered (`tests/integration/test_mcp_server.py` exercises a few handlers).
- Many tests assert only “not None / not 'Error:'”; minimal or no data assertions.
- Tool 16 (protein functions) is xfail due to missing GO annotations.
- Unit/cache/performance suites use mocks heavily; good for speed but do not guarantee live correctness.

## Gap List
1) Weak assertions: happy-path tests don’t fail on empty payloads.  
2) Incomplete MCP-path coverage: most tools tested via tool functions, not handlers/JSON-RPC.  
3) Tool 16 unresolved: xfail blocks “all tools green.”  
4) No live sanity per client outside integration layer; mocks mask API regressions.  
5) Flake control/threshold policy not standardized.  
6) Observability: no per-tool data metrics recorded in CI artifacts.  
7) Contributor guidance missing for new tests and thresholds.

## Closure Actions (exhaustive)

### A. Data-Validation Upgrades (All 16 Tools)
- Add shared helpers in `tests/integration/utils.py`:
  - `assert_json(result) -> dict`
  - `assert_keys(data, required_keys)`
  - `assert_non_empty(data, key, min_len=1)`
  - `assert_id_format(value, pattern_fn)`
  - `assert_pagination(first_page, second_page)` ensures offsets differ and combined unique count increases.
- For each tool’s happy-path test:
  - Parse JSON; assert required top-level keys present.
  - Assert key payloads non-empty for canonical entities (thresholds below).
  - Check identifier format (HGNC numeric/“HGNC:”, NCT starts “NCT”, GO starts “GO:”).
  - Pagination tests must verify non-overlap and growth.
- For edge-case tests:
  - Assert structured empties (`len == 0`) or explicit error message substrings; never swallow exceptions silently.

### B. Canonical Entities & Thresholds
- Centralize in `tests/integration/fixtures_known.py`:
  - Genes: TP53 (≥5 pathways, ≥5 GO terms, expression rows >0), BRCA1 (≥3 variants), EGFR (≥1 kinase activity if data exists).
  - Drugs: imatinib (targets >0, indications >0), pembrolizumab (trials >0).
  - Diseases: breast cancer (mechanisms >0), Alzheimer disease (phenotypes >0).
  - Pathways: MAPK signaling (genes >3).
  - Cell lines: A549 (mutations >0).
  - Variants: rs7412 (diseases/phenotypes >0).
  - Trials: NCT02576431 must return a title/status.
- Keep thresholds minimal to avoid flakiness; prefer “>0” with format checks.

### C. MCP Server Path Parity
- Add `tests/integration/test_mcp_server_tools.py`:
  - Session fixture boots MCP server (stdio) once; reuses across tests.
  - Parametrized over all 16 tools with 1–2 canonical inputs each.
  - Sends JSON-RPC `initialize`, then `call_tool`, and validates with the same data assertions as A.
  - Validates handler importability and tool registry completeness.
- Expand `test_mcp_server.py`:
  - Add handler completeness check that compares `server.handlers.*` functions against `tools.*` signatures for each tool.
  - Add JSON-RPC pagination case for at least one tool (e.g., gene_to_features).

### D. Tool 16 Resolution
- Option 1 (preferred): Ingest GO annotations or enable REST fallback that supplies GO-based functions; then remove `xfail` and add assertions: EGFR activities list non-empty and includes kinase-like string.
- Option 2: If data cannot be provided soon, redefine contract: tool returns structured “not available” with `reason`; tests assert that shape and do not xfail. Document this contract in README and test file.
- Decision deadline: 2025-12-05. Block “all tools covered” until one path is chosen and implemented.

### E. Live Sanity per Client (De-mock Critical Path)
- For each client module (gene, subnetwork, enrichment, drug, disease, pathway, literature, variant, cell line, clinical trials, ontology, resolver, markers, kinase/protein function):
  - Add one test in `tests/integration/test_client_sanity.py` that calls the real backend with a canonical entity and asserts non-empty payload.
  - Keep existing mocked unit tests; this sanity layer guards API regressions.

### F. Flake Controls
- Timeouts: mark slow queries with `pytest.mark.timeout` using per-mode defaults (simple 5s, feature 15s, subnetwork 30s, enrichment 45s, workflow 60s).
- Threshold discipline: only use small “>0” or “>=3” counts; avoid brittle high counts.
- Retry policy: allow one retry on network/transport errors only, not on empty data.
- Environment override: allow `KNOWN_ENTITY_OVERRIDE=...` to swap fixtures when running against different regions.

### G. CI Profiles
- `integration-smoke`: JSON-RPC path, one happy + one edge per tool, limits small, target <10 minutes; make this the default CI job.
- `integration-full`: all existing integration tests + new data assertions; run nightly or pre-release.
- Add Make targets / scripts:
  - `make test-smoke`
  - `make test-full`
  - `make test-mcp` (server JSON-RPC suite only)

### H. Metrics & Artifacts
- After test session, write `artifacts/integration_metrics.json` capturing per-tool:
  - pass/fail, row counts, durations, endpoint used.
- On CI, upload artifact; alert if any canonical entity returns zero rows where previously >0 (simple diff against last artifact).

### I. Contributor Checklist (add to CONTRIBUTING/TESTING)
- Added/updated assertions for non-empty data?
- Covered tool via MCP server JSON-RPC?
- Updated thresholds/fixtures if backend shape changed?
- For Tool 16 changes: contract documented and tests aligned?
- Smoke profile still under 10 minutes locally?

### J. Ownership
- Tool leads: one owner per tool to maintain thresholds and fixtures.
- QA lead: oversee MCP server suite and flake management.
- DevEx: maintain CI profiles and artifact publishing.

### K. Timeline (proposed)
- By 2025-12-01: Shared helpers, fixture file, upgraded Tool 1–5 tests with data assertions; smoke profile wired in CI.
- By 2025-12-03: MCP server tool matrix in place; per-client sanity tests added.
- By 2025-12-05: Tool 16 decision and implementation.
- By 2025-12-08: All tools upgraded with assertions; artifacts + alerts live.

## File/Code Changes Needed (concise list)
- New: `tests/integration/utils.py` (assertion helpers)
- New: `tests/integration/fixtures_known.py` (canonical entities + thresholds)
- New: `tests/integration/test_mcp_server_tools.py` (JSON-RPC matrix)
- New: `tests/integration/test_client_sanity.py` (per-client live sanity)
- Updates: all `tests/integration/test_tool*.py` to use helpers and assert non-empty data
- Update: `tests/integration/test_mcp_server.py` to add handler completeness checks
- Update: `TESTING.md` and `CONTRIBUTING.md` with profiles/checklist
- CI: add artifacts upload and alert step; add make targets

## Risks & Mitigations
- Backend variability may cause empties: keep thresholds minimal and entities well-known; allow env override.
- Longer runtimes: keep smoke profile lean; cap pagination limits.
- Server start flakiness: start once per session; increase startup timeout to 15s; capture stderr on failure.

## Definition of Done
- All 16 tools have happy-path tests that fail on empty/ill-shaped data.
- MCP server JSON-RPC suite exercises all tools successfully.
- Tool 16 no longer xfail; contract is explicit and enforced.
- CI smoke <10 min, full suite green nightly; artifacts produced with per-tool counts.
