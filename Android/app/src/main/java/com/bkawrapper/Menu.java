// File: Android/app/src/main/java/com/bkawrapper/Menu.java
package com.bkawrapper;

import android.view.View;
import android.widget.LinearLayout;

public class Menu {

    private final LinearLayout menuOverlay;
    private boolean visible = false;

    public Menu(LinearLayout overlay) {
        this.menuOverlay = overlay;
        hide();
    }

    public void show() {
        menuOverlay.setVisibility(View.VISIBLE);
        visible = true;
    }

    public void hide() {
        menuOverlay.setVisibility(View.GONE);
        visible = false;
    }

    public void toggle() {
        if (visible) hide();
        else show();
    }

    public boolean isVisible() {
        return visible;
    }
}