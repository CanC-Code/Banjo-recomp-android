import os
import subprocess
import time
from source_conversion import SourceConverter
from error_parser import generate_failed_log, read_file

LOG_FILE = "Android/full_build_log.txt"

def main():
    converter = SourceConverter()
    intelligence_level = 1
    
    for cycle in range(1, 401):
        print(f"\n[Cycle {cycle}] Intelligence: {intelligence_level}")
        
        # 1. Bootstrap essential headers
        converter.bootstrap_n64_types()
        
        # 2. Run Build
        # (Use your existing run_build() function here)
        success = run_build_logic() 
        
        if success:
            print("🎯 Build Success!")
            break
            
        # 3. Analyze Failures
        log_data = read_file(LOG_FILE)
        failed_files = generate_failed_log(log_data)
        
        # 4. Load Logic and Patch
        converter.load_logic(intelligence_level)
        total_fixes = 0
        for fp in failed_files:
            # We pass the full log as context so the converter knows which rule to pick
            total_fixes += converter.apply_to_file(fp, error_context=log_data)
            
        if total_fixes == 0:
            if intelligence_level < 2:
                print("🧠 No fixes found. Escalating to Intelligence Level 2...")
                intelligence_level += 1
            else:
                print("🛑 Stalled. Manual intervention required for remaining errors.")
                break
        
        time.sleep(1)

if __name__ == "__main__":
    main()
