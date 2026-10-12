# Keeping trexio-python up to date when TREXIO changes

This is the runbook for the three things that happen to an *installed TREXIO*:
new data (new variables in `trex.json`), new C features (new prototypes in
`trexio.h`), or breaking changes (renumbered enums, new return/argument
contracts). It assumes you already have the TREXIO tree and the `trexio-python`
tree as sibling directories.

## How the update pipeline works (read this once)

Three inputs feed one generated output:

| Input | Where it lives here | Comes from |
|---|---|---|
| Installed C header + lib | `$HOME/.local/include/trexio.h`, `$HOME/.local/lib*/libtrexio.so` | your `make install` of `../trexio` |
| Data model | `third_party/trex.json` | `trexio/trex.json` |
| Python API (the *list of functions we must expose*) | `api/trexio.py` → `tools/required_api.names` | `trexio/src/trexio.py` |

`tools/gen_binding.py` is **header-driven**: it parses the *installed*
`trexio.h` for the exact C parameter shape of every required name and classifies
each one into one of the recipe families in
`tools/gen_binding.py` (`HAS`, `SCALAR_R/W`, `SIZE`, `SAFARR_R/W`, `STR_R/W`,
`STRARR_W`, `OFF5_R/W`, `SPARSE_R/W`). Types come from the header — a bad
type guess cannot compile, by design. It **exits 1** if any required name is
missing from the header or has a shape no family covers. CMake re-runs it
automatically whenever `trexio.h`, `trex.json`, `required_api.names`, or the
script itself change — but you should run it manually first, because its
`UNHANDLED:` list is your TODO.

**Pin discipline (most important rule):** the vendored API (`api/trexio.py`),
re-generated `generated_bindings.cpp`, and the installed `libtrexio` **must all
come from the same TREXIO release/commit**. If `api/trexio.py` calls a C
function that the installed lib doesn't export, the generator will report it as
`UNHANDLED (not found in trexio.h)` — the fix is to match versions (re-vendor
from a checkout that matches your installed lib, or install a lib that matches
your API), never to hand-patch `api/trexio.py` unless it's a documented,
minimal, ABI-forcing exception (see `PROVENANCE.md`).

## Decide which case you are in

| What changed in TREXIO? | Case |
|---|---|
| New variables / new `*_num` / new dsets, new `str` fields, new back-end *data* — all with the usual prototypes | **A — golden path** (runbook below) |
| A new C function family no emitter covers (e.g. a new `offset`-style dset, new sparse variant), or a new core/lifecycle/NAO/state function, or a new back end | **B — new recipe or core work** (Step 3.5) |
| Renumbered/added enums, changed open semantics, changed in/out buffer conventions, changed signature shapes used by existing functions | **C — breaking change** (Step 4) |

A real release is usually A + part of B. The 2026-10-12 rebase
(`0102739`) was A+B+C (back-end renumber + new in/out `buffer_size` contract +
STR buffer sizing) and took a full session — use it as the difficulty ceiling.

## Golden path (Case A) — copy-paste runbook

### Step 1 — Update TREXIO upstream (in `../trexio`)

```sh
cd ../trexio
git pull                                    # your TREXIO update
make -j                                     # regenerates org sources → C
make -j check && make -j check              # TREXIO convention: twice
module load trexio                          # if you install into ~/.local:
make install                                # (keeps prefix=$HOME/.local)
# sanity:
nm -D $HOME/.local/lib64/libtrexio.so | grep -cE ' T trexio_memory_'   # back ends still present
grep -E "define TREXIO_(HDF5|TEXT|AUTO|MEMORY|INVALID)" $HOME/.local/include/trexio.h
```
**Stop if `make check` is red or constants moved.** Enum movement = Case C.

### Step 2 — Re-vendor the API + data model (in `trexio-python`)

```sh
cd ../trexio-python
T=$(cd ../trexio && pwd)
cp $T/src/trexio.py                 api/trexio.py
cp $T/python/pytrexio/__init__.py  api/pytrexio/__init__.py
cp $T/python/pytrexio/_version.py  api/pytrexio/_version.py
cp $T/trex.json                     third_party/trex.json
ls -l api/trexio                    # both symlinks must be intact (mode 120000):
                                    #   __init__.py  -> ../trexio.py
                                    #   _version.py  -> ../pytrexio/_version.py
# Refresh the provenance table in PROVENANCE.md (commit + date of $T) and,
# if the new release changed ABI, its "Documented exception" note.
```
If the new `src/trexio.py` no longer declares the constants exactly as the
installed header (release lag), either wait, or re-apply the minimal
constants-block exception and record it in `PROVENANCE.md` + `Plan/STATUS.md`
append-only log (that is exactly what `0102739` did).

### Step 3 — Refresh the required-name list + regenerate

