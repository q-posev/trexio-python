// core.cpp — TREXIO low-level core (nanobind). SWIG-free replacement for the
// pytrexio SWIG module. Phase 2: lifecycle / state / NAO / bitfield / deletes.
//
// ABI contract (Plan README "Canonical low-level ABI", Layout A):
//   * return containers are Python lists (nb::list);
//   * ordering: the C return value comes first, then output values in
//     argument order (e.g. read -> [rc, value]);
//   * trexio_open: a plain int rc on failure, else [trexio_s, rc];
//   * close / flush / state-setters / delete_* / get_int64 helpers: int rc;
//   * trexio_has_backend(_back_end): Python bool;
//   * trexio_string_of_error: str.
//
// The per-variable has/read/write surface (~850 of 878 required names) is
// added in Phase 3 as src/generated_bindings.cpp (tools/gen_binding.py from
// third_party/trex.json). Everything in this file is hand-written.
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <trexio.h>

#include <cstdint>
#include <string>
#include <type_traits>
#include <vector>

namespace nb = nanobind;

namespace {

// ------------------------------- handle -------------------------------------
// RAII wrapper around trexio_t*. nanobind invokes the C++ destructor of a
// bound type when the Python object is released / garbage-collected, so the
// still-open file is closed on GC -- dropping the handle can never leak.
// An explicit trexio_close() nulls the pointer first and becomes a no-op
// (mimics SWIG thisown; closes exactly once).
class TrexioHandle {
 public:
  explicit TrexioHandle(trexio_t* f) noexcept : ptr_(f) {}
  TrexioHandle(TrexioHandle&& o) noexcept : ptr_(o.ptr_) { o.ptr_ = nullptr; }
  TrexioHandle(const TrexioHandle&) = delete;
  TrexioHandle& operator=(const TrexioHandle&) = delete;
  ~TrexioHandle() { close(); }

  bool open() const noexcept { return ptr_ != nullptr; }
  trexio_t* raw() const noexcept { return ptr_; }

  // int by contract: 0 = closed successfully, -1 (TREXIO_FAILURE) = the
  // handle was already closed/invalid.
  int close() noexcept {
    if (!ptr_) return static_cast<int>(TREXIO_FAILURE);
    int rc = static_cast<int>(trexio_close(ptr_));
    ptr_ = nullptr;
    return rc;
  }

  int back_end() const {
    back_end_t be = TREXIO_INVALID_BACK_END;
    if (ptr_ && trexio_get_back_end(ptr_, &be) == TREXIO_SUCCESS)
      return static_cast<int>(be);
    return static_cast<int>(TREXIO_FAILURE);
  }

 private:
  trexio_t* ptr_ = nullptr;
};

// --------------------------- sequence helpers -------------------------------
// Convert an iterable of Python scalars (list, tuple, or 1-D numpy array)
// into a C vector of T. (Phase 3's generated bindings reuse the same idea.)
template <typename T>
std::vector<T> cast_vec(const nb::object& o) {
  std::vector<T> v;
  if (o) {
    for (const auto& x : o) {
      if constexpr (std::is_floating_point_v<T>)
        v.push_back(static_cast<T>(nb::cast<double>(x)));
      else
        v.push_back(static_cast<T>(nb::cast<std::int64_t>(x)));
    }
  }
  return v;
}

// Vector of T -> a fresh Python list (lists are the ABI container).
template <typename T>
nb::object vec_list(const std::vector<T>& v) {
  nb::list l;
  for (auto x : v) {
    if constexpr (std::is_floating_point_v<T>)
      l.append(nb::float_(x));
    else
      l.append(nb::int_(x));
  }
  return l;
}

}  // namespace

