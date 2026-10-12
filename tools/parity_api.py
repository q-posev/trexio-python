#!/usr/bin/env python3
"""Print a canonical contract report of the installed trexio Python API.
Run with both the SWIG and the nanobind install; diff the two outputs."""
import json
import trexio

names = sorted(n for n in dir(trexio) if not n.startswith("_"))
report = {"names": names}
for n in names:
    v = getattr(trexio, n)
    if isinstance(v, (int, float, str)):
        report[n] = str(v)          # constants: TREXIO_HDF5, TREXIO_SUCCESS, etc.
print(json.dumps(report, sort_keys=True))
