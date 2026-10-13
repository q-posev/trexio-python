"""The Python API of the TREXIO library.

This package is a top-level wrapper of the SWIG-generated pytrexio module.
"""

# NOTE: the numpy/pytrexio imports, PYTREXIO_MAX_STR_LENGTH, the TREXIO_* codes, and the
#       Error class live in `_base` (shared with the generated surface) and are re-exported
#       below so `trexio.<name>` keeps working exactly as before.
from ._version import __version__
from ._base import *

def string_of_error(return_code: int) -> str:
    """Decode the TREXIO exit code.

    Argument is an integer return code that correspond to one of the TREXIO errors.
    Returns a string that contains description of TREXIO ~return_code~.
    """

    return pytr.trexio_string_of_error(return_code)

class File:
    """trexio.File class.

    General information about the TREXIO file.

    Parameters:

    filename: str
        Is a name of the full path to the TREXIO file.
    back_end: int
        One of the currently supported TREXIO back ends.
        For example, TREXIO_HDF5 (0) or TREXIO_TEXT (1).
    mode: str
        One of the currently supported TREXIO open modes.
        For example, 'r' or 'w'.
    state: int
        Active (excited or ground) state of the file.
        Default is 0.
    isOpen: bool
        Flag indicating whether the current object is still open for I/O
    pytrexio_s:
        A PyObject corresponding to SWIG proxy of the trexio_s struct in C.
        This argument is in fact a TREXIO file handle, which is required for
        communicating with the C back end.
    info: dict
        Dictionary of key-value pairs with additional information about the file.
    """


    def __init__(self, filename, mode='r', back_end=TREXIO_HDF5,
                 pytrexio_s=None, info=None):
        """TREXIO File class constructor."""
        self.filename = filename
        self.mode = mode
        self.state = 0

        self.isOpen = False
        self.exists = False
        if pytrexio_s is None:
            self.pytrexio_s = _open(filename, mode, back_end)
            self.isOpen = True
            self.exists = True
        else:
            self.pytrexio_s = pytrexio_s
            self.isOpen = None
            self.exists = None

        self.back_end = self.pytrexio_s.back_end
        self.info = info


    def __enter__(self):
        """Enter statement for with ... as ... handling."""
        return self


    def __exit__(self, *args):
        """Exit statement for with ... as ... handling."""
        if self.isOpen:
           self.close()


    def close(self):
        """Close a TREXIO File."""
        if self.isOpen:
            _close(self.pytrexio_s)
            self.isOpen = False
        else:
            raise Exception("TREXIO File object has not been opened.")


    def set_state(self, state):
        """Set the state of the TREXIO File."""
        if not isinstance(state, int):
            raise TypeError("state argument has to be int")

        rc = pytr.trexio_set_state(self.pytrexio_s, state)
        if rc != TREXIO_SUCCESS:
            raise Error(rc)

        self.state = state


    def get_state(self):
        """Get the state of the TREXIO File."""
        rc, state = pytr.trexio_get_state(self.pytrexio_s)
        if rc != TREXIO_SUCCESS:
            raise Error(rc)

        if state != self.state:
            raise Exception("Inconsistent state of the TREXIO file.")

        return self.state


    def flush(self):
        """Flush the data on disk."""
        rc = pytr.trexio_flush(self.pytrexio_s)
        if rc != TREXIO_SUCCESS:
            raise Error(rc)


    def inquire(self):
        """Inquire whether a TREXIO file exists."""
        self.exists = _inquire(self.filename)


    def __del__(self):
        """TREXIO File class destructor."""
        if self.isOpen:
            _close(self.pytrexio_s)
        elif self.isOpen is None:
            raise Exception("[WIP]: TREXIO file handle provided but what if the file is already closed?")
        else:
            pass

