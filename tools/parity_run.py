#!/usr/bin/env python3
"""Behavioral contract script. Prints normalized results; must print the same
lines under the SWIG and the nanobind install (same TREXIO lib version).

Both environments share the same public API shape (module-level
trexio.read_*/write_* functions + thin File wrapper), so the *same* calls run
in both. Output is normalized via json.dumps(..., sort_keys=True) so envs
produce comparable text; no absolute paths, addresses, or timestamps."""
import json
import os
import tempfile

import numpy as np
import trexio

out = {}
d = tempfile.mkdtemp(prefix="parity_")

# --- text + hdf5: write / read-back / reopen ---
for be, name in [(trexio.TREXIO_TEXT, "text"), (trexio.TREXIO_HDF5, "hdf5")]:
    path = os.path.join(d, "p." + name + (".h5" if be == trexio.TREXIO_HDF5 else ""))
    if os.path.exists(path):
        os.remove(path)
    try:
        f = trexio.File(path, "w", trexio.BACK_ENDS_BY_ID[be] if hasattr(trexio, "BACK_ENDS_BY_ID") else be)
        trexio.write_nucleus_num(f, 2)
        trexio.write_nucleus_repulsion(f, 1.0)
        trexio.write_nucleus_coord(
            f, np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.4]], dtype=np.float64))
        trexio.write_electron_num(f, 1)
        r1 = [trexio.read_nucleus_num(f),
              trexio.read_nucleus_repulsion(f),
              trexio.read_nucleus_coord(f).tolist()]
        f.close()
        f2 = trexio.File(path, "r", be)
        r2 = [trexio.read_nucleus_coord(f2).tolist(),
              trexio.read_nucleus_num(f2)]
        f2.close()
        out[name] = {"ok": True, "seq": r1, "reopen": r2}
    except Exception as e:  # e.g. missing back-end support
        out[name] = {"ok": False, "error": type(e).__name__, "msg": str(e)}

# --- memory back-end (2.6.1 line): in-process round-trip ---
try:
    f = trexio.File("/tmp/parity_mem_" + name, "w", trexio.TREXIO_MEMORY)
    trexio.write_nucleus_num(f, 1)
    trexio.write_nucleus_repulsion(f, 0.5)
    out["memory"] = {"ok": True, "num": trexio.read_nucleus_num(f),
                     "repulsion": trexio.read_nucleus_repulsion(f)}
    f.close()
except Exception as e:
    out["memory"] = {"ok": False, "error": type(e).__name__, "msg": str(e)}

# --- bitfield <-> orbital list round-trips (backend-independent) ---
orbitals = [0, 1, 2]
try:
    bf = trexio.to_bitfield_list(2, orbitals)
    back = trexio.to_orbital_list(2, bf)
    out["bitfield"] = {"to_bits": [int(x) for x in bf],
                       "back": [int(x) for x in back]}
except Exception as e:
    out["bitfield"] = f"ERROR: {type(e).__name__}: {e}"

# up_dn variant
try:
    up, dn = trexio.to_orbital_list_up_dn(2, [1, 2])
    out["up_dn"] = [int(x) for x in list(up) + list(dn)]
except Exception as e:
    out["up_dn"] = f"ERROR: {type(e).__name__}: {e}"

# --- error path: reading a missing attribute raises the same Error class ---
f = None
try:
    try:
        f = trexio.File(os.path.join(d, "e"), "w", trexio.TREXIO_TEXT)
        trexio.read_nucleus_num(f)  # not present -> must raise
        out["missing_read"] = "NO ERROR RAISED"
    except Exception as e:
        out["missing_read"] = type(e).__name__
finally:
    if f is not None:
        try:
            f.close()
        except Exception:
            pass

# --- string_of_error produces the same message for a known code ---
try:
    out["err_str_24"] = trexio.string_of_error(24)
except Exception as e:
    out["err_str_24"] = f"ERROR: {type(e).__name__}: {e}"

print(json.dumps(json.loads(json.dumps(out, default=str)), sort_keys=True))
