cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10") # Explicitly targeting US Version 1.0

# --- 1. Define Native Port Infrastructure ---
set(VERIFICATION_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp" 
)

# --- 2. Original N64 Source Integration ---
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "Including original N64 source files from ${REPO_ROOT}/src")

    # 1. Recursively find all C files
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- THE CRITICAL FIX: US.V10 VERSION SELECTOR ---
    set(FILES_TO_REMOVE "")
    
    foreach(FILE_PATH ${GAME_SOURCES})
        # Identify versioned files (containing us, pal, jp, v10, or v11)
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            
            # If it's NOT our target version, discard it entirely
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                # If it IS our target version, we must remove the "generic" 
                # base file so this one can take its place.
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()

    # 2. Identify Bridge Conflicts
    # We prune the recompiled stubs for OS, IO, and Audio because 
    # your modern Android bridge handles these subsystems.
    file(GLOB_RECURSE BRIDGE_CONFLICTS 
        "${REPO_ROOT}/src/core1/os/*.c"      # Use /src/done/ overrides instead
        "${REPO_ROOT}/src/core1/io/*.c"      # Use pi_hle.cpp instead
        "${REPO_ROOT}/src/core1/audio/sl*.c" # Catch sl.c or sl.us.v10.c (alGlobals)
        "${REPO_ROOT}/src/core1/code_0*.c"   # Catch code_0 variants (mainLoop)
        "${REPO_ROOT}/src/core1/code_7F60*.c" # Math library duplicate
    )
    
    # 3. Apply the filter
    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
        message(STATUS "Applied Version Preference: Keeping only ${TARGET_VERSION} variants.")
    endif()
    
    if(BRIDGE_CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${BRIDGE_CONFLICTS})
        message(STATUS "Pruned recompiled OS/Audio library conflicts.")
    endif()

    set(ALL_SOURCES ${VERIFICATION_SOURCES} ${GAME_SOURCES})
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

# --- 3. Include Paths ---
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src               
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# --- 4. Compilation Flags ---
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"                           
    "-fpermissive"                 
    "-Wno-error=implicit-int"      
    "-Wno-error=int-conversion"    
    "-Wno-error=implicit-function-declaration"
    "-Wno-error=incompatible-pointer-types"
)

# Define version-specific constants
target_compile_definitions(bkawrapper PRIVATE 
    F3DEX_GBI
    VERSION=0 # 0 corresponds to us.v10
)

# --- 5. Linking ---
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
