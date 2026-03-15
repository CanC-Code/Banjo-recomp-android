 import os
import re
import sys

# Directories to process within the root path
TARGET_DIRS = ["src", "include"]

# Symbols to namespace to avoid collisions with standard library and modern headers
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
    """
    Ensures static functions have forward declarations and fixes linkage 
    mismatches to avoid 'conflicting types' or 'missing prototype' errors.
    """
    # 1. Identify static function implementations
    static_func_pattern = re.compile(
        r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\)\s*)\{", 
        re.MULTILINE
    )

    matches = static_func_pattern.findall(content)
    if not matches:
        return content

    signatures = []
    # Track existing declarations to avoid duplicate prototypes
    existing_decls = set(re.findall(r"^static\s+.*?;", content, re.MULTILINE))

    for full_sig, func_name in matches:
        decl = f"{full_sig.strip()};"
        if decl not in existing_decls:
            signatures.append(decl)
            existing_decls.add(decl)

    # 2. Convert non-static declarations of these functions to static
    for _, func_name in matches:
        mismatch_pattern = rf"^(?!\s)(?<!static\s)([\w\s\*]*?\b{func_name}\b\s*\([^)]*\)\s*;)"
        content = re.sub(mismatch_pattern, r"static \1", content, flags=re.MULTILINE)

    # 3. Cleanup: Remove 'static' if it was accidentally prepended to indented calls
    content = re.sub(r"^[ \t]+static\s+", "    ", content, flags=re.MULTILINE)

    # 4. Insert Forward Declarations after the last #include
    if signatures:
        header_block = "\n/* Automated Forward Decls */\n" + "\n".join(signatures) + "\n"
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        if includes:
            last_include_pos = includes[-1].end()
            content = content[:last_include_pos] + "\n" + header_block + content[last_include_pos:]
        else:
            content = header_block + "\n" + content

    return content

def sanitize_codebase(root_path):
    """
    Walks the codebase and applies token replacements and linkage fixes.
    """
    print(f"🧹 Scanning for sanitization: {root_path}")
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
                    # 🛡️ PROTECTION: Skip renaming if the line is an include directive.
                    # This prevents #include "bool.h" from becoming #include "n64_bool.h".
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

                # Linkage repairs are primarily for implementation (.c) files
                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")

    print(f"✅ Sanitization Complete! {patch_count} files modified.")

if __name__ == "__main__":
    # Use provided argument or default to current directory
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
