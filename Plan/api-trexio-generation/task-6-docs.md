# Task 6 — Update the docs + provenance to the new (core + generated) model

**Track:** B (docs) · **Depends on:** none — **can run now, in parallel with Track A.**
It only re-points prose at the new layout. **Do not change code in this task** (if the code isn't
done yet, base the wording on `references/10-architecture.md`; it describes the target layout).

## Files I own (only these)
- `PROVENANCE.md`
- `docs/updating-with-trexio.md`
- `docs/package-layout.md`
- `README.md` (the "File discipline" block + any layout mention)
- `Plan/api-trexio-generation/README.md` (add a one-line pointer, optional)

## The new model to describe (single source: `references/10-architecture.md`)
- `api/trexio.py` = **hand-written CORE** (File class, lifecycle, bitfield/orbital helpers, NAO).
- `api/trexio/_base.py` = **shared** (pytr, numpy, Error, `TREXIO_*` codes, back-end ids,
  `PYTREXIO_MAX_STR_LENGTH`) — breaks the import cycle.
- `api/trexio_gen.py` = **GENERATED** surface (`tools/gen_trexio_py.py`), 862 `has_/read_/write_/delete_`;
  symlinked into the wheel as `trexio/trexio_gen.py`.
- The 2 PROVENANCE exceptions are now: **Phase 3** = constants live in `_base.py` (core; match the
  installed lib); **Phase 4** = `write_basis_r_power` = a generator **OVERRIDES** behavior (client-compat,
  permanent), NOT a "patch to the vendored file."

## Edits

### `PROVENANCE.md`
1. Reframe the intro: the vendored files are `api/pytrexio/__init__.py`, `api/pytrexio/_version.py`,
   `third_party/trex.json`. **`api/trexio.py` is no longer "vendored verbatim"** — it is now the
   hand-written **core** (adopted once from `src/trexio.py`, then maintained), and **`api/trexio_gen.py`
   is generated** from `trex.json` + the installed `trexio.h` (see the Plan).
2. Rewrite the two exception paragraphs:
   - **Phase 3 (constants):** restate as a normal core fact — `_base.py` declares the back-end id
     values to match TREXIO 2.6.1 (TREX-CoE#340 renumber: `AUTO=2, MEMORY=3`). A release renumber →
     update `_base.py`. (Drop the "exception" framing.)
   - **Phase 4 (`write_basis_r_power`):** restate as a **client-compatibility behavior** — clients
     pass a 1-D float list for an int64 field; trexio-python normalizes it. Now emitted by the
     generator's `OVERRIDES` in `tools/gen_trexio_py.py` (reference: `Plan/api-trexio-generation/references/30`).
     Explicitly mark it **permanent, not a temp patch**.
3. Update the file table:
   | File | How it's kept current |
   |---|---|
   | `api/pytrexio/__init__.py`, `api/pytrexio/_version.py`, `third_party/trex.json` | **re-vendor** (the `cp` block) |
   | `api/trexio.py` (core) | hand-maintained (adopted from `src/trexio.py`) |
   | `api/trexio_gen.py` | **generated** (`tools/gen_trexio_py.py`) — do not hand-edit |
4. Keep the **re-vendor `cp` block** for the three genuinely-vendored files; **remove** the
   `cp $T/src/trexio.py api/trexio.py` line (the API is now core + generated, not a verbatim copy).
   Add: regenerate = `python tools/gen_trexio_py.py`.

### `docs/updating-with-trexio.md`
1. **Step 2 (re-vendor):** change "Re-vendor the API + data model" → "Re-vendor **core + data model**;
   regenerate the surface". Keep the `cp` for `api/pytrexio/*` + `trex.json`; for the API, note the
   core is hand-maintained (port the few changes from the new `src/trexio.py` core if any) and then
   `python tools/gen_trexio_py.py`.
2. **Step 3:** the `check_api_symbols.py --list` / `gen_binding.py` flow is unchanged; add
   `python tools/gen_trexio_py.py` right after `gen_binding.py` (both regenerate from the same inputs).
3. **"Files you will touch, by case" table:** add rows for `api/trexio_gen.py` (regenerate) and
   `api/trexio.py` (core, edit only if lifecycle/helpers changed); mark `api/trexio_gen.py` as
   `auto (generator)` for Case A/B/C.
4. **Pin discipline:** keep it, but clarify the Python side now regenerates (not re-vendors) the surface.

### `docs/package-layout.md`
1. The `api/` tree table: reclassify `api/trexio.py` (was **VENDORED → re-copy**) to **HAND-WRITTEN
   CORE (adopted)**; add a row `api/trexio_gen.py` = **GENERATED (regenerate, never hand-edit)**.
2. Add `api/trexio/_base.py` to the tree (symlink `api/trexio/_base.py`? — no, it's a real file `api/trexio/_base.py`
   inside the package dir; document it as shared base).
3. The "Generated files vs. hand-maintained" section I added earlier: the `api/trexio.py` row moves
   out of *VENDORED* into *HAND-WRITTEN core*, and `api/trexio_gen.py` joins *GENERATED* alongside
   `src/generated_bindings.cpp`.
4. Link to `Plan/api-trexio-generation/` for the how.

### `README.md`
- The **File discipline** block (Development section): change `api/trexio.py … **vendored** —
  re-copy` → "`api/trexio.py` (core) is hand-maintained / `api/trexio_gen.py` is **generated**
  (regenerate, never hand-edit)". Keep `third_party/trex.json` / `api/pytrexio/*` as **vendored — re-copy**.

## Gate
- All four files are internally consistent with `references/10-architecture.md` (core vs generated vs
  vendored), and no prose still says `api/trexio.py` is "vendored / re-copy" or that its surface is
  hand-edited on release.
- No broken relative links. `grep -n "re-copy\|VERB.*api/trexio.py" README.md docs/prob* 2>/dev/null`
  returns nothing claiming the surface is hand-maintained.

## DoD
A reader of `README.md` + `PROVENANCE.md` + `docs/package-layout.md` +
`docs/updating-with-trexio.md` gets one consistent picture: **core is hand-written, the surface is
generated, the low-level module is the nanobind drop-in, and a new release = re-vendor core+json,
regenerate (both generators), test.**
