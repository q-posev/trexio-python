#!/usr/bin/env python3
"""Shared classification model for the trexio API surface.

This module is the SINGLE source of the name/type tables and the C-signature
classification that decides, for every API name, which "family" it belongs to.
It is imported by BOTH the C++ emitter (``tools/gen_binding.py``) and the
Python emitter (``tools/gen_trexio_py.py``), so the two surfaces are driven by
one definition and cannot drift.

DO NOT duplicate this logic in either emitter -- import it from here instead.
"""
import re

__all__ = [
    "SKIP", "EXTRA", "CT_T", "LOW_DIM_FN",
    "parse_protos", "locate_group_var", "Rec", "classify", "FAMILIES",
]

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


# The set of classification families the emitters handle (see references/10).
# classify() only ever returns one of these names in Rec.family.
FAMILIES = {
    "HAS", "SCALAR_R", "SCALAR_W", "SIZE", "SAFARR_R", "SAFARR_W",
    "STR_R", "STR_W", "STRARR_W", "OFF5_R", "OFF5_W", "SPARSE_R", "SPARSE_W",
}


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
