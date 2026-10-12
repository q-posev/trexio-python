Phase 4 gate summaries (2026-10-12)

Baseline A (SWIG, official tree build of TREXIO 2.6.1+0102739, "same version" as B):
  Built with:  mamba install -c conda-forge swig   (SWIG 4.5.1)
               cd <trexio tree> && make python-install SWIG=$HOME/miniforge3/bin/swig
  Installed into: /tmp/opencode/trexpA   (wheel: trexio-2.6.1-cp312-cp312-linux_aarch64.whl)
  A trexio:  site-packages/trexio/__init__.py          (official API, 0102739)
  A low:     site-packages/trexio/_pytrexio.cpython-312-aarch64-linux-gnu.so  (SWIG 4.5.1)
  A constants: HDF5=0 TEXT=1 AUTO=2 MEMORY=3 INVALID_BACK_END=4  (identical to B)

Candidate B (nanobind, this repository):
  Installed into: /tmp/opencode/trexp2   (pip install . from trexio-python @ ab8b3a7)
  B trexio:  site-packages/trexio/__init__.py
  B low:     site-packages/trexio/pytrexio.cpython-312-aarch64-linux-gnu.so   (nanobind 3.1.0)

Suite results:
  B (pytest tests/ --all, full trexio-python suite):  88 passed in 0.29s  (0 failed)
  A (pytest test_api.py test_memory.py test_pytrexio.py --all, trexio/python/test):
                                                   51 passed in 0.24s  (0 failed)

Parity outputs:
  parity_api.py -> parity_A.json vs parity_B.json : diff empty  (931 public names + all constants)
  parity_run.py -> run_A.txt   vs run_B.txt       : diff empty  (text/hdf5/memory IO, bitfield,
                                                      up_dn, error path, string_of_error)
Zero-SWIG in B:
  trexio pkg files : __init__.py, _version.py, pytrexio.cpython-312-aarch64-linux-gnu.so
  SWIG symbols in the extension: 0   | nanobind symbols: 13
  no pytrexio.py wrapper anywhere in site-packages; no SWIG runtime libs in $HOME/.local/lib
