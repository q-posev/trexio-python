# Task 5 — Drop-in verification gate (evidence)

Run: 2026-10-13 · Worktree `/tmp/opencode/t5` · branch `work-task-5` · base `9fb44e7` (master, tasks 1–4 merged)
Python: conda base **3.10.12** (`~/miniconda3`); TREXIO via `module load conda; module load trexio/2.6.2; export LD_LIBRARY_PATH`
Wheel venv: `/tmp/opencode/t5run` (fresh, wheel + pytest only) · Build venv: `/tmp/opencode/trexpU` (python 3.10.12, build toolchain)

## Gate results

| # | Gate | Result | Key verbatim line(s) |
|---|------|--------|----------------------|
| 1 | Static equivalence (`check_equivalence.py`) | **PASS** | `RESULT: PASS -- split preserves surface, core, and ABI.` — 862/862 surface, none duplicated in core, 13/13 core, 878/878 symbols, 8/8 probes ok |
| 2 | ABI symbols via legacy tool (`check_api_symbols.py --verify`, trexpU venv) | **PASS** | `required=14 missing=0` (reads `api/trexio.py` = core subset after split; authoritative 878 check is gate 1) |
| 3 | C++ generator quiet (`gen_binding.py`) | **PASS** | `wrote /tmp/opencode/task5/t5_gen_binding.cpp: 840 bindings, 0 unhandled, 0 cross-check warnings` |
| 4 | C++ byte-identity | **PASS** | `cmp` exit 0 → `C++ byte-identical` |
| 5 | Fresh wheel from source | **PASS** | `Created wheel for trexio: filename=trexio-0.1.0-cp310-cp310-linux_x86_64.whl size=235842 sha256=976b…0af23c` · `WHEEL-EXIT=0` |
| 6 | Wheel-venv import + `check_public_namespace.py` + pytest | **FAIL** (namespace script only) | `RESULT: FAIL` — `round-trip raised: Error('Attribute does not exist in the file')`; import-from-site-packages and `namespace: 862/862` + `core names present (18/18)` OK; same step's pytest: `53 passed in 0.18s` |
| 7 | In-tree dev-style pytest (`PYTHONPATH=api`) | **PASS** | `53 passed in 0.29s` |
| 8 | Line counts + discipline | **PASS** | `415 api/trexio.py` · `34591 api/trexio_gen.py` · `97 api/trexio/_base.py`; banner line 1; `862` defs == `862` baseline lines |
| 9 | Phase-3 constants + r_power standardization | **PASS** | `2 3`; `#define TREXIO_AUTO ((back_end_t) 2)`, `#define TREXIO_MEMORY ((back_end_t) 3)` in installed header; AST byte-equivalence `True`; all 3 `trexio_write_safe_basis_r_power_64` occurrences inside `def write_basis_r_power` (lines 25071/25073/25075, def spans 25026..25078); live: `int64 round-trip: [2 4] ['int64','int64']`; `float write -> TypeError: 'float' object is not iterable` |
| 10 | Public-namespace spot proof | **PASS** | `no __all__`; surface-style names in `dir(trexio)`: `862`; `File, Error, string_of_error, get_int64_num: True True True True` |
| 11 | Final repo state + commit of evidence | done in git section below | — |

## Gate 6 FAIL — root-cause analysis (NOT a split regression; recorded, not fixed, per task instruction)

`check_public_namespace.py` performs, in the script's fixed order:
`write_nucleus_num(4)` → `write_nucleus_charge([1..4])` → **`write_metadata_code(["alpha","beta"])`** without writing `metadata_code_num` first.

TREXIO 2.6.2 (installed C library; spec in `/home/scemama/TREX/trexio/include/trexio.h`: `"code" : [ "str", [ "metadata.code_num" ] ]`) sizes the `metadata.code` string array by `metadata.code_num`; writing the array before the num precondition returns `TREXIO_ATTR_MISSING` (`Error: Attribute does not exist in the file`). Verified live in the wheel venv:

- A: code without num → `Error('Attribute does not exist in the file')`
- B: `write_metadata_code_num(2)` then `write_metadata_code(["alpha","beta"])` → reads back `['alpha', 'beta']` (works)

