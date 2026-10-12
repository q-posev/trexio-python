#!/usr/bin/env python3
"""Generate src/generated_bindings.cpp: the per-variable has/read/write
bindings of the pytrexio nanobind module.

Inputs:
  * tools/required_api.names      -- the names the vendored api/trexio.py calls
                                     (the authoritative required set);
  * third_party/trex.json         -- semantic cross-check of variable kinds;
  * the installed <trexio.h>      -- the authoritative C signatures (types,
                                     argument order).  Default location:
                                     $TREXIO_HOME/include/trexio.h or
                                     $HOME/.local/include/trexio.h.

The classification is driven by the *C signature shape* of each name
(verified against the 2.6.1 line of TREXIO):

  | family   | C params after the handle            | Python binding                          |
  |----------|--------------------------------------|-----------------------------------------|
  | HAS      | (none)                               | (h)                       -> int       |
  | SCALAR_R | (T* out)                             | (h)                       -> [rc, v]   |
  | SCALAR_W | (const T in)                         | (h, v)                  -> int         |
  | SIZE     | (int64_t* size), name ends _size     | (h)                       -> [rc, n]   |
  | SAFARR_R | (T* out, int64 dim)                  | (h, dim)                -> [rc, list]  |
  | SAFARR_W | (const T* in, int64 dim)             | (h, arr)                -> int         |
  | STR_R    | (char* out, int32 len)               | (h, max_len)            -> [rc, str]   |
  | STR_W    | (const char* in, int32 len)          | (h, s, max_len)         -> int         |
  | STRARR_W | (const char** in, int32 len)         | (h, [s...], max_len)    -> int         |
  | OFF5_R   | (int64 off, int64* n, T* out, int64) | (h, off, n, dim)        -> [rc, n, ls] |
  | OFF5_W   | (int64 off, int64 n, const T*, int64)| (h, off, n, arr)        -> int         |
  | SPARSE_R | (off, n*, int32* i, si, double* v, sv)| (h, off, n, si, sv)    -> [rc, n,i,v] |
  | SPARSE_W | (off, n, const int32*, si, const dbl,sv)| (h, off, n, i, v)      -> int         |

These Python shapes were verified against the vendored api/trexio.py call
sites (the ABI is what that file unpacks).

Usage:
  python3 tools/gen_binding.py [--trex-json PATH] [--out PATH] [--trexio-header PATH]
"""
import argparse
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Names bound by hand in src/core.cpp (Phase 2) -- never emitted here.
SKIP = {
    "TREXIO_DELIM",
    "trexio_open", "trexio_close", "trexio_flush", "trexio_inquire", "trexio_info",
    "trexio_set_state", "trexio_get_state", "trexio_set_one_based", "trexio_cp",
    "trexio_string_of_error", "trexio_has_backend", "trexio_has_back_end",
    "trexio_get_back_end", "trexio_get_int64_num",
    "trexio_to_bitfield_list", "trexio_safe_to_orbital_list",
    "trexio_safe_to_orbital_list_up_dn",
    "trexio_convert_nao_radius_py", "trexio_evaluate_nao_radial_py",
    "trexio_evaluate_nao_radial_all_py",
}

# Extra names beyond tools/required_api.names (the 878 vendored-API names) that
# TREXIO's own test suite (tests/test_pytrexio.py, SWIG era) calls. They follow
# the exact call shapes SWIG exposed (write: dim derived from the array;
# read: explicit dim), so the SAFARR emitters handle them as-is.
EXTRA = {
    "trexio_read_safe_nucleus_charge",
    "trexio_write_safe_nucleus_charge",
    "trexio_read_safe_basis_nucleus_index",
    "trexio_write_safe_basis_nucleus_index",
}

CT_T = {"int32_t": "int32_t", "int64_t": "int64_t", "long long": "int64_t",
        "double": "double", "float": "float", "int": "int32_t"}


def load_required():
    return [l.strip() for l in (ROOT / "tools" / "required_api.names").read_text().splitlines() if l.strip()]


def default_header():
    env = os.environ.get("TREXIO_HOME")
    cands = [
        pathlib.Path(env) / "include" / "trexio.h" if env else None,
        pathlib.Path.home() / ".local" / "include" / "trexio.h",
    ]
    for c in cands:
        if c and c.exists():
            return c
    sys.exit(f"gen_binding: no installed trexio.h found (set TREXIO_HOME or --trexio-header)")


