# Migrating from the SWIG `trexio` binding to this package

**TL;DR for application users: no code changes.** Same distribution name
(`trexio`), same public API, same constants, same `File` class, same return
shapes. Swap the installed package; keep your code.

Evidence (Phase 4, 2026-10-12): the public-API diff between the SWIG build of
the same TREXIO line and this package is **byte-empty** (931 names, all
constants), and a behavioral contract script produces **byte-identical**
results in both environments (text/HDF5/MEMORY I/O, bitfield round-trips,
error paths). Full record: `tests/evidence/` (`parity_*.json`, `run_*.txt`,
`README-suites.txt`).

## 1. Swapping the package

```sh
pip show trexio                       # confirm what is installed
pip uninstall -y trexio               # remove whichever one (SWIG or this build)
pip install ./dist/trexio-0.1.0-*.whl  # this package (wheel), or `pip install .`
```

- The old SWIG package and this one ship under the **same name** (`trexio`) —
  they are meant to shadow each other; never keep both in one environment.
- Do **not** "upgrade in place" in a shared/HPC module Python if that
  environment is someone's SWIG parity baseline — do it in a venv and test.
- Code that imported the low-level SWIG module as `pytrexio.pytrexio` (the
  old top-level `pytrexio` package) should switch to
  `import trexio.pytrexio` — same names, same shapes. Code using the public
  `trexio` API does not change at all.

## 2. What must be present

- **`libtrexio` ≥ 2.6 installed** with the back ends you use — this package
  does **not** bundle the C library (the SWIG wheels did):
  - text + MEMORY: any such build of TREXIO 2.6.1+;
  - HDF5: the installed `libtrexio` built with HDF5 (`trexio.info()` says
    `HAVE_HDF5: true`).
- `LD_LIBRARY_PATH` (or `module load trexio`) so the runtime can load it.
- `TREXIO_MEMORY` requires a memory-enabled build (the TREX-2.6.1 line has it;
  the renumbered ABI is `HDF5=0, TEXT=1, AUTO=2, MEMORY=3, INVALID=4`).

## 3. Known intentional differences

**None** — the Phase-4 parity diffs are empty (recorded above and in
`Plan/STATUS.md`). The only user-relevant new fact: the low-level module is
now one compiled extension (`trexio/pytrexio…so`) with no SWIG `.py` shims —
anything that was reaching into the SWIG internals (typemaps, SWIG runtime)
was never part of the supported API.

## 4. When the TREXIO API line moves (maintenance)

1. **Re-vendor** the Python API + schema (documented step; do not hand-edit):
   see `PROVENANCE.md` — `cp` the four files from a fresh TREXIO checkout and
   re-record the commit hash.
2. **Regenerate** the per-variable surface from the vendored API + installed
   `trexio.h`: `python tools/gen_binding.py` (deterministic; 0 unhandled
   expected; output is committed).
3. **Verify**: `python tools/check_api_symbols.py --verify` (missing = 0),
   `pip install -v .`, `python -m pytest tests/ --all`.
4. **Pin discipline**: the vendored `third_party/trex.json` hash goes into the
   commit message (as in
   `Generated per-variable surface (gen_binding.py, trex.json ae0abbd)`).

## 5. Build recipes

- **Local**: `pip install .` with TREXIO visible via `TREXIO_HOME` /
  `CMAKE_PREFIX_PATH` / `~/.local` (the default).
- **Wheel**: `python -m build` → `dist/trexio-0.1.0-*` (sdist + wheel);
  install the wheel into clean venvs for testing
  (`pip install dist/trexio-0.1.0-*.whl pytest && python -m pytest tests/ --all`).
- **CI**: `.github/workflows/ci.yml` builds TREXIO from upstream on
  ubuntu-24.04/macos-14 × Python 3.10/3.12, installs this package, and runs
  the full suite with `--all`.
