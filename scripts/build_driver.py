        if failed_files:
            # FIX 2: Omni-Routed GLOBAL_INJECT logic perfectly synced with Level 3 triggers
            trigger_pattern = r"unknown type name '(?:OSMesg|OSTime|OSPri|OSId|Mtx|Gfx|Acmd|ADPCM_STATE|u32|u16|u8|s32|f32|f64|ALFilter|ALCmdHandler|ALSeq|ALCSeq)'|undeclared identifier '(?:m|l)'|expected '\(' for function-style cast"
            
            if re.search(trigger_pattern, log_data):
                print("🛡️ Master Shield Trigger Detected: Routing to n64_types.h")
                fixes_applied = converter.apply_to_file(TYPES_HEADER, error_context=log_data)
                total_fixes_this_cycle += fixes_applied

            for file_path in failed_files:
                if file_path != TYPES_HEADER: 
                    fixes_applied = converter.apply_to_file(file_path, error_context=log_data)
                    total_fixes_this_cycle += fixes_applied
