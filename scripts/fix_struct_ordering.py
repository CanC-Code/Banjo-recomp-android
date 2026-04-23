import os
import re

def fix_struct_ordering(directory):
    print(f"📐 Reordering structs, enums, and unions in {directory}...")
    match_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            # Only process .c files
            if file.endswith('.c'):
                filepath = os.path.join(root, file)

                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()

                types = []
                new_text = ""
                idx = 0
                changed = False

                while idx < len(text):
                    # Find struct, enum, OR union definitions.
                    match = re.search(r'\b((?:typedef\s+)?(?:struct|enum|union)\b[^{;=()]*)\{', text[idx:])
                    if not match:
                        new_text += text[idx:]
                        break

                    start = idx + match.start()
                    new_text += text[idx:start]

                    brace_start = idx + match.end() - 1
                    
                    # Robust brace matching that ignores comments and strings
                    count = 0
                    in_string = False
                    in_char = False
                    in_line_comment = False
                    in_block_comment = False
                    brace_end = -1
                    
                    for i in range(brace_start, len(text)):
                        if in_string:
                            if text[i] == '"' and text[i-1] != '\\': in_string = False
                        elif in_char:
                            if text[i] == "'" and text[i-1] != '\\': in_char = False
                        elif in_line_comment:
                            if text[i] == '\n': in_line_comment = False
                        elif in_block_comment:
                            if text[i-1:i+1] == '*/': in_block_comment = False
                        else:
                            if text[i:i+2] == '//': in_line_comment = True
                            elif text[i:i+2] == '/*': in_block_comment = True
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
                        # Ensure we found a semicolon and it belongs strictly to the block
                        if semi_end != -1 and (semi_end - brace_end) < 100:
                            tail = text[brace_end+1:semi_end].strip()
                            is_typedef = "typedef" in text[start:start+20]
                            
                            # If it's NOT a typedef, and the tail contains variable names, DO NOT hoist it!
                            # We only want to hoist true type definitions, not inline variable declarations.
                            if not is_typedef and tail != "" and not tail.startswith('__attribute__'):
                                new_text += text[start:brace_end+1]
                                idx = brace_end + 1
                            else:
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

                    # Hoist all genuine types to the top
                    final_text = top_part + "\n/* AUTO-HOISTED TYPES */\n" + "\n\n".join(types) + "\n" + bottom_part

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(final_text)
                    match_count += 1
                    print(f"  🏗️ Reordered types in: {filepath}")

    print(f"✅ Finished reordering {match_count} files.")

if __name__ == '__main__':
    fix_struct_ordering('src')
