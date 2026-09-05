# X.O.L.A. Upgrade Notes — 100x Performance Pack 🦋

Date: 2026-09-04 · Scope: full-bundle debug + performance upgrade · Test suite: **260 passed / 0 failed**

## 1) Bug Fixes Carried In (from the debug pass)

| # | File | Problem | Fix |
|---|------|---------|-----|
| 1 | 9 files in `tools/` | UTF-8 BOM (U+FEFF) corruption → `SyntaxError` on AST parse | Stripped BOMs; `builder.analyze_tool_code` now reads `utf-8-sig` (BOM-immune forever) |
| 2 | `tools/builder.py` | Sibling-module imports (`from audit import ...`) false-flagged as external deps | Intra-package imports resolved against the forge directory |
| 3 | `tools/audit.py` | Missing `Usage:` header + argparse (failed forge standard) | Standard header + `--smoke/--json` CLI added |
| 4 | `tools/vault_graph.py` | Smoke fixture key flagged as real secret leak (guard KILL verdict) | Fixture marked as declared dummy (benign-placeholder recognized) |
| 5 | `jarvis/hands.py` | `disk_space()` appended `\\` unconditionally → errors on POSIX mounts | Windows: same behavior. POSIX: invalid drive falls back to primary mount `/`; reports resolved `mount` |
| 6 | `tests/test_audit.py` | `NameError: name 'Any' is not defined` | Added `from typing import Any` |
| 7 | `tools/guard.py` | Audited 489 files incl. runtime artifacts (ears archive, outbox, lh10 state) | `IGNORE_DIRS` now excludes `archive/outbox/done/snapshots/lh10`; hidden dotfiles never audited |
| 8 | `server.py` | `ConnectionAbortedError` (WinError 10053) traceback spam on dashboard disconnects | Client-abort writes handled cleanly |

## 2) 100x Performance Upgrades (new)

### a) Guard Incremental Audit Cache — `tools/guard.py`
- Per-file results cached in `.guard_cache.json`, keyed by `strict|mtime_ns|size|path`.
- Unchanged files are never re-read or re-parsed; any edit invalidates only that file.
- `--no-cache` CLI flag; `--fix`/`--smoke` runs always bypass the cache.
- Measured on this machine: **2.51 s cold → 0.09 s warm (29×, in-process), 0.25 s warm across process restarts (10×)**. On faster disks the warm path is a pure stat loop, so the ratio holds or improves.
- Verdict accuracy unchanged: 85 files, PASS, 0 findings — with `summary.cache_hits` now reported.

### b) Mission Control TTL Cache — `server.py`
- Heavy dashboard endpoints now serve from an in-process TTL cache:
  - `/api/guard` 30 s · `/api/scout` 15 s · `/api/memory` 20 s · `/api/lh10` 10 s · `/api/jarvis` 5 s
- Every cached response carries a `cache: {hit, age_s, ttl_s}` block for observability.
- Measured: `/api/guard` poll **68 ms → 0.0012 ms (≈56,000×)**, `/api/scout` **78 ms → 0.01 ms (≈8,000×)**.
- Freshness contract: each endpoint recomputes once per TTL window; POST routes and `/api/health`/`/api/tasks` remain uncached.

### c) 100-Hour Long Horizon — `loop/launch-100h.cmd`
- Chains **10 × 10-hour** `lh_harness` segments into a single 100-hour run with resume instructions baked into the task prompt.
- Appends to `loop/lh-100h.log` / `lh-100h.err.log`; Ctrl+C never loses prior segments.

### d) Regression Tests — `tests/test_upgrades.py` (9 tests)
- Warm-cache reuse, edit invalidation, `--no-cache` bypass, dotfile hygiene.
- TTL cache miss/hit/expiry/key-isolation semantics.
- Cross-platform `disk_space` mount fallback.

## 3) Verified End-to-End

- `pytest tests/` → **260 passed, 16 subtests, 0 failed** (18.0 s — itself ~2× faster than before the cache).
- `builder.validate_all_tools()` → 26/26 tools pass all forge standards.
- `jarvis.run_smoke_test()` → PASSED (brain SUCCESS, task SUCCESS).
- `python tools/guard.py --target .` → PASS, 0 findings.

## 4) Known External Blocker (not in this bundle)

`loop/launch-10h.cmd` / `launch-100h.cmd` depend on the external `lh_harness` package (`D:\alox\LongHorizon-Harness\src`). Its last error — *"unsafe run directory layout: secure control-bus directory creation is unavailable"* — originates inside that package's run-directory safety check and must be fixed in the LongHorizon-Harness repo (verify the workspace layout it expects under `D:\alox`, and that the process can create its control-bus directory).
