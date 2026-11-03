#!/usr/bin/env python3
"""
Patch script: Zero 84 bytes at offset 0x1F4F38 in ilaunch3 and recompute header checksum.
Official GXR 1.51 diagnostic image: menu-detail data region zeroed for boot-hang diagnosis.
"""

import struct

staging_path = '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/exp_zero_detail/local/SD_ROOT/ilaunch3'

# Read the entire file
with open(staging_path, 'rb') as f:
    data = bytearray(f.read())

print(f"Original file size: {len(data)} bytes")
print(f"Original SHA256 expected: da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7")

# Step 1: Zero 84 bytes at offset 0x1F4F38
detail_offset = 0x1F4F38
detail_length = 84
print(f"\nZeroing {detail_length} bytes at offset 0x{detail_offset:X} (decimal {detail_offset})")
print(f"Byte range: [0x{detail_offset:X}, 0x{detail_offset + detail_length:X})")

for i in range(detail_length):
    data[detail_offset + i] = 0x00

print(f"Zeroed successfully")

# Step 2: Compute header checksum over the PATCHED data
print(f"\nComputing checksum over patched data...")
acc = 0
for i in range(len(data) - 512):
    acc += data[512 + i] * (i % 6 + 2)
acc &= 0xFFFFFFFF

checksum_bytes = struct.pack('>I', acc)  # big-endian 4 bytes
print(f"Computed checksum: 0x{acc:08X}")
print(f"Checksum bytes (big-endian): {' '.join(f'{b:02X}' for b in checksum_bytes)}")

# Write checksum at offset 0x16C
checksum_offset = 0x16C
print(f"Writing checksum at offset 0x{checksum_offset:X}")
for i, byte in enumerate(checksum_bytes):
    data[checksum_offset + i] = byte

# Write the patched file back
with open(staging_path, 'wb') as f:
    f.write(data)

print(f"\nPatched file written back to {staging_path}")
print(f"Patched file size: {len(data)} bytes")

# Compute SHA256 of patched file
import hashlib
with open(staging_path, 'rb') as f:
    patched_sha256 = hashlib.sha256(f.read()).hexdigest()

print(f"Patched file SHA256: {patched_sha256}")
print(f"Expected SHA256:     1c177c1ccefebd9d1385ba7baec4ee1dbb988ce9e11efd1a97240e76097630a3")

if patched_sha256 == '1c177c1ccefebd9d1385ba7baec4ee1dbb988ce9e11efd1a97240e76097630a3':
    print("\n✓ SHA256 matches expected value")
else:
    print("\n✗ SHA256 MISMATCH")
    exit(1)

print("\n✓ Patch completed successfully")
