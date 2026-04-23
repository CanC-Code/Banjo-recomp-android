cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Force the Full Build
set(EXCLUDE_GAME_SRC FALSE) 

# 2. Bulletproof Repo Root Finder
# This walks up the directory tree until it finds the "src/core1" folder
set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
while(NOT EXISTS "${REPO_ROOT}/src/core1" AND NOT "${REPO_ROOT}" STREQUAL "/")
    get_filename_component(REPO_ROOT "${REPO_ROOT}/.." ABSOLUTE)
endwhile()

if(NOT EXISTS "${REPO_ROOT}/src/core1")
    message(FATAL_ERROR "CRITICAL: Could not find the repo root! Looked all the way up to: ${REPO_ROOT}")
endif()

message(STATUS "BKA-BUILD: Successfully located Repo Root at: ${REPO_ROOT}")

# 3. Base Bridge Sources
set(LIB_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp" 
)

# 4. Glob the Game Source
file(GLOB_RECURSE GAME_C "${REPO_ROOT}/src/*.c")
file(GLOB_RECURSE GAME_CPP "${REPO_ROOT}/src/*.cpp")
list(APPEND LIB_SOURCES ${GAME_C} ${GAME_CPP})

list(LENGTH LIB_SOURCES TOTAL_FILES)
message(STATUS "BKA-BUILD: Added ${TOTAL_FILES} files to the build.")

# 5. Build and Include
add_library(bkawrapper SHARED ${LIB_SOURCES})

target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/tools       # <-- FIX 1: For rare_decompression.h
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/include/2.0L/PR            # <-- FIX 2: For ultratypes.h
    ${REPO_ROOT}/src
)

target_compile_options(bkawrapper PRIVATE "-w" "-O3" "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h")
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
