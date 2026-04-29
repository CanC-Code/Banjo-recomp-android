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

void comusic_8025AB44(...) {
    LOGW("comusic_8025AB44 stub");
}

/* =========================
   Audio Engine
========================= */

void n_alSynAddPlayer(...) {
    LOGW("n_alSynAddPlayer stub");
}

void n_alSynRemovePlayer(...) {
    LOGW("n_alSynRemovePlayer stub");
}

void n_alSynStartVoice(...) {}
void n_alSynStopVoice(...) {}

/* =========================
   SFX
========================= */

void sfx_play(...) {
    LOGW("sfx_play stub");
}

void func_8025F4F0(...) {
    LOGW("audio func_8025F4F0 stub");
}

}