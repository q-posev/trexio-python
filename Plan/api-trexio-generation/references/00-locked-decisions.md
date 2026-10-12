# 00 — Locked decisions + scope

These three were chosen with the owner. They are **binding** for this effort; revisit only
with explicit sign-off.

## D1 — Location: sibling generated module (A)
- `api/trexio.py` becomes a **small hand-written core** (File class, `_open/_close/_cp`,
  `flush`, `info`, bitfield/orbital helpers, NAO-radial).
- `api/trexio_gen.py` is the **generated surface** (the 862 `has_/read_/write_/delete_`).
- `api/trexio/_base.py` holds the shared bits both need (`pytr`, `numpy`, `Error`,
  `string_of_error`, `TREXIO_*` codes, `PYTREXIO_MAX_STR_LENGTH`) to **break the import
  cycle** and stay DRY.
- Rationale: mirrors `src/core.cpp` + `src/generated_bindings.cpp`; makes "generated vs
  hand-edit" unambiguous; keeps the small stable core human-ownable.

## D2 — "Which functions": anchor to proven list + header
- Surface = names in `tools/required_api.names` (the *proven* call set), with the exact
  C symbol + shape read from the **installed `trexio.h`** (ABI authority), and dims/kinds
  from **`third_party/trex.json`**.
- Not a pure-from-trex.json guess (that would require re-deriving the read-only / safe /
  unsafe / `_low` / `_64` / sparse curation — higher risk of emitting for names not in the
  proven surface). The proven list + header keep it a strict drop-in; the JSON supplies the
  data model so **new variables in a release appear automatically** when `required_api.names`
  or the header is refreshed.
- Guard: any required name with a shape no emitter covers → the generator **exits 1 with a
  `TODO:` list** (same contract as `tools/gen_binding.py`). Never silently mis-generate.

## D3 — Docstrings: regenerate, compact-but-full
- Emit a family template: signature line, one-line description naming the variable,
  `Parameters`, `Returns` (type + shape note), `Raises`. Dims come from `trex.json`.
- Rationale: 90% of the 35k lines are docstrings; compact-but-full collapses the file to
  ~6–9k lines and is trivially regenerable. Docstrings are not the tested contract, so this
  is safe. (Verbatim preservation was considered and rejected as high-effort + re-introduces
  hand-maintained text.)

## Scope — what IS generated
- The 862 wrappers: `read_*` (289), `write_*` (260), `has_*` (287, incl. group-level
  `has_<group>`), `delete_*` (26, group-level).
- Their bodies AND docstrings (D3). Their `pytr.trexio_<sym>` calls (D2).

## Scope — what is NOT generated (stays core, hand-maintained)
- `File` class (`__init__/__enter__/__exit__/close/set_state/get_state/flush/inquire`).
- Module helpers: `_open`, `_close`, `flush`, `_inquire`, `_cp`, `info`, `to_bitfield_list`,
  `to_orbital_list`, `to_orbital_list_up_dn`, `convert_nao_radius`, `evaluate_nao_radial`,
  `evaluate_nao_radial_all`.
- `Error`, `string_of_error`, and all module constants (`TREXIO_*` codes, back-end ids,
  `PYTREXIO_MAX_STR_LENGTH`) → moved to `_base.py`.
- One remaining PROVENANCE item: the Phase-3 back-end constants → `_base.py`.
  The older Phase-4 `write_basis_r_power` "exception" (a misdiagnosis) was removed on
  2026-10-14; `write_basis_r_power` is generated with the standard int64 SAFE_ARRAY_W
  template, like each other `write_basis_*`.

## Explicit out-of-scope
- Changing the C++ binding (`generated_bindings.cpp` output stays **byte-identical**;
  `tools/gen_binding.py` is refactored *in place* to import the shared model but produces
  the same file).
- Adding/removing variables, new back ends, new families (those arrive via a normal
  TREXIO release → run the generators).
