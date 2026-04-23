import os
import yaml
import struct

def parse_splat_yaml(yaml_path):
    if not os.path.exists(yaml_path):
        print(f"Skipping {yaml_path}: File not found")
        return []

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    asset_entries = []
    # Splat YAMLs organize data under 'segments'
    segments = config.get('segments', [])

    for seg in segments:
        if isinstance(seg, dict):
            subsegments = seg.get('subsegments', [])
            for sub in subsegments:
                # Standard Splat format: [rom_offset, type, name]
                if isinstance(sub, list) and len(sub) >= 3:
                    offset = sub[0]
                    # Filter out non-asset types if necessary
                    asset_entries.append({
                        'offset': offset,
                        'type': str(sub[1])[:7],
                        'name': str(sub[2])[:31]
                    })

    # Sort by offset is mandatory for size calculation
    asset_entries.sort(key=lambda x: x['offset'])
    return asset_entries

def write_binary_manifest(entries, output_path):
    if not entries:
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'wb') as f:
        # Header: Entry Count (4 bytes)
        f.write(struct.pack('<I', len(entries)))

        for i in range(len(entries)):
            entry = entries[i]
            offset = entry['offset']

            # Size = Next offset - Current offset
            if i < len(entries) - 1:
                size = entries[i+1]['offset'] - offset
            else:
                # Last asset: often we don't know the end of the ROM here, 
                # so we set it to 0 and handle it in C++ if needed.
                size = 0 

            name_bin = entry['name'].encode('ascii', 'ignore').ljust(32, b'\0')
            type_bin = entry['type'].encode('ascii', 'ignore').ljust(8, b'\0')

            # Format: Offset(I), Size(I), Name(32s), Type(8s) = 48 bytes
            f.write(struct.pack('<II32s8s', offset, size, name_bin, type_bin))

    print(f"Successfully generated {output_path} with {len(entries)} entries.")

def main():
    # Adjusted paths for your workflow structure
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Generate for US and PAL
    configs = [
        ("decompressed.us.v10.yaml", "Android/app/src/main/assets/manifest_us.bin"),
        ("decompressed.pal.yaml", "Android/app/src/main/assets/manifest_pal.bin")
    ]

    for yaml_name, bin_name in configs:
        yaml_path = os.path.join(base_dir, yaml_name)
        bin_path = os.path.join(base_dir, bin_name)
        write_binary_manifest(parse_splat_yaml(yaml_path), bin_path)

if __name__ == "__main__":
    main()