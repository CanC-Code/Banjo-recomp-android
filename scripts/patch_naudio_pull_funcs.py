import os
import re

def patch_audio_engine():
    """
    Fixes duplicate member errors in n64_types.h by cleaning the structs
    before injecting the required Banjo-Kazooie audio track arrays.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # The authoritative fields required for Banjo-Kazooie's multi-track audio engine.
    # We use u8 to remain consistent with existing N64 types.
    bk_fields = "    u8 lastStatus[16];\n    u8 *curBUPtr[16];\n"

    def clean_and_patch_struct(full_text, struct_name, new_fields):
        # 1. Identify the specific struct block
        struct_pattern = r'(typedef struct .*?\{)(.*?)(\}\s*' + struct_name + r';)'
        match = re.search(struct_pattern, full_text, re.DOTALL)
        
        if not match:
            print(f"⚠️ Warning: Struct {struct_name} not found in header.")
            return full_text
            
        header, body, footer = match.groups()
        
        # 2. Strip ALL existing instances of the conflicting members.
        # This handles scalars, arrays, u8, unsigned char, and standard libultra names.
        # We use a multi-line regex to delete any line containing these identifiers.
        body = re.sub(r'.*lastStatus.*;\n?', '', body)
        body = re.sub(r'.*curBUPtr.*;\n?', '', body)
        body = re.sub(r'.*curPtr.*;\n?', '', body)
        body = re.sub(r'.*// removed scalar.*\n?', '', body) # Clean up previous patch artifacts
        
        # 3. Reconstruct the struct with the clean body and the new BK fields.
        # We ensure the body ends with a clean newline before adding the fields.
        clean_body = body.rstrip() + "\n" + new_fields
        return full_text[:match.start()] + header + clean_body + footer + full_text[match.end():]

    # Apply the fix to both relevant structures
    content = clean_and_patch_struct(content, "ALCSeq", bk_fields)
    content = clean_and_patch_struct(content, "ALCSeqMarker", bk_fields)

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h fixed: Purged duplicates and restored BK-specific audio arrays.")

if __name__ == '__main__':
    patch_audio_engine()
