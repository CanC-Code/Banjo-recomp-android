// Android/app/src/main/cpp/ultra/audio_helper.cpp

#include <stdint.h>
#include <stdio.h>

struct UnwrappedSound {
    uint32_t sfxId;
    float volume;
    uint32_t sampleRate;
};

UnwrappedSound unwrap_sfx_params(uint32_t packedVal) {
    UnwrappedSound result;
    
    result.sfxId = packedVal & 0x7FF;
    result.sampleRate = ((packedVal >> 11) & 0x3FF) << 5;
    result.volume = (float)((packedVal >> 21) & 0x7FF) / 1023.0f;
    
    return result;
}