def parse_protos(header_text, names):
    """Return {name: [params]} where each param is (base_type, ptrs, const)."""
    collapsed = re.sub(r"\s+", " ", header_text)
    protos = {}
    for name in names:
        m = re.search(r"\b" + re.escape(name) + r"\s*\(", collapsed)
        if not m:
            protos[name] = None
            continue
        i = collapsed.index("(", m.start())
        depth, j = 0, i
        while True:
            if collapsed[j] == "(":
                depth += 1
            elif collapsed[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inside = collapsed[i + 1:j]
        parts = []
        if inside.strip():
            cur, d = "", 0
            for ch in inside:
                if ch == "(" and d == 0:
                    d += 1
                    cur += ch
                elif ch == ")" and d == 1:
                    d = 0
                    cur += ch
                elif ch == "," and d == 0:
                    parts.append(cur.strip())
                    cur = ""
                else:
                    cur += ch
            if cur.strip():
                parts.append(cur.strip())
        params = []
        for p in parts:
            ptrs = max(p.count("*"), 0)
            const = "const" in p
            toks = p.replace("*", "").split()
            base = toks[1] if (toks and toks[0] == "const") else (toks[0] if toks else "")
            params.append((base, ptrs, const))
        protos[name] = params
    return protos


def locate_group_var(data, var):
    """Resolve '<group>_<var>' against trex.json (longest group prefix wins)."""
    groups = sorted(data, key=len, reverse=True)
    for g in groups:
        if var == g or var.startswith(g + "_"):
            v = var[len(g) + 1:] if var != g else ""
            if v and v in data[g]:
                return g, v
    for g in groups:  # group-level name (e.g. has_ao): var is the group itself
        if var == g:
            return g, None
    return None, None


class Rec:
    def __init__(self, name, family, T=None, verb=None):
        self.name = name
        self.family = family
        self.T = T
        self.verb = verb


def classify(name, params, data):
    """Map a name + its C params (after the handle) to a recipe.

    Returns Rec or None (unhandled).
    """
    verb = None
    m = re.match(r"trexio_(has|read|write)_", name)
    if not m:
        return None
    verb = m.group(1)
    P = params[1:] if params and params[0][0] == "trexio_t" else params

    def data_T(idx):
        base = P[idx][0] if P[idx][0] not in CT_T else CT_T[P[idx][0]]
        return base if base in CT_T else None

    if verb == "has":
        return Rec(name, "HAS") if len(P) == 0 else None

    if len(P) == 1 and P[0][1] == 1:                    # (T* out)
        T = data_T(0)
        if T:
            if verb == "read":
                if name.endswith("_size") and T == "int64_t":
                    return Rec(name, "SIZE", T)
                return Rec(name, "SCALAR_R", T)
            return Rec(name, "SCALAR_W", T)
    if len(P) == 1 and P[0][1] == 0:                    # (const T in)
        base = P[0][0]
        if base in CT_T:
            return Rec(name, "SCALAR_W", CT_T[base])
    if len(P) == 2:
        if P[0][1] == 1 and P[0][0] == "char" and verb == "read":
            return Rec(name, "STR_R")
        if P[0][1] == 1 and P[0][0] == "char" and verb == "write":
            return Rec(name, "STR_W")
        if P[0][1] == 2 and P[0][0] == "char" and verb == "write":
            return Rec(name, "STRARR_W")
        T = data_T(0)
        if T and verb == "read":
            return Rec(name, "SAFARR_R", T)
        if T and verb == "write":
            return Rec(name, "SAFARR_W", T)
    if len(P) == 4:
        T = data_T(2)
        if T and verb == "read":
            return Rec(name, "OFF5_R", T)
        if T and verb == "write":
            return Rec(name, "OFF5_W", T)
    if len(P) == 6:
        if verb == "read":
            return Rec(name, "SPARSE_R")
        if verb == "write":
            return Rec(name, "SPARSE_W")
    return None


# ---------------------------------------------------------------- emitters --
EPI = '}, nb::arg('

def e_HAS(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  return static_cast<int>({r.name}(h->raw()));\n'
        + EPI + '"handle"));')


def e_SCALAR_R(r):
    t = "nb::float_" if r.T in ("double", "float") else "nb::int_"
    return (
        f'm.def("{r.name}", [](TrexioHandle* h) -> nb::object {{\n'
        f'  {r.T} v{{}};\n'
        f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), &v)) : static_cast<int>(TREXIO_FAILURE);\n'
        f'  nb::list l; l.append(nb::int_(rc)); l.append({t}(v)); return l;\n'
        + EPI + '"handle"));')