```sh
python3 tools/check_api_symbols.py --list          # rewrites tools/required_api.names
git diff --stat tools/required_api.names           # the NEW names the API now calls — this is your delta
cp tools/required_api.names /tmp/required.names.new

python3 tools/gen_binding.py                        # header-driven; exits 1 on UNHANDLED
python3 tools/gen_binding.py 2>&1 | tee /tmp/gen.log
grep -A5 "UNHANDLED" /tmp/gen.log || echo "all names mapped ✓"
git diff --stat src/generated_bindings.cpp          # expect: additions for the new variables only
```

- `UNHANDLED (not found in trexio.h)` → version mismatch (Step 1/2 pin
  discipline) — do NOT "fix" by editing the generator's name list.
- `UNHANDLED (shape ...)` → **Case B**, Step 3.5 below.
- `CROSS-CHECK WARNINGS` → `trex.json` kind vs recipe family disagreement —
  inspect each manually; a warning can hide a mis-type in the C header or a
  stale `trex.json`. Do not dismiss without reading the header.

### Step 3.5 (Case B) — new C feature

Pick the recipe that matches the *shape* (count + kinds of the C params after
the handle), add it to `tools/gen_binding.py`:

```python
# 1) classify(): extend the len(P)==N branch with the new shape, e.g.
if len(P) == 3:
    T = data_T(1)
    if T and verb == "read":  return Rec(name, "NEWFAM_R", T)
# 2) emit: e_NEWFAM_R(r) — copy the closest e_<FAM> and adjust
    #    - return shape: [rc, ...outputs in C-argument order] (the ABI rule,
    #      see docs/migration-from-swig.md and tests/test_abi.py)
    #    - in/out args: init in/out pointers with the caller's value (see
    #      e_OFF5_R / e_SPARSE_R — the 0102739 lesson: C overwrites the
    #      buffer_size the caller passed; passing 0 → INVALID_ARG_3)
    #    - close-once/handle guard: `if (!h || !h->open()) return TREXIO_FAILURE;`
# 3) register: EMIT["NEWFAM_R"] = e_NEWFAM_R   (and the crosscheck table entry)
# 4) If it's a *core* function (lifecycle, state, NAO, bitfield, back-end
#    helpers — anything the new API calls that is NOT has/read/write):
#    add it to SKIP in gen_binding.py AND hand-write it in src/core.cpp
#    (follow the existing m.def style; add a contract test in tests/test_abi.py).
# 5) New back end: expose its constant in core.cpp (TREXIO_* block, pulled
#    from the C header — auto-consistent), add a roundtrip test modeled on
#    tests/test_memory.py, and check the vendored API's constant names match.
```

Then re-run Step 3 until `unhandled=0`.

**Known hot spot — new multi-entry `str` reads** (`e_STR_R`): the C backends
write `count * (max_str_len + TREXIO_DELIM)` bytes *without bounds checks* and
expect the caller to have sized the buffer for `count` entries. If the new
variable is a `*_low`-style string list, add its mapping to `LOW_DIM_FN` in
`gen_binding.py` (the `trexio_read_<g>_<var>_low → trexio_read_<g>_<dimvar>`)
or the default single-entry buffer will **heap-overflow** (caught as SIGABRT
in the Phase-3 audit — this is a hard requirement, not a nicety).

### Step 4 (Case C) — breaking changes

1. **Enums/constants:** `core.cpp` already exposes `TREXIO_HDF5/TEXT/AUTO/MEMORY/...`
   from the linked C header (auto-consistent). The *vendored API's* constants
   block must match — if it doesn't (release lag), apply the documented minimal
   patch + record in `PROVENANCE.md`.
2. **Semantics** (e.g. "AUTO cannot create", "MEMORY rejects 'r'"): the
   contracts live in `tests/test_abi.py` (the pins added in Phase 3/4) — update
   the expectations, not the binding, unless the binding itself encodes the old
   semantics (e.g. an in/out arg convention).
3. **Shapes:** re-run `gen_binding.py`; any name whose *shape* changed will be
   `UNHANDLED` → Step 3.5.
4. **Re-run parity** against a SWIG build of *the same* new tree
   (`tools/parity_api.py` + `tools/parity_run.py`, per
   `Plan/06-phase-5-packaging-ci.md` Step-4 of that doc; rebuild env A via
   `make python-install SWIG=<path>` in `../trexio` into a fresh venv, exactly
   as the Phase-4 baseline was built). Empty diffs = still drop-in.

### Step 5 — Build, test, ship (all cases)

```sh
PY=$HOME/miniforge3/bin/python3.12            # your 3.10+ Python
$PY -m venv /tmp/opencode/trexpU && . /tmp/opencode/trexpU/bin/activate
pip install -U pip build "scikit-build-core>=0.9" nanobind numpy pytest
export CMAKE_PREFIX_PATH="$HOME/.local"
export LD_LIBRARY_PATH="$HOME/.local/lib64:${LD_LIBRARY_PATH:-}"
pip install -v .                                   # full suite:
python -m pytest tests/ --all -q                   #   test_abi (ABI contracts)
                                                   #   test_examples (upstream examples)
                                                   #   test_api (text+hdf5)
                                                   #   test_memory
                                                   #   test_pytrexio (SWIG-era suite)
python3 tools/check_api_symbols.py --verify        # required=____ missing=0
# Wheel + install-from-wheel acceptance (same as Phase 5):
$PY -m build
$PY -m venv /tmp/opencode/trexpUrun && . /tmp/opencode/trexpUrun/bin/activate
pip install ../trexio-python/dist/*.whl pytest
python -m pytest tests/ --all -q                   # must pass from the wheel too
```

