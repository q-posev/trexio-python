# PROVENANCE — vendored files from TREXIO

All vendored files are taken **unmodified** from the TREXIO repository at the commit shown below.
They are never hand-edited; re-vendoring = rerun `cp` commands in this file's instructions.

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