def e_SCALAR_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, {r.T} v) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  return static_cast<int>({r.name}(h->raw(), v));\n'
        + EPI + '"handle"), nb::arg("value"));')


def e_SIZE(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h) -> nb::object {{\n'
        f'  int64_t s{{}};\n'
        f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), &s)) : static_cast<int>(TREXIO_FAILURE);\n'
        f'  nb::list l; l.append(nb::int_(rc)); l.append(nb::int_(s)); return l;\n'
        + EPI + '"handle"));')


def e_SAFARR_R(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int64_t dim) -> nb::object {{\n'
        f'  std::vector<{r.T}> v(static_cast<size_t>(dim < 0 ? 0 : dim), {{}});\n'
        f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), v.data(), static_cast<int64_t>(dim))) : static_cast<int>(TREXIO_FAILURE);\n'
        f'  nb::list l; l.append(nb::int_(rc)); l.append(vec_list(v)); return l;\n'
        + EPI + '"handle"), nb::arg("dim"));')


def e_SAFARR_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, const nb::object& a) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  std::vector<{r.T}> v = cast_vec<{r.T}>(a);\n'
        f'  return static_cast<int>({r.name}(h->raw(), v.data(), static_cast<int64_t>(v.size())));\n'
        + EPI + '"handle"), nb::arg("data"));')


# _low string-array reads: C writes `count * (max_str_len + TREXIO_DELIM)`
# bytes into the caller buffer (no bounds check), so the count must be known
# up front. It is the sibling *_num variable of the string dataset.
LOW_DIM_FN = {
    "trexio_read_nucleus_label_low":     "trexio_read_nucleus_num",
    "trexio_read_state_label_low":       "trexio_read_state_num",
    "trexio_read_state_file_name_low":   "trexio_read_state_num",
    "trexio_read_metadata_author_low":   "trexio_read_metadata_author_num",
    "trexio_read_metadata_code_low":     "trexio_read_metadata_code_num",
    "trexio_read_mo_class_low":          "trexio_read_mo_num",
    "trexio_read_mo_symmetry_low":       "trexio_read_mo_num",
}


def e_STR_R(r):
    # The C backends write count*(max_str_len + TREXIO_DELIM) bytes into the
    # caller buffer WITHOUT bounds checks (they trust the caller sized it for
    # `count` entries -- SWIG derived `count` via typemaps). We must do the
    # same: read the sibling *_num variable and size the buffer accordingly.
    nfn = LOW_DIM_FN.get(r.name)
    if nfn:
        head = (
            f'  int32_t n = 0;\n'
            f'  int nrc = {nfn}(h->raw(), &n);\n'
            f'  if (nrc != 0) {{ nb::list l; l.append(nb::int_(nrc)); l.append(std::string()); return l; }}\n'
            f'  int32_t mlen = max_str_len > 0 ? max_str_len : 256;\n'
            f'  std::vector<char> buf(static_cast<size_t>(n) * static_cast<size_t>(mlen) + 2 * static_cast<size_t>(n) + 4, 0);\n'
            f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), buf.data(), mlen)) : static_cast<int>(TREXIO_FAILURE);\n'
        )
    else:
        head = (
            f'  int32_t mlen = max_str_len > 0 ? max_str_len : 256;\n'
            f'  std::vector<char> buf(static_cast<size_t>(mlen) + 4, 0);\n'
            f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), buf.data(), mlen)) : static_cast<int>(TREXIO_FAILURE);\n'
        )
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int32_t max_str_len) -> nb::object {{\n'
        + head
        + f'  nb::list l; l.append(nb::int_(rc)); l.append(std::string(buf.data())); return l;\n'
        + EPI + '"handle"), nb::arg("max_str_len"));')


def e_STR_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, const std::string& s, int32_t max_str_len) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  return static_cast<int>({r.name}(h->raw(), s.c_str(), max_str_len > 0 ? max_str_len : static_cast<int32_t>(s.size() + 1)));\n'
        + EPI + '"handle"), nb::arg("value"), nb::arg("max_str_len"));')


