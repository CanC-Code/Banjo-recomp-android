import os
import re

def patch_audio_engine():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # Authoritative multi-track arrays for Banjo-Kazooie
    bk_fields = "    u8 lastStatus[16];\n    u8 *curBUPtr[16];\n"

    def apply_patch(text, struct_name):
        # This regex finds the struct block and captures the body.
        # It looks for the closing brace followed by the struct name OR the tag name.
        pattern = r'(struct\s+\w*?' + struct_name + r'.*?\{)(.*?)(\}\s*' + struct_name + r'?;)'
        match = re.search(pattern, text, re.DOTALL)
        
        if not match:
            # Fallback for anonymous structs or different spacing
            pattern = r'(\{\s*)(.*?)(\}\s*' + struct_name + r';)'
            match = re.search(pattern, text, re.DOTALL)

        if match:
            header, body, footer = match.groups()
            # Clean out any existing variants of these members (u8 or char, scalar or array)
            body = re.sub(r'.*lastStatus.*;\n?', '', body)
            body = re.sub(r'.*curBUPtr.*;\n?', '', body)
            body = re.sub(r'.*curPtr.*;\n?', '', body)
            
            # Inject clean fields
            new_body = body.rstrip() + "\n" + bk_fields
            print(f"✅ Applied patch to {struct_name}")
            return text[:match.start()] + header + new_body + footer + text[match.end():]
        
        print(f"⚠️ Warning: Could not find struct definition for {struct_name}")
        return text

    # Apply to the primary structures used by cseq.c
    content = apply_patch(content, "ALCSeq")
    content = apply_patch(content, "ALCSeqMarker")

    with open(header_path, 'w') as f:
        f.write(content)

    # Verification Step
    if "lastStatus[16]" in open(header_path).read():
        print("🚀 Patch Verified: lastStatus array is present in n64_types.h")
    else:
        print("❌ Patch Failed: lastStatus not found after write!")

if __name__ == '__main__':
    patch_audio_engine()
