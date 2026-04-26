cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(EXCLUDE_GAME_SRC FALSE)

# --- Repo Root Detection ---

set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
while(NOT EXISTS "${REPO_ROOT}/src/core1" AND NOT "${REPO_ROOT}" STREQUAL "/")
    get_filename_component(REPO_ROOT "${REPO_ROOT}/.." ABSOLUTE)
endwhile()

if(NOT EXISTS "${REPO_ROOT}/src/core1")
    message(FATAL_ERROR "CRITICAL: Could not find repo root: ${REPO_ROOT}")
endif()

# --- Base Sources ---

set(LIB_SOURCES
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp
)

# --- Game Sources ---

file(GLOB_RECURSE GAME_C "${REPO_ROOT}/src/*.c")
file(GLOB_RECURSE GAME_CPP "${REPO_ROOT}/src/*.cpp")

# --- FILTER BAD FILES ---

set(FILTERED_C "")
foreach(f ${GAME_C})
    if(NOT f MATCHES "dynarec|rsp|os_.*\\.c|libultra|ultra64")
        list(APPEND FILTERED_C ${f})
    endif()
endforeach()

set(FILTERED_CPP "")
foreach(f ${GAME_CPP})
    if(NOT f MATCHES "dynarec|rsp|platform|gl|dx|vulkan")
        list(APPEND FILTERED_CPP ${f})
    endif()
endforeach()

list(APPEND LIB_SOURCES ${FILTERED_C} ${FILTERED_CPP})

# --- Library ---

add_library(bkawrapper SHARED ${LIB_SOURCES})

# --- Includes ---

target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# --- Apply PR headers ONLY to C files ---

set_property(SOURCE ${FILTERED_C}
    APPEND PROPERTY INCLUDE_DIRECTORIES
    "${REPO_ROOT}/include/2.0L/PR"
)

# --- Compile Options ---

target_compile_options(bkawrapper PRIVATE
    -w
    -O3
    -include ${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h
)

# --- Android Linking ---

find_library(log-lib log)

target_link_libraries(bkawrapper
    android
    ${log-lib}
    GLESv3
    EGL
    z
)
