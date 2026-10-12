"""Acceptance tests: the Python examples from ``trexio/docs/examples.org``.

These mirror the *documented* Python usage, verbatim in spirit:

  * "Writing nuclear coordinates"  -- a water molecule is written with
    ``trexio.File`` / ``trexio.write_nucleus_num`` / ``trexio.write_nucleus_coord``
    and then read back to confirm the round trip.
  * "Accessing sparse quantities (integrals)" -- the ``print_energy`` path:
    write nucleus_repulsion + 1e/2e quantities, read them back, and compute
    the energy exactly as the example does.

Each test is *gated on the low-level names it needs*.  The low-level
``trexio.pytrexio`` module is a nanobind extension (Layout A); in the Phase-1
stub those names are absent, so the gated tests skip (documenting the
acceptance target).  They start running -- and must pass -- as the binding
lands: Phase 2 (lifecycle / error decoding) and Phase 3 (per-variable
read/write).  The API-layer test always runs.

Run:  python -m pytest tests/test_examples.py -v  [--all]
"""
import os
import shutil

import numpy as np
import pytest

import trexio
from trexio import File, Error


# ------------------------------------------------------------ helpers ----
def _pytr():
    """The low-level nanobind module (Layout A: ``trexio.pytrexio``)."""
    return trexio.pytrexio


def skipif_missing(*names):
    """Skip a test until every required low-level name is bound.

    ``names`` are the ``pytr.trexio_*`` symbols the test exercises.  This is
    the "gated on the binding" mechanism: skipped in the Phase-1 stub, run
    once Phases 2/3 provide the symbols.
    """
    m = _pytr()
    missing = [n for n in names if not hasattr(m, n)]
    return pytest.mark.skipif(
        bool(missing),
        reason=("low-level binding not implemented yet (missing: {}); "
                "provided by Phases 2/3").format(", ".join(missing)),
    )


BACKEND = {
    "text": trexio.TREXIO_TEXT,
    "hdf5": trexio.TREXIO_HDF5,
}


def _suffix(backend):
    return ".h5" if backend == "hdf5" else ""


