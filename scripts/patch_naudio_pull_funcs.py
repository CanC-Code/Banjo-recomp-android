import os
import re

def patch_audio_engine():
    """
    Fixes the ALCSeq and ALCSeqMarker struct definitions in n64_types.h.
    The previous patch incorrectly converted the Banjo-Kazooie specific 
    arrays `lastStatus[16]` and `curBUPtr[16]` into standard libultra scalars
    `lastStatus` and `curPtr`. This restores the custom BK arrays.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # Clean up any leftover comments from the previous bad patch
    content = content.replace("// removed lastStatus array", "")
    content = content.replace("// removed curBUPtr array", "")

    def fix_struct(struct_content):
        # 1. Remove incorrect scalar fields injected previously
        struct_content = re.sub(r'unsigned char\s*\*\s*curPtr\s*;', '', struct_content)
        struct_content = re.sub(r'unsigned char\s*lastStatus\s*;', '', struct_content)
        struct_content = re.sub(r'u8\s*\*\s*curPtr\s*;', '', struct_content)
        struct_content = re.sub(r'u8\s*lastStatus\s*;', '', struct_content)
        
        # 2. Remove array fields if they already exist so we don't duplicate them on re-runs
        struct_content = re.sub(r'unsigned char\s*lastStatus\[16\]\s*;', '', struct_content)
        struct_content = re.sub(r'unsigned char\s*\*\s*curBUPtr\[16\]\s*;', '', struct_content)
        struct_content = re.sub(r'u8\s*lastStatus\[16\]\s*;', '', struct_content)
        struct_content = re.sub(r'u8\s*\*\s*curBUPtr\[16\]\s*;', '', struct_content)

        # 3. Append the correct multi-track array fields for Banjo-Kazooie
        return struct_content + "    unsigned char lastStatus[16];\n    unsigned char *curBUPtr[16];\n"

    # Apply to ALCSeq
    alcseq_match = re.search(r'(typedef struct .*?\{)(.*?)(\}\s*ALCSeq;)', content, re.DOTALL)
    if alcseq_match:
        fixed_body = fix_struct(alcseq_match.group(2))
        content = content[:alcseq_match.start()] + alcseq_match.group(1) + fixed_body + alcseq_match.group(3) + content[alcseq_match.end():]

    # Apply to ALCSeqMarker
    alcseqmarker_match = re.search(r'(typedef struct .*?\{)(.*?)(\}\s*ALCSeqMarker;)', content, re.DOTALL)
    if alcseqmarker_match:
        fixed_body = fix_struct(alcseqmarker_match.group(2))
        content = content[:alcseqmarker_match.start()] + alcseqmarker_match.group(1) + fixed_body + alcseqmarker_match.group(3) + content[alcseqmarker_match.end():]

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: Restored custom Banjo-Kazooie ALCSeq and ALCSeqMarker arrays (lastStatus[16] & curBUPtr[16]).")

if __name__ == '__main__':
    patch_audio_engine()