Why this is pre-existing, not introduced by the split:
- `def write_metadata_code` is **byte-identical** in the pre-split snapshot (`scratch/task1/api_trexio.py.orig` line 34726) and the split `api/trexio_gen.py` (line 34282) — same body, same call `pytr.trexio_write_metadata_code(f.pytrexio_s, dset_w, max_str_length)`.
- The C binding in `src/generated_bindings.cpp` (line 2939, `trexio_write_metadata_code` → `TREXIO_WRITE_metadata_code` array call) is unchanged by tasks 1–4 and was re-proven byte-identical to generator output (gate 4).
- The same A/B behavior (A fails, B works) reproduces in the independently installed trexio in the build venv `/tmp/opencode/trexpU` (contains `trexio_gen.py`, i.e. a split-layout 0.1.0 build).
- No test in `tests/` calls `write_metadata_code` (suite is green 53/53 in both venvs), so the split itself was never broken by this.

Per this task's standing instruction — "if a test broke after the split, the split is wrong, not the test" — and its stronger form here ("DO NOT fix; report the failure"): the failure is reported, nothing was modified. Disposition options for the owner: (a) teach `check_public_namespace.py` the TREXIO 2.x num-first write order (add `write_metadata_code_num` before `write_metadata_code`, matching the existing `nucleus_num`→`nucleus_charge` pattern in the same script), and/or (b) file a note that `write_metadata_code`/`write_nucleus_label`-style STRARR writes under TREXIO 2.x require their `_num` sibling first — the wrapper bodies are legacy-identical and would fail the same way in the pre-split package.

## Stale-plan / prompt adaptations actually made
1. Plan line `PY=/usr/bin/python3.12` with pip → not usable on this machine; all Python uses conda base 3.10.12 via `module load conda` (login shell).
2. Plan lines `export CMAKE_PREFIX_PATH="$HOME/.local"` / header `$HOME/.local/include/trexio.h` → unused; TREXIO comes from `module load trexio/2.6.2` (pkg-config discovery) and the direct generator run used `TREXIO_HOME=/home/scemama/TREX/trexio` + `--trexio-header /home/scemama/TREX/trexio/include/trexio.h`.
3. Plan's `pytest --all` is an invalid flag → plain `python -m pytest tests/ --quiet` (as adapted in the task prompt).
4. Plan step 3 flag `--json` (task prompt) → actual flag is `--trex-json` (per `gen_binding.py --help`).
5. Plan step 4 diff target `scratch/task2/generated_bindings.cpp.orig` does not exist → instead: fresh `gen_binding.py --out /tmp/opencode/task5/t5_gen_binding.cpp` vs committed `src/generated_bindings.cpp` via `cmp` (task prompt authorized this and authorized keeping the .cpp in /tmp and citing it — done).
6. Task prompt's `"$(ls -1t dist/*.whl | head -1)"` could have selected the `numpy-2.2.6…` wheel (pip's isolated build saved the runtime dep wheel into `dist/` too) → installed `dist/trexio-0.1.0-cp310-cp310-linux_x86_64.whl` explicitly.
7. Gate-6 pytest capture `tail -5` ended up capturing `trexio.info()` banner lines (printed at interpreter shutdown, after pytest's summary) → re-captured; the pass line is `53 passed in 0.18s` (see `pytest_wheel_venv.log`).
8. Gate-9 live check needs the TREXIO 2.x precondition `write_basis_shell_num(2)` before `write_basis_r_power([2,4])` (`basis.r_power` is sized by `basis.shell_num`); not required by the pre-split API's own test patterns since no test exists for r_power.

## Artifacts
- Wheel: `trexio-0.1.0-cp310-cp310-linux_x86_64.whl`, **235,842 bytes** (see `wheel_dist.log`; `numpy-2.2.6…whl` also saved in `dist/` by pip's isolated build — not part of the deliverable).
- C++ generation output kept per prompt allowance in `/tmp/opencode/task5/t5_gen_binding.cpp` (296,624 bytes / 3,989 lines; byte-identical to `src/generated_bindings.cpp`).
- Log files in this directory: `check_equivalence.log`, `check_api_symbols.log`, `gen_binding.log`, `gate4_cmp.log`, `wheel_build.log`, `wheel_install.log`, `check_public_namespace.log`, `pytest_wheel_venv.log`, `pytest_in_tree.log`, `wc.log`, `constants.log`, `gate9_ast_equiv.log`, `r_power_live.log`, `gate10_spot_namespace.log`, `wheel_dist.log`.

## Observations (no action taken)
- `trexio.__version__` resolves to the TREXIO runtime version `2.6.1` (C library banner under trexpU/t5run shows `TREXIO_PACKAGE_VERSION : 2.6.1`, while the module fileset loaded is `trexio/2.6.2`) — worth a one-line sanity check by the owner; not a gate criterion.
- `trexio.info()` prints a multi-line banner at interpreter shutdown (after pytest's summary line) — cosmetic; affects naive `tail -N` captures.
- No test skipped/failed/xfailed; 53/53 in both venvs. No deprecation warnings surfaced in the captured tails.
