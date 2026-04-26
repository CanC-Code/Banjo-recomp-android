import os
import re

def fix_struct_ordering(directory):
    """
    Reorders structs, enums, and unions in .c files.
    Cooperatively removes definitions that are already present in n64_types.h
    to prevent redefinition errors.
    """
    print(f"📐 Syncing and Reordering types in {directory}...")
    
    # Types already defined in our Master n64_types.h.
    # If these appear in .c files, they MUST be removed.
    FORBIDDEN_REDEFINITIONS = {
        # Foundation & OS
        'OSPri', 'OSMesg', 'OSMesgQueue', 'OSThread', 'OSThread_s', 
        'OSIoMesg', 'OSPiHandle', 'OSContPad', 'OSIntMask',
        # Graphics
        'Mtx', 'Gfx', 'Vtx', 'Vtx_t',
        # Audio Engine
        'ALSynth', 'ALGlobals', 'ALGlobals_s', 'ALSyn', 'N_ALSyn', 
        'ALHeap', 'ALHeap_s', 'ALParam', 'ALParam_s', 'ALLink', 'ALLink_s',
        'ALEvtq', 'ALEvtq_s', 'ALPVoice', 'ALPVoice_s', 'ALWaveTable', 
        'ALBank', 'ALInstrument', 'ALSound', 'ALEnvelope', 'ALKeyMap',
        'ALFilter', 'ALFilter_s', 'ALResampler', 'ALAdpcm', 'ALEnvmixer',
        'Acmd', 'ADPCM_STATE', 'POLEF_STATE', 'RESAMPLE_STATE', 'ENVMIX_STATE'
    }

    match_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.c'):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()

            types_to_hoist = []
            new_text = ""
            idx = 0
            changed = False

            while idx < len(text):
                # Search for struct, enum, or union definitions
                match = re.search(r'\b((?:typedef\s+)?(?:struct|enum|union)\b\s*([a-zA-Z0-9_]*)[^{;=()]*)\{', text[idx:])
                if not match:
                    new_text += text[idx:]
                    break

                start = idx + match.start()
                type_header = match.group(1) # e.g., "typedef struct OSThread_s"
                type_name = match.group(2)   # e.g., "OSThread_s"
                
                # If the name is empty (anonymous), check the tail after the brace
                new_text += text[idx:start]
                brace_start = idx + match.end() - 1

                # Robust brace matching
                count = 0
                brace_end = -1
                in_string = in_char = in_line = in_block = False
                
                for i in range(brace_start, len(text)):
                    if in_string:
                        if text[i] == '"' and text[i-1] != '\\': in_string = False
                    elif in_char:
                        if text[i] == "'" and text[i-1] != '\\': in_char = False
                    elif in_line:
                        if text[i] == '\n': in_line = False
                    elif in_block:
                        if text[i-1:i+1] == '*/': in_block = False
                    else:
                        if text[i:i+2] == '//': in_line = True
                        elif text[i:i+2] == '/*': in_block = True
                        elif text[i] == '"': in_string = True
                        elif text[i] == "'": in_char = True
                        elif text[i] == '{': count += 1
                        elif text[i] == '}':
                            count -= 1
                            if count == 0:
                                brace_end = i
                                break

                if brace_end != -1:
                    semi_end = text.find(';', brace_end)
                    if semi_end != -1 and (semi_end - brace_end) < 100:
                        type_def = text[start:semi_end+1]
                        
                        # Identify the final typedef name if it exists
                        # e.g., "} OSThread;" -> OSThread
                        tail = text[brace_end+1:semi_end].strip()
                        
                        # Check if this type or its alias is forbidden
                        is_forbidden = (type_name in FORBIDDEN_REDEFINITIONS or 
                                      tail in FORBIDDEN_REDEFINITIONS or
                                      "ALGlobals" in type_def)

                        if is_forbidden:
                            print(f"  🗑️  Removed global redefinition from {file}: {type_name or tail}")
                            idx = semi_end + 1
                            changed = True
                        else:
                            # It's a local type, check if it's a genuine definition to hoist
                            is_typedef = "typedef" in type_header
                            if not is_typedef and tail != "" and not tail.startswith('__attribute__'):
                                # Likely an inline variable declaration, don't hoist
                                new_text += text[start:semi_end+1]
                            else:
                                types_to_hoist.append(type_def)
                            idx = semi_end + 1
                            changed = True
                    else:
                        new_text += text[start:brace_end+1]
                        idx = brace_end + 1
                else:
                    new_text += text[start:]
                    break

            if changed:
                # Find the inclusion zone
                last_include_end = 0
                for m in re.finditer(r'#include\s+.*?\n', new_text):
                    last_include_end = m.end()

                final_text = (new_text[:last_include_end] + 
                             ("\n/* HOISTED LOCAL TYPES */\n" + "\n\n".join(types_to_hoist) + "\n" if types_to_hoist else "") + 
                             new_text[last_include_end:])

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(final_text)
                match_count += 1

    print(f"✅ Finished syncing {match_count} files.")

if __name__ == '__main__':
    fix_struct_ordering('src')
