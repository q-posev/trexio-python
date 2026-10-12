# 30 — Constraints, invariants, and the one behavior that must survive

## Hard invariants (definition of "drop-in" — every session's gate)

1. **Public namespace unchanged.** After the split, `import trexio` exposes exactly the names it
   does today: `File`, `Error`, `string_of_error`, the `TREXIO_*` constants, `open`-less module
   helpers (`to_bitfield_list`, `to_orbital_list(_up_dn)`, `convert_nao_radius`,
   `evaluate_nao_radial(_all)`, `flush`, `info`), **and** all 862 `has_/read_/write_/delete_`.
2. **ABI unchanged.** The set of `pytr.<name>` references in `api/trexio.py` + `api/trexio_gen.py`
   **== `tools/required_api.names` (878)**. Neither more (unless a deliberate release bump) nor
   fewer. `tools/check_api_symbols.py --verify` must report `missing=0`.
3. **C++ output byte-identical.** `tools/gen_binding.py` refactored to import the shared model must
   still produce the **exact same** `src/generated_bindings.cpp` (`git diff` empty) as before.
4. **No new public constant**, no renamed function, no changed signature. Signatures are part of
   the surface (e.g. `read_nucleus_charge(trexio_file, dim=None, doReshape=None, dtype=None)`).

## "Do NOT touch" list (touching any = stop and reconsider)

- `src/core.cpp` — hand-written core binding (lifecycle/state/NAO/bitfield/delete/backend constants).
- The compiled `pytrexio.*.so` (build artifact) and the `api/trexio/` symlink scheme (except the
  documented *addition* of the `trexio_gen.py` symlink in task-4).
- `tools/required_api.names` — it is the contract; generation reads it, never rewrites it.
- `tests/` — the suites define the contract; if a test fails after the split, the **split is wrong**,
  not the test. (The only edit the split needs to make to tests is if one of them was asserting a
  behavior we *removed*, e.g. a `write_basis_r_power(<list of floats>)` round-trip — update it to a
  list of ints.)
- The 13 core functions' logic (they move to `_base.py`/core but keep identical bodies).

## PROVENANCE items — one survives (Phase-3 constants), one was removed (Phase-4)

### (a) Back-end constants (Phase 3) — normal core content now
`TREXIO_HDF5=0, TREXIO_TEXT=1, TREXIO_AUTO=2, TREXIO_MEMORY=3, TREXIO_INVALID_BACK_END=4` for
2.6.1+0102739 (TREX-CoE#340 renumber). Put them in `api/trexio/_base.py`. **They must equal the
installed `libtrexio`/`trexio.h`** — verify with:
```sh
grep -E "define TREXIO_(HDF5|TEXT|AUTO|MEMORY|INVALID)" $HOME/.local/include/trexio.h
```
A future release that renumbers them → update the literals in `_base.py` (or emit them from the
header). This is a normal core edit, not an "exception."

### (b) `write_basis_r_power` — standard int64 SAFE_ARRAY_W writer (Phase-4 exception REMOVED)
The old `PROVENANCE.md` "documented exception (Phase 4)" claimed `write_basis_r_power`'s list/tuple
branch must unconditionally flatten a 1-D float list to int64 (a "client-compat behavior"). That was
a **misdiagnosis, removed 2026-10-14**. `write_basis_r_power` is generated with the **same standard
SAFE_ARRAY_W int64 template** as every other int64 array (`write_basis_nao_grid_start`,
`write_auxbasis_r_power`, ...) — see `references/20` with `{npw} = np.int64`. There is **no**
per-name OVERRIDES entry and **no** forced-flatten special case.

The pre-generation `api/trexio.py` still carries the old forced-flatten deviation for this one name
(list/tuple branch: `dset_flat = np.array(dset_w, dtype=np.int64).flatten()` unconditionally).
**Do not preserve it.** Task-3 replaces that body with the standard int64 writer — the same
list/tuple branch as `write_basis_nao_grid_start` (`try: ncol = len(dset_w[0]); flatten` then
`except TypeError: doFlatten = False`). The "clients pass a float list for an int64 field" issue is
on the client (`trexio_tools`) side, not trexio-python's.

**Test implication:** if `tests/` asserts the forced-flatten (e.g. a `write_basis_r_power([0.0]*n)`
round-trip), update it to a list of ints (`[0]*n`) or remove it — it is *not* a regression to protect.

## Every session: the loop

```sh
# 0) env (see README)
# <task-specific command(s)>
python3 Plan/api-trexio-generation/verify/check_equivalence.py      # static, no build -> MUST PASS
python3 tools/check_api_symbols.py --verify                         # missing=0
# once task-4 wiring is in place:
pip install -v . && python -m pytest tests/ --quiet                 # full suite
```

Drop any non-trivial output/log into `scratch/<task>/`. Leave a one-line note of what you changed.

## Rollback (cheap)

- The only tracked files that change pre-commit are the four `api/*` + the new `tools/trexio_api_model.py`
  + `tools/gen_trexio_py.py` + `CMakeLists.txt`. If anything goes sideways before committing:
  `git -C <worktree> restore api/trexio.py` and `git -C <worktree> status` to see the rest.
- The frozen baselines in `Plan/.../verify/` are **read-only references**; a session never edits them.
