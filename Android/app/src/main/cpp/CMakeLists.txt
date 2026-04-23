cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Force the Full Build
set(EXCLUDE_GAME_SRC FALSE) 

# 2. Bulletproof Repo Root Finder
set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
while(NOT EXISTS "${REPO_ROOT}/src/core1" AND NOT "${REPO_ROOT}" STREQUAL "/")
    get_filename_component(REPO_ROOT "${REPO_ROOT}/.." ABSOLUTE)
endwhile()

if(NOT EXISTS "${REPO_ROOT}/src/core1")
    message(FATAL_ERROR "CRITICAL: Could not find the repo root! Looked all the way up to: ${REPO_ROOT}")
endif()

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

add_library(bkawrapper SHARED ${LIB_SOURCES})

# 5. Global Includes (Safe directories only!)
# We REMOVED the 2.0L/PR folder from this global list so it doesn't break C++ <map>
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# 6. Target-Specific Includes (The Magic Fix)
# We apply the N64 PR folder ONLY to the old game source files. 
set_property(SOURCE ${GAME_C} ${GAME_CPP} APPEND PROPERTY INCLUDE_DIRECTORIES "${REPO_ROOT}/include/2.0L/PR")

# 7. Compile Options & Linking
target_compile_options(bkawrapper PRIVATE "-w" "-O3" "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h")
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