def _open(file_name: str, mode: str, back_end: int):
    """Create TREXIO file or open existing one.

    Parameters:

    file_name: str
        Name of the TREXIO file

    mode: str
        One of the currently supported ~open~ modes (e.g. 'w', 'r')

    back_end: int
        One of the currently supported TREXIO back ends (e.g. TREXIO_HDF5, TREXIO_TEXT)

    Return:
        SWIG object of type trexio_s.

    Examples:
    >>> from trexio import open as tr_open
    >>> trex_file = tr_open("example.h5", "w", TREXIO_HDF5)
    """

    # The new trexio_open function is capable of returning error code which SWIG can append to the output trexio_s file struct
    # However, if trexio_s* == NULL, then SWIG returns only an error code rc_open instead of a list [trexio_s, rc_open]
    # Thus, the following try/except sequence is needed
    try:
        return_obj = pytr.trexio_open(file_name, mode, back_end)
        assert return_obj is not None
        if isinstance(return_obj, int):
            raise Error(return_obj)
        else:
            rc_open = return_obj[1]
            # this is a sanity check in case the code evolves and SWIG issue is patched
            if rc_open == TREXIO_SUCCESS:
                trexio_file = return_obj[0]
                assert trexio_file is not None

            return trexio_file
    except Error:
        # the C library already told us what went wrong (e.g. that the requested
        # back end is disabled), so do not mask it behind TREXIO_FILE_ERROR
        raise
    except:
        raise Error(18) # 18 is an error code for encountering an invalid file

def _close(trexio_file):
    """Close TREXIO file.

    Parameter is a ~trexio_file~ object that has been created by a call to ~open~ function.
    """

    rc = pytr.trexio_close(trexio_file)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)

def flush(trexio_file):
    """Flush buffers into the TREXIO file.

    Parameter is a ~trexio_file~ object that has been created by a call to ~open~ function.
    """

    rc = pytr.trexio_flush(trexio_file.pytrexio_s)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)

def _inquire(file_name: str) -> bool:
    """Check whether ~file_name~ TREXIO file exists.
    """
    rc = pytr.trexio_inquire(trexio_file_name)
    if rc == TREXIO_SUCCESS:
        return True
    elif rc == TREXIO_FAILURE:
        return False
    else:
        raise Error(rc)

def _cp(source: str, destination: str):
    """Copies a TREXIO file

    Parameters:

    source: str
        Name of the source file

    destination: str
        Name of the destination file

    Examples:
    >>> from trexio import cp as tr_cp
    >>> tr_cp("example.h5", "new.h5")
    """

    from shutil import copytree, copyfile

    f = File(filename=source, mode='r', back_end=TREXIO_AUTO)
    if f.back_end == TREXIO_TEXT:
      copytree(source, destination)
    elif f.back_end == TREXIO_HDF5:
      copyfile(source, destination)

def info():
    """Print the info about the installed TREXIO library."""

    rc = pytr.trexio_info()
    if rc != TREXIO_SUCCESS:
        raise Error(rc)

def to_bitfield_list(n_int: int, orbitals: list) -> list:
    """Convert a list of occupied orbitals into a bitfield determinant.

    Input:
        ~orbitals~ - list of occupied orbital indices fields (integers)
        ~n_int~ - number of bitfields per determinant of a given spin

    Returns:
        ~bitfield_list~: list

    Raises:
        - Exception from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Exception from some other error (e.g. RuntimeError).
    """


    rc, bitfield_list = pytr.trexio_to_bitfield_list(orbitals, n_int)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
    if len(bitfield_list) != n_int:
        raise Exception("Inconsistent size of the bitfield_list.")

    return bitfield_list

def to_orbital_list(n_int: int, determinant: list) -> list:
    """Convert a given determinant into a list of occupied orbitals.

    Input:
        ~determinant~ - list of bit fields (integers)
        ~n_int~ - number of bit fields per determinant of a given spin

    Returns:
        ~orbital_list~: list

    Raises:
        - Exception from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Exception from some other error (e.g. RuntimeError).
    """

    # max possible size of the orbital list per spin component (upper limit on the number of MOs)
    size_max = n_int * 64

    rc, orbital_list, occ_num = pytr.trexio_safe_to_orbital_list(n_int, determinant, size_max)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
    if len(orbital_list) < occ_num:
        raise Exception("Inconsistent size of the orbital_list.")

    return orbital_list[0:occ_num]

