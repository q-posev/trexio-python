// Phase 1 stub: proves the scikit-build-core + CMake + nanobind + libtrexio
// pipeline end-to-end.  It deliberately does NOT #include <trexio.h>; the
// TREXIO version is injected by CMake as a compile definition (TREXIO_PKG_VERSION).
// The real 877-function surface is added in Phases 2/3 (then <trexio.h> is needed).
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <string>

namespace nb = nanobind;

// Installed layout (user-approved "Option A", package form):
//   site-packages/trexio/__init__.py   <- api/trexio.py   (does "from . import pytrexio as pytr")
//   site-packages/trexio/pytrexio.*.so <- this module      (importable as trexio.pytrexio)
//   site-packages/trexio/_version.py   <- version module
NB_MODULE(pytrexio, m) {
  m.doc() = "TREXIO low-level bindings (nanobind); SWIG-free replacement for SWIG pytrexio.";
#ifdef TREXIO_PKG_VERSION
  m.attr("TREXIO_PACKAGE_VERSION") = std::string(TREXIO_PKG_VERSION);  // of the linked libtrexio
#else
  m.attr("TREXIO_PACKAGE_VERSION") = std::string("unknown");
#endif
  m.attr("TREXIO_BOUND_VERSION") = "0.1.0";  // of this binding
  m.def("trexio_backend_names", []() { return std::string("TEXT;HDF5;MEMORY"); });
}
