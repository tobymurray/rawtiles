cmake_minimum_required(VERSION 3.16)
project(rawtiles_reference_reader
        VERSION 0.1.0
        DESCRIPTION "rawtiles spec v0.6 reference reader (C99)"
        LANGUAGES C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

add_compile_options(-Wall -Wextra -Wpedantic -Wshadow -Wstrict-prototypes
                    -Wmissing-prototypes -Wcast-align -Wpointer-arith)

# --- library --------------------------------------------------------------
add_library(rawtiles STATIC src/rawtiles.c)
target_include_directories(rawtiles PUBLIC include)
set_target_properties(rawtiles PROPERTIES
    PUBLIC_HEADER include/rawtiles/rawtiles.h)

# --- tests ----------------------------------------------------------------
enable_testing()
add_executable(rawtiles_conformance tests/conformance.c)
target_link_libraries(rawtiles_conformance PRIVATE rawtiles)
target_include_directories(rawtiles_conformance PRIVATE include)

# Default corpus path: spec/conformance/ relative to repo root (two levels up
# from reference-reader/build/).
set(RAWTILES_CORPUS_DEFAULT "${CMAKE_SOURCE_DIR}/../spec/conformance")
add_test(NAME conformance
         COMMAND rawtiles_conformance "${RAWTILES_CORPUS_DEFAULT}")
