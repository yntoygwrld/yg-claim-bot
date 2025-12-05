#!/usr/bin/env python3
"""
MP4 XMP Injector
Directly replaces XMP metadata in MP4 files with fake realistic metadata
NO re-encoding required - pure binary manipulation
"""

import struct
import os
import shutil
from typing import Tuple, Optional

# XMP UUID identifier used in MP4 files
XMP_UUID = b'\xbe\x7a\xcf\xcb\x97\xa9\x42\xe8\x9c\x71\x99\x94\x91\xe3\xaf\xac'


def find_xmp_box(data: bytes) -> Optional[Tuple[int, int, int, int]]:
    """
    Find XMP UUID box in MP4 file data

    Returns: (box_start, box_size, xmp_content_start, xmp_content_end) or None
    """
    pos = 0
    while pos < len(data) - 8:
        # Read box size (big endian 32-bit)
        size = struct.unpack('>I', data[pos:pos+4])[0]
        box_type = data[pos+4:pos+8]

        if size == 0:
            # Box extends to end of file
            size = len(data) - pos
        elif size == 1:
            # 64-bit extended size
            if pos + 16 > len(data):
                break
            size = struct.unpack('>Q', data[pos+8:pos+16])[0]

        if size < 8:
            break

        if box_type == b'uuid':
            uuid_val = data[pos+8:pos+24]
            if uuid_val == XMP_UUID:
                xmp_start = pos + 24  # After UUID header
                xmp_end = pos + size
                return (pos, size, xmp_start, xmp_end)

        pos += size

    return None


def replace_xmp_in_mp4(input_path: str, output_path: str, new_xmp: str) -> bool:
    """
    Replace XMP metadata in MP4 file with new XMP content

    Args:
        input_path: Path to source MP4 file
        output_path: Path to output MP4 file
        new_xmp: New XMP XML string to inject

    Returns: True on success, False on failure
    """
    # Read entire file
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())

    # Find existing XMP box
    result = find_xmp_box(data)
    if result is None:
        print("❌ No XMP UUID box found in file")
        return False

    box_start, box_size, xmp_start, xmp_end = result
    old_xmp_size = xmp_end - xmp_start

    print(f"📍 Found XMP box at position {box_start}")
    print(f"   Old XMP size: {old_xmp_size} bytes")

    # Encode new XMP
    new_xmp_bytes = new_xmp.encode('utf-8')
    new_xmp_size = len(new_xmp_bytes)

    print(f"   New XMP size: {new_xmp_size} bytes")

    # Calculate size difference
    size_diff = new_xmp_size - old_xmp_size

    # Method depends on size difference
    if size_diff == 0:
        # Same size - just replace bytes
        print("   ✅ Same size - direct replacement")
        data[xmp_start:xmp_end] = new_xmp_bytes

    else:
        # Different size - need to rebuild file structure
        print(f"   ⚠️ Size difference: {size_diff:+d} bytes")

        # Build new file:
        # 1. Everything before XMP content
        # 2. New XMP content
        # 3. Everything after old XMP content

        # Update box size in header
        new_box_size = 24 + new_xmp_size  # 8 (size+type) + 16 (UUID) + content

        # Create new data
        new_data = bytearray()

        # Everything before the box size field
        new_data.extend(data[:box_start])

        # New box size (32-bit big endian)
        new_data.extend(struct.pack('>I', new_box_size))

        # Box type 'uuid'
        new_data.extend(b'uuid')

        # XMP UUID
        new_data.extend(XMP_UUID)

        # New XMP content
        new_data.extend(new_xmp_bytes)

        # Everything after the old XMP box
        new_data.extend(data[xmp_end:])

        data = new_data

    # Write output file
    with open(output_path, 'wb') as f:
        f.write(data)

    print(f"✅ Written to: {output_path}")
    print(f"   File size: {len(data):,} bytes")

    return True


def verify_xmp_replacement(filepath: str) -> str:
    """Read and return the XMP content from an MP4 file"""
    with open(filepath, 'rb') as f:
        data = f.read()

    result = find_xmp_box(data)
    if result is None:
        return "No XMP found"

    _, _, xmp_start, xmp_end = result
    return data[xmp_start:xmp_end].decode('utf-8', errors='ignore')


# ============ MAIN TEST ============

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    from video_uniquifier import generate_complete_fake_metadata, generate_xmp_xml

    print("=" * 60)
    print("MP4 XMP INJECTOR TEST")
    print("=" * 60)

    input_file = "test_video.mp4"
    output_file = "unique_video.mp4"

    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        print("   Creating test copy from original...")
        if os.path.exists("video (1).mp4"):
            shutil.copy("video (1).mp4", input_file)
        else:
            print("   No source video found!")
            exit(1)

    # Generate fake metadata
    print("\n📋 Generating fake metadata...")
    fake_metadata = generate_complete_fake_metadata()
    fake_xmp = generate_xmp_xml(fake_metadata)

    print(f"   Creator Tool: {fake_metadata['creatorTool']}")
    print(f"   Project Path: {fake_metadata['windowsAtom']['uncProjectPath']}")
    print(f"   Source files: {[i['filePath'] for i in fake_metadata['ingredients']]}")

    # Inject XMP
    print(f"\n🔧 Injecting XMP into {input_file}...")
    success = replace_xmp_in_mp4(input_file, output_file, fake_xmp)

    if success:
        # Verify
        print("\n🔍 Verifying replacement...")
        new_xmp = verify_xmp_replacement(output_file)

        # Check for key fields
        if fake_metadata['creatorTool'] in new_xmp:
            print("   ✅ CreatorTool correctly replaced")
        else:
            print("   ❌ CreatorTool NOT found in new XMP")

        if fake_metadata['windowsAtom']['uncProjectPath'] in new_xmp:
            print("   ✅ Project path correctly replaced")
        else:
            print("   ❌ Project path NOT found in new XMP")

        # Show first source file
        first_ingredient = fake_metadata['ingredients'][0]['filePath']
        if first_ingredient in new_xmp:
            print(f"   ✅ Source file '{first_ingredient}' correctly added")
        else:
            print(f"   ❌ Source file NOT found in new XMP")

        print("\n" + "=" * 60)
        print("SUCCESS! Created unique video with fake metadata")
        print("=" * 60)
        print(f"\n📁 Output file: {output_file}")
        print(f"   Original:    {os.path.getsize(input_file):,} bytes")
        print(f"   Unique:      {os.path.getsize(output_file):,} bytes")
