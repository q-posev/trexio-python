# Package layout: what is in `api/`, and whether each file is needed

**TL;DR:** `api/trexio.py` is the real, installed public API — `import trexio`
loads it. The only thing it needs is the low-level `pytrexio` extension, which
in this project is a **nanobind** module that is a drop-in replacement for the
old SWIG one. The `api/` tree is small, symlinked so the vendored files are not
duplicated, and every *text* file under it is load-bearing tracked source — the
only non-source things are the two compiled `.so` build artifacts.

This answers the recurring question: *"What is in `api/`, and are those files
needed?"* (It complements `README.md`, which shows the *installed* layout, and
`PROVENANCE.md`, which tracks *where* the vendored files come from.)

## Two-layer architecture

```
 +------------------------------------------------------------------+
 | import trexio                                                     |
 | Public API: File, open/close/flush/inquire,                      |
 |   read_*/write_*/has_*, to_bitfield_list, ...                    |
 | = api/trexio.py  ->  trexio/__init__.py                           |
 |   (vendored from official TREXIO — see PROVENANCE.md)            |
 +----------------------------+-------------------------------------+
                              |  from . import pytrexio as pytr
                              |  pytr.trexio_open / read_* / write_* / ...
 +----------------------------v-------------------------------------+
 | import trexio.pytrexio                                            |
 | Low-level C-ABI, Python lists, return code first.                 |
 | = src/core.cpp + src/generated_bindings.cpp  ->  pytrexio.<tag>.so|
 |   nanobind — a SWIG-free module that reproduces the old SWIG      |
 |   `pytrexio` ABI, so the wrapper above is unchanged.              |
 +------------------------------------------------------------------+
```

- **High level** — `api/trexio.py`. The user-facing API. It is written in the
  classic TREXIO Python style (originally authored to wrap the SWIG module);
  here it wraps the nanobind module instead. This is what `import trexio` loads
  and what `tests/test_api.py` drives.
- **Low level** — `trexio/pytrexio.*.so`. One compiled extension exposing the
  C-ABI surface (`trexio_open`, `trexio_read_*`, `trexio_write_*`, the
  `trexio_*` helpers, and the opaque `trexio_s` handle). Hand-written core in
  `src/core.cpp` plus a large set of generated per-variable bindings in
  `src/generated_bindings.cpp`.

## What is in `api/` (and why each piece is there)

```
api/
+-- trexio.py                          # CANONICAL high-level API (the real file)
+-- pytrexio/
|   +-- __init__.py                    # vendored official `python/pytrexio/__init__.py`
|   +-- _version.py                    # CANONICAL version (__version__ = "2.6.1")
+-- trexio/                            # the WHEEL package (becomes site-packages/trexio/)
    +-- __init__.py   -> ../trexio.py                # symlink
    +-- _version.py   -> ../pytrexio/_version.py     # symlink
    +-- pytrexio.cpython-310-….so   # BUILD OUTPUT (gitignored)
    +-- pytrexio.cpython-312-….so   # BUILD OUTPUT (gitignored)
```

| Path | Role | In the wheel? | Keep? |
|---|---|---|---|
| `api/trexio.py` | Canonical public API (symlink target for `trexio/__init__.py`) | yes, as `trexio/__init__.py` | **Required** — source of truth |
| `api/trexio/` | Wheel package dir (`pyproject.toml` `wheel.packages`; `CMakeLists.txt` `WHEEL_PKG`) | yes, copied in (prefix stripped) | **Required** — build needs it |
| `api/trexio/__init__.py` | Symlink to `../trexio.py`; git stores it as a symlink (tiny) | yes, resolves to the full API | **Required** |
| `api/trexio/_version.py` | Symlink to `../pytrexio/_version.py` | yes, as `trexio/_version.py` | **Required** |
| `api/pytrexio/_version.py` | Canonical version string (`2.6.1`); source of the symlink above | yes, via that symlink | **Required** |
| `api/pytrexio/__init__.py` | Vendored official `python/pytrexio/__init__.py` (a 1-line file in this TREXIO line); kept for provenance and the re-vendor step | no — only `api/trexio/` is the wheel package | Kept: part of the documented re-vendor contract (`PROVENANCE.md`); not loaded by this binding |
| `api/trexio/pytrexio.*.so` | Compiled nanobind module (build output) | yes (rebuilt into the wheel) | **Build artifact** — gitignored (`*.so`); regenerated on build, safe to delete |

Every *file* under `api/` (not the `.so`) is tracked source. The only non-source
entries are the two compiled `.so` files inside `api/trexio/`.

## Why the symlinks

`api/trexio/` is the directory the wheel builder copies in (with its path
prefix stripped to `trexio/`), but the content is not duplicated there:

- `api/trexio/__init__.py` is a symlink to the canonical `api/trexio.py`;
- `api/trexio/_version.py` is a symlink to `api/pytrexio/_version.py`.

So there is exactly one copy of the API and one copy of the version, and the
`api/trexio/` package and the top-level `api/trexio.py` can never drift apart.
`scikit-build-core` follows the symlinks when it stages the wheel — the shipped
`trexio/__init__.py` is the full high-level API (~35k lines), not a 1-line stub.
(If the symlinks break — e.g. a checkout that doesn't preserve them — the wheel
would come out wrong; the `ls -l api/trexio` in the re-vendor runbook asserts
both are still symlinks, mode `120000`.)

