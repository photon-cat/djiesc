#!/usr/bin/env python3
"""
Decode 0xA021 (FC→ESC) command frames to understand throttle and arming.
"""

import csv
import struct

def decode_a021(payload_hex):
    """
    Decode 0xA021 payload (26 bytes).

    Frame structure observed:
    [0:1]   - Unknown (varies: 0x154E, 0x1550, etc.)
    [2]     - 0x07 (constant)
    [3]     - 0x00 (constant)
    [4]     - 0x98 or 0x99 (varies slightly)
    [5:7]   - 0x00 00 00 (constant)
    [8:9]   - Voltage feedback? (0x0000 when disarmed, 0x03B0-0x03B2 when armed = ~944-946 = 48.2V)
    [10:14] - 0x00 00 00 00 00 (constant)
    [15]    - ARM FLAG: 0x00 = disarmed, 0x80 = armed
    [16:17] - Counter (increments over time)
    [18:19] - 0x00 00 (constant)
    [20:21] - Unknown field (changes with byte 22)
    [22]    - State byte (changes during arming/motor control)
    [23:25] - 0x00 00 00 (constant)
    """
    payload = bytes.fromhex(payload_hex.replace(' ', ''))

    if len(payload) < 26:
        return None

    result = {
        'unknown_0_1': struct.unpack('<H', payload[0:2])[0],
        'const_2': payload[2],
        'const_3': payload[3],
        'byte_4': payload[4],
        'voltage_8_9': struct.unpack('<H', payload[8:10])[0],
        'arm_flag_15': payload[15],
        'counter_16_17': struct.unpack('<H', payload[16:18])[0],
        'unknown_20_21': struct.unpack('<H', payload[20:22])[0],
        'state_22': payload[22],
        'raw_hex': payload.hex(' ').upper(),
    }

    # Interpret fields
    result['armed'] = (result['arm_flag_15'] == 0x80)
    result['voltage_volts'] = result['voltage_8_9'] * 0.051 if result['voltage_8_9'] > 0 else 0.0

    return result

def main():
    print("=" * 100)
    print("0xA021 (FC→ESC) COMMAND DECODER")
    print("=" * 100)

    time_ranges = [
        ("IDLE (13s)", 13000, 13500),
        ("ARMING (69s)", 69000, 69500),
        ("BEEPING (71s)", 71000, 71500),
        ("MOTOR START (75s)", 75000, 75500),
        ("MOTOR RAMP (76s)", 76000, 76500),
        ("FLYING (90s)", 90000, 90500),
        ("TAKEOFF2 (101s)", 101000, 101500),
    ]

    with open('cap3.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = [row for row in reader if row['cmd_id'] == '0xA021']

    for name, start_ms, end_ms in time_ranges:
        print(f"\n{name}")
        print("-" * 100)

        frames = [row for row in data if start_ms <= int(row['timestamp_ms']) < end_ms]

        if not frames:
            print("  No frames in this range")
            continue

        # Show first 3 frames
        for i, row in enumerate(frames[:3]):
            decoded = decode_a021(row['payload_hex'])
            if not decoded:
                continue

            timestamp = int(row['timestamp_ms'])
            armed_str = "ARMED" if decoded['armed'] else "DISARMED"
            voltage_str = f"{decoded['voltage_volts']:.2f}V" if decoded['voltage_volts'] > 0 else "0.00V"

            print(f"  [{timestamp:6d}ms] {armed_str:9s} | Voltage: {voltage_str:7s} | "
                  f"State: 0x{decoded['state_22']:02X} | Counter: {decoded['counter_16_17']:4d} | "
                  f"Unk20-21: 0x{decoded['unknown_20_21']:04X}")

        if len(frames) > 3:
            print(f"  ... ({len(frames) - 3} more frames)")

        # Summary
        decoded_frames = [decode_a021(row['payload_hex']) for row in frames]
        decoded_frames = [d for d in decoded_frames if d is not None]
        armed_count = sum(1 for d in decoded_frames if d['armed'])
        voltages = [d['voltage_8_9'] for d in decoded_frames]
        states = set(d['state_22'] for d in decoded_frames)

        print(f"\n  Summary: {armed_count}/{len(frames)} frames armed | "
              f"Voltage raw range: {min(voltages)}-{max(voltages)} | "
              f"State bytes: {sorted([hex(s) for s in states])}")

    print("\n" + "=" * 100)
    print("KEY FINDINGS:")
    print("=" * 100)
    print("  Byte [15] = ARM FLAG:")
    print("    0x00 = Disarmed")
    print("    0x80 = Armed")
    print("")
    print("  Bytes [8:9] = Voltage feedback (little-endian uint16):")
    print("    0x0000 when disarmed")
    print("    0x03B0-0x03B2 (944-946) when armed → 48.2V @ 0.051V/unit")
    print("")
    print("  Byte [22] = State/Control byte:")
    print("    Changes during different flight phases")
    print("    Observed values: 0x00, 0x40, 0x80, 0xC0, 0x01, 0x41, 0x81, 0xC1")
    print("")
    print("  Bytes [16:17] = Counter (increments over time)")
    print("=" * 100)

if __name__ == '__main__':
    main()
