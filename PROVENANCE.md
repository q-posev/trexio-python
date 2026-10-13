# PROVENANCE — upstream TREXIO files this project keeps

Only **three** files are genuinely **vendored** (copied from a TREXIO checkout and
kept current by re-vendor — the `cp` block at the bottom): `api/pytrexio/__init__.py`,
`api/pytrexio/_version.py`, and `third_party/trex.json`.

The high-level Python API is **not** a verbatim copy anymore — it is split into a
hand-written core, a shared base, and a generated surface:

- `api/trexio.py` — the **hand-written CORE** (`File` class, lifecycle,
  bitfield/orbital helpers, NAO). It was **adopted once** from TREXIO's
  `src/trexio.py` and is since **maintained here** (see `Plan/api-trexio-generation/`).
- `api/trexio/trexio_gen.py` (→ `api/trexio_gen.py`) — the **generated**
  per-variable surface (the 862 `has_/read_/write_/delete_` wrappers), produced by
  `tools/gen_trexio_py.py` from `third_party/trex.json` + the installed `trexio.h`.
  **Regenerate; never hand-edit.**
- `api/trexio/_base.py` — the **shared base** (numpy / `pytrexio` imports,
  `PYTREXIO_MAX_STR_LENGTH`, the `TREXIO_*` exit codes and back-end ids, and the
  `Error` class). It breaks the import cycle between core and generated surface.

**Provenance commit.** The three vendored files were last taken from TREXIO commit
`862d68b Add trexio_get_back_end front end accessor` (2026-10-09). Update this line
whenever you re-vendor.

## Core constants that must match the installed library

`api/trexio/_base.py` declares the back-end id values to match the installed TREXIO.
These are a normal **core** fact (not a "documented exception" to a verbatim copy):
when a TREXIO release renumbers the back-end enums — e.g. the TREX-CoE#340 renumber on
the 2.6.1+0102739 line that set `AUTO=2, MEMORY=3` — update the constants in
`api/trexio/_base.py` to match the new installed `trexio.h` / `libtrexio`.

> **Note.** The old **Phase 4** item — special-casing `write_basis_r_power` — was
> **removed 2026-10-14** as a misdiagnosis. Do **not** re-add it.
> `write_basis_r_power` is a **normal generated int64 `SAFE_ARRAY_W` writer**, with the
> standard body shared by `write_basis_nao_grid_start`, `write_auxbasis_r_power`, and
> every other int64 array. It is emitted by `tools/gen_trexio_py.py` like the rest.

| File | How it's kept current |
|---|---|
| `api/pytrexio/__init__.py`, `api/pytrexio/_version.py`, `third_party/trex.json` | **re-vendor** (the `cp` block below) |
| `api/trexio.py` (core) | hand-maintained (adopted once from `src/trexio.py`, then maintained here) |
| `api/trexio/_base.py` | hand-maintained shared base (update the back-end constants when a release renumbers them) |
| `api/trexio_gen.py` | **generated** (`tools/gen_trexio_py.py`) — regenerate, never hand-edit |

## Re-vendor + regenerate instructions

```sh
T=<path-to-trexio-repo>
cp $T/python/pytrexio/__init__.py  api/pytrexio/__init__.py
cp $T/python/pytrexio/_version.py  api/pytrexio/_version.py
cp $T/trex.json                    third_party/trex.json
# the core is hand-maintained — port any *new* core pieces (lifecycle / NAO /
# bitfield helpers) from $T/src/trexio.py by hand if they exist, then
# regenerate the generated surface:
python tools/gen_trexio_py.py
```
**Do not** `cp $T/src/trexio.py api/trexio.py` — the API is now core + generated, not
a verbatim copy.
