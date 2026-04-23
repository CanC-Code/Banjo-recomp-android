cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Force the Full Build flag
option(EXCLUDE_GAME_SRC "Exclude game source" OFF) # Set to OFF for the real build

set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../..")

# 2. Bridge Files (The "Engine Room")
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

# 3. Game Source (The "Body of the Car")
if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "BKA-BUILD: Found source directory at ${REPO_ROOT}/src")
    
    # This gathers every .c file we saw in your 'ls -R' output
    file(GLOB_RECURSE GAME_C "${REPO_ROOT}/src/*.c")
    list(APPEND LIB_SOURCES ${GAME_C})
    
    list(LENGTH LIB_SOURCES TOTAL_FILES)
    message(STATUS "BKA-BUILD: Total files to compile: ${TOTAL_FILES}")
endif()

add_library(bkawrapper SHARED ${LIB_SOURCES})

# 4. Include Paths (The "Nerves")
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# 5. Compile & Link
target_compile_options(bkawrapper PRIVATE "-w" "-O3" "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h")
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
