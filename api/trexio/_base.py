"""Shared base for the `trexio` package (core + generated surface).

BOTH the hand-written core (api/trexio.py) and the generated surface
(api/trexio_gen.py) import from here. It holds the numpy / pytrexio imports,
PYTREXIO_MAX_STR_LENGTH, the TREXIO_* exit-code and back-end constants, and the
`Error` exception class, so the two modules share those names without any import
cycle. This module imports ONLY `numpy` and `pytrexio`.
"""

try:
    import numpy as np
except ImportError:
    raise Exception("NumPy cannot be imported.")

try:
    from . import pytrexio as pytr
except ImportError:
    raise Exception("Could not import the pytrexio extension module.")

# define max length of a string to be read, required for the low-level C routines
PYTREXIO_MAX_STR_LENGTH = 2048

# define TREXIO exit codes
TREXIO_FAILURE                 = -1
TREXIO_SUCCESS                 = 0
TREXIO_INVALID_ARG_1           = 1
TREXIO_INVALID_ARG_2           = 2
TREXIO_INVALID_ARG_3           = 3
TREXIO_INVALID_ARG_4           = 4
TREXIO_INVALID_ARG_5           = 5
TREXIO_END                     = 6
TREXIO_READONLY                = 7
TREXIO_ERRNO                   = 8
TREXIO_INVALID_ID              = 9
TREXIO_ALLOCATION_FAILED       = 10
TREXIO_HAS_NOT                 = 11
TREXIO_INVALID_NUM             = 12
TREXIO_ATTR_ALREADY_EXISTS     = 13
TREXIO_DSET_ALREADY_EXISTS     = 14
TREXIO_OPEN_ERROR              = 15
TREXIO_LOCK_ERROR              = 16
TREXIO_UNLOCK_ERROR            = 17
TREXIO_FILE_ERROR              = 18
TREXIO_GROUP_READ_ERROR        = 19
TREXIO_GROUP_WRITE_ERROR       = 20
TREXIO_ELEM_READ_ERROR         = 21
TREXIO_ELEM_WRITE_ERROR        = 22
TREXIO_UNSAFE_ARRAY_DIM        = 23
TREXIO_ATTR_MISSING            = 24
TREXIO_DSET_MISSING            = 25
TREXIO_BACK_END_MISSING        = 26
TREXIO_INVALID_ARG_6           = 27
TREXIO_INVALID_ARG_7           = 28
TREXIO_INVALID_ARG_8           = 29
TREXIO_INVALID_STR_LEN         = 30
TREXIO_INT_SIZE_OVERFLOW       = 31
TREXIO_SAFE_MODE               = 32
TREXIO_INVALID_ELECTRON_NUM    = 33
TREXIO_INVALID_DETERMINANT_NUM = 34
TREXIO_INVALID_STATE           = 35
TREXIO_VERSION_PARSING_ISSUE   = 36
TREXIO_PHASE_CHANGE            = 37
TREXIO_INVALID_MO_INDEX        = 38
TREXIO_INVALID_ARG_9           = 39
TREXIO_INVALID_ARG_10          = 40
TREXIO_INVALID_ARG_11          = 41
TREXIO_INVALID_ARG_12          = 42
TREXIO_INVALID_ARG_13          = 43
TREXIO_INVALID_ARG_14          = 44
TREXIO_CORRUPTION_ATTEMPT      = 45
TREXIO_AMBIGUOUS_CARTESIAN     = 46

class Error(Exception):
    """Base class for TREXIO errors.

    Attributes:
       error: int -- exit code returned by the call to TREXIO library;
       message: str -- decoded string corresponding to trexio_exit_code.

    """

    def __init__(self, trexio_return_code):
        self.error = trexio_return_code
        # NOTE: Error lives in `_base` (shared with the generated surface) while the
        # `string_of_error` wrapper lives in core, so call the C binding directly here.
        # Behavior is identical to the original (string_of_error is just that same call).
        self.message = pytr.trexio_string_of_error(trexio_return_code)
        super().__init__(self.message)

# define TREXIO back ends
# NOTE: renumbered to match the installed libtrexio 2.6.1 (TREX-CoE#340,
# post-release master 0102739): AUTO moved to 2, MEMORY to 3.
TREXIO_HDF5 = 0
TREXIO_TEXT = 1
TREXIO_AUTO = 2
TREXIO_MEMORY = 3
TREXIO_INVALID_BACK_END = 4
