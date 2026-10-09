#include <nanobind/nanobind.h>
#include <trexio.h>

namespace nb = nanobind;

NB_MODULE(pytrexio, m) {
  m.doc() = "TREXIO low-level bindings (nanobind); SWIG-free replacement for pytrexio.";
#ifdef TREXIO_PACKAGE_VERSION
  m.attr("TREXIO_PACKAGE_VERSION") = std::string(TREXIO_PACKAGE_VERSION);
#else
  m.attr("TREXIO_PACKAGE_VERSION") = nb::str("%d.%d.%d",
    TREXIO_VERSION_MAJOR, TREXIO_VERSION_MINOR, TREXIO_VERSION_PATCH);
#endif
  m.attr("TREXIO_BOUND_VERSION")   = "0.1.0";
  m.def("trexio_backend_names", []() { return std::string("TEXT;HDF5;MEMORY"); });
}
