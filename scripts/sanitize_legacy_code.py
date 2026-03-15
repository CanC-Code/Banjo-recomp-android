import os
import re
import sys

TARGET_DIRS = ["src", "include"]

# Expanded to include more standard types and common collision points
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
    r"\bcalloc\b": "n64_calloc",
    r"\bsprintf\b": "n64_sprintf",
    r"\bprintf\b": "n64_printf",
    r"\bsin\b": "n64_sin",
    r"\bcos\b": "n64_cos",
}

def fix_linkage_conflicts(content):
    # 1. Improved Regex for static function implementations
    static_func_pattern = re.compile(
        r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\)\s*)\{", 
        re.MULTILINE
    )

    matches = static_func_pattern.findall(content)
    if not matches:
        return content

    signatures = []
    # Use a set to track already declared signatures to prevent duplicates
    existing_decls = set(re.findall(r"^static\s+.*?;", content, re.MULTILINE))

    for full_sig, func_name in matches:
        decl = f"{full_sig.strip()};"
        if decl not in existing_decls:
            signatures.append(decl)
            existing_decls.add(decl)

    # 2. Fix mismatched non-static declarations
    for _, func_name in matches:
        mismatch_pattern = rf"^(?!\s)(?<!static\s)([\w\s\*]*?\b{func_name}\b\s*\([^)]*\)\s*;)"
        content = re.sub(mismatch_pattern, r"static \1", content, flags=re.MULTILINE)

    # 3. SELF-REPAIR: Remove 'static' from accidental matches on calls/indented lines
    content = re.sub(r"^[ \t]+static\s+", "    ", content, flags=re.MULTILINE)

    # 4. Smart Forward Declaration Placement
    if signatures:
        header_block = "\n/* Automated Forward Decls */\n" + "\n".join(signatures) + "\n"

        # Prefer placing after the last #include, otherwise at the top
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        if includes:
            last_include_pos = includes[-1].end()
            content = content[:last_include_pos] + "\n" + header_block + content[last_include_pos:]
        else:
            content = header_block + "\n" + content

    return content

def sanitize_codebase(root_path):
    print(f"扫 Scanning: {root_path}")
    patch_count = 0

    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): 
            continue

        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename.endswith('.c') or filename.endswith('.h')):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                except Exception as e:
                    print(f"  [Error Reading] {filepath}: {e}")
                    continue

                original_content = "".join(lines)
                new_lines = []
                modified_tokens = False

                for line in lines:
                    # 🛡️ PROTECTION: Do not apply replacements to include directives
                    # This prevents #include "bool.h" from becoming #include "n64_bool.h"
                    if line.strip().startswith("#include"):
                        new_lines.append(line)
                        continue
                    
                    original_line = line
                    for pattern, replacement in TOKEN_REPLACEMENTS.items():
                        line = re.sub(pattern, replacement, line)
                    
                    if line != original_line:
                        modified_tokens = True
                    new_lines.append(line)

                content = "".join(new_lines)

                # Apply Linkage Fixes (C files only)
                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")

    print(f"✅ Sanitization Complete! {patch_count} files modified.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
