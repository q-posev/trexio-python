# 20 — Shapes, C-symbol naming, and the exact Python bodies

This is the reference the generator (`tools/gen_trexio_py.py`) emits from. **Everything
below is taken verbatim from the current `api/trexio.py`.** Identities confirmed:

- low-level module alias: **`pytr`**  (import: `from . import pytrexio as pytr` → in the
  generated file it comes from `_base`, so write `from ._base import pytr`).
- file handle attr: **`trexio_file.pytrexio_s`**
- success/failure codes: **`TREXIO_SUCCESS`** (0), **`TREXIO_FAILURE`** (-1),
  **`TREXIO_UNSAFE_ARRAY_DIM`** (23) — all from `_base`.
- string-length constant: **`PYTREXIO_MAX_STR_LENGTH`** (2048) — from `_base`.
- string delimiter: **`pytr.TREXIO_DELIM`** (low-level constant, already in the required set).

> `{name}` = the Python name minus the verb (e.g. for `read_nucleus_charge`, `{name} = nucleus_charge`).
> `{dims}` = the variable's dimension list from `third_party/trex.json` (see the rule below).

## Naming transform (Python name → C symbol)  ← the crux

| Family (from `gen_binding.classify`) | Python fn | C symbol called |
|---|---|---|
| HAS | `has_{name}` | `trexio_has_{name}` |
| SCALAR_R | `read_{name}` | `trexio_read_{name}` |
| SCALAR_W | `write_{name}` | `trexio_write_{name}` |
| SAFE_ARRAY_R | `read_{name}` | `trexio_read_safe_{name}_64` |
| SAFE_ARRAY_W | `write_{name}` | `trexio_write_safe_{name}_64` |
| STRARR_R | `read_{name}` | `trexio_read_{name}_low` |
| STRARR_W | `write_{name}` | `trexio_write_{name}` |
| SPARSE_R | `read_{name}` | `trexio_read_safe_{name}`  (no `_64`) |
| SPARSE_W | `write_{name}` | `trexio_write_safe_{name}`  (no `_64`) |
| DELETE | `delete_{group}` | `trexio_delete_{group}` |

**Do NOT invent the C symbol from the JSON name alone** — the `safe_` infix and the `_64` /
`_low` suffixes are ABI conventions. The generator must get the exact symbol from
`required_api.names` (the proven set) and only pick the *family* (hence the right template)
from the classification. `required_api.names` is the source of truth for "which symbol"; the
family/JSON tells "which template + dims".

## ABI contract (what the C++ binding returns; how the wrapper unpacks)

| Family | `pytr.<sym>(…)` returns | rc check |
|---|---|---|
| HAS | `int` (0 / -1 / 11) | `== TREXIO_FAILURE` → raise |
| SCALAR_R | `[rc, value]` | `[0] != TREXIO_SUCCESS` → raise |
| SAFE_ARRAY_R | `[rc, array]` | `[0] != SUCCESS` → raise |
| STRARR_R | `[rc, "a\1b\1…"]` | `[0] != SUCCESS` → raise |
| SPARSE_R | `[rc, n, indices, values]` | `[0] != SUCCESS` → raise |
| SCALAR_W | `int rc` | `!= SUCCESS` → raise |
| SAFE_ARRAY_W | `int rc` | `!= SUCCESS` → raise |
| STRARR_W | `int rc` | `!= SUCCESS` → raise |
| SPARSE_W | `int rc` | `!= SUCCESS` → raise |
| DELETE | `int rc` | `!= 0` → raise |

## The `{dims}` rule (from `third_party/trex.json`)

`trex.json` stores each variable as `data[group][var] = [kind, dims]`, `dims = ["<g>.<v>"|"<n>", …]`.
For each token in `dims`:

- token looks like **`<group>.<var>`** (has a dot) → a *local* named `<group>_<var>`:
  emit `    <group>_<var> = read_<group>_<var>(trexio_file)` once, and use `<group>_<var>`
  in `dims_list`.