def e_STRARR_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, const nb::object& arr, int32_t max_str_len) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  std::vector<std::string> strs;\n'
        f'  for (const auto& x : arr) strs.push_back(nb::cast<std::string>(x));\n'
        f'  std::vector<const char*> cs; cs.reserve(strs.size());\n'
        f'  for (const auto& s : strs) cs.push_back(s.c_str());\n'
        f'  return static_cast<int>({r.name}(h->raw(), cs.data(), max_str_len > 0 ? max_str_len : static_cast<int32_t>(1)));\n'
        + EPI + '"handle"), nb::arg("data"), nb::arg("max_str_len"));')


def e_OFF5_R(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int64_t offset, int64_t buffer_size, int64_t dim) -> nb::object {{\n'
        f'  int64_t n = buffer_size;  // in/out: C reads the requested count, writes the actual one\n'
        f'  std::vector<{r.T}> v(static_cast<size_t>(dim < 0 ? 0 : dim), {{}});\n'
        f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), static_cast<int64_t>(offset), &n, v.data(), static_cast<int64_t>(dim))) : static_cast<int>(TREXIO_FAILURE);\n'
        f'  nb::list l; l.append(nb::int_(rc)); l.append(nb::int_(n)); l.append(vec_list(v)); return l;\n'
        + EPI + '"handle"), nb::arg("offset"), nb::arg("buffer_size"), nb::arg("dim"));')


def e_OFF5_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int64_t offset, int64_t buffer_size, const nb::object& a) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  std::vector<{r.T}> v = cast_vec<{r.T}>(a);\n'
        f'  return static_cast<int>({r.name}(h->raw(), static_cast<int64_t>(offset), static_cast<int64_t>(buffer_size), v.data(), static_cast<int64_t>(v.size())));\n'
        + EPI + '"handle"), nb::arg("offset"), nb::arg("buffer_size"), nb::arg("data"));')


