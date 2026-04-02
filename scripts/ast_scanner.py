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
        "forward_declarations": set(),
        "struct_union_enum_typedefs": set(),
        "func_pointer_typedefs": set()
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

                # 3. Primitive Typedefs: typedef unsigned long long u64;
                # (Negative lookahead prevents it from matching structs/unions/enums)
                prim_tds = re.findall(r'typedef\s+(?!struct|union|enum)([\w\s\*]+?)\s+(\w+)\s*;', content)
                for td_type, td_alias in prim_tds:
                    # Ignore function pointers that accidentally partial-match
                    if '(' not in td_type and ')' not in td_type:
                        database["primitive_typedefs"].add(td_alias.strip())

                # 4. Function Pointers: typedef void (*OSTimerFunc)(void);
                func_tds = re.findall(r'typedef\s+[\w\s\*]+\s*\(\s*\*\s*(\w+)\s*\)\s*\(.*?\)\s*;', content)
                database["func_pointer_typedefs"].update(func_tds)

                # 5. Forward Declarations: typedef struct ch_vegatable sChVegetable;
                fwd_tds = re.findall(r'typedef\s+(?:struct|union|enum)\s+\w+\s+(\w+)\s*;', content)
                database["forward_declarations"].update(fwd_tds)

                # 6. Struct/Union/Enum with braces: typedef struct { ... } MtxF;
                # Modified to include Enums, and safely extract the alias at the end.
                struct_tds = re.findall(r'typedef\s+(?:struct|union|enum)[^;]*?\}\s*(\w+)\s*;', content, re.DOTALL)
                database["struct_union_enum_typedefs"].update(struct_tds)

            except Exception as e:
                pass

    # Convert sets to sorted lists for clean JSON serialization
    report = {k: sorted(list(v)) for k, v in database.items()}

    out_file = root / "n64_ast_requirements.json"
    with open(out_file, 'w') as f:
        json.dump(report, f, indent=4)

    # Calculate total types found
    total_types = (len(report['primitive_typedefs']) + 
                   len(report['forward_declarations']) + 
                   len(report['struct_union_enum_typedefs']) + 
                   len(report['func_pointer_typedefs']))

    print(f"--- SCAN COMPLETE ---")
    print(f"System Includes requested:      {len(report['system_includes'])}")
    print(f"Local Includes mapped:          {len(report['local_includes'])}")
    print(f"Primitive Typedefs discovered:  {len(report['primitive_typedefs'])}")
    print(f"Forward Declarations mapped:    {len(report['forward_declarations'])}")
    print(f"Func Pointer Typedefs mapped:   {len(report['func_pointer_typedefs'])}")
    print(f"Struct/Union/Enums mapped:      {len(report['struct_union_enum_typedefs'])}")
    print(f"-----------------------------------")
    print(f"Total Types Discovered:         {total_types}")
    print(f"-> Report saved to: {out_file.name}\n")

if __name__ == "__main__":
    scan_n64_codebase()
