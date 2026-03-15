import os
import re
import sys

TARGET_DIRS = ["src", "include"]

FILE_RENAMES = {
    "bool.h": "n64_bool.h",
    "string.h": "n64_string.h",
    "time.h": "n64_time.h",
    "math.h": "n64_math.h",
    "stdlib.h": "n64_stdlib.h",
    "stddef.h": "n64_stddef.h",
    "stdarg.h": "n64_stdarg.h",
    "stdio.h": "n64_stdio.h",
    "sched.h": "n64_sched.h"
}

TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "TRUE",
    r"\bfalse\b": "FALSE",
    r"\bTRUE\b": "TRUE",
    r"\bFALSE\b": "FALSE",
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
    """
    Finds static function definitions and ensures a static forward 
    declaration exists at the top of the file to prevent implicit 
    declaration errors in Clang.
    """
    # 1. Find all static function implementations: static return_type func_name(args) {
    # This regex captures the signature up to the opening brace
    static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\))\s*\{", re.MULTILINE)
    matches = static_func_pattern.findall(content)
    
    if not matches:
        return content

    signatures = []
    for full_sig, func_name in matches:
        # Avoid duplicating existing forward declarations
        decl = f"{full_sig};"
        if decl not in content:
            signatures.append(decl)

    if not signatures:
        return content

    # 2. Fix mismatched non-static declarations (the code_BF0.c error)
    # If we find "void func();" but it's actually "static void func() {"
    for full_sig, func_name in matches:
        # Look for the same signature WITHOUT 'static' ending in a semicolon
        mismatch_pattern = rf"^(?<!static\s)([\w\s\*]+?\b{func_name}\b\s*\([^)]*\)\s*;)"
        content = re.sub(mismatch_pattern, f"static \\1", content, flags=re.MULTILINE)

    # 3. Insert new forward declarations after the last #include
    header_block = "\n".join(signatures)
    include_end = content.rfind("#include")
    if include_end != -1:
        # Find the end of that line
        line_end = content.find("\n", include_end)
        content = content[:line_end] + "\n\n/* Automated Forward Decls */\n" + header_block + content[line_end:]
    else:
        content = "/* Automated Forward Decls */\n" + header_block + "\n\n" + content

    return content

def sanitize_codebase(root_path):
    print("🧹 Starting Legacy Code Sanitization...")

    # Handle File Renames
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if filename in FILE_RENAMES:
                    old_file = os.path.join(root, filename)
                    new_file = os.path.join(root, FILE_RENAMES[filename])
                    os.rename(old_file, new_file)
                    print(f"  [Renamed] {old_file} -> {new_file}")

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

                # Apply standard token/include replacements
                for old_file, new_file in FILE_RENAMES.items():
                    content = re.sub(rf'#include\s+["<]{old_file}[">]', f'#include "{new_file}"', content)

                for pattern, replacement in TOKEN_REPLACEMENTS.items():
                    content = re.sub(pattern, replacement, content)

                # NEW: Fix Linkage (Only for .c files)
                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1

    print(f"✅ Sanitization Complete! Patched {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
