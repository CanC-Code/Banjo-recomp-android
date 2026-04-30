#include <sched.h>
#include <map>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>
#include <android/log.h>

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static std::map<uint32_t, std::string> g_offsetToName;
static std::string g_assetDir;

// Helper to match your builder's 32-bit reading logic
static uint32_t read_u32_le(const uint8_t* p) {
    return (uint32_t(p[0])) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}

extern "C" {

void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize) {
    if (!assetDir || !manifestBuf) return;

    g_assetDir = assetDir;
    if (g_assetDir.back() != '/') g_assetDir += "/";

    g_offsetToName.clear();
    uint32_t entryCount = read_u32_le(manifestBuf);
    
    // STRIDE: Must be 48 to match otr_builder.cpp's (i * 48)
    const uint32_t RECORD_SIZE = 48; 
    const uint8_t* p = manifestBuf + 4;

    for (uint32_t i = 0; i < entryCount; ++i) {
        const uint8_t* record = p + (i * RECORD_SIZE);
        uint32_t romOffset = read_u32_le(record);
        const char* name = reinterpret_cast<const char*>(record + 8);
        
        if (name[0] != '\0') {
            g_offsetToName[romOffset] = std::string(name, strnlen(name, 32));
        }
    }
    LOGI("ResourceMgr: Initialized with %zu assets from %s", g_offsetToName.size(), assetDir);
}

void ResourceMgr_HandleDma(void* dramAddr, uint32_t devAddr, uint32_t size) {
    auto it = g_offsetToName.find(devAddr);
    if (it == g_offsetToName.end()) {
        LOGE("DMA Fail: No asset at 0x%08X. Fix LinkerSymbols!", devAddr);
        memset(dramAddr, 0, size);
        return;
    }

    std::string fullPath = g_assetDir + it->second;
    FILE* f = fopen(fullPath.c_str(), "rb");
    if (!f) {
        LOGE("DMA Fail: Cannot open %s (Error: %s)", fullPath.c_str(), strerror(errno));
        memset(dramAddr, 0, size);
        return;
    }

    // Read the actual file data
    size_t read = fread(dramAddr, 1, size, f);
    fclose(f);

    if (read < size) memset((uint8_t*)dramAddr + read, 0, size - read);
    LOGI("DMA Success: Loaded %s to %p", it->second.c_str(), dramAddr);
    sched_yield();
}
}