def _cleanup(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


BUFSIZE = 100000


# water molecule, xyz coordinates in atomic units (verbatim: docs/examples.org)
WATER = [
    [0. , 0., -0.24962655],
    [0. , 2.70519714, 1.85136466],
    [0. , -2.70519714, 1.85136466],
]


# -------------------------------------------------------- API layer ----
def test_api_surface_for_examples():
    """The documented surface the examples rely on (no binding required).

    Runs in every phase: it checks the *pure-Python* API layer that the
    examples call, which exists from the scaffold onward.
    """
    assert isinstance(File, type)
    assert hasattr(File, "__enter__") and hasattr(File, "__exit__")
    # back-end constants the examples reference
    assert trexio.TREXIO_HDF5 == 0
    assert trexio.TREXIO_TEXT == 1
    # module-level free functions with the exact calling convention
    for name in ("write_nucleus_num", "write_nucleus_coord",
                 "read_nucleus_num", "read_nucleus_coord",
                 "write_mo_1e_int_core_hamiltonian", "read_mo_1e_int_core_hamiltonian",
                 "write_rdm_1e", "read_rdm_1e",
                 "write_mo_2e_int_eri", "read_mo_2e_int_eri",
                 "write_rdm_2e", "read_rdm_2e",
                 "read_nucleus_repulsion"):
        assert callable(getattr(trexio, name)), name
    assert issubclass(Error, Exception)


# ------------------------------------- Example 1: water write/read ----
@skipif_missing(
    "trexio_open", "trexio_close", "trexio_get_back_end", "trexio_string_of_error",
    "trexio_write_nucleus_num", "trexio_write_safe_nucleus_coord_64",
    "trexio_read_nucleus_num", "trexio_read_safe_nucleus_coord_64",
)
def test_water_write_readback(tmp_path, backend):
    """docs/examples.org *Writing nuclear coordinates*: write water, read it back."""
    name = tmp_path / ("water" + _suffix(backend))
    _cleanup(str(name))
    coord = WATER

    # --- the documented write path (with ... as ...) ---
    with File(str(name), 'w', back_end=BACKEND[backend]) as f:
        assert f.back_end == BACKEND[backend]
        trexio.write_nucleus_num(f, len(coord))
        trexio.write_nucleus_coord(f, coord)

    # --- read back and verify the round trip ---
    g = File(str(name), 'r', back_end=trexio.TREXIO_AUTO)
    n = trexio.read_nucleus_num(g)
    assert n == len(coord)
    rt = np.asarray(trexio.read_nucleus_coord(g), dtype=np.float64).reshape(-1)
    assert rt.size == len(coord) * 3
    assert np.allclose(rt, np.asarray(coord, dtype=np.float64).reshape(-1), atol=1e-12)
    _cleanup(str(name))


# ---------------------------------- Example 2: energy path (sparse) ----
def _fill_eri(indices, values, n):
    """Fill W from (i,j,k,l,value) sparse ERI entries, as the example does."""
    W = np.zeros((n, n, n, n), dtype=np.float64)
    idx = np.asarray(indices, dtype=np.int64).reshape(-1, 4)
    val = np.asarray(values, dtype=np.float64).reshape(-1)
    for (i, j, k, l), v in zip(idx, val):
        for a, b, c, d in ((i, j, k, l), (k, j, i, l), (i, l, k, j), (k, l, i, j),
                          (j, i, l, k), (j, k, l, i), (l, i, j, k), (l, k, j, i)):
            W[a, b, c, d] = v
    return W


def _fill_rdm2e(indices, values, n):
    """Fill G from (i,j,k,l,value) sparse 2-RDM entries, as the example does."""
    G = np.zeros((n, n, n, n), dtype=np.float64)
    idx = np.asarray(indices, dtype=np.int64).reshape(-1, 4)
    val = np.asarray(values, dtype=np.float64).reshape(-1)
    for (i, j, k, l), v in zip(idx, val):
        G[i, j, k, l] = v
    return G


def _energy(E_nn, D, h0, G, W, n):
    """Energy, computed exactly as docs/examples.org does."""
    G = np.asarray(G, dtype=np.float64).reshape(n * n, n * n)
    W = np.asarray(W, dtype=np.float64).reshape(n * n, n * n)
    E = E_nn
    E += 0.5 * sum([np.dot(G[:, l], W[:, l]) for l in range(n * n)])
    E += sum([np.dot(D[:, l], h0[:, l]) for l in range(n)])
    return E


def _read_sparse(func, f):
    """Accumulate a sparse (indices[m,4], values[m]) read until EOF."""
    offset = 0
    idxs, vals = [], []
    for _ in range(1000):  # hard safety cap
        idx, val, icount, feof = func(f, offset, BUFSIZE)
        if icount is None or icount <= 0:
            break
        idxs.append(np.asarray(idx, dtype=np.int64).reshape(-1, 4))
        vals.append(np.asarray(val, dtype=np.float64).reshape(-1))
        offset += int(icount)
        if feof:
            break
    if not idxs:
        return np.zeros((0, 4), dtype=np.int64), np.zeros(0, dtype=np.float64)
    return np.vstack(idxs), np.concatenate(vals)


_ENERGY_NAMES = [
    "trexio_open", "trexio_close", "trexio_get_back_end", "trexio_string_of_error",
    "trexio_write_mo_num", "trexio_read_mo_num",
    "trexio_write_nucleus_repulsion", "trexio_read_nucleus_repulsion",
    "trexio_has_nucleus_repulsion",
    "trexio_write_safe_mo_1e_int_core_hamiltonian_64",
    "trexio_read_safe_mo_1e_int_core_hamiltonian_64",
    "trexio_has_mo_1e_int_core_hamiltonian",
    "trexio_write_safe_rdm_1e_64", "trexio_read_safe_rdm_1e_64", "trexio_has_rdm_1e",
    "trexio_write_safe_mo_2e_int_eri", "trexio_read_safe_mo_2e_int_eri",
    "trexio_read_mo_2e_int_eri_size", "trexio_has_mo_2e_int_eri",
    "trexio_write_safe_rdm_2e", "trexio_read_safe_rdm_2e",
    "trexio_read_rdm_2e_size", "trexio_has_rdm_2e",
]


@skipif_missing(*_ENERGY_NAMES)
def test_energy_path_roundtrip(tmp_path, backend):
    """docs/examples.org *Accessing sparse quantities*: write + read back an energy system.

    Writes a tiny (n=2) system: nucleus_repulsion, 1e core Hamiltonian, 1e RDM,
    a few ERIs and 2-RDM entries; reads everything back and verifies
    (a) the dense quantities round-trip, (b) each sparse entry survives the
    round trip, and (c) the energy computed from the read-back data is finite
    and equals the energy of what was written.
    """
    n = 2
    name = tmp_path / ("energy" + _suffix(backend))
    _cleanup(str(name))

    E_nn = 1.25
    h0 = np.array([[0.5, 0.1], [0.1, -0.5]], dtype=np.float64)
    D = np.array([[1.0, 0.2], [0.2, 1.1]], dtype=np.float64)
    # sparse ERI entries (i, j, k, l, value), 0-based
    eri = [
        [0, 0, 0, 0, 0.5],
        [0, 0, 1, 1, 0.3],
        [0, 1, 1, 1, 0.2],
    ]
    # sparse 2-RDM entries (i, j, k, l, value), 0-based
    rdm = [
        [0, 0, 0, 0, 0.4],
        [0, 1, 1, 0, 0.1],
        [1, 1, 1, 1, 0.3],
    ]
    eri_idx = np.array([r[:4] for r in eri], dtype=np.int32)
    eri_val = np.array([r[4] for r in eri], dtype=np.float64)
    rdm_idx = np.array([r[:4] for r in rdm], dtype=np.int32)
    rdm_val = np.array([r[4] for r in rdm], dtype=np.float64)

    # --- write (mo_num first: the 1e reads reshape using it) ---
    f = File(str(name), 'w', back_end=BACKEND[backend])
    try:
        trexio.write_mo_num(f, n)
        trexio.write_nucleus_repulsion(f, E_nn)
        trexio.write_mo_1e_int_core_hamiltonian(f, h0)
        trexio.write_rdm_1e(f, D)
        trexio.write_mo_2e_int_eri(f, 0, len(eri_val), eri_idx, eri_val)
        trexio.write_rdm_2e(f, 0, len(rdm_val), rdm_idx, rdm_val)
    finally:
        if getattr(f, "isOpen", False):
            f.close()

    # --- read back ---
    g = File(str(name), 'r', back_end=trexio.TREXIO_AUTO)
    try:
        assert trexio.has_nucleus_repulsion(g)
        E_nn_r = trexio.read_nucleus_repulsion(g)

        assert trexio.has_mo_1e_int_core_hamiltonian(g)
        h0_r = np.asarray(trexio.read_mo_1e_int_core_hamiltonian(g), dtype=np.float64).reshape(n, n)

        assert trexio.has_rdm_1e(g)
        D_r = np.asarray(trexio.read_rdm_1e(g), dtype=np.float64).reshape(n, n)

        assert trexio.has_mo_2e_int_eri(g)
        eri_idx_r, eri_val_r = _read_sparse(lambda h, o, b: trexio.read_mo_2e_int_eri(h, o, b), g)

        assert trexio.has_rdm_2e(g)
        rdm_idx_r, rdm_val_r = _read_sparse(lambda h, o, b: trexio.read_rdm_2e(h, o, b), g)
    finally:
        if getattr(g, "isOpen", False):
            g.close()
    _cleanup(str(name))

    # (a) dense round trips
    assert pytest.approx(E_nn, abs=1e-12) == E_nn_r
    assert np.allclose(h0_r, h0, atol=1e-12)
    assert np.allclose(D_r, D, atol=1e-12)

    # (b) each sparse entry survives the round trip
    W_r = _fill_eri(eri_idx_r, eri_val_r, n)
    for i, j, k, l, v in eri:
        assert W_r[i, j, k, l] == pytest.approx(v, abs=1e-12)
    G_r = _fill_rdm2e(rdm_idx_r, rdm_val_r, n)
    for i, j, k, l, v in rdm:
        assert G_r[i, j, k, l] == pytest.approx(v, abs=1e-12)

    # (c) energy from the read-back data is finite and self-consistent
    W = _fill_eri(eri_idx, eri_val, n)
    G = _fill_rdm2e(rdm_idx, rdm_val, n)
    E_written = _energy(E_nn, D, h0, G, W, n)
    E_read = _energy(E_nn_r, D_r, h0_r, G_r, W_r, n)
    assert np.isfinite(E_read)
    assert E_read == pytest.approx(E_written, abs=1e-9)


# ------------------------------------------------------- error path ----
@skipif_missing("trexio_open", "trexio_string_of_error")
def test_error_message_is_string(tmp_path):
    """A failed open raises trexio.Error whose message is a decoded string.

    This pins the ABI the examples depend on: ``trexio_string_of_error`` must
    return a Python ``str`` (``Error.__init__`` puts it in ``str(exc)``).
    """
    bad = tmp_path / "no" / "such" / "dir" / ("x" + _suffix("hdf5"))
    with pytest.raises(Error) as ei:
        File(str(bad), "w", trexio.TREXIO_HDF5)
    msg = ei.value.message
    assert isinstance(msg, str) and len(msg) > 0
    assert isinstance(str(ei.value), str) and len(str(ei.value)) > 0
