import os
import re
import sys

TARGET_DIRS = ["src", "include"]

TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "TRUE",
    r"\bfalse\b": "FALSE",
    r"\bstrcat\b": "n64_strcat",
    r"\bstrcpy\b": "n64_strcpy",
    r"\bstrlen\b": "n64_strlen",
    r"\bmemcpy\b": "n64_memcpy",
    r"\bmemmove\b": "n64_memmove",
    r"\bmalloc\b": "n64_malloc",
    r"\bfree\b": "n64_free",
    r"\brealloc\b": "n64_realloc",
    r"\bcalloc\b": "n64_calloc"
}

def fix_linkage_conflicts(content):
    # 1. Find all static function implementations
    static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\))\s*\{", re.MULTILINE)
    matches = static_func_pattern.findall(content)
    
    if not matches:
        return content

    signatures = []
    for full_sig, func_name in matches:
        decl = f"{full_sig};"
        if decl not in content:
            signatures.append(decl)

    # 2. Fix mismatched non-static declarations (ONLY if they start at Column 1)
    for _, func_name in matches:
        # This regex now requires the line to start with a non-space character (\S)
        # preventing it from matching indented function calls.
        mismatch_pattern = rf"^(?<!static\s)(\S[\w\s\*]*?\b{func_name}\b\s*\([^)]*\)\s*;)"
        content = re.sub(mismatch_pattern, f"static \\1", content, flags=re.MULTILINE)

    # 3. SELF-REPAIR: Clean up mangled calls from the previous script run
    # If a line starts with 'static' followed by indentation, it's a mistake.
    content = re.sub(r"^static\s+(\s+\w+\s*\(.*?\)\s*;)", r"\1", content, flags=re.MULTILINE)

    # 4. Insert forward declarations
    if signatures:
        header_block = "\n".join(signatures)
        include_end = content.rfind("#include")
        if include_end != -1:
            line_end = content.find("\n", include_end)
            content = content[:line_end] + "\n\n/* Automated Forward Decls */\n" + header_block + content[line_end:]
        else:
            content = "/* Automated Forward Decls */\n" + header_block + "\n\n" + content

    return content

def sanitize_codebase(root_path):
    print("🧹 Starting Safe Code Sanitization...")
    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue

        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename.endswith('.c') or filename.endswith('.h')):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception: continue

                original_content = content

                for pattern, replacement in TOKEN_REPLACEMENTS.items():
                    content = re.sub(pattern, replacement, content)

                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1

    print(f"✅ Sanitization Complete! Patched/Repaired {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
