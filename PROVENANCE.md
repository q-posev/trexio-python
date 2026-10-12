# PROVENANCE — vendored files from TREXIO

All vendored files are taken from the TREXIO repository at the commit shown
below. They are not hand-edited *except* the documented exceptions below
(see also `Plan/STATUS.md`, Phases 3 & 4). Re-vendoring = rerun the `cp`
commands in this file's instructions.

**Documented exception (Phase 3, 2026-10-12):** `api/trexio.py` back-end
constants block (5 lines) updated to the ABI of TREXIO 2.6.1+0102739
(`TREXIO_AUTO=2, TREXIO_MEMORY=3, TREXIO_INVALID_BACK_END=4`) after the
user's rebase renumbered the C enum (TREX-CoE#340). This is exactly what the
official `src/trexio.py` of the 0102739 tree declares (verified by the Phase-4
byte-empty parity against a SWIG build of that tree). Re-vendoring from a
matching TREXIO checkout removes the need for this patch.

**Documented exception (Phase 4, 2026-10-12):** `api/trexio.py` `write_basis_r_power`
list/tuple branch. `basis_r_power` is an int64 TREXIO array, but tools (e.g.
`trexio_tools` converters for Gaussian/ORCA basis sets) pass it as a 1-D list of
floats (e.g. `[0.0, 0.0, ...]`). The nanobind binding
`pytrexio.trexio_write_safe_basis_r_power_64` rejects a bare Python list that
contains float elements (`TypeError: 'float' object is not iterable`). The fix
normalizes any list/tuple input to a flat int64 numpy array before the call,
matching the function's own docstring ("list OR numpy.ndarray … the conversion
is performed"). The same latent defect exists in the other int64 array writers;
only `write_basis_r_power` is patched here because it is the sole int64 field
routinely supplied as a float list. Upstream should adopt the same normalization
for all int64 writers.

| File | TREXIO source path | TREXIO commit (date) |
|------|-------------------|---------------------|
| `api/trexio.py` | `src/trexio.py` | `862d68b Add trexio_get_back_end front end accessor` (2026-10-09) |
| `api/pytrexio/__init__.py` | `python/pytrexio/__init__.py` | `862d68b Add trexio_get_back_end front end accessor` (2026-10-09) |
| `api/pytrexio/_version.py` | `python/pyreoxio/_version.py` | `862d68b Add trexio_get_back_end front end accessor` (2026-10-09) |
| `third_party/trex.json` | `trex.json` | `862d68b Add trexio_get_back_end front end accessor` (2026-10-09) |

## Re-vendor instructions

```sh
T=<path-to-trexio-repo>
cp $T/src/trexio.py                 api/trexio.py
cp $T/python/pytrexio/__init__.py  api/pytrexio/__init__.py
cp $T/python/pytrexio/_version.py  api/pytrexio/_version.py
cp $T/trex.json                     third_party/trex.json
```
