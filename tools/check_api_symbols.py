#!/usr/bin/env python3
"""Enumerate/verify the low-level names the vendored trexio API needs.

  --list    write tools/required_api.names (sorted, one per line)
  --verify  import pytrexio.pytrexio, report+exit(1) on missing required names
"""
import argparse, re, sys, pathlib

ROOT  = pathlib.Path(__file__).resolve().parent.parent
API   = ROOT / "api" / "trexio.py"
NAMES = ROOT / "tools" / "required_api.names"


def required_names():
    src = API.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\bpytr\.([A-Za-z_0-9]+)\s*\(", src)))


def main():
    p = argparse.ArgumentParser()
    a = p.add_argument
    a("--list", action="store_true")
    a("--verify", action="store_true")
    ns = p.parse_args()

    if ns.list:
        names = required_names()
        NAMES.write_text("\n".join(names) + "\n")
        print(f"wrote {NAMES}: {len(names)} names")

    if ns.verify:
        names = required_names()
        try:
            import pytrexio.pytrexio as m
        except Exception as e:
            print("FAIL: import pytrexio.pytrexio:", e)
            sys.exit(1)

        missing = [n for n in names if not hasattr(m, n)]
        print(f"required={len(names)} missing={len(missing)}")

        if missing:
            join_text = "\n  "
            printed = missing[:40]
            rest = "(..." if len(missing) > 40 else ""
            print("MISSING:\n  " + join_text.join(printed) + f"{rest}")

        sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
