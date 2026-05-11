import os
import yaml
import struct
import sys

def parse_splat_yaml(yaml_path):
    """
    Parses the Splat YAML and extracts segment/subsegment data.
    Now calculates ROM limits to prevent 0-size assets.
    """
    if not os.path.exists(yaml_path):
        # Fail the GitHub Action if the file is missing instead of skipping silently
        print(f"ERROR: Critical file missing: {yaml_path}")
        sys.exit(1)

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    asset_entries = []
    segments = config.get('segments', [])
    
    # We need the absolute end of the ROM or the last segment to calculate the final size
    rom_end = 0

    for seg in segments:
        if isinstance(seg, dict):
            # Track the furthest point in the ROM
            seg_start = seg.get('start', 0)
            if isinstance(seg_start, int) and seg_start > rom_end:
                rom_end = seg_start
            
            subsegments = seg.get('subsegments', [])
            for sub in subsegments:
                # Splat format: [rom_offset, type, name]
                if isinstance(sub, list) and len(sub) >= 3:
                    offset = sub[0]
                    # Ensure we don't crash on non-integer offsets
                    if not isinstance(offset, int):
                        continue
                        
                    asset_entries.append({
                        'offset': offset,
                        'type': str(sub[1])[:7],
                        # Use the full name here; truncation happens at the binary write stage
                        'name': str(sub[2])
                    })

    if not asset_entries:
        print(f"ERROR: No assets found in {yaml_path}")
        sys.exit(1)

    # Sort by offset is mandatory for size calculation
    asset_entries.sort(key=lambda x: x['offset'])
    
    # If rom_end wasn't explicitly larger than the last offset, 
    # we use a safe buffer or the end of the last segment.
    if rom_end <= asset_entries[-1]['offset']:
        # Fallback: assume at least 1KB for the last asset if unknown
        rom_end = asset_entries[-1]['offset'] + 0x1000 

    return asset_entries, rom_end

def write_binary_manifest(entries, rom_end, output_path):
    """
    Writes a 48-byte fixed-width binary manifest.
    Structure: Offset(4), Size(4), Name(32), Type(8)
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'wb') as f:
        # Header: Entry Count (4 bytes, Little Endian)
        f.write(struct.pack('<I', len(entries)))

        for i in range(len(entries)):
            entry = entries[i]
            offset = entry['offset']

            # Size calculation logic
            if i < len(entries) - 1:
                size = entries[i+1]['offset'] - offset
            else:
                # Fix for the "Size 0" crash: Calculate against the ROM end
                size = rom_end - offset

            # Safety check: if size is still 0 or negative, provide a 4-byte padding size
            if size <= 0:
                size = 4

            # Encode and Pad strings
            # We use 'replace' to handle non-ascii chars and ensure null termination
            name_bytes = entry['name'].encode('ascii', 'replace')[:31]
            name_bin = name_bytes.ljust(32, b'\0')
            
            type_bytes = entry['type'].encode('ascii', 'replace')[:7]
            type_bin = type_bytes.ljust(8, b'\0')

            # Format: Offset(I), Size(I), Name(32s), Type(8s) = 48 bytes
            try:
                f.write(struct.pack('<II32s8s', offset, size, name_bin, type_bin))
            except struct.error as e:
                print(f"Padding error on asset {entry['name']}: {e}")
                sys.exit(1)

    print(f"SUCCESS: Generated {output_path}")
    print(f"  - Count: {len(entries)} entries")
    print(f"  - Table Size: {os.path.getsize(output_path)} bytes")

def main():
    # Base directory is one level up from the scripts folder
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    configs = [
        ("decompressed.us.v10.yaml", "Android/app/src/main/assets/manifest_us.bin"),
        ("decompressed.pal.yaml", "Android/app/src/main/assets/manifest_pal.bin")
    ]

    for yaml_name, bin_name in configs:
        yaml_path = os.path.join(base_dir, yaml_name)
        bin_path = os.path.join(base_dir, bin_name)
        
        print(f"Processing {yaml_name}...")
        entries, rom_end = parse_splat_yaml(yaml_path)
        write_binary_manifest(entries, rom_end, bin_path)

if __name__ == "__main__":
    main()