NB_MODULE(pytrexio, m) {
  m.doc() = "TREXIO low-level bindings (nanobind); SWIG-free replacement of "
            "the pytrexio SWIG module (Layout A: importable as trexio.pytrexio).";

  // ---------------------------- module-level -------------------------------
#ifdef TREXIO_PKG_VERSION
  m.attr("TREXIO_PACKAGE_VERSION") = std::string(TREXIO_PKG_VERSION);  // of the linked libtrexio
#else
  m.attr("TREXIO_PACKAGE_VERSION") = std::string("unknown");
#endif
  m.attr("TREXIO_BOUND_VERSION") = std::string("0.1.0");  // of this binding (0.1.x line)
#ifdef TREXIO_DELIM
  m.attr("TREXIO_DELIM") = std::string(TREXIO_DELIM);  // sparse dset delimiter (vendored API constant)
#endif

  // ---------------------------- handle class -------------------------------
  nb::class_<TrexioHandle>(m, "trexio_s",
                           "Opaque TREXIO file handle (wraps a trexio_t*).")
    .def_prop_ro("back_end", [](const TrexioHandle& h) { return h.back_end(); })
    .def("__repr__", [](const TrexioHandle& h) {
        std::string s = "trexio_s(";
        s += h.open() ? ("back_end=" + std::to_string(h.back_end())) : "closed";
        return s + ")";
      });

  // ------------------------------- lifecycle --------------------------------
  m.def("trexio_open",
      [](const std::string& file_name, const std::string& mode, int back_end) -> nb::object {
        const char cmode = mode.empty() ? 'i' : mode.at(0);
        trexio_exit_code rc = 0;
        trexio_t* f = trexio_open(file_name.c_str(), cmode,
                                  static_cast<back_end_t>(back_end), &rc);
        if (!f)
          return nb::int_(static_cast<int>(rc));  // ABI: plain int rc on failure
        // Explicit take_ownership: the new Python object owns (and on release,
        // destructor-closes) the C++ TrexioHandle.
        nb::object pyh =
            nb::cast(new TrexioHandle(f), nb::rv_policy::take_ownership);
        nb::list l;
        l.append(pyh);
        l.append(nb::int_(static_cast<int>(rc)));
        return l;  // -> [trexio_s, rc]
      },
      "Open (or create) a TREXIO file. Returns [handle, rc] on success, or a "
      "plain int rc on failure.",
      nb::arg("file"), nb::arg("mode"), nb::arg("back_end"));

  m.def("trexio_close", [](TrexioHandle* h) -> int {
        return (h && h->open()) ? h->close() : static_cast<int>(TREXIO_FAILURE);
      },
      "Close a TREXIO file handle (0 on success; -1 if already closed).",
      nb::arg("handle"));

  m.def("trexio_flush", [](TrexioHandle* h) -> int {
        if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);
        return static_cast<int>(trexio_flush(h->raw()));
      },
      "Flush buffers to the TREXIO file.", nb::arg("handle"));

  m.def("trexio_inquire", [](const std::string& file_name) -> int {
        return static_cast<int>(trexio_inquire(file_name.c_str()));
      },
      "Check whether a file name is (or contains) a TREXIO file.",
      nb::arg("file"));

  m.def("trexio_info", []() -> int {
        return static_cast<int>(trexio_info());
      },
      "Print TREXIO library build information (C function prints; returns rc).");

  m.def("trexio_set_state", [](TrexioHandle* h, int state) -> int {
        if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);
        return static_cast<int>(trexio_set_state(h->raw(), static_cast<int32_t>(state)));
      },
      "Set the active state of the file.", nb::arg("handle"), nb::arg("state"));

  m.def("trexio_get_state", [](TrexioHandle* h) -> nb::object {
        int32_t num = 0;
        int rc = (h && h->open())
                     ? static_cast<int>(trexio_get_state(h->raw(), &num))
                     : static_cast<int>(TREXIO_FAILURE);
        nb::list l;
        l.append(nb::int_(rc));   // rc first
        l.append(nb::int_(num));
        return l;                 // -> [rc, state]
      },
      "Get the active state. Returns [rc, state].", nb::arg("handle"));

  m.def("trexio_set_one_based", [](TrexioHandle* h) -> int {
        if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE);
        return static_cast<int>(trexio_set_one_based(h->raw()));
      },
      "Request 1-based indexing for the opened file (2.6.x API).",
      nb::arg("handle"));

  m.def("trexio_cp", [](const std::string& source, const std::string& dest) -> int {
        return static_cast<int>(trexio_cp(source.c_str(), dest.c_str()));
      },
      "Copy a TREXIO file (portable, back-end-aware).",
      nb::arg("source"), nb::arg("dest"));

  m.def("trexio_string_of_error", [](int code) -> std::string {
        const char* s = trexio_string_of_error(static_cast<trexio_exit_code>(code));
        return s ? std::string(s) : std::string("unknown TREXIO error");
      },
      "Decode a TREXIO exit code into a human-readable string.", nb::arg("code"));

  m.def("trexio_get_back_end", [](TrexioHandle* h) -> int {
        return (h && h->open()) ? h->back_end() : static_cast<int>(TREXIO_FAILURE);
      },
      "Return the back_end number of the opened file.", nb::arg("handle"));

  m.def("trexio_has_backend", [](int be) -> bool {
        return trexio_has_backend(static_cast<back_end_t>(be));
      },
      "True if the library was built with this back end.", nb::arg("back_end"));
  m.def("trexio_has_back_end", [](int be) -> bool {
        return trexio_has_back_end(static_cast<back_end_t>(be));
      },
      "True if the library was built with this back end (alias of has_backend).",
      nb::arg("back_end"));

  m.def("trexio_get_int64_num", [](TrexioHandle* h) -> nb::object {
        int32_t num = 0;
        int rc = (h && h->open())
                     ? static_cast<int>(trexio_get_int64_num(h->raw(), &num))
                     : static_cast<int>(TREXIO_FAILURE);
        nb::list l;
        l.append(nb::int_(rc));   // rc first
        l.append(nb::int_(num));
        return l;                 // -> [rc, num]
      },
      "Number of int64s in the (last read) determinant dset. Returns [rc, num].",
      nb::arg("handle"));

  // ------------------------ determinants / orbitals -------------------------
  m.def("trexio_to_bitfield_list",
      [](const nb::object& orbitals, int n_int) -> nb::object {
        auto orb = cast_vec<int32_t>(orbitals);
        std::vector<int64_t> bits(static_cast<size_t>(n_int < 0 ? 0 : n_int), 0);
        int rc = static_cast<int>(trexio_to_bitfield_list(
            orb.data(), static_cast<int32_t>(orb.size()),
            bits.data(), static_cast<int32_t>(n_int)));
        nb::list l;
        l.append(nb::int_(rc));              // rc first
        l.append(vec_list(bits));
        return l;                            // -> [rc, bitfield_list]
      },
      "Occ. orbital list -> bitfield determinant. Returns [rc, bitfield_list].",
      nb::arg("orbitals"), nb::arg("n_int"));

  m.def("trexio_safe_to_orbital_list",
      [](int n_int, const nb::object& dets, int size_max) -> nb::object {
        auto d = cast_vec<int64_t>(dets);
        std::vector<int32_t> out(static_cast<size_t>(size_max < 0 ? 0 : size_max), 0);
        int32_t num = 0;
        int rc = static_cast<int>(trexio_safe_to_orbital_list(
            static_cast<int32_t>(n_int), d.data(), static_cast<int64_t>(d.size()),
            out.data(), static_cast<int64_t>(size_max), &num));
        nb::list l;
        l.append(nb::int_(rc));              // rc first
        l.append(vec_list(out));
        l.append(nb::int_(num));
        return l;                            // -> [rc, orbital_list, occ_num]
      },
      "Bitfield determinant -> list of occupied orbitals (safe buffer).",
      nb::arg("n_int"), nb::arg("dets"), nb::arg("size_max"));

  m.def("trexio_safe_to_orbital_list_up_dn",
      [](int n_int, const nb::object& dets, int size_up, int size_dn) -> nb::object {
        auto d = cast_vec<int64_t>(dets);
        std::vector<int32_t> up(static_cast<size_t>(size_up < 0 ? 0 : size_up), 0);
        std::vector<int32_t> dn(static_cast<size_t>(size_dn < 0 ? 0 : size_dn), 0);
        int32_t nu = 0, nd = 0;
        int rc = static_cast<int>(trexio_safe_to_orbital_list_up_dn(
            static_cast<int32_t>(n_int), d.data(), static_cast<int64_t>(d.size()),
            up.data(), static_cast<int64_t>(size_up),
            dn.data(), static_cast<int64_t>(size_dn), &nu, &nd));
        nb::list l;
        l.append(nb::int_(rc));              // rc first
        l.append(vec_list(up));
        l.append(vec_list(dn));
        l.append(nb::int_(nu));
        l.append(nb::int_(nd));
        return l;                            // -> [rc, up, dn, num_up, num_dn]
      },
      "Bitfield determinant (up+dn halves) -> two occ. orbital lists (safe).",
      nb::arg("n_int"), nb::arg("dets"), nb::arg("size_up"), nb::arg("size_dn"));

  // ---------------------------------- NAO -----------------------------------
  m.def("trexio_convert_nao_radius_py",
      [](double r, const nb::object& grid_r) -> nb::object {
        auto gr = cast_vec<double>(grid_r);
        double out = 0.0;
        int rc = static_cast<int>(trexio_convert_nao_radius_py(
            r, gr.data(), static_cast<int32_t>(gr.size()), &out));
        nb::list l;
        l.append(nb::int_(rc));    // rc first
        l.append(nb::float_(out));
        return l;                  // -> [rc, r_log]
      },
      "Convert a radius r into shell-logarithmic units. Returns [rc, r_log].",
      nb::arg("r"), nb::arg("grid_r"));

  m.def("trexio_evaluate_nao_radial_py",
      [](int shell_index, double r, const nb::object& grid_start,
         const nb::object& grid_size, const nb::object& grid_r,
         const nb::object& interpolator, const nb::object& normalization)
          -> nb::object {
        auto gs = cast_vec<int64_t>(grid_start);
        auto gz = cast_vec<int64_t>(grid_size);
        auto gr = cast_vec<double>(grid_r);
        auto it = cast_vec<double>(interpolator);
        auto nm = cast_vec<double>(normalization);
        double amp = 0.0;
        int rc = static_cast<int>(trexio_evaluate_nao_radial_py(
            shell_index, r,
            gs.data(), static_cast<int>(gs.size()),
            gz.data(), static_cast<int>(gz.size()),
            gr.data(), static_cast<int>(gr.size()),
            it.data(), static_cast<int>(it.size()),
            nm.data(), static_cast<int>(nm.size()), &amp));
        nb::list l;
        l.append(nb::int_(rc));    // rc first
        l.append(nb::float_(amp));
        return l;                  // -> [rc, amplitude]
      },
      "Evaluate the radial NAO function of one shell at a radius.",
      nb::arg("shell_index"), nb::arg("r"), nb::arg("grid_start"), nb::arg("grid_size"),
      nb::arg("grid_r"), nb::arg("interpolator"), nb::arg("normalization"));

  m.def("trexio_evaluate_nao_radial_all_py",
      [](int shell_cnt, const nb::object& nucleus_index, const nb::object& nucleus_coords,
         const nb::object& grid_start, const nb::object& grid_size,
         const nb::object& grid_r, const nb::object& interpolator,
         const nb::object& normalization,
         double rx, double ry, double rz, int amplitude_cnt) -> nb::object {
        auto ni = cast_vec<int64_t>(nucleus_index);
        auto nc = cast_vec<double>(nucleus_coords);
        auto gs = cast_vec<int64_t>(grid_start);
        auto gz = cast_vec<int64_t>(grid_size);
        auto gr = cast_vec<double>(grid_r);
        auto it = cast_vec<double>(interpolator);
        auto nm = cast_vec<double>(normalization);
        std::vector<double> am(static_cast<size_t>(amplitude_cnt < 0 ? 0 : amplitude_cnt), 0.0);
        int rc = static_cast<int>(trexio_evaluate_nao_radial_all_py(
            static_cast<int32_t>(shell_cnt),
            ni.data(), static_cast<int>(ni.size()),
            nc.data(), static_cast<int>(nc.size()),
            gs.data(), static_cast<int>(gs.size()),
            gz.data(), static_cast<int>(gz.size()),
            gr.data(), static_cast<int>(gr.size()),
            it.data(), static_cast<int>(it.size()),
            nm.data(), static_cast<int>(nm.size()),
            rx, ry, rz, am.data(), static_cast<int>(amplitude_cnt)));
        nb::list l;
        l.append(nb::int_(rc));     // rc first
        l.append(vec_list(am));
        return l;                   // -> [rc, amplitudes]
      },
      "Evaluate all NAO shells at a given position in space.",
      nb::arg("shell_cnt"), nb::arg("nucleus_index"), nb::arg("nucleus_coords"),
      nb::arg("grid_start"), nb::arg("grid_size"), nb::arg("grid_r"),
      nb::arg("interpolator"), nb::arg("normalization"),
      nb::arg("rx"), nb::arg("ry"), nb::arg("rz"), nb::arg("amplitude_cnt"));

  // ------------------------------ delete groups -----------------------------
