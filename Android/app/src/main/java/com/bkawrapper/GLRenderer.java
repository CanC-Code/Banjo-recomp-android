// File: Android/app/src/main/java/com/bkawrapper/GLRenderer.java
package com.bkawrapper;

import android.content.Context;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.util.Log;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/**
 * GLRenderer
 *
 * Drives the N64 framebuffer → Android display pipeline.
 *
 * Design:
 *   onSurfaceCreated  → tell native side the GL context is alive (allocates
 *                        the RGBA8 320×240 texture on the GL thread).
 *   onSurfaceChanged  → resize viewport.
 *   onDrawFrame       → call NativeBridge.updateTexture() which uploads the
 *                        current screenBuffer and draws it as a fullscreen quad.
 */
public class GLRenderer implements GLSurfaceView.Renderer {

    private static final String TAG = "BKA-GLRenderer";

    private final Context context;
    private int surfaceWidth  = 320;
    private int surfaceHeight = 240;

    public GLRenderer(Context context) {
        this.context = context;
    }

    // -----------------------------------------------------------------------
    // GLSurfaceView.Renderer callbacks — all called on the GL thread
    // -----------------------------------------------------------------------

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        Log.i(TAG, "onSurfaceCreated: GL context ready");

        // Set a black clear colour so we don't get garbage on first frame
        GLES20.glClearColor(0f, 0f, 0f, 1f);

        // Tell the native side: allocate the framebuffer texture now that
        // we have a valid GL context.
        NativeBridge.surfaceReady(surfaceWidth, surfaceHeight);
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        surfaceWidth  = width;
        surfaceHeight = height;
        GLES20.glViewport(0, 0, width, height);
        Log.i(TAG, "onSurfaceChanged: " + width + "×" + height);
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        // updateTexture uploads gBridgeGlobals->screenBuffer → GL texture,
        // then draws the fullscreen quad.  The native implementation guards
        // against null pointers and an uninitialised surface, so it is safe
        // to call unconditionally here.
        NativeBridge.updateTexture(0);
    }
}