def e_SPARSE_R(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int64_t offset, int64_t buffer_size, int64_t size_index, int64_t size_value) -> nb::object {{\n'
        f'  int64_t n = buffer_size;  // in/out: C reads the requested count, writes the actual one\n'
        f'  std::vector<int32_t> ix(static_cast<size_t>(size_index < 0 ? 0 : size_index), 0);\n'
        f'  std::vector<double>  vv(static_cast<size_t>(size_value < 0 ? 0 : size_value), 0.0);\n'
        f'  int rc = (h && h->open()) ? static_cast<int>({r.name}(h->raw(), static_cast<int64_t>(offset), &n, ix.data(), static_cast<int64_t>(ix.size()), vv.data(), static_cast<int64_t>(vv.size()))) : static_cast<int>(TREXIO_FAILURE);\n'
        f'  nb::list l; l.append(nb::int_(rc)); l.append(nb::int_(n)); l.append(vec_list(ix)); l.append(vec_list(vv)); return l;\n'
        + EPI + '"handle"), nb::arg("offset"), nb::arg("buffer_size"), nb::arg("size_index"), nb::arg("size_value"));')


def e_SPARSE_W(r):
    return (
        f'm.def("{r.name}", [](TrexioHandle* h, int64_t offset, int64_t buffer_size, const nb::object& ix, const nb::object& vv) -> int {{\n'
        f'  if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);\n'
        f'  std::vector<int32_t> i32 = cast_vec<int32_t>(ix);\n'
        f'  std::vector<double>  d64 = cast_vec<double>(vv);\n'
        f'  return static_cast<int>({r.name}(h->raw(), static_cast<int64_t>(offset), static_cast<int64_t>(buffer_size), i32.data(), static_cast<int64_t>(i32.size()), d64.data(), static_cast<int64_t>(d64.size())));\n'
        + EPI + '"handle"), nb::arg("offset"), nb::arg("buffer_size"), nb::arg("indices"), nb::arg("values"));')


EMIT = {
    "HAS": e_HAS, "SCALAR_R": e_SCALAR_R, "SCALAR_W": e_SCALAR_W, "SIZE": e_SIZE,
    "SAFARR_R": e_SAFARR_R, "SAFARR_W": e_SAFARR_W, "STR_R": e_STR_R,
    "STR_W": e_STR_W, "STRARR_W": e_STRARR_W, "OFF5_R": e_OFF5_R,
    "OFF5_W": e_OFF5_W, "SPARSE_R": e_SPARSE_R, "SPARSE_W": e_SPARSE_W,
}


def crosscheck(data, recs, unhandled):
    """Warn (not fail) if a bound variable's trex.json kind contradicts its recipe T."""
    kinds = {"HAS": "any", "SIZE": "int", "SCALAR_R": "int|float", "SCALAR_W": "int|float",
             "SAFARR_R": "int|float", "SAFARR_W": "int|float", "STR_R": "str",
             "STR_W": "str", "STRARR_W": "str", "OFF5_R": "float|int",
             "OFF5_W": "float|int", "SPARSE_R": "sparse|buffered", "SPARSE_W": "sparse|buffered"}
    bad = []
    for r in recs:
        var = r.name[9:]  # strip trexio_
        g, v = locate_group_var(data, var)
        if v is None:
            continue
        spec = data[g][v]
        kind = spec[0]
        if "sparse" in kind or "buffered" in kind:
            if r.family not in ("SPARSE_R", "SPARSE_W", "OFF5_R", "OFF5_W"):
                bad.append(f"{r.name}: json kind {kind!r} vs family {r.family}")
        elif kind == "str":
            if r.family not in ("STR_R", "STR_W", "STRARR_W"):
                bad.append(f"{r.name}: json kind 'str' vs family {r.family}")
        else:  # dim / int / float / index
            want = "int" if (r.T in (None, "int32_t", "int64_t")) else "float"
            json_int = kind in ("dim", "int", "index") or (kind == "float" and r.T in ("double", "float"))
            json_float = kind == "float"
            ok = (want == "int" and json_int) or (want == "float" and (json_float or kind in ("dim", "int"))) or want == "int"
            if not ok:
                bad.append(f"{r.name}: json kind {kind!r} vs family {r.family} (T={r.T})")
    return bad


def gen(trex_json, required, out_path, header_path):
    data = json.loads(trex_json.read_text())
    names = sorted(set(required) | EXTRA)
    protos = parse_protos(header_path.read_text(), names)

    recs, unhandled = [], []
    for name in names:
        if name in SKIP or name.startswith("trexio_delete_"):
            continue
        params = protos.get(name)
        if params is None:
            unhandled.append(f"{name} (not found in {header_path.name})")
            continue
        rec = classify(name, params, data)
        if rec is None:
            unhandled.append(f"{name} (shape {[p[0] + '*' * p[1] for p in params[1:]]})")
            continue
        recs.append(rec)

    fam = {}
    warnings = crosscheck(data, recs, unhandled)
    out = [
        "/* GENERATED by tools/gen_binding.py -- DO NOT EDIT BY HAND. */",
        "/* Source: tools/required_api.names + installed trexio.h + third_party/trex.json */",
        '#include "bind_helpers.hpp"',
        "",
        "void generated_defs(nb::module_ & m) {",
    ]
    for r in recs:
        fam[r.family] = fam.get(r.family, 0) + 1
        out.append(EMIT[r.family](r))
    out.append("}")
    out_path.write_text("\n".join(out) + "\n")

    print(f"wrote {out_path}: {len(recs)} bindings, {len(unhandled)} unhandled, {len(warnings)} cross-check warnings")
    for k in sorted(fam):
        print(f"  {k:10s} {fam[k]:5d}")
    if warnings:
        print("CROSS-CHECK WARNINGS (trex.json vs header):", file=sys.stderr)
        for w in warnings[:20]:
            print("  " + w, file=sys.stderr)
    if unhandled:
        print("UNHANDLED:", file=sys.stderr)
        for u in unhandled:
            print("  " + u, file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    a = p.add_argument
    a("--trex-json", default=str(ROOT / "third_party" / "trex.json"))
    a("--out", default=str(ROOT / "src" / "generated_bindings.cpp"))
    a("--trexio-header", default=None)
    ns = p.parse_args()
    header = pathlib.Path(ns.trexio_header) if ns.trexio_header else default_header()
    gen(pathlib.Path(ns.trex_json), load_required(), pathlib.Path(ns.out), header)


if __name__ == "__main__":
    main()