#define DEF_DELETE(g) \
  m.def("trexio_delete_" #g, \
      [](TrexioHandle* h) -> int { \
        if (!h || !h->open()) return static_cast<int>(TREXIO_FAILURE); \
        return static_cast<int>(trexio_delete_##g(h->raw())); \
      }, \
      "Remove the " #g " group from the file.", nb::arg("handle"))

  // Reconciled with api/trexio.py (26 pytr.trexio_delete_* calls) -- the full
  // group set declared by the 2.6.1 header (templator_front.h).
  DEF_DELETE(metadata);
  DEF_DELETE(nucleus);
  DEF_DELETE(cell);
  DEF_DELETE(pbc);
  DEF_DELETE(electron);
  DEF_DELETE(state);
  DEF_DELETE(basis);
  DEF_DELETE(auxbasis);
  DEF_DELETE(auxbasis2);
  DEF_DELETE(ecp);
  DEF_DELETE(grid);
  DEF_DELETE(ao);
  DEF_DELETE(ao_1e_int);
  DEF_DELETE(ao_2e_int);
  DEF_DELETE(mo);
  DEF_DELETE(mo_1e_int);
  DEF_DELETE(mo_2e_int);
  DEF_DELETE(auxao);
  DEF_DELETE(auxao2);
  DEF_DELETE(densityfit);
  DEF_DELETE(determinant);
  DEF_DELETE(csf);
  DEF_DELETE(amplitude);
  DEF_DELETE(rdm);
  DEF_DELETE(jastrow);
  DEF_DELETE(qmc);
#undef DEF_DELETE
}
