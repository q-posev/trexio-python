#!/usr/bin/env python3
"""Prove the api/trexio.py -> core + generated split is a no-op (static, no build).

Compares FROZEN baselines (captured before any change) against the current split:
    api/trexio.py       -> CORE (File class, helpers, constants -> _base)
    api/trexio_gen.py   -> GENERATED surface (has_/read_/write_/delete_)

Four checks:
  1. SURFACE  -- every wrapper `def` in the frozen baseline is present in the NEW
                 generated file by the same name (and not duplicated in core).
  2. CORE     -- every baseline core `def` is still present in core.
  3. SYMBOLS  -- the frozen required set (== tools/required_api.names, the proven
                 878 `pytr.<name>` refs) is fully referenced by core+gen together,
                 with no unexpected extras (unless --tolerate-new-symbols).
  4. NAME→SYM -- for a set of probe functions, the `pytr.trexio_*` call inside the
                 new generated function still matches the baseline (guards against a
                 wrong safe_/_low/_64 symbol being emitted).

Exit 0 = PASS, 1 = FAIL, 2 = files missing (run the split first).

Usage:
    python3 check_equivalence.py
    python3 check_equivalence.py --core api/trexio.py --gen api/trexio_gen.py
    python3 check_equivalence.py --required tools/required_api.names
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SURF = re.compile(r"^(read_|write_|has_|delete_)")
SYMBOL = re.compile(r"pytr\.([A-Za-z_0-9]+)")
DEF = re.compile(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(")


def read(p):
    return Path(p).read_text().splitlines()


def defs(file):
    return set(DEF.findall(Path(file).read_text()))


def _defname(line):
    """Strip the leading 'lineno:' and return the def name (or None)."""
    m = DEF.match(line.split(":", 1)[-1])
    return m.group(1) if m else None


def baseline_surface():
    s = set()
    for ln in read(HERE / "baseline_surface.txt"):
        n = _defname(ln)
        if n and SURF.match(n):
            s.add(n)
    return s


def baseline_core():
    s = set()
    for ln in read(HERE / "baseline_core.txt"):
        n = _defname(ln)
        if n and not SURF.match(n):
            s.add(n)
    return s


def baseline_required(required):
    required = Path(required)
    return set(x.strip() for x in required.read_text().splitlines() if x.strip())


def symbol_calls(file):
    txt = Path(file).read_text()
    return set(SYMBOL.findall(txt))


def section(title, ok):
    print(f"\n[{'PASS' if ok else 'FAIL'}] {title}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default="api/trexio.py")
    ap.add_argument("--gen", default="api/trexio_gen.py")
    ap.add_argument("--required", default=str(HERE / "baseline_symbols.txt"))
    ap.add_argument("--tolerate-new-symbols", action="store_true",
                    help="allow symbols beyond the required set (only on a deliberate release bump).")
    a = ap.parse_args()

    print("=" * 74)
    print("trexio.py split equivalence (frozen baselines vs current split)")
    print(f"  core     = {a.core}")
    print(f"  gen      = {a.gen}")
    print(f"  required = {a.required}")
    for f in (a.core, a.gen):
        if not Path(f).exists():
            print(f"\nFAIL: {f} does not exist -- run task-1 (split) + task-3 (generate) first.")
            return 2

    ok = True

    # 1) SURFACE
    base_surf = baseline_surface()
    gen_defs = defs(a.gen)
    gen_surf = {n for n in gen_defs if re.match(r"^(read_|write_|has_|delete_)", n)}
    missing = base_surf - gen_surf
    dup_in_core = base_surf & {n for n in defs(a.core) if re.match(r"^(read_|write_|has_|delete_)", n)}
    ok &= section(f"surface: {len(base_surf) - len(missing)}/{len(base_surf)} wrappers in {a.gen}", not missing)
    if missing:
        print(f"  MISSING from gen ({len(missing)}): {sorted(missing)[:15]}")
    ok &= section("surface: none duplicated/defined in core", not dup_in_core)
    if dup_in_core:
        print(f"  DUPLICATED in core ({len(dup_in_core)}): {sorted(dup_in_core)[:15]}")

    # 2) CORE
    base_core = baseline_core()
    core_defs = defs(a.core)
    missing_core = base_core - core_defs
    ok &= section(f"core: {len(base_core) - len(missing_core)}/{len(base_core)} functions in {a.core}", not missing_core)
    if missing_core:
        print(f"  MISSING from core ({len(missing_core)}): {sorted(missing_core)}")

    # 3) SYMBOLS (ABI)
    req = baseline_required(a.required)
    new_refs = symbol_calls(a.core) | symbol_calls(a.gen)
    missing_sym = req - new_refs
    extra_sym = new_refs - req
    sym_ok = (not missing_sym) and (a.tolerate_new_symbols or not extra_sym)
    ok &= section(f"ABI: {len(req) - len(missing_sym)}/{len(req)} required symbols referenced", sym_ok)
    if missing_sym:
        print(f"  MISSING symbols ({len(missing_sym)}): {sorted(missing_sym)[:15]}")
    if extra_sym:
        print(f"  EXTRA symbols ({len(extra_sym)}): {sorted(extra_sym)[:15]}")

    # 4) NAME->SYMBOL probes
    probes = {
        "read_nucleus_charge": "pytr.trexio_read_safe_nucleus_charge_64",
        "write_nucleus_charge": "pytr.trexio_write_safe_nucleus_charge_64",
        "read_nucleus_num": "pytr.trexio_read_nucleus_num",
        "write_nucleus_num": "pytr.trexio_write_nucleus_num",
        "read_metadata_code": "pytr.trexio_read_metadata_code_low",
        "write_metadata_code": "pytr.trexio_write_metadata_code",
        "has_nucleus_num": "pytr.trexio_has_nucleus_num",
        "delete_basis": "pytr.trexio_delete_basis",
    }
    print("\n[name->symbol] probes in generated file:")
    for fn, want in probes.items():
        body = re.search(rf"\ndef {fn}\(.*?(?=\ndef |\Z)", Path(a.gen).read_text(), re.S)
        has = bool(body and want in body.group(0))
        print(f"  {'ok ' if has else 'BAD'} {fn:22s} expects {want}")
        ok &= has

    print("\n" + "=" * 74)
    print("RESULT:", "PASS -- split preserves surface, core, and ABI."
          if ok else "FAIL -- see lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