Also: bump `version` in `pyproject.toml` if you're publishing; note the new
TREXIO commit hash in the wheel's provenance (the Phase-5 evidence pattern).
`TREXIO_PKG_VERSION` in the module is auto-derived from the linked header
(`CMakeLists.txt` — no manual sync).

### Step 6 — Commit

```sh
git add -A
git commit -m "Update to TREXIO <$short-hash> (<one-line: what's new>)

- re-vendor: api/trexio.py, api/pytrexio/*, third_party/trex.json (PROVENANCE updated)
- required_api.names: +<n> names
- gen_binding: <n> bindings (new families: ...); 0 unhandled, 0 cross-check warnings
- new LOW_DIM_FN entry for <name> (if any)
- suite: 88→<n> passed; wheel built + wheel-venv suite green
"
```

## Gates (definition of done for an update)

- [ ] `gen_binding.py`: `unhandled=0`, `cross-check warnings=0` (or each warning read and justified).
- [ ] `check_api_symbols.py --verify` → `missing=0`.
- [ ] `pytest tests/ --all` green, **including** `test_abi.py` (the ABI contract pins) and the memory suite.
- [ ] `test_pytrexio.py` green (SWIG-era suite; if it needs a new EXTRA name, add it to the `EXTRA` set — do NOT let it force a change to the `required_api.names` contract).
- [ ] For any Case B/C: parity re-run empty (or deltas recorded in `PROVENANCE.md`).
- [ ] `PROVENANCE.md` table + exception notes updated; commit message carries the TREXIO commit hash.
- [ ] Wheel build + wheel-installed clean-venv suite green.

## Failure-signature cheat sheet

| Symptom | Meaning | Fix |
|---|---|---|
| `UNHANDLED (not found in trexio.h)` | vendored API is from a different TREXIO line than your installed lib | match versions (Step 2/1), never patch `api/trexio.py` |
| `UNHANDLED (shape ...)` | new C signature no family covers | Step 3.5 (new emitter + classify rule) |
| Cross-check warning | `trex.json` kind contradicts the recipe family | read the header, fix the smaller of: `trex.json` re-vendor vs. `T` remap rule |
| SIGABRT mid-suite on a `*_low` string read | multi-entry string without a `LOW_DIM_FN` sizing var | add the `LOW_DIM_FN` mapping |
| `rc = 40` (`INVALID_ARG_10`) on NAO calls | interpolator arity contract (`n_interp >= 4*n_grid+3`) | size test inputs per the pin in `test_abi.py` |
| `INVALID_ARG_3` on sparse/safe reads | in/out `buffer_size` — caller must init with requested count | use the `e_OFF5_R`/`e_SPARSE_R` pattern (pass the Python `buffer_size`, not 0) |
| `undefined reference to trexio_*` at link | installed lib predates the symbol (or you're linking an older prefix) | reinstall from the matching checkout (`CMAKE_PREFIX_PATH=$HOME/.local`) |
| `make check` red after a TREXIO enum change (Fortran module) | stale `tests/*.o` with baked-in old constants | `rm tests/*.o && make -j check` (Phase-4 lesson) |
| `import trexio` fails in the new venv | `libtrexio.so` not resolvable at runtime | `LD_LIBRARY_PATH=$HOME/.local/lib64` (or `module load trexio`) |

## Files you will touch, by case

| File | Case A | Case B | Case C |
|---|---|---|---|
| `api/trexio.py`, `api/pytrexio/*`, `third_party/trex.json` | re-vendor | re-vendor | re-vendor (+ documented constants exception) |
| `tools/required_api.names` | `--list` | `--list` | `--list` |
| `src/generated_bindings.cpp` | auto (generator) | auto + **`tools/gen_binding.py`** (new family) | auto + `gen_binding.py` (shape rules) |
| `src/core.cpp` | — | new core function / new back-end constant | enum/semantics contract |
| `src/bind_helpers.hpp` | — | new shared C++ helper | — |
| `tests/test_abi.py` | — (should stay green) | new contract pin | updated expectations |
| `tests/test_pytrexio.py` + `EXTRA` set in `gen_binding.py` | — | only if the SWIG-era suite needs a name not in `required_api.names` | — |
| `PROVENANCE.md` | table + date | table + date (+ exception if ABI-forced) | table + date + exception note |
| `pyproject.toml` | version bump if publishing | same | same |

Everything else (`CMakeLists.txt`, `pyproject.toml` build backend, `tests/test_api.py`,
`tests/test_memory.py`, `tests/test_examples.py`) is expected to be **untouched** on
a routine update. If you find yourself editing one of them, stop and reconsider —
a change there usually means a Case B/C you haven't classified yet.
