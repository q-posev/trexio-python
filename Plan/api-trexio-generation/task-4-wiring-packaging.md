# Task 4 — Wire the generator into the build (CMake) + prove the wheel carries `trexio_gen.py`

**Track:** A · **Depends on:** task-3 (emitters done, `api/trexio_gen.py` exists) · Parallel-safe: docs (task-6)
**Why:** without the CMake target the "generated surface" won't regenerate on a source build;
without `install(FILES)` the non-wheel install misses it. Task-4 also does the FIRST full
build so the next task has a wheel to test against.

## Files I own
- `CMakeLists.txt` (MODIFIED — one new custom target + one line in `install(FILES)`)
- `api/trexio/trexio_gen.py` (NEW symlink IF task-1 did not already create it)
- (no `pyproject.toml` change — `wheel.packages = ["api/trexio"]` already ships the new symlink)

## Steps

1. **Confirm the pkg symlink exists** (task-1 should have made it; if not, make it):
   ```sh
   ln -sfn ../trexio_gen.py api/trexio/trexio_gen.py
   ls -l api/trexio
   ```
2. **Add the generator to `CMakeLists.txt`.** Insert a new custom target alongside the existing
   `gen_bindings` block (keep the style of that block; it already uses `Python::Interpreter`):
   ```cmake
   # ---------------- generated PYTHON surface (has_/read_/write_/delete_) -------
   # Regenerated from required_api.names + the installed trexio.h + trex.json.
   # (C++ equivalent is the gen_bindings target above; both share tools/trexio_api_model.py.)
   if(EXISTS "${CMAKE_SOURCE_DIR}/tools/gen_trexio_py.py")
     add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/api/trexio_gen.py"
       COMMAND Python::Interpreter "${CMAKE_SOURCE_DIR}/tools/gen_trexio_py.py"
               --trex-json   "${CMAKE_SOURCE_DIR}/third_party/trex.json"
               --out         "${CMAKE_SOURCE_DIR}/api/trexio_gen.py"
               --required    "${CMAKE_SOURCE_DIR}/tools/required_api.names"
               --trexio-header "${TREXIO_INC}/trexio.h"
       DEPENDS
               "${CMAKE_SOURCE_DIR}/tools/gen_trexio_py.py"
               "${CMAKE_SOURCE_DIR}/tools/trexio_api_model.py"
               "${CMAKE_SOURCE_DIR}/third_party/trex.json"
               "${CMAKE_SOURCE_DIR}/tools/required_api.names"
               "${TREXIO_INC}/trexio.h"
       COMMENT "Generating api/trexio_gen.py (trexio surface)")
     add_custom_target(gen_trexio_py DEPENDS "${CMAKE_SOURCE_DIR}/api/trexio_gen.py")
     add_dependencies(pytrexio gen_trexio_py)
   endif()
   ```
   (If `gen_trexio_py.py`'s CLI is different, adjust the flags to match its `argparse`; the intent
   is to run it once at configure/build and produce `api/trexio_gen.py`.)
3. **Add the generated file to the non-wheel install** (the wheel path already ships it via
   `wheel.packages`):
   ```cmake
   install(FILES "${CMAKE_SOURCE_DIR}/api/trexio/__init__.py"
                 "${CMAKE_SOURCE_DIR}/api/trexio/_version.py"
                 "${CMAKE_SOURCE_DIR}/api/trexio/trexio_gen.py"   # NEW
                 DESTINATION "trexio")
   ```
4. **Full build + install.**
   ```sh
   PY=/usr/bin/python3.12
   $PY -m venv /tmp/opencode/trexpU && . /tmp/opencode/trexpU/bin/activate
   pip install -U pip build "scikit-build-core>=0.9" nanobind numpy pytest
   export CMAKE_PREFIX_PATH="$HOME/.local"
   export LD_LIBRARY_PATH="$HOME/.local/lib64:${LD_LIBRARY_PATH:-}"
   pip install -v .            # CMake runs gen_trexio_py + gen_binding, builds pytrexio, makes the wheel
   python - <<'PY'             # quick wheel-content + import check
   import zipfile, glob, importlib
   whl = sorted(glob.glob("dist/*.whl"), key=lambda p: __import__("os").path.getmtime(p))[-1]
   names = zipfile.ZipFile(whl).namelist()
   keep = [n for n in names if n.startswith("trexio/")]
   print("wheel trexio/ files:", keep)
   import trexio
   print("import trexio OK  __version__ =", trexio.__version__)
   assert any("trexio_gen" in n for n in keep), "trexio_gen.py missing from wheel"
   print("trexio_gen present in wheel: OK")
   PY
   ```
5. Gate + hand off.

## Gate
- `pip install -v .` completes; the wheel's `trexio/` directory contains `__init__.py`, `_version.py`,
  **`trexio_gen.py`**, and `pytrexio.<tag>.so`.
- `import trexio` succeeds in a clean venv with `LD_LIBRARY_PATH` set.
- `python3 Plan/api-trexio-generation/verify/check_equivalence.py --required tools/required_api.names` → PASS.

## DoD
A fresh `pip install -v .` rebuilds `api/trexio_gen.py` from sources (CMake target fires), the wheel
carries `trexio_gen.py`, and a clean venv can `import trexio`. The next task (task-5) runs the full
verification suite against this wheel.

## Notes
- If `gen_trexio_py.py` needs `numpy` or `nanobind` at runtime to import its model, that's fine (the
  build env has them). If `gen_trexio_py.py` only needs the standard library + trex.json, the CMake
  target can run with any Python.
- The `add_dependencies(pytrexio gen_trexio_py)` line is there only for ordering; there is no C++
  dependency. It mirrors the `gen_bindings` pattern already in `CMakeLists.txt`.
