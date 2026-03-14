// File: Android/app/src/main/java/com/bkawrapper/GLRenderer.java
package com.bkawrapper;

import android.opengl.GLSurfaceView;
import android.content.Context;

import javax.microedition.khronos.opengles.GL10;
import javax.microedition.khronos.egl.EGLConfig;

public class GLRenderer implements GLSurfaceView.Renderer {

    private Context context;

    public GLRenderer(Context context) {
        this.context = context;
    }

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        // TODO: initialize GL textures if needed
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        gl.glViewport(0, 0, width, height);
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        NativeBridge.updateTexture(0); // stub
    }
}