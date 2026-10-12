# 30 — Constraints, invariants, and the two behaviors that must survive

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
  not the test (the only acceptable new test is a *round-trip / r_power* addition, see Known behaviors).
- The 13 core functions' logic (they move to `_base.py`/core but keep identical bodies).

## Known behaviors the split must PRESERVE (from PROVENANCE.md)

### (a) Back-end constants (Phase 3) — normal core content now
`TREXIO_HDF5=0, TREXIO_TEXT=1, TREXIO_AUTO=2, TREXIO_MEMORY=3, TREXIO_INVALID_BACK_END=4` for
2.6.1+0102739 (TREX-CoE#340 renumber). Put them in `api/trexio/_base.py`. **They must equal the
installed `libtrexio`/`trexio.h`** — verify with:
```sh
grep -E "define TREXIO_(HDF5|TEXT|AUTO|MEMORY|INVALID)" $HOME/.local/include/trexio.h
```
A future release that renumbers them → update the literals in `_base.py` (or emit them from the
header). This is a normal core edit, not an "exception."

### (b) `write_basis_r_power` — PERMANENT client-compat behavior (Phase 4)  ← preserve, never drop
**Context (owner-confirmed 2026-10-12):** `basis_r_power` is an int64 array, but clients (e.g.
`trexio_tools` Gaussian/ORCA converters) routinely pass a **1-D list of floats** (e.g.
`[0.0, 0.0, ...]`). The int64 binding `pytr.trexio_write_safe_basis_r_power_64` **rejects** a bare
Python list containing float elements (`TypeError: 'float' object is not iterable`). trexio-python
fixes this by normalizing list/tuple input to a **flat int64 numpy array** before the call. This is
correct, intended behavior ("the conversion is performed" per the docstring), **not a temp patch** —
the plan must keep emitting it. **Do NOT adopt the generic SAFE_ARRAY_W template for this name** —
that template's list branch probes `len(dset_w[0])` and would let a 1-D float list through.

The exact current logic to reproduce (`api/trexio.py` @ 25471, the list/tuple branch is the key
difference):
```python
    doConversion = False
    doFlatten = False
    if not isinstance(dset_w, (list, tuple)):
       if isinstance(dset_w, np.ndarray) and (not dset_w.dtype==np.int64 or not dset_w.dtype==np.float64):
           doConversion = True
       if len(dset_w.shape) > 1:
           doFlatten = True
           if doConversion:
               dset_64 = np.int64(dset_w).flatten()
           else:
               dset_flat = np.array(dset_w, dtype=np.int64).flatten()
       else:
           if doConversion:
               dset_64 = np.int64(dset_w)
    else:
        # <-- THE FIX: always flatten a list/tuple to int64 (clients pass 1-D float lists)
        doFlatten = True
        dset_flat = np.array(dset_w, dtype=np.int64).flatten()

    if doConversion:
        rc = pytr.trexio_write_safe_basis_r_power_64(trexio_file.pytrexio_s, dset_64)
    elif doFlatten:
        rc = pytr.trexio_write_safe_basis_r_power_64(trexio_file.pytrexio_s, dset_flat)
    else:
        rc = pytr.trexio_write_safe_basis_r_power_64(trexio_file.pytrexio_s, dset_w)

    if rc != TREXIO_SUCCESS:
        raise Error(rc)
```

**Generator handling:** `OVERRIDES={"write_basis_r_power": <int64-writer-with-forced-list-flatten>}`.
Concretely: the SAFE_ARRAY_W int64 template, but the `list/tuple` branch does
`dset_flat = np.array(dset_w, dtype=np.int64).flatten()` **unconditionally** (skip the `len(dset_w[0])`
probe). **Conservative scope: only `write_basis_r_power`.**
*Optional (owner-only, NOT default):* the same latent defect exists in other int64 writers — the
owner may ask to extend the forced-flatten to ALL int64 arrays. Do this only if explicitly requested;
it changes behavior beyond the documented fix.

**Gate:** there is a test exercising `write_basis_r_power` with a 1-D float list (search
`tests/` for `write_basis_r_power` / `r_power`). If none exists, add one (round-trip: write
`[0.0]*n` then read back an int64 array). This is the one allowed *new* test.

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
