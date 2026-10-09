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

# ---------------- version + accessor guards ----------------
file(STRINGS "${TREXIO_INC}/trexio.h" _v REGEX "#define[ \t]+TREXIO_VERSION_(MAJOR|MINOR|PATCH)")
string(REGEX MATCH "MAJOR[ \t]+([0-9]+)" _a "${_v[0]}"); set(TVMAJ ${CMAKE_MATCH_1})
string(REGEX MATCH "MINOR[ \t]+([0-9]+)" _a "${_v[1]}"); set(TVMIN ${CMAKE_MATCH_1})
string(REGEX MATCH "PATCH[ \t]+([0-9]+)" _a "${_v[2]}"); set(TVPAT ${CMAKE_MATCH_1})
message(STATUS "TREXIO ${TVMAJ}.${TVMIN}.${TVPAT}")
if(NOT (TVMAJ GREATER 2 OR (TVMAJ EQUAL 2 AND TVMIN GREATER_EQUAL 6)))
  message(FATAL_ERROR "TREXIO >= 2.6 required (found ${TVMAJ}.${TVMIN}.${TVPAT}).")
endif()
file(WRITE "${CMAKE_BINARY_DIR}/trexio_probe.c"
"typedef int t;\n#include \"trexio.h\"\nint f(t* p){return (int)trexio_get_back_end((trexio_t*)p);}\n")
try_compile(TV_OK ${CMAKE_BINARY_DIR}/probe
  SOURCES "${CMAKE_BINARY_DIR}/trexio_probe.c"
  C_INCLUDE_DIRECTORIES "${TREXIO_INC}")
if(NOT TV_OK)
  message(FATAL_ERROR "Installed TREXIO lacks trexio_get_back_end() (run Plan phase 01, reinstall).")
endif()

# ---------------- nanobind module ----------------
find_package(Python 3.9 COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind CONFIG REQUIRED)
nanobind_add_module(pytrexio src/core.cpp)
target_include_directories(pytrexio PRIVATE ${TREXIO_INC})
target_link_libraries(pytrexio PRIVATE ${TREXIO_LIB})
set_target_properties(pytrexio PROPERTIES OUTPUT_NAME "pytrexio")

# ---------------- install layout (mirrors the SWIG build) ----------------
set(SITE "${Python_SITEARCH}")
message(STATUS "installing into ${SITE}")
install(TARGETS pytrexio              DESTINATION "${SITE}/pytrexio")
install(FILES "api/trexio.py"          DESTINATION "${SITE}")
install(FILES "api/pytrexio/__init__.py" "api/pytrexio/_version.py"
               DESTINATION "${SITE}/pytrexio")

# ---------------- Phase 3 hook (no-op until gen_binding.py exists) -------------
if(EXISTS "${CMAKE_SOURCE_DIR}/tools/gen_binding.py")
  add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp"
    COMMAND Python::Interpreter "${CMAKE_SOURCE_DIR}/tools/gen_binding.py"
            --trex-json "${CMAKE_SOURCE_DIR}/third_party/trex.json"
            --out "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp"
    DEPENDS "${CMAKE_SOURCE_DIR}/tools/gen_binding.py"
             "${CMAKE_SOURCE_DIR}/third_party/trex.json"
    COMMENT "Generating pytrexio bindings from trex.json")
  add_custom_target(gen_bindings DEPENDS "${CMAKE_SOURCE_DIR}/src/generated_bindings.cpp")
  add_dependencies(pytrexio gen_bindings)
endif()