def to_orbital_list_up_dn(n_int: int, determinant: list) -> tuple:
    """Convert a given determinant into two lists of occupied orbitals.

    Input:
        ~determinant~ - list of bit fields (integers)
        ~n_int~ - number of bit fields per determinant of a given spin

    Returns:
        result: tuple with the following items:
          ~orbital_list_up~: list of orbitals occupied by up-spin electrons
          ~orbital_list_dn~: list of orbitals occupied by down-spin electrons

    Raises:
        - Exception from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Exception from some other error (e.g. RuntimeError).
    """

    # max possible size of the orbital list per spin component (upper limit on the number of MOs)
    size_max = n_int * 64

    rc, orbital_list_up, orbital_list_dn, occ_num_up, occ_num_dn = pytr.trexio_safe_to_orbital_list_up_dn(n_int, determinant, size_max, size_max)
    if rc != TREXIO_SUCCESS:
        raise Error(rc)
    if len(orbital_list_up) < occ_num_up:
        raise Exception("Inconsistent size of the orbital_list for up-spin electrons.")
    if len(orbital_list_dn) < occ_num_dn:
        raise Exception("Inconsistent size of the orbital_list for down-spin electrons.")

    return (orbital_list_up[0:occ_num_up], orbital_list_dn[0:occ_num_dn])

def convert_nao_radius(r: float, grid_r) -> float:
  """Converts the radius r as a distance from a nucleus to the shell
  s logarithmic grid.

  Input:
      ~r~ - the radius to be converted
      ~grid_r~ - The radial grid of the shell. Note that this is only the
                 grid of the shell of interest, not the array of all shells.

      Returns:
        Float that gives the radius in the shell's logarithmic units

      Raises:
        - Exception from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Exception from some other error (e.g. RuntimeError).

  """

  rc, r_log = pytr.trexio_convert_nao_radius_py(r, grid_r)

  if rc != TREXIO_SUCCESS:
    raise Error(rc)

  return r_log

def evaluate_nao_radial(shell_index, r, grid_start, grid_size, grid_r, interpolator, normalization) -> float:
  """Evaluates the radial function of a given NAO shell at a distance from its center.

  Input:
      ~shell_index~ - index of the shell of interest
      ~r~ - distance from the shell center
      ~grid_start~ - array of starting points of the individual splines
      ~grid_size~ - array of number of data points per spline
      ~grid_r~ - The radial grid of the shell. Note that this is only the
                 grid of the shell of interest, not the array of all shells.
      ~interpolator~ - Interpolator of the spline. It is assumed to contain a cubic spline.
                       An interpolator for a kinetic energy spline can also be passed.
      ~normalization~ - array of radial function normalization constants.

      Returns:
        Value of the spline at the given radius

      Raises:
        - Error from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Error from some other error (e.g. RuntimeError).

  """
  rc, amplitude = pytr.trexio_evaluate_nao_radial_py(shell_index, r, grid_start, grid_size, grid_r, interpolator.flatten(), normalization)

  if rc != TREXIO_SUCCESS:
    raise Error(rc)

  return amplitude

def evaluate_nao_radial_all(nucleus_index, nucleus_coords, grid_start,
  grid_size, grid_r, interpolator, normalization, r) -> float:
  """Evaluates the radial functions of all NAO shells at a given position in space.

  Input:
      ~nucleus_index~ - array giving the centers of the NAO
      ~nucleus_coords~ - array giving the coordinates of the NAO centers
      ~grid_start~ - array of starting points of the individual splines
      ~grid_size~ - array of number of data points per spline
      ~grid_r~ - The radial grid of the shell. Note that this is only the
                 grid of the shell of interest, not the array of all shells.
      ~interpolator~ - Interpolator of the spline. It is assumed to contain a cubic spline.
                       An interpolator for a kinetic energy spline can also be passed.
      ~normalization~ - array of radial function normalization constants.
      ~r~ - the position in space at which the functions are evaluated

      Returns:
        Array of spline values at ~r~

      Raises:
        - Error if ~r~ is not three dimensional
        - Error from AssertionError if TREXIO return code ~rc~ is different from TREXIO_SUCCESS and prints the error message using trexio_string_of_error.
        - Error from some other error (e.g. RuntimeError).

  """
  if len(r) != 3:
    raise Error(TREXIO_INVALID_ARG7)
  shell_cnt = len(nucleus_index)
  rc, amplitudes = pytr.trexio_evaluate_nao_radial_all_py(shell_cnt, \
    nucleus_index, nucleus_coords.flatten(), grid_start, grid_size, grid_r, \
    interpolator.flatten(), normalization, r[0], r[1], r[2], shell_cnt)

  if rc != TREXIO_SUCCESS:
    raise Error(rc)

  return amplitudes

from .trexio_gen import *
