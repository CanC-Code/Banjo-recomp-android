import os
import sys
import subprocess

def run_magick(args):
    """Fallback logic for environments using ImageMagick 6 (convert) or 7 (magick)."""
    try:
        # Try convert first for Ubuntu/Debian runners
        subprocess.run(["convert"] + args, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            subprocess.run(["magick"] + args, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"Error: ImageMagick command failed: {e}")
            sys.exit(1)

def generate_icons(source_path):
    icon_specs = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192
    }

    res_dir = "Android/app/src/main/res"

    if not os.path.exists(source_path):
        print(f"Error: Source file {source_path} not found.")
        return

    for folder, size in icon_specs.items():
        target_dir = os.path.join(res_dir, folder)
        os.makedirs(target_dir, exist_ok=True)

        # 1. Standard ic_launcher.png
        # We fill the square then crop to ensure 1:1 ratio
        standard_path = os.path.join(target_dir, "ic_launcher.png")
        run_magick([
            source_path,
            "-resize", f"{size}x{size}^",
            "-gravity", "center",
            "-extent", f"{size}x{size}",
            "-unsharp", "0x1",
            standard_path
        ])

        # 2. Round ic_launcher_round.png
        # Uses a high-compatibility masking technique
        round_path = os.path.join(target_dir, "ic_launcher_round.png")
        radius = size / 2
        run_magick([
            source_path,
            "-resize", f"{size}x{size}^",
            "-gravity", "center",
            "-extent", f"{size}x{size}",
            "(", "+clone", "-alpha", "extract", "-threshold", "0", 
            "-draw", f"fill black polygon 0,0 0,{size} {size},{size} {size},0 fill white circle {radius},{radius} {radius},0", 
            ")", "-alpha", "off", "-compose", "CopyOpacity", "-composite",
            round_path
        ])
        
        print(f"✓ Created {size}px icons in {folder}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_icons.py <master_image>")
    else:
        generate_icons(sys.argv[1])
