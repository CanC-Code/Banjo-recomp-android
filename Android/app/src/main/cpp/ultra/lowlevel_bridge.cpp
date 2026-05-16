    // -------------------------------------------------------------------------
    // ANDROID NATIVE BRIDGE HOOKS
    // -------------------------------------------------------------------------

    // 2. Input Memory Allocation: 
    struct BKA_ControllerPad {
        uint16_t button;
        int8_t   stick_x;
        int8_t   stick_y;
        uint8_t  errno_val;
    };

    // Allocate the physical memory array for all 4 standard controller ports.
    BKA_ControllerPad gN64_ControllerData[4] = {{0, 0, 0, 0}};

    // 3. Engine Clock Signal Stub:
    // Connects the asynchronous Android OpenGL thread to the synchronous N64 OS.
    void N64_TriggerVirtualVBlankInterrupt(void) {
        if (gN64_Reg_Base == nullptr) return;

        // Assert the VI Interrupt bit inside the emulated hardware register space.
        // The recompilation engine's background thread will detect this register 
        // change and organically dispatch the OS_EVENT_VI message to the VI Manager.
        gN64_Reg_Base[MI_INTR_REG_IDX] |= MI_INTR_VI;
    }

    // 4. Hardware Renderer Stub:
    // Connects the recompiled N64 Display List executor to the Android GL surface.
    void VideoPlugin_OutputFrameTexture(uint32_t hostTextureId) {
        // STUB: This must eventually route the active frame buffer or hardware 
        // RDP texture context to the provided Android hostTextureId.
    }

} // end extern "C"
