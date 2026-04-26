import os

def banjo_structural_harmony():
header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

if not os.path.exists(header_path):
    print(f"❌ {header_path} not found.")
    return

with open(header_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("🚀 Applying SAFE Banjo compatibility layer...")

# --- SAFETY: Do not reapply ---
if "BKA_BANJO_LAYER" in content:
    print("✅ Banjo layer already applied. Skipping.")
    return

banjo_layer = """

/* =========================
BKA BANJO COMPAT LAYER
(NON-DESTRUCTIVE)
========================= */
#ifndef BKA_BANJO_LAYER
#define BKA_BANJO_LAYER

/* --- Safe typedef aliases --- */
typedef ALEventListItem N_ALEventListItem;
typedef ALCSeqMarker    ALSeqMarker;

/* --- Missing constants --- */
#define AL_SEQP_LOOP_EVT 10
#define AL_MIDI_FX_CTRL_0 20
#define AL_MIDI_FX_CTRL_1 21
#define AL_MIDI_FX_CTRL_2 22
#define AL_MIDI_FX_CTRL_3 23

/* --- SAFE forward-only prototypes (no signature conflicts) --- */
#ifdef __cplusplus
extern "C" {
#endif

/* Use void* to avoid ABI mismatch */
extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alResamplePull(void *, s16 *, Acmd *);
extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);
extern Acmd *n_alSavePull(s32, Acmd *);
extern Acmd *n_alAuxBusPull(void);
extern Acmd *n_alFxPull(void);
extern Acmd *n_alMainBusPull(void);

#ifdef __cplusplus
}
#endif

#endif /* BKA_BANJO_LAYER */

"""

# Insert before final #endif
if content.strip().endswith("#endif"):
    content = content.rstrip()[:-6] + banjo_layer + "\n#endif\n"
else:
    content += banjo_layer

with open(header_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ SAFE Banjo layer applied (no structural mutations).")

if name == 'main':
banjo_structural_harmony()