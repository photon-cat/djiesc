#!/usr/bin/env python3
"""
Deep dive into 0xA021 payload structure to find throttle values.
"""

import struct

# Sample payloads from cap3
payloads = {
    "idle_13s": "51 15 07 00 98 00 00 00 00 00 00 00 00 00 00 00 03 00 00 00 00 00 40 00 00 00",
    "armed_69s": "4E 15 07 00 98 00 00 00 B1 03 00 00 00 00 00 80 AE 02 00 00 00 00 40 19 00 00",
    "motor_75s": "4F 15 07 00 98 00 00 00 B0 03 00 00 00 00 00 80 F8 02 00 00 00 00 00 29 00 00",
    "flying_90s": "02 15 65 15 A0 00 5F 00 96 04 08 0F 00 00 00 80 B4 03 00 00 00 00 80 11 00 00",
}

print("=" * 100)
print("0xA021 PAYLOAD STRUCTURE ANALYSIS")
print("=" * 100)

for name, hex_str in payloads.items():
    payload = bytes.fromhex(hex_str.replace(' ', ''))
    print(f"\n{name.upper()}:")
    print(f"  Raw: {hex_str}")
    print()

    # Try different interpretations
    print("  Byte-by-byte:")
    for i in range(26):
        print(f"    [{i:2d}] = 0x{payload[i]:02X} ({payload[i]:3d})", end="")
        if i % 4 == 3:
            print()
        else:
            print(" | ", end="")

    print("\n  16-bit little-endian words:")
    for i in range(0, 26, 2):
        if i + 1 < 26:
            val = struct.unpack('<H', payload[i:i+2])[0]
            print(f"    [{i:2d}:{i+1:2d}] = 0x{val:04X} ({val:5d})")

    # Look for patterns
    print("\n  Key observations:")
    print(f"    Byte [15] = 0x{payload[15]:02X} {'(ARMED)' if payload[15] == 0x80 else '(DISARMED)'}")
    print(f"    Bytes [8:9] = 0x{struct.unpack('<H', payload[8:10])[0]:04X} = {struct.unpack('<H', payload[8:10])[0]}")

    # Check if there are multiple throttle values (for 4 motors)
    # Possible locations: could be 4x 16-bit values, or 4x 8-bit values, or interleaved
    print("\n  Searching for multi-motor throttle values...")

    # Try hypothesis: 4 motors, each with 16-bit throttle
    # Might be in different parts of the payload
    for start_byte in [0, 6, 8]:
        if start_byte + 8 <= 26:
            motors = []
            for i in range(4):
                val = struct.unpack('<H', payload[start_byte + i*2:start_byte + i*2 + 2])[0]
                motors.append(val)
            print(f"    If 4× 16-bit throttles starting at byte [{start_byte}]: {motors}")

print("\n" + "=" * 100)
print("FLYING PAYLOAD DETAILED ANALYSIS")
print("=" * 100)

flying = bytes.fromhex(payloads["flying_90s"].replace(' ', ''))

print(f"\nFlying payload: {payloads['flying_90s']}")
print()
print("Hypothesis: This ESC is only seeing commands for 1 motor (out of 4 total)")
print()
print("Key fields that changed from idle→armed→flying:")
print(f"  [0:1]   = 0x{struct.unpack('<H', flying[0:2])[0]:04X} = {struct.unpack('<H', flying[0:2])[0]:5d} (was 0x154E/5454 at armed)")
print(f"  [2:3]   = 0x{struct.unpack('<H', flying[2:4])[0]:04X} = {struct.unpack('<H', flying[2:4])[0]:5d} (was 0x0007/7 at armed)")
print(f"  [4:5]   = 0x{struct.unpack('<H', flying[4:6])[0]:04X} = {struct.unpack('<H', flying[4:6])[0]:5d} (was 0x0098/152 at armed)")
print(f"  [6:7]   = 0x{struct.unpack('<H', flying[6:8])[0]:04X} = {struct.unpack('<H', flying[6:8])[0]:5d} (was 0x0000/0 at armed)")
print(f"  [8:9]   = 0x{struct.unpack('<H', flying[8:10])[0]:04X} = {struct.unpack('<H', flying[8:10])[0]:5d} (was 0x03B0/944 at armed) ← THROTTLE?")
print(f"  [10:11] = 0x{struct.unpack('<H', flying[10:12])[0]:04X} = {struct.unpack('<H', flying[10:12])[0]:5d} (was 0x0000/0 at armed)")
print()
print("Bytes [2:3] changed from 0x0007 to 0x1565 (5477) - could be throttle!")
print("Bytes [4:5] changed from 0x0098 to 0x00A0 (160) - minor change")
print("Bytes [6:7] changed from 0x0000 to 0x005F (95) - could be related")
print("Bytes [8:9] changed from 0x03B0 to 0x0496 (1174) - significant increase!")
print("Bytes [10:11] changed from 0x0000 to 0x0F08 (3848) - could be throttle too!")
