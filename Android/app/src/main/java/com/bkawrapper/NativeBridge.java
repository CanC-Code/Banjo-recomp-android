package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {

    static {
        System.loadLibrary("bkawrapper");
    }

    public static native void nativeInit(OtrService service);

    /**
     * Extracts ROM assets using the Python-generated manifest buffer.
     * @return true if successful, false if manifest missing or malformed.
     */
    public static native boolean runOtrGeneration(int fd, AssetManager assetManager, String outDir);

    public static native void nativeGameBoot(String otrPath, AssetManager assetManager);

    public static native void surfaceReady(int width, int height);

    public static native void updateTexture(int unused);

    public static native void nativeUpdateInput(int buttonMask, float stickX, float stickY);
}