- token is a **bare integer** (e.g. `"3"`) → use the literal `3` directly in `dims_list`.

Then `dims_list = [ …tokens… ]` and the loop `for i in range(<len(dims)>):`.

```
nucleus_charge ["float", ["nucleus.num"]]        -> nucleus_num=read_nucleus_num(…);  dims_list=[nucleus_num];      range(1)
mo_coefficient ["float", ["mo.num","ao.num"]]    -> mo_num=read_mo_num(…), ao_num=read_ao_num(…); dims_list=[mo_num, ao_num]; range(2)
nucleus_coord  ["float", ["nucleus.num","3"]]    -> nucleus_num=read_nucleus_num(…);  dims_list=[nucleus_num, 3];   range(2)
```

> Every `<group>.<var>` dim is a `*_num` scalar, which always has a `read_<group>_<var>`, so the
> generator can resolve it; if it can't, **halt with a `TODO:`** (do not guess).

## The exact bodies (copy-paste; fill `{name}` / `{dims}` / `{npw}`)

`{npw}` = `np.float64` for float-kind arrays, `np.int64` for int/index/dim-kind arrays.

### HAS
```python
def has_{name}(trexio_file) -> bool:
    """{docstring}"""

    rc = pytr.trexio_has_{name}(trexio_file.pytrexio_s)
    if rc == TREXIO_FAILURE:
        raise Error(rc)

    return rc == TREXIO_SUCCESS
```
### SCALAR_R  (`{ret}` = `int` or `float` from the kind)
```python
def read_{name}(trexio_file) -> {ret}:
    """{docstring}"""

    rc, num_r = pytr.trexio_read_{name}(trexio_file.pytrexio_s)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)

    return num_r
```
### SCALAR_W
```python
def write_{name}(trexio_file, num_w: {ret}) -> None:
    """{docstring}"""

    rc = pytr.trexio_write_{name}(trexio_file.pytrexio_s, num_w)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
```
### SAFE_ARRAY_R
```python
def read_{name}(trexio_file, dim = None, doReshape = None, dtype = None):
    """{docstring}"""

    if doReshape is None:
        doReshape = True

    # if dim is not specified, read dimensions from the TREXIO file
    dims_list = None
    if doReshape:
        {DIM_DECLS}          # <- e.g.  nucleus_num = read_nucleus_num(trexio_file)

        dims_list = [{DIMS_LIST}]      # <- e.g. [nucleus_num]  /  [mo_num, ao_num]
        dim_real  = 1
        for i in range({NDIM}):
            dim_real *= dims_list[i]

    if dim:
        if dim_real != dim:
            raise Error(TREXIO_UNSAFE_ARRAY_DIM)
    else:
        dim = dim_real

    shape = tuple(dims_list)
    if shape is None and doReshape:
        raise ValueError("Reshaping failure: shape is None.")


    rc, dset_64 = pytr.trexio_read_safe_{name}_64(trexio_file.pytrexio_s, dim)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)


    isConverted = False
    dset_converted = None
    if dtype is not None:
        try:
            assert isinstance(dtype, type)
        except AssertionError:
            raise TypeError("dtype argument has to be an instance of the type class (e.g. np.float32).")

        if not dtype==np.int64 or not dtype==np.float64:
            dset_converted = np.array(dset_64, dtype=dtype)
            isConverted = True

    if doReshape:
        if isConverted:
            dset_reshaped = np.reshape(dset_converted, shape, order='C')
        else:
            dset_reshaped = np.reshape(dset_64, shape, order='C')

    if isConverted:
        return dset_converted
    elif doReshape:
        return dset_reshaped
    else:
        return dset_64
```
### SAFE_ARRAY_W  (`{npw}` = np.float64 | np.int64)
```python
def write_{name}(trexio_file, dset_w) -> None:
    """{docstring}"""

    doConversion = False
    doFlatten = False
    if not isinstance(dset_w, (list, tuple)):
       if isinstance(dset_w, np.ndarray) and (not dset_w.dtype==np.int64 or not dset_w.dtype==np.float64):
           doConversion = True
       if len(dset_w.shape) > 1:
           doFlatten = True
           if doConversion:
               dset_64 = {npw}(dset_w).flatten()
           else:
               dset_flat = np.array(dset_w, dtype={npw}).flatten()
       else:
           if doConversion:
               dset_64 = {npw}(dset_w)
    else:
       try:
           doFlatten = True
           ncol = len(dset_w[0])
           dset_flat = np.array(dset_w, dtype={npw}).flatten()
       except TypeError:
           doFlatten = False
           pass

    if doConversion:
        rc = pytr.trexio_write_safe_{name}_64(trexio_file.pytrexio_s, dset_64)
    elif doFlatten:
        rc = pytr.trexio_write_safe_{name}_64(trexio_file.pytrexio_s, dset_flat)
    else:
        rc = pytr.trexio_write_safe_{name}_64(trexio_file.pytrexio_s, dset_w)

    if rc != TREXIO_SUCCESS:
        raise Error(rc)
```
### STRARR_R (string *list* read — 7 names; uses `read_{name}_num` + `_low`)
```python
def read_{name}(trexio_file, dim = None) -> list:
    """{docstring}"""

    {name}_num = read_{name}_num(trexio_file)

    dims_list = [{name}_num]
    dim_real  = 1
    for i in range(1):
        dim_real *= dims_list[i]

    if dim:
        if dim_real != dim:
            raise Error(TREXIO_UNSAFE_ARRAY_DIM)
    else:
        dim = dim_real

    rc, dset_1d_r = pytr.trexio_read_{name}_low(trexio_file.pytrexio_s, PYTREXIO_MAX_STR_LENGTH)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)


    dset_full = dset_1d_r.split(pytr.TREXIO_DELIM)
    dset_2d_r = [dset_full[i] for i in range(dim) if dset_full[i]]
    if not dset_2d_r:
        raise ValueError(f"Output of {read_{name}.__name__} function cannot be an empty list.")

    return dset_2d_r
```
### STRARR_W (string *list* write)
```python
def write_{name}(trexio_file, dset_w: list) -> None:
    """{docstring}"""

    max_str_length = len(max(dset_w, key=len)) + 1
    for s in dset_w:
        s.encode('ascii')

    rc = pytr.trexio_write_{name}(trexio_file.pytrexio_s, dset_w, max_str_length)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
```
### SPARSE_R / SPARSE_W  — complex shape; **copy the exemplar verbatim then generalize the name + symbol**
- SPARSE_R exemplar: `read_ao_2e_int_eri` @ 20464 (calls `pytr.trexio_read_safe_ao_2e_int_eri`,
  returns `[rc, n, indices, values]`; reshapes `indices`).
- SPARSE_W exemplar: `write_ao_2e_int_eri` @ 32600 (calls `pytr.trexio_write_safe_ao_2e_int_eri`
  with the `indices_32`/`values_64` conversion branches).
These have a 4-way conversion branch (int32/float64) — **do not hand-derive**, lift the body and
substitute the name/symbol.

### DELETE
```python
def delete_{group}(trexio_file) -> None:
    """{docstring}"""

    rc = pytr.trexio_delete_{group}(trexio_file.pytrexio_s)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
```

## Docstring family templates (D3: compact-but-full)

```
has_/read_  :  "<verb-capitalize> the {name} variable/array of <kind> in/from the TREXIO file."
write       :  "Write the {name} variable/array ... in the TREXIO file."
delete      :  "Delete the {group} group ... from the TREXIO file."
```
Each followed by `Parameters:` (trexio_file, + dim/dtype/doReshape for safe arrays, + dset_w for
writes), `Returns:` (type + 1-D/shape note from `{dims}`), `Raises:` (TREXIO.Error on non-success).
The **content is not the tested contract** — keep it terse and consistent; correctness is carried
by the body + symbol, not the prose.
