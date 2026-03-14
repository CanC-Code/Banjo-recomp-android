package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {
    static {
        System.loadLibrary("bkawrapper");
    }

    public static native void nativeInit(Object activity);
    public static native void runOtrGeneration(int romFd, AssetManager assetManager, String outputDir);

    // Required by OtrService.java
    public static void notifyFinished() {
        android.util.Log.i("NativeBridge", "Extraction complete notification received.");
    }

    // Required by GLRenderer.java
    public static void updateTexture(int textureId) {
        // Stub for future rendering logic
    }
}
