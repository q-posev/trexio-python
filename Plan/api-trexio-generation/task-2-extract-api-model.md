# Task 2 — Extract `tools/trexio_api_model.py` (the shared classifier) from `gen_binding.py`

**Track:** A · **Depends on:** none · **Parallel-safe with:** task-1, task-6
**Why it matters:** one classifier, both emitters (C++ gen_binding + the new Python gen_trexio_py).
If the classifier lives in one importable module, the C++ and Python surfaces can't drift.

## Objective
Move the *classification* logic out of `tools/gen_binding.py` into a shared module
(`tools/trexio_api_model.py`) that both `gen_binding.py` and the (new) `gen_trexio_py.py` will
import. **`src/generated_bindings.cpp` must come out byte-identical to today's.**

## Files I own
- `tools/trexio_api_model.py`  (NEW — the shared model)
- `tools/gen_binding.py`       (MODIFIED — now imports the model; output invariant)

## Steps

1. **Snapshot the baseline C++** for the byte-identity check:
   ```sh
   mkdir -p Plan/api-trexio-generation/scratch/task2
   cp src/generated_bindings.cpp Plan/api-trexio-generation/scratch/task2/generated_bindings.cpp.orig
   ```
2. **Create `tools/trexio_api_model.py`.** Move these verbatim from `tools/gen_binding.py`:
   - `CT_T`, `SKIP`, `EXTRA`, `LOW_DIM_FN` (the name-sets + type table)
   - `parse_protos(header_text, names) -> dict[name, params]`
   - `locate_group_var(data, var) -> (group, var)`
   - `class Rec` (fields: `name, family, T, verb`)
   - `classify(name, params, data) -> Rec` (returns `None` for unhandled shapes)
   - the family table names (`HAS, SCALAR_R, SCALAR_W, SIZE, SAFARR_R, SAFARR_W,
     STR_R, STR_W, STRARR_W, OFF5_R, OFF5_W, SPARSE_R, SPARSE_W`) as a set / list constant
   Add a `__all__` and a module docstring noting it is **imported by both `gen_binding.py` and
   `gen_trexio_py.py` — do not duplicate this logic in either file.
   ```python
   # tools/trexio_api_model.py
   __all__ = [
       "CT_T","SKIP","EXTRA","LOW_DIM_FN",
       "parse_protos","locate_group_var","Rec","classify","FAMILIES",
   ]
   # …moved definitions…
   FAMILIES = {
       "HAS","SCALAR_R","SCALAR_W","SIZE","SAFARR_R","SAFARR_W",
       "STR_R","STR_W","STRARR_W","OFF5_R","OFF5_W","SPARSE_R","SPARSE_W",
   }
   ```
3. **Rewrite `tools/gen_binding.py`** to `from trexio_api_model import *` (or a named import),
   and delete the moved definitions. **All emitters (`e_HAS`, `e_SCALAR_R`, …) and `EMIT`,
   `crosscheck`, `gen`, `main` stay in `tools/gen_binding.py`** — they emit C++; that part is
   unchanged.
4. **Byte-identity gate:**
   ```sh
   python3 tools/gen_binding.py \
     --trex-json third_party/trex.json \
     --out src/generated_bindings.cpp \
     --trexio-header "$HOME/.local/include/trexio.h"
   diff Plan/api-trexio-generation/scratch/task2/generated_bindings.cpp.orig src/generated_bindings.cpp
   ```
   `diff` must be empty. If it is not, the move introduced a difference (whitespace, import order
   in the header, etc.) — revert and re-do the move, do not "fix" the output.
5. **Run the existing verifier** (it reads `required_api.names` which hasn't changed) — should still pass.

## Gate
- `diff tools/gen_binding.py` — the moved functions are gone, the import is present.
- `diff Plan/.../task2/generated_bindings.cpp.orig src/generated_bindings.cpp` — **empty**.
- `python3 tools/check_api_symbols.py --verify` → `missing=0`.
- `python3 Plan/api-trexio-generation/verify/check_equivalence.py --required tools/required_api.names` → PASS
  (the C++ side is not in the file set, but the gate confirms the model refactor didn't break the
  surface/symbol invariants).

## DoD
`tools/trexio_api_model.py` is the single importable source of `parse_protos`, `locate_group_var`,
`classify`, `Rec`, and the name tables. Both emitters in the repo (`gen_binding.py`, and later
`gen_trexio_py.py`) import from it. `src/generated_bindings.cpp` is byte-identical to the pre-refactor
output.
