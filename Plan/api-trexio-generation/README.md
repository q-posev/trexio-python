# Plan: generate `api/trexio.py`'s per-variable surface from trex.json (+ C header)

**Goal.** Stop hand-editing the ~862 `has_ / read_ / write_ / delete_` wrappers in
`api/trexio.py` (35,038 lines, ~90% boilerplate) on every TREXIO release. Generate them
into a sibling module `api/trexio_gen.py` from the same trusted inputs the C++ side already
uses (`third_party/trex.json` + installed `trexio.h` + `tools/required_api.names`), and keep
only the small stable **core** hand-maintained.

**Drop-in guarantee.** The public `trexio` namespace AND the set of `pytr.trexio_<sym>`
calls must be byte-identical to today (862 wrappers, 877 C symbols). `scratch/` and the
frozen baselines are there to prove it without relying on memory.

## The PROVENANCE "documented exceptions" — how this plan treats them

| PROVENANCE exception | Nature | Plan treatment |
|---|---|---|
| **Phase 3** — back-end constants (`TREXIO_AUTO=2, TREXIO_MEMORY=3, ...`) | ABI value set for 2.6.1+0102739 (TREX-CoE#340 renumber) | Lives in `api/trexio/_base.py` (core). Must match the installed `trexio.h`/lib. A release that renumbers them → small update here (or emit from the header). **Not** a real "exception" once the core is our own. |
| **Phase 4** — `write_basis_r_power` list→int64 | ~~Client-compat behavior~~ — **removed 2026-10-14 as a misdiagnosis** | Generate `write_basis_r_power` with the **standard SAFE_ARRAY_W int64 template** (same body as `write_basis_nao_grid_start`). **No** OVERRIDES, **no** forced-flatten special case. The "client passes a float list" issue is `trexio_tools`-side, not trexio-python's. |

**Read this before anything else:** there is exactly **one** behavior that must survive the split —
the Phase-3 back-end constants, kept in `_base.py`. `write_basis_r_power` is generated **like every
other int64 array**; the old "preserve the forced-flatten" note is gone (2026-10-14).

> **Shipped docs this plan re-points** (task-6): `README.md` · `PROVENANCE.md` ·
> `docs/package-layout.md` · `docs/updating-with-trexio.md` — one consistent
> picture: core is hand-written, the surface is generated, low-level module is the
> nanobind drop-in; a new release = re-vendor core+json, regenerate both, test.

## Directory contents

```
README.md                          <- you are here (overview + dispatch + DoD)
references/
  00-locked-decisions.md           -> the 3 decisions + rationale + scope (what IS / IS NOT generated)
  10-architecture.md               -> target layout, symlink+packaging, import-cycle fix, public-name flow
  20-shape-and-templates.md        -> THE key file: shape->C-symbol table + exact Python bodies for every family
  30-constraints-and-gates.md      -> "don't touch" list, invariants, the Phase-3 constants to preserve
                                       (r_power = standard int64 writer), env+verify snippet
task-1-base-and-core-split.md      -> independent session A
task-2-extract-api-model.md        -> independent session B
task-3-python-emitters.md          -> independent session C  (depends on 1 + 2)
task-4-wiring-packaging.md         -> independent session D  (depends on 3)
task-5-verification.md             -> independent session E  (depends on 4)
task-6-docs.md                     -> independent session F  (independent, can run now)
verify/
  baseline_surface.txt             -> FROZEN "before": 862 wrappers (name+signature)
  baseline_symbols.txt             -> FROZEN "before": 877 distinct pytr.trexio_* symbols
  baseline_core.txt                -> FROZEN "before": 13 core module defs
  check_equivalence.py             -> no-build gate: split is a no-op (surface + symbols + core)
  check_public_namespace.py        -> import-time gate (task-5 creates it; needs built .so + installed lib)
scratch/                           -> session evidence (diffs, logs, wc -l). Not code.
```

## Dispatch (run independent sessions)

Use **one git worktree/branch per session**. File ownership is fixed per task (below); a
session must not edit files it doesn't own.

```
Track A (code, sequential):
    task-1 (core split + _base)  ─┐
    task-2 (extract api model)   ─┴─► task-3 ─► task-4 ─► task-5
    (parallel-safe starting set : task-1, task-2, task-6)   (emitters)(wiring)(verify)

Track B (docs, independent — safe to start now):
    task-6 (PROVENANCE, updating-with-trexio, package-layout, README)
```

**Every session:**
1. Read `references/00`, `10`, `20`, `30` (they are short and shared).
2. Do only its task file's steps; touch only its "Files I own".
3. Run its gate(s); drop evidence into `scratch/<task>/`.
4. Stop at its DoD; the owner merges in the recommended order.

## Definition of done (master checklist)

- [ ] `python3 verify/check_equivalence.py` → **PASS** (surface 862 + symbols 877 + core 13 preserved).
- [ ] `python3 verify/check_public_namespace.py` → **PASS** (importable; every old name present; a few round-trips ok).
- [ ] `python3 tools/check_api_symbols.py --verify` → `missing=0`.
- [ ] `python3 tools/gen_binding.py` → `unhandled=0`, `cross-check warnings=0` (or each warning read+justified).
- [ ] `python -m pytest tests/ --all` green (**incl.** `test_abi.py`, `test_pytrexio.py`, memory suite).
- [ ] Wheel build + wheel-venv `import trexio; pytest tests/ --all` green.
- [ ] `wc -l api/trexio.py` ≈ 5–9k (was **35,038**); `api/trexio_gen.py` generated, never hand-edited.
- [ ] `write_basis_r_power` uses the **standard int64 SAFE_ARRAY_W** template (body identical to `write_basis_nao_grid_start`).
- [ ] Docs updated: `api/trexio.py` references re-pointed to core/generated; PROVENANCE retains only the
      Phase-3 constants item (Phase-4 removed as a misdiagnosis on 2026-10-14).

## Shared environment (copy into each session)

```sh
PY=/usr/bin/python3.12                       # or your miniconda 3.12
$PY -m venv /tmp/opencode/trexpU && . /tmp/opencode/trexpU/bin/activate
pip install -U pip build "scikit-build-core>=0.9" nanobind numpy pytest
export CMAKE_PREFIX_PATH="$HOME/.local"
export LD_LIBRARY_PATH="$HOME/.local/lib64:${LD_LIBRARY_PATH:-}"
# verify the ABI inputs are present before building:
grep -E "define TREXIO_(HDF5|TEXT|AUTO|MEMORY|INVALID)" $CMAKE_PREFIX_PATH/../include/trexio.h \
  2>/dev/null || grep -E "define TREXIO_(AUTO|MEMORY)" $HOME/.local/include/trexio.h
```
