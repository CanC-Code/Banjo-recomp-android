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

    # --- THE CRITICAL FIX: SMART VERSION FILTERING ---
    set(FILES_TO_REMOVE "")
    
    foreach(FILE_PATH ${GAME_SOURCES})
        # If the file is versioned (contains us, pal, jp, v10, v11)
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            
            # If it's NOT our target version, get rid of it
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                # If it IS our target version, find the "base" file name 
                # (e.g. src/SM/code_46C0.c) and mark it for removal so the 
                # versioned file takes its place.
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                if(EXISTS ${BASE_FILE})
                    list(APPEND FILES_TO_REMOVE ${BASE_FILE})
                endif()
            endif()
        endif()
    endforeach()

    # 2. Identify explicit system/library collisions
    file(GLOB_RECURSE SYSTEM_CONFLICTS 
        "${REPO_ROOT}/src/core1/os/*.c"      # Use /src/done/ instead
        "${REPO_ROOT}/src/core1/io/*.c"      # Use pi_hle.cpp instead
        "${REPO_ROOT}/src/core1/audio/sl.c"  # Clash on alGlobals
        "${REPO_ROOT}/src/core1/code_0.c"    # Clash on mainLoop
        "${REPO_ROOT}/src/core1/code_7F60.c" # Math library duplicate
    )
    
    # Apply all prunings
    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
        message(STATUS "Applied Version Filtering for ${TARGET_VERSION}")
    endif()
    
    if(SYSTEM_CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${SYSTEM_CONFLICTS})
        message(STATUS "Pruned OS/Audio library conflicts.")
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

# Define version and microcode
target_compile_definitions(bkawrapper PRIVATE 
    F3DEX_GBI
    VERSION=0 # 0 usually represents us.v10 in this project
)

# --- 5. Linking ---
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
