import os
import re

def fix_unterminated_directives():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        print(f"File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Strip comments to avoid false positives in counts
    # Strips /* block */ and // line comments
    clean_content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    clean_content = re.sub(r'//.*', '', clean_content)

    # 2. Count opening vs closing directives
    # We count #if, #ifdef, and #ifndef as openers
    open_count = len(re.findall(r'^\s*#(?:if|ifdef|ifndef)\b', clean_content, flags=re.MULTILINE))
    close_count = len(re.findall(r'^\s*#endif\b', clean_content, flags=re.MULTILINE))

    diff = open_count - close_count

    if diff > 0:
        print(f"⚠️ Found {diff} unterminated directive(s). Repairing...")
        
        # Ensure we don't append to a line that already has text
        if not content.endswith('\n'):
            content += '\n'
            
        # Append the missing terminators
        for i in range(diff):
            content += f"#endif /* BKA_AUTO_CLOSE_{i} */\n"
            
        with open(header_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ n64_types.h is now balanced.")

    elif diff < 0:
        # Extra endifs usually happen if a script injected content AFTER the final guard.
        # This is dangerous as it can terminate the header early.
        print(f"⚠️ Warning: Found {abs(diff)} extra #endif directives. File may be malformed.")
    else:
        # Check if the very last non-empty line is an #endif
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if lines and not lines[-1].startswith('#endif'):
            print("🧐 Balance is correct, but file does not end with #endif. Checking structure...")
        else:
            print("✅ n64_types.h directives are balanced and correctly terminated.")

if __name__ == '__main__':
    fix_unterminated_directives()
