import os
import re

def fix_struct_ordering(directory):
    print(f"📐 Reordering structs and enums in {directory}...")
    match_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.c') or file.endswith('.h'):
                filepath = os.path.join(root, file)

                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()

                types = []
                new_text = ""
                idx = 0
                changed = False

                while idx < len(text):
                    # Find struct or enum definitions, avoiding variable assignments (=)
                    match = re.search(r'\b((?:typedef\s+)?(?:struct|enum)\b[^{;=]*)\{', text[idx:])
                    if not match:
                        new_text += text[idx:]
                        break

                    start = idx + match.start()
                    new_text += text[idx:start]

                    brace_start = idx + match.end() - 1
                    brace_count = 0
                    brace_end = -1

                    # Smart brace matching to extract the entire struct safely
                    for i in range(brace_start, len(text)):
                        if text[i] == '{':
                            brace_count += 1
                        elif text[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                brace_end = i
                                break

                    if brace_end != -1:
                        semi_end = text.find(';', brace_end)
                        # Ensure we found a semicolon and it belongs to the struct (distance < 50 chars)
                        if semi_end != -1 and (semi_end - brace_end) < 50:
                            type_def = text[start:semi_end+1]
                            types.append(type_def)
                            idx = semi_end + 1
                            changed = True
                        else:
                            new_text += text[start:brace_end+1]
                            idx = brace_end + 1
                    else:
                        new_text += text[start:]
                        break

                if changed and types:
                    # Find the last #include so we can insert safely beneath them
                    last_include_end = 0
                    for m in re.finditer(r'#include\s+.*?\n', new_text):
                        last_include_end = m.end()

                    top_part = new_text[:last_include_end]
                    bottom_part = new_text[last_include_end:]

                    # Hoist all types to the top
                    final_text = top_part + "\n/* AUTO-HOISTED TYPES */\n" + "\n\n".join(types) + "\n" + bottom_part

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(final_text)
                    match_count += 1
                    print(f"  🏗️ Reordered types in: {filepath}")

    print(f"✅ Finished reordering {match_count} files.")

if __name__ == '__main__':
    fix_struct_ordering('src')
