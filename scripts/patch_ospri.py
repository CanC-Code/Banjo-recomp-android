import os

def patch_ospri():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    if "typedef s32 OSPri;" not in content and "typedef int OSPri;" not in content:
        # Define OSPri as an s32 (which is typically typedef'd earlier in n64_types.h)
        type_def = "\n/* Injected OSPri for libultra compatibility */\ntypedef s32 OSPri;\n"
        
        # Inject it right before the final #endif
        last_endif_idx = content.rfind('#endif')
        
        if last_endif_idx != -1:
            content = content[:last_endif_idx] + type_def + "\n" + content[last_endif_idx:]
        else:
            content += type_def

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ Successfully injected OSPri definition into n64_types.h")
    else:
        print("✅ OSPri definition is already present.")

if __name__ == '__main__':
    patch_ospri()
