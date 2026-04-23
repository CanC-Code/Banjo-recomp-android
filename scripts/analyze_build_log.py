import sys
import os

def analyze_log(log_path, context_lines=20):
    if not os.path.exists(log_path):
        print(f"❌ Error: Log file '{log_path}' not found.")
        return

    # Read the log file, ignoring weird characters that sometimes come from Ninja/Clang
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # The specific keywords that indicate a compiler or build system crash
    keywords = [
        'FAILED:', 
        'fatal error:', 
        'error:', 
        'FAILURE: Build failed', 
        'Exception:',
        'undefined reference to'
    ]
    
    match_indices = []

    # Find every line that contains a failure keyword
    for i, line in enumerate(lines):
        if any(keyword in line for keyword in keywords):
            match_indices.append(i)

    if not match_indices:
        print("✅ No obvious error keywords found in the log.")
        return

    # Create a set of line numbers to keep (this automatically handles overlapping windows)
    lines_to_keep = set()
    for idx in match_indices:
        start = max(0, idx - context_lines)
        end = min(len(lines), idx + context_lines + 1)
        lines_to_keep.update(range(start, end))

    # Sort the line numbers so the output is chronological
    sorted_lines = sorted(list(lines_to_keep))

    summary = []
    summary.append("=" * 80 + "\n")
    summary.append(f"🚨 BUILD FAILURE SUMMARY (Found {len(match_indices)} error triggers) 🚨\n")
    summary.append("=" * 80 + "\n\n")

    last_idx = -2
    for idx in sorted_lines:
        # If there is a jump in line numbers, insert a clear separator
        if last_idx != -2 and idx != last_idx + 1:
            summary.append("\n" + "-" * 30 + " [SNIP / CONTINUED LATER IN LOG] " + "-" * 30 + "\n\n")
        
        # Format: [Line Number] | Log Text
        summary.append(f"{idx + 1:5d} | {lines[idx]}")
        last_idx = idx

    summary_text = "".join(summary)

    # Print to the GitHub Actions console
    print(summary_text)

    # Save to an artifact file
    summary_path = "build_failure_summary.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"\n💾 Saved condensed summary to {summary_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_build_log.py <path_to_log>")
        sys.exit(1)
    analyze_log(sys.argv[1])