## Generated files vs. hand-maintained files

One rule to internalize: **never hand-edit a file that a tool produces.** After a
new TREXIO release you *regenerate* the generated files and *re-copy* the vendored
ones, and you touch the hand-written ones only when the release genuinely forces
it. (The full step-by-step procedure is in `docs/updating-with-trexio.md`.)

| File / dir | Kind | On a new TREXIO release |
|---|---|---|
| `src/generated_bindings.cpp` | **GENERATED** by `tools/gen_binding.py` (banner: *"DO NOT EDIT BY HAND"*). Inputs: `tools/required_api.names` + installed `trexio.h` + `third_party/trex.json` | **Regenerate, don't edit**: `python tools/gen_binding.py` (CMake re-runs it at build). |
| `tools/required_api.names` | **GENERATED** by `tools/check_api_symbols.py --list` from every `pytr.*` reference in `api/trexio.py` | **Regenerate**: `python tools/check_api_symbols.py --list` — the diff vs. the last release is your change delta. |
| `api/trexio.py`, `api/pytrexio/__init__.py`, `api/pytrexio/_version.py`, `third_party/trex.json` | **VENDORED** — copied verbatim from the matching TREXIO commit (`PROVENANCE.md`). Hand edits only for a *documented* ABI exception | **Re-copy** the four files from the new TREXIO checkout (`cp` block in `PROVENANCE.md`), then record the new commit/date. |
| `src/core.cpp` | **HAND-WRITTEN** core (lifecycle / state / NAO / bitfield / `delete_*` / back-end constants) | **Edit by hand only if** the release adds a new core function, a new back end, or changes an ABI contract (runbook Cases B / C). |
| `src/bind_helpers.hpp` | **HAND-WRITTEN** shared C++ helper | **Edit by hand only** if a new binding family needs a new helper (Case B). |
| `tools/gen_binding.py` | **HAND-MAINTAINED** generator (the recipe families / shape rules) | **Edit by hand only** for a C signature no family covers, or a changed shape (Cases B / C). |
| `tools/check_api_symbols.py`, `tools/parity_api.py`, `tools/parity_run.py` | **HAND-MAINTAINED** tooling | Usually untouched; adjust only if the shape contract changes. |
| `CMakeLists.txt`, `pyproject.toml` | **HAND-MAINTAINED** build manifest | Usually untouched on a routine (Case A) update — a change there usually means the update was mis-classified. |
| `tests/` (`test_abi.py`, `test_api.py`, `test_memory.py`, `test_pytrexio.py`, …) | **HAND-MAINTAINED** suites | **Extend by hand** for new variables / back ends (new contract pins, `LOW_DIM_FN`-driven string sizing, `EXTRA` names in the SWIG-era suite). |
| `build/`, `dist/`, `api/trexio/pytrexio.*.so`, `benzene.h5`, `__pycache__/` | **BUILD / TEST ARTIFACTS** (gitignored) | **Regenerated** — never edit, never commit. |

### The two rules, restated

1. **Generated** (`src/generated_bindings.cpp`, `tools/required_api.names`):
   produced by a tool — after a release, *regenerate* them and **never** hand-edit.
   If you need a change, fix one of their *inputs* (`tools/gen_binding.py`,
   `api/trexio.py`, `third_party/trex.json`, or the installed `trexio.h`) and
   regenerate.
2. **Hand-managed on a release**: *re-copy* the vendored files (`api/trexio.py`,
   `api/pytrexio/*`, `third_party/trex.json`) from the matching TREXIO tree; then
   hand-edit only what the release actually demands — `src/core.cpp` /
   `src/bind_helpers.hpp` for new core C, `tools/gen_binding.py` for new shapes,
   and `tests/` for new pins. `CMakeLists.txt` / `pyproject.toml` should remain
   untouched on a routine update.

## "Is this the old SWIG interface?"

- The **wrapper** `api/trexio.py` is in the classic SWIG-era *style* (it calls
  `pytr.trexio_open`, `pytr.trexio_read_*`, …), but the module it binds to is
  the **new nanobind** `pytrexio`. The old SWIG `.so` is gone; the nanobind
  module was written specifically to reproduce that ABI so the wrapper keeps
  working unchanged (`src/core.cpp`: "SWIG-free replacement of the pytrexio SWIG
  module"). So the wrapper is not "left here for the docs" — it is the live API.
- The one genuinely SWIG-era artifact is the test `tests/test_pytrexio.py`
  (it does `from trexio.pytrexio import *` and writes to `test_py_swig.*` files).
  It is kept as a low-level ABI-compatibility regression test, not as
  documentation.
- Proof of what ships is in the built wheel under `dist/`
  (`trexio-0.1.0-*.whl`): it contains `trexio/__init__.py` (the full API),
  `trexio/_version.py`, and `trexio/pytrexio.<tag>.so` — nothing else.

## Related docs

- `README.md` — install, usage, "What changed vs the SWIG release" (installed
  layout and drop-in guarantees).
- `PROVENANCE.md` — exactly which upstream TREXIO commit each vendored file
  (`api/trexio.py`, `api/pytrexio/*`, `third_party/trex.json`) comes from, and
  the re-vendor command that touches `api/*`.
- `docs/migration-from-swig.md` — swapping the official SWIG `trexio` package
  for this one.
- `docs/updating-with-trexio.md` — the runbook for when the installed TREXIO
  changes (re-vendor `api/*`, regenerate, test).
