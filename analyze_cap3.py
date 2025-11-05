#!/usr/bin/env python3
"""
Analyze capture 3 to decode throttle and arming commands.
"""

import csv
import struct
from collections import defaultdict

def parse_payload(hex_str):
    """Parse hex payload string into bytes."""
    return bytes.fromhex(hex_str.replace(' ', ''))

def analyze_a021_payload(payload_bytes):
    """
    Analyze 0xA021 (FC->ESC) command payload.
    Payload is 26 bytes according to the captures.
    """
    if len(payload_bytes) < 26:
        return None

    # Try to decode as little-endian values
    result = {
        'raw_hex': payload_bytes.hex(' '),
        'byte_00_01': struct.unpack('<H', payload_bytes[0:2])[0],   # 0x154E, 0x1550, etc.
        'byte_02': payload_bytes[2],                                 # 0x07
        'byte_03': payload_bytes[3],                                 # 0x00
        'byte_04': payload_bytes[4],                                 # 0x98
        'byte_05_06': struct.unpack('<H', payload_bytes[5:7])[0],   # Usually 0x0000
        'byte_07': payload_bytes[7],                                 # 0x00
        'byte_08_09': struct.unpack('<H', payload_bytes[8:10])[0],  # Changes! 0x03B1, etc.
        'byte_10_11': struct.unpack('<H', payload_bytes[10:12])[0], # 0x0000
        'byte_12_13': struct.unpack('<H', payload_bytes[12:14])[0], # 0x0000
        'byte_14': payload_bytes[14],                               # 0x00
        'byte_15': payload_bytes[15],                               # 0x80
        'byte_16_17': struct.unpack('<H', payload_bytes[16:18])[0], # Changes! 0x02BA, etc.
        'byte_18_19': struct.unpack('<H', payload_bytes[18:20])[0], # 0x0000
        'byte_20_21': struct.unpack('<H', payload_bytes[20:22])[0], # Changes! 0x0000, 0x0040, 0x0080, 0x00C0
        'byte_22': payload_bytes[22],                               # Changes! 0x1B, 0x26, 0x27, etc.
        'byte_23_24': struct.unpack('<H', payload_bytes[23:25])[0], # Usually 0x0000
        'byte_25': payload_bytes[25] if len(payload_bytes) > 25 else 0,
    }
    return result

def main():
    # Key timestamps from user notes:
    # - 70s: Takeoff sequence begins
    # - 71-72s: BEEP BEEP BEEP (ESC noisemaker)
    # - 75s: Click click click, motors partial turn, props spin up
    # - 75-79s: Low speed ramp up
    # - 101s: Second takeoff attempt

    time_windows = [
        ("idle", 0, 20000),           # First 20 seconds - idle/startup
        ("pre_beep", 69000, 71000),   # Before beeping
        ("beeping", 71000, 73000),    # During beeps
        ("pre_motor", 73000, 75000),  # Before motor engagement
        ("motor_start", 75000, 76000),# Motor clicks and initial spin
        ("ramp_up", 76000, 79000),    # Ramping up
        ("flying", 79000, 100000),    # Flying/hovering
        ("takeoff2", 100000, 103000), # Second takeoff attempt
    ]

    a021_frames_by_window = defaultdict(list)

    with open('cap3.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cmd_id = row['cmd_id']
            if cmd_id != '0xA021':
                continue

            timestamp = int(row['timestamp_ms'])
            payload_hex = row['payload_hex']
            payload = parse_payload(payload_hex)

            # Categorize by time window
            for window_name, start, end in time_windows:
                if start <= timestamp < end:
                    analysis = analyze_a021_payload(payload)
                    if analysis:
                        analysis['timestamp'] = timestamp
                        analysis['elapsed'] = int(row['elapsed_ms'])
                        a021_frames_by_window[window_name].append(analysis)
                    break

    # Print analysis
    print("=" * 80)
    print("0xA021 (FC→ESC Command) Analysis by Time Window")
    print("=" * 80)

    for window_name, start, end in time_windows:
        frames = a021_frames_by_window[window_name]
        if not frames:
            continue

        print(f"\n{window_name.upper()}: {start}ms - {end}ms ({len(frames)} frames)")
        print("-" * 80)

        # Show first few frames
        for i, frame in enumerate(frames[:3]):
            print(f"  Frame {i+1} @ {frame['timestamp']}ms (+{frame['elapsed']}ms):")
            print(f"    Bytes [08:09] (16-bit LE): 0x{frame['byte_08_09']:04X} = {frame['byte_08_09']}")
            print(f"    Bytes [16:17] (16-bit LE): 0x{frame['byte_16_17']:04X} = {frame['byte_16_17']}")
            print(f"    Bytes [20:21] (16-bit LE): 0x{frame['byte_20_21']:04X} = {frame['byte_20_21']}")
            print(f"    Byte  [22]    (uint8):     0x{frame['byte_22']:02X} = {frame['byte_22']}")

        if len(frames) > 3:
            print(f"  ... ({len(frames) - 3} more frames)")

        # Look for unique values in key fields
        unique_08_09 = set(f['byte_08_09'] for f in frames)
        unique_16_17 = set(f['byte_16_17'] for f in frames)
        unique_20_21 = set(f['byte_20_21'] for f in frames)
        unique_22 = set(f['byte_22'] for f in frames)

        print(f"\n  Unique values in this window:")
        print(f"    Bytes [08:09]: {sorted(unique_08_09)}")
        print(f"    Bytes [16:17]: {sorted(unique_16_17)}")
        print(f"    Bytes [20:21]: {sorted(unique_20_21)} (hex: {[hex(x) for x in sorted(unique_20_21)]})")
        print(f"    Byte  [22]:    {sorted(unique_22)} (hex: {[hex(x) for x in sorted(unique_22)]})")

    print("\n" + "=" * 80)
    print("HYPOTHESIS:")
    print("=" * 80)
    print("Bytes [20:21] appear to increment in 0x40 steps:")
    print("  0x0000 = Disarmed/Idle")
    print("  0x0040 = Armed but not throttled")
    print("  0x0080 = Low throttle")
    print("  0x00C0 = Higher throttle")
    print("  ... potentially up to 0xFFFF for max throttle")
    print("\nByte [22] also changes - could be related to motor control state.")
    print("Bytes [08:09] and [16:17] change over time - likely counters or status values.")

if __name__ == '__main__':
    main()
