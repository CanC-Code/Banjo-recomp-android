import os
import re
import json
from pathlib import Path

def scan_n64_codebase():
    root = Path.cwd().resolve()
    
    # We only care about the pristine source and includes
    target_dirs = ['include', 'src']
    
    database = {
        "system_includes": set(),
        "local_includes": set(),
        "primitive_typedefs": set(),
        "struct_union_typedefs": set()
    }
    
    print("=== STARTING READ-ONLY AST SCAN ===")
    
    for d in target_dirs:
        dir_path = root / d
        if not dir_path.exists(): 
            continue
        
        for path in dir_path.rglob("*.[ch]"):
            try:
                content = path.read_text(errors='ignore')
                
                # 1. System Includes: <math.h>, <string.h>
                sys_incs = re.findall(r'#include\s+<([^>]+)>', content)
                database["system_includes"].update(sys_incs)
                
                # 2. Local Includes: "PR/gbi.h"
                loc_incs = re.findall(r'#include\s+"([^"]+)"', content)
                database["local_includes"].update(loc_incs)
                
                # 3. Primitive Typedefs: typedef void* OSTask;
                prim_tds = re.findall(r'typedef\s+(?!struct|union|enum)([\w\s\*]+?)\s+(\w+)\s*;', content)
                for td_type, td_alias in prim_tds:
                    database["primitive_typedefs"].add(td_alias.strip())
                    
                # 4. Struct/Union Typedefs: typedef struct { ... } MtxF;
                # Matches the alias at the end of the block.
                struct_tds = re.findall(r'typedef\s+(?:struct|union).*?\}\s*(\w+)\s*;', content, re.DOTALL)
                database["struct_union_typedefs"].update(struct_tds)
                
            except Exception as e:
                pass

    # Convert sets to sorted lists for clean JSON serialization
    report = {k: sorted(list(v)) for k, v in database.items()}
    
    out_file = root / "n64_ast_requirements.json"
    with open(out_file, 'w') as f:
        json.dump(report, f, indent=4)
    
    print(f"--- SCAN COMPLETE ---")
    print(f"System Includes requested:      {len(report['system_includes'])}")
    print(f"Local Includes mapped:          {len(report['local_includes'])}")
    print(f"Primitive Typedefs discovered:  {len(report['primitive_typedefs'])}")
    print(f"Struct/Union Models mapped:     {len(report['struct_union_typedefs'])}")
    print(f"-> Report saved to: {out_file.name}\n")

if __name__ == "__main__":
    scan_n64_codebase()
