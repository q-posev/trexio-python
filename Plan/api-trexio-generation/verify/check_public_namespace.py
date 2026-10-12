#!/usr/bin/env python3
"""Import-time gate: prove the split package behaves like the old trexio.

Requires a BUILT + INSTALLED package (run after task-4 with `pip install -v .`) and a
resolvable libtrexio (LD_LIBRARY_PATH set). This is the DYNAMIC half of the "drop-in" proof
(check_equivalence.py is the static half).

Checks:
  1. import trexio succeeds.
  2. Every frozen-surface name (baseline_surface.txt) is present on `trexio`.
  3. Core names (File, Error, string_of_error, back-end ids, helpers) present.
  4. Minimal round-trips on a TREXIO_TEXT file: nucleus_num, nucleus_charge, metadata_code.
  5. write_basis_r_power is a normal generated int64 writer (the old Phase-4 forced-flatten was
     removed 2026-10-14 as a misdiagnosis); we only check it is callable — no special path.

Exit 0 = PASS, 1 = FAIL, 2 = environment not ready (build/install first).
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def surface_names():
    out = set()
    txt = (HERE / "baseline_surface.txt").read_text()
    for ln in txt.splitlines():
        body = ln.split(":", 1)[-1]
        for verb in ("read_", "write_", "has_", "delete_"):
            if body.lstrip().startswith("def " + verb):
                out.add(body.lstrip()[4:].split("(", 1)[0])
    # re-parse robustly
    import re
    out = set()
    for ln in txt.splitlines():
        body = ln.split(":", 1)[-1].strip()
        m = re.match(r"^def (read_|write_|has_|delete_)([A-Za-z_0-9]+)\(", body)
        if m:
            out.add(m.group(1) + m.group(2))
    return out


def fail(msg, code=1):
    print("FAIL:", msg)
    sys.exit(code)


def main():
    try:
        import trexio
    except Exception as e:  # noqa: BLE001
        fail(f"cannot `import trexio` ({e!r}). Build + install first (task-4) and set LD_LIBRARY_PATH.", 2)

    failures = []

    # 1) namespace: every frozen surface name present
    surf = surface_names()
    missing = [n for n in sorted(surf) if not hasattr(trexio, n)]
    if missing:
        failures.append(f"surface names missing ({len(missing)}): {missing[:15]}")
    print(f"[{'ok ' if not missing else 'BAD'}] namespace: {len(surf) - len(missing)}/{len(surf)} surface names present")

    # 2) core names
    core_need = ["File", "Error", "string_of_error",
                 "TREXIO_HDF5", "TREXIO_TEXT", "TREXIO_AUTO", "TREXIO_MEMORY",
                 "TREXIO_INVALID_BACK_END", "TREXIO_SUCCESS", "TREXIO_FAILURE",
                 "PYTREXIO_MAX_STR_LENGTH", "to_bitfield_list", "to_orbital_list",
                 "to_orbital_list_up_dn", "convert_nao_radius",
                 "evaluate_nao_radial", "evaluate_nao_radial_all", "__version__"]
    miss_core = [n for n in core_need if not hasattr(trexio, n)]
    if miss_core:
        failures.append(f"core names missing: {miss_core}")
    print(f"[{'ok ' if not miss_core else 'BAD'}] core names present ({len(core_need) - len(miss_core)}/{len(core_need)})")

    # 3) callable spot-checks
    for n in ("read_nucleus_charge", "write_nucleus_charge", "write_basis_r_power",
              "read_metadata_code", "delete_basis"):
        if not callable(getattr(trexio, n, None)):
            failures.append(f"{n} is not callable")

    # 4) round-trips on a TREXIO_TEXT file
    import numpy as np
    d = tempfile.mkdtemp(prefix="trexpynsp_")
    f = os.path.join(d, "case")
    try:
        fobj = trexio.File(f, mode="w", back_end=trexio.TREXIO_TEXT)
        trexio.write_nucleus_num(fobj, 4)
        if not trexio.has_nucleus_num(fobj):
            failures.append("has_nucleus_num False after write")
        if trexio.read_nucleus_num(fobj) != 4:
            failures.append(f"read_nucleus_num != 4 (got {trexio.read_nucleus_num(fobj)!r})")
        trexio.write_nucleus_charge(fobj, [1.0, 2.0, 3.0, 4.0])
        got = list(trexio.read_nucleus_charge(fobj))
        if [float(x) for x in got] != [1.0, 2.0, 3.0, 4.0]:
            failures.append(f"nucleus_charge round-trip mismatch: {got!r}")
        trexio.write_metadata_code(fobj, ["alpha", "beta"])
        gotcode = list(trexio.read_metadata_code(fobj))
        if gotcode != ["alpha", "beta"]:
            failures.append(f"metadata_code round-trip mismatch: {gotcode!r}")
        # 5) write_basis_r_power — a normal generated int64 writer; just confirm it is callable.
        #    (The old "Phase-4" forced-flatten was removed as a misdiagnosis 2026-10-14; it is
        #     emitted with the standard SAFE_ARRAY_W template, same as write_basis_nao_grid_start.)
        if not callable(getattr(trexio, "write_basis_r_power", None)):
            failures.append("write_basis_r_power is not callable")
        fobj.close()
    except Exception as e:  # noqa: BLE001
        failures.append(f"round-trip raised: {e!r}")

    print("\n" + "=" * 60)
    if failures:
        print("RESULT: FAIL")
        for x in failures:
            print("  -", x)
        return 1
    print("RESULT: PASS -- the split package imports and behaves like the old trexio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
