package com.bkawrapper;

import android.view.View;
import android.widget.Button;

public class MenuController {
    private final MainActivity activity;

    public MenuController(MainActivity activity) {
        this.activity = activity;
        setupListeners();
    }

    private void setupListeners() {
        // Find the button using the ID defined in activity_main.xml
        Button selectBtn = activity.findViewById(R.id.button_select_rom);
        
        if (selectBtn != null) {
            selectBtn.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    activity.openFilePicker();
                }
            });
        }
    }
}
