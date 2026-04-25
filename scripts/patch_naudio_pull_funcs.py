import os
import re

def patch_audio_engine():
    """
    Restores the Banjo-Kazooie specific 16-channel audio arrays.
    This script targets the end of the ALCSeq and ALCSeqMarker structs
    to ensure the fields are present for cseq.c to compile.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # Define the fields required by Banjo's cseq.c
    bk_fields = "    unsigned char lastStatus[16];\n    unsigned char *curBUPtr[16];\n"

    # Helper to safely inject fields into a typedef struct
    def inject_into_struct(full_text, struct_name, fields):
        # Pattern looks for the closing brace of the struct with the specific name
        pattern = r'\}\s*' + struct_name + r';'
        if struct_name in full_text and fields not in full_text:
            # We insert the fields right before the closing brace
            return re.sub(r'(\n\s*)(\}\s*' + struct_name + r';)', r'\1' + fields + r'\2', full_text)
        return full_text

    # Apply injections
    content = inject_into_struct(content, "ALCSeq", bk_fields)
    content = inject_into_struct(content, "ALCSeqMarker", bk_fields)

    # Clean up previous incorrect scalar injections if they exist
    # These often cause "subscripted value is not an array" errors if left behind
    content = re.sub(r'unsigned char\s+lastStatus\s*;', '// removed scalar', content)
    content = re.sub(r'unsigned char\s*\*\s*curPtr\s*;', '// removed scalar', content)

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h updated: Successfully restored BK-specific audio track arrays.")

if __name__ == '__main__':
    patch_audio_engine()
