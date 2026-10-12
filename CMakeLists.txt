cmake_minimum_required(VERSION 3.21...3.30)
project(trexio LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ------------- locate TREXIO (installed prefix: include/ + lib{,64}/) ----------
set(TREXIO_HOME "$ENV{TREXIO_HOME}" CACHE PATH "TREXIO install prefix (e.g. $HOME/.local)")
if(NOT TREXIO_HOME)
  get_filename_component(_home "$ENV{HOME}" ABSOLUTE)
  if(EXISTS "${_home}/.local/include/trexio.h")
    set(TREXIO_HOME "${_home}/.local")
  endif()
endif()
if(NOT TREXIO_HOME OR NOT EXISTS "${TREXIO_HOME}/include/trexio.h")
  message(FATAL_ERROR "TREXIO not found (need <prefix>/include/trexio.h). "
                      "module load trexio, install locally, or -DTREXIO_HOME=...")
endif()
set(TREXIO_INC "${TREXIO_HOME}/include")
find_library(TREXIO_LIB trexio PATHS "${TREXIO_HOME}/lib64" "${TREXIO_HOME}/lib" NO_DEFAULT_PATH)
if(NOT TREXIO_LIB)
  message(FATAL_ERROR "libtrexio not found under ${TREXIO_HOME}")
endif()
message(STATUS "TREXIO_HOME=${TREXIO_HOME}  lib=${TREXIO_LIB}")

# ---------------- version + accessor guards (from installed header) -----------
file(READ "${TREXIO_INC}/trexio.h" _hdr)
if(_hdr MATCHES "TREXIO_VERSION_MAJOR[ \t]+([0-9]+)")
  set(TVMAJ ${CMAKE_MATCH_1})
endif()
if(_hdr MATCHES "TREXIO_VERSION_MINOR[ \t]+([0-9]+)")
  set(TVMIN ${CMAKE_MATCH_1})
endif()
if(_hdr MATCHES "TREXIO_VERSION_PATCH[ \t]+([0-9]+)")
  set(TVPAT ${CMAKE_MATCH_1})
endif()
message(STATUS "TREXIO ${TVMAJ}.${TVMIN}.${TVPAT}")
if(NOT (TVMAJ GREATER 2 OR (TVMAJ EQUAL 2 AND TVMIN GREATER_EQUAL 6)))
  message(FATAL_ERROR "TREXIO >= 2.6 required (found ${TVMAJ}.${TVMIN}.${TVPAT}).")
endif()
if(NOT _hdr MATCHES "trexio_get_back_end")
  message(FATAL_ERROR "Installed TREXIO lacks trexio_get_back_end() (run Plan phase 01, reinstall).")
endif()

# ---------------- nanobind module ---------------------------------------------
# Layout A (user decision 2026-10-09): the module is installed as
# site-packages/trexio/pytrexio.<tag>.so, i.e. importable as `trexio.pytrexio`.
find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)
# core.cpp = hand-written core (lifecycle/state/NAO/bitfield/delete);
# generated_bindings.cpp = per-variable has/read/write (tools/gen_binding.py).
nanobind_add_module(pytrexio src/core.cpp src/generated_bindings.cpp)
target_include_directories(pytrexio PRIVATE ${TREXIO_INC})
target_compile_definitions(pytrexio PRIVATE TREXIO_PKG_VERSION="${TVMAJ}.${TVMIN}.${TVPAT}")
target_link_libraries(pytrexio PRIVATE ${TREXIO_LIB})
set_target_properties(pytrexio PROPERTIES OUTPUT_NAME "pytrexio")

# ---------------- the trexio/ wheel package ------------------------------------
# Layout A: site-packages/trexio/{__init__.py, _version.py, pytrexio.<tag>.so}.
# api/trexio/ is the tracked package source (symlinks to the canonical vendored
# files -- no content duplication; see api/trexio/__init__.py -> ../trexio.py).
# scikit-build-core (wheel.packages = ["api/trexio"]) copies it into the wheel
# as "trexio/" (prefix stripped).  Its default include mode respects .gitignore,
# so the package dir is tracked; only the compiled module overlay is ignored.
set(WHEEL_PKG "${CMAKE_SOURCE_DIR}/api/trexio")
add_custom_command(TARGET pytrexio POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different $<TARGET_FILE:pytrexio> "${WHEEL_PKG}/"
  COMMENT "Copying pytrexio.<tag>.so into the trexio/ wheel package")

# ---------------- cmake --install layout (non-wheel installs) ------------------
# Relative destinations so that `cmake --install --prefix <dir>` lands them in
# <dir>/trexio/ (absolutes would escape the install prefix).
install(TARGETS pytrexio DESTINATION "trexio")
install(FILES "${CMAKE_SOURCE_DIR}/api/trexio/__init__.py"
              "${CMAKE_SOURCE_DIR}/api/trexio/_version.py"
              DESTINATION "trexio")

# ---------------- generated bindings (per-variable surface) -------------------
# Regenerated from required_api.names + the installed trexio.h + trex.json.
if(EXISTS "${CMAKE_SOURCE_DIR}/tools/gen_binding.py")
  add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp"
    COMMAND Python::Interpreter "${CMAKE_SOURCE_DIR}/tools/gen_binding.py"
            --trex-json "${CMAKE_SOURCE_DIR}/third_party/trex.json"
            --out "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp"
    DEPENDS "${CMAKE_SOURCE_DIR}/tools/gen_binding.py"
            "${CMAKE_SOURCE_DIR}/third_party/trex.json"
            "${CMAKE_SOURCE_DIR}/tools/required_api.names"
            "${TREXIO_INC}/trexio.h"
    COMMENT "Generating pytrexio per-variable bindings")
  add_custom_target(gen_bindings DEPENDS "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp")
  add_dependencies(pytrexio gen_bindings)
endif()
