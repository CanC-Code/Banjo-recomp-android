#include <android/log.h>

#define LOG_TAG "BKA_AUDIO"
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Music
========================= */

void coMusicPlayer_playMusic(int id) {
    LOGW("playMusic stub: %d", id);
}

// FIXED: Replaced '...' with 'void' for strict C compatibility inside extern "C"
void comusic_8025AB44(void) {
    LOGW("comusic_8025AB44 stub");
}

/* =========================
   Audio Engine
========================= */

void n_alSynAddPlayer(void) {
    LOGW("n_alSynAddPlayer stub");
}

void n_alSynRemovePlayer(void) {
    LOGW("n_alSynRemovePlayer stub");
}

void n_alSynStartVoice(void) {}
void n_alSynStopVoice(void) {}

/* =========================
   SFX
========================= */

// FIXED: Commented out sfx_play to resolve the "duplicate symbol" linker error.
// The game already provides the full definition for this in src/core2/code_85800.c.
/*
void sfx_play(void) {
    LOGW("sfx_play stub");
}
*/

void func_8025F4F0(void) {
    LOGW("audio func_8025F4F0 stub");
}

} // extern "C"
