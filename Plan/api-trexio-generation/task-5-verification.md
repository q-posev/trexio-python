# Task 5 — Full verification (static + import-time + suite + wheel-venv + line count)

**Track:** A · **Depends on:** task-4 (built wheel available). This is the drop-in gate.
**Run this session with a CLEAN venv** (fresh `pip install` from source, not the dev one).
```sh
PY=/usr/bin/python3.12
rm -rf /tmp/opencode/trexpU && $PY -m venv /tmp/opencode/trexpU && . /tmp/opencode/trexpU/bin/activate
pip install -U pip build "scikit-build-core>=0.9" nanobind numpy pytest
export CMAKE_PREFIX_PATH="$HOME/.local"
export LD_LIBRARY_PATH="$HOME/.local/lib64:${LD_LIBRARY_PATH:-}"
```

## Gate sequence (run top-to-bottom; any FAIL = rollback via references/30)

```sh
cd <worktree root>

# 1) Static equivalence (split is a no-op on names/symbols/core)
python3 Plan/api-trexio-generation/verify/check_equivalence.py --required tools/required_api.names
#    -> PASS: 862 surface in gen, 13 core present, 878 symbols referenced.

# 2) ABI symbol set is unchanged
python3 tools/check_api_symbols.py --verify          # -> missing=0

# 3) C++ generator is quiet (shared model refactor didn't change classification)
python3 tools/gen_binding.py --trex-json third_party/trex.json \
        --out src/generated_bindings.cpp \
        --trexio-header "$HOME/.local/include/trexio.h" 2>&1 | tee /tmp/task5_gen.log
grep -aE "UNHANDLED|CROSS-CHECK" /tmp/task5_gen.log && echo "!! investigate" || echo "all names mapped, no cross-check warnings"

# 4) Byte-identity of the C++ output (task-2's diff)
diff Plan/api-trexio-generation/scratch/task2/generated_bindings.cpp.orig src/generated_bindings.cpp && echo "C++ byte-identical"

# 5) Build the wheel fresh, then the import-time gate
pip install -v . >/tmp/task5_build.log 2>&1 || tail -40 /tmp/task5_build.log
python3 Plan/api-trexio-generation/verify/check_public_namespace.py   # -> PASS

# 6) Full test suite (in-tree text/hdf5/memory + SWIG-era + ABI pins)
python -m pytest tests/ --all --quiet

# 7) Wheel-installed suite (the actual deliverable) — fresh venv as the runbook does
$PY -m venv /tmp/opencode/trexpUrun && . /tmp/opencode/trexpUrun/bin/activate
pip install $(ls -1t dist/*.whl | head -1) pytest
python -m pytest tests/ --all --quiet

# 8) Size + discipline
wc -l api/trexio.py api/trexio_gen.py api/trexio/_base.py
echo "api/trexio.py was 35,038 lines BEFORE; expect ~5k–9k now."

# 9) The two PROVENANCE behaviors
grep -E "define TREXIO_(AUTO|MEMORY)" $HOME/.local/include/trexio.h
grep -n "write_basis_r_power\|int64" api/trexio_gen.py | head

# 10) Record evidence
mkdir -p Plan/api-trexio-generation/scratch/task5
cp /tmp/task5_gen.log /tmp/task5_build.log Plan/api-trexio-generation/scratch/task5/ 2>/dev/null || true
```

## Gate checklist (all must hold)
- [ ] `check_equivalence.py` → **PASS** (862/13/878)
- [ ] `check_api_symbols.py --verify` → `missing=0`
- [ ] `gen_binding.py` → `unhandled=0`, no cross-check warnings
- [ ] `diff` of `generated_bindings.cpp` → **empty** (C++ preserved)
- [ ] `check_public_namespace.py` → **PASS** (incl. no `write_basis_r_power` float-list TypeError)
- [ ] `pytest tests/ --all --quiet` green **in** the dev venv
- [ ] `pytest tests/ --all --quiet` green **from the wheel venv**
- [ ] `wc -l api/trexio.py` ≤ ~10,000 (was 35,038); `api/trexio_gen.py` is generated (banner present)
- [ ] `grep` shows the Phase-3 constants in `_base.py` and the Phase-4 `write_basis_r_power` override in the gen file
- [ ] The 862-wrapper count in `api/trexio_gen.py` matches `wc -l < Plan/.../baseline_surface.txt` (862)

## Evidence to hand back
- The two `FAIL`/`WARN` lines in each of the 10 steps (or a note "all clean").
- `wc -l` numbers.
- The one-line test-suite pass/fail summary (in-tree + wheel venv).
- Any test that needed an adjustment — **if any**, stop and check with the owner before continuing
  (see references/30: if a test broke after the split, the split is wrong, not the test).

## Rollback note
If anything fails:
```sh
git -C <worktree> restore api/trexio.py
# (and, per the failure, git restore tools/gen_trexio_py.py, CMakeLists.txt, src/generated_bindings.cpp, etc.)
# The task-1 snapshot is at Plan/api-trexio-generation/scratch/task1/api_trexio.py.orig
cp Plan/api-trexio-generation/scratch/task1/api_trexio.py.orig api/trexio.py   # last-resort core restore
```
