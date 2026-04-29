cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Bridge Sources
# ============================================================

set(BRIDGE_SOURCES
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp
    ultra/missing_stubs.c
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp
)

# ============================================================
# 2. Game Sources
# ============================================================

option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    set(FILES_TO_REMOVE "")
    foreach(FILE_PATH ${GAME_SOURCES})
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()

    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
    endif()

    file(GLOB_RECURSE CONFLICTS "${REPO_ROOT}/src/done/*")
    if(CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${CONFLICTS})
    endif()

    set(ALL_SOURCES ${BRIDGE_SOURCES} ${GAME_SOURCES})
else()
    set(ALL_SOURCES ${BRIDGE_SOURCES})
endif()

# ============================================================
# 3. Source Properties
# ============================================================

set_source_files_properties(
    "${REPO_ROOT}/src/core2/code_85800.c" 
    PROPERTIES COMPILE_DEFINITIONS "sfx_play=original_sfx_play"
)

# ============================================================
# 4. Library & Includes
# ============================================================

add_library(bkawrapper SHARED ${ALL_SOURCES})

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

# ============================================================
# 5. Compile Options (FIXED: No forced include)
# ============================================================

target_compile_options(bkawrapper PRIVATE
    -w
    -fpermissive
    -Wno-error=implicit-int
    -Wno-error=int-conversion
    -Wno-error=implicit-function-declaration
    -Wno-error=incompatible-pointer-types
    -Wno-error=unused-function

    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

# ============================================================
# 6. Defines & Linking
# ============================================================

target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    VERSION=0
    N64_RECOMP
    __ANDROID__
)

find_library(log-lib log)

target_link_options(bkawrapper PRIVATE "-Wl,--allow-multiple-definition")

target_link_libraries(bkawrapper PRIVATE
    android
    ${log-lib}
    GLESv3
    EGL
    z
    atomic
    m
)
