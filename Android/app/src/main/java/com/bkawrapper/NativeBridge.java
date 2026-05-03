package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {

    static {
        System.loadLibrary("bkawrapper");
    }

    // Still used for context initialization in the C++ layer
    public static native void nativeInit(OtrService service);

    // REMOVED: runOtrGeneration (Moved to OtrService.java)

    // Used for booting the engine once extraction is confirmed
    public static native void nativeGameBoot(String otrPath, AssetManager assetManager);

    public static native void surfaceReady(int width, int height);

    public static native void updateTexture(int unused);

    public static native void nativeUpdateInput(int buttonMask, float stickX, float stickY);
}
