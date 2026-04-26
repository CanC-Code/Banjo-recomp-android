import os
import re

def fix_unterminated_directives():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        print(f"File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # Strip comments temporarily to accurately count preprocessor directives
    # Match block comments /* ... */ and line comments // ...
    content_no_comments = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content_no_comments = re.sub(r'//.*', '', content_no_comments)

    # Count opening and closing conditional directives
    open_directives = len(re.findall(r'^\s*#(?:if|ifdef|ifndef)\b', content_no_comments, flags=re.MULTILINE))
    close_directives = len(re.findall(r'^\s*#endif\b', content_no_comments, flags=re.MULTILINE))

    missing_endifs = open_directives - close_directives

    if missing_endifs > 0:
        print(f"Found {missing_endifs} unterminated conditional directive(s). Appending #endif...")
        with open(header_path, 'a') as f:
            f.write('\n' + '#endif /* Auto-closed by script */\n' * missing_endifs)
        print("✅ n64_types.h include guards have been properly closed.")
    elif missing_endifs < 0:
        print(f"Warning: Found {-missing_endifs} extra #endif directives.")
    else:
        print("✅ Directives are already balanced.")

if __name__ == '__main__':
    fix_unterminated_directives()
