# Task 1 — Split `api/trexio.py` → core + `_base.py`; surface into `api/trexio_gen.py` (a copy)

**Track:** A · **Depends on:** none (can run now) · **Parallel-safe with:** task-2, task-6
**Why first:** establishes the exact target layout and makes the generated file's *location +
imports* real, so task-3's generator just swaps the copy for generated output.

## Objective
Break the 35,038-line `api/trexio.py` into three files **without changing any logic**:
CORE (`api/trexio.py`) + SHARED BASE (`api/trexio/_base.py`) + a **verbatim copy** of the surface
(`api/trexio_gen.py`). After this task `check_equivalence.py` passes STATIC (names/symbols/core
preserved) and the package still imports.

## Files I own (only these)
- `api/trexio.py`          (becomes the core — surface REMOVED)
- `api/trexio/_base.py`    (NEW — the shared bits)
- `api/trexio_gen.py`      (NEW — verbatim copy of the 862 surface functions)
- `api/trexio/trexio_gen.py` (NEW symlink → `../trexio_gen.py`)
Do NOT touch `tools/`, `CMakeLists.txt`, `pyproject.toml`, `tests/` (other tasks own those).

## Steps

1. **Snapshot the rollback copy** (so you can diff/restore):
   ```sh
   mkdir -p Plan/api-trexio-generation/scratch/task1
   cp api/trexio.py Plan/api-trexio-generation/scratch/task1/api_trexio.py.orig
   ```
2. **Create `api/trexio/_base.py`** by MOVING these exactly (keep bodies byte-identical):
   - the `numpy` import (`import numpy as np`)
   - the low-level module import, alias **`pytr`**: `from . import pytrexio as pytr`
   - `PYTREXIO_MAX_STR_LENGTH = 2048`
   - the whole `TREXIO_FAILURE … TREXIO_AMBIGUOUS_CARTESIAN` constant block (module-level `TREXIO_*` codes)
   - the back-end id block `TREXIO_HDF5 / TEXT / AUTO / MEMORY / INVALID_BACK_END` (values must
     match the installed lib — see references/30 §a)
   - `class Error` and `def string_of_error`
   `_base.py` must import **only** `numpy` and `pytrexio` — nothing from the package `__init__`.
3. **Create `api/trexio_gen.py`** = the 862 surface functions (everything whose name starts
   `read_ / write_ / has_ / delete_`), moved verbatim. Its header (first importable lines):
   ```python
   # GENERATED (task-1 copy; task-3 replaces the bodies) — DO NOT HAND-EDIT.
   from __future__ import annotations      # <- lets the sparse defs keep `trexio_file: File` without importing File
   from ._base import (
       pytr, np, Error,
       TREXIO_SUCCESS, TREXIO_FAILURE, TREXIO_UNSAFE_ARRAY_DIM, TREXIO_DELIM and any other codes used,
       PYTREXIO_MAX_STR_LENGTH,
   )
   ```
   (The sparse signatures like `def read_ao_2e_int_eri(trexio_file: File, …)` are why
   `from __future__ import annotations` is required — `File` lives in core and must NOT be
   imported here or it is the import cycle from references/10.)
4. **Rewrite `api/trexio.py`** to be CORE only. It must now:
   ```python
   from . import _base
   from ._base import (Error, string_of_error, PYTREXIO_MAX_STR_LENGTH,
                       TREXIO_SUCCESS, TREXIO_FAILURE, TREXIO_UNSAFE_ARRAY_DIM,
                       TREXIO_HDF5, TREXIO_TEXT, TREXIO_AUTO, TREXIO_MEMORY, TREXIO_INVALID_BACK_END,
                       TREXIO_FAILURE, /* … all code constants used by the 13 core helpers … */)
   from ._base import pytr, np          # only if a core helper uses pytr/np (it does: _open, flush, …)
   from ._version import __version__
   # … class File (unchanged) …
   # … the 13 module helpers: _open _close flush _inquire _cp info
   #    to_bitfield_list to_orbital_list to_orbital_list_up_dn
   #    convert_nao_radius evaluate_nao_radial evaluate_nao_radial_all (unchanged) …
   from . import trexio_gen              # <-- LAST line: pulls has_/read_/write_/delete_ into `trexio`
   ```
   The core helpers' bodies are unchanged (they already call `pytr.*` / `np.*`, which now come from `_base`).
5. **Create the symlink** and confirm the package dir:
   ```sh
   ln -s ../trexio_gen.py api/trexio/trexio_gen.py
   ls -l api/trexio          # expect: __init__.py→../trexio.py, _version.py→../pytrexio/_version.py, trexio_gen.py→../trexio_gen.py
   ```
6. **Sanity greps** (paste the results into `scratch/task1/notes.txt`):
   ```sh
   grep -nE "^def (read_|write_|has_|delete_)" api/trexio.py | wc -l   # must be 0 (all moved to gen)
   grep -nE "^def (read_|write_|has_|delete_)" api/trexio_gen.py | wc -l  # must be 862
   python -c "import ast,sys; ast.parse(open('api/trexio.py').read()); ast.parse(open('api/trexio_gen.py').read()); ast.parse(open('api/trexio/_base.py').read()); print('syntax OK')"
   ```

## Gate (must all pass before hand-off)
```sh
python3 Plan/api-trexio-generation/verify/check_equivalence.py \
        --required tools/required_api.names
python3 -m pyflakes api/trexio.py api/trexio/_base.py api/trexio_gen.py || true   # no undefined names
```
- `check_equivalence.py` → **PASS** (surface 862 in gen + core 13 in core + 878 symbols referenced by the two files).
- `api/trexio.py` has **0** surface `def`s; `api/trexio_gen.py` has **862**.
- All three files compile (`ast.parse`).

## DoD
The package imports identically (verify in task-5, which builds the wheel); the only difference is
structure. No logic was added or removed. `api/trexio.py` line count drops from 35,038 to roughly
900–1,200 (core + re-exports + `trexio_gen` import).

## Notes / gotchas
- The back-ends constants (`TREXIO_AUTO=2`, `TREXIO_MEMORY=3`, `TREXIO_INVALID_BACK_END=4`) come
  from the Phase-3 PROVENANCE exception — keep them here (references/30 §a).
- `write_basis_r_power` and every other int64 writer move to gen here (a verbatim move); task-3 will
  re-emit all of them with the **standard** SAFE_ARRAY_W template — including `write_basis_r_power`
  (no per-name override; the old Phase-4 forced-flatten is dropped). **Do not "fix" any body in this
  task.**
- If task-3 (generator) is already partway when you run, coordinate via the branch/worktree — you're
  the owner of the file layout, task-3 only rewrites the *bodies* of `api/trexio_gen.py`.
