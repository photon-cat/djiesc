#!/usr/bin/env python3
"""
Parse hex log output from busprint.ino
Extracts frames and decodes them
"""

import sys
import re
import struct

def parse_hex_log(log_file):
    """Extract bytes from busprint.ino hex output"""
    bytes_list = []

    with open(log_file, 'r') as f:
        for line in f:
            # Match lines with hex bytes like: "[123] 0x55 0x1A 0x00 ..."
            hex_matches = re.findall(r'0x([0-9A-Fa-f]{2})', line)
            for hex_byte in hex_matches:
                bytes_list.append(int(hex_byte, 16))

    return bytes_list

def extract_frames(data):
    """Extract frames starting with 0x55 sync byte"""
    frames = []
    i = 0

    while i < len(data):
        # Look for sync byte
        if data[i] == 0x55:
            if i + 1 < len(data):
                length = data[i + 1]
                frame_size = length + 2  # +2 for sync and length byte

                if i + frame_size <= len(data):
                    frame = data[i:i+frame_size]
                    frames.append(frame)
                    i += frame_size
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return frames

def decode_frame(frame):
    """Decode DJI ESC frame"""
    if len(frame) < 10:
        return None

    sync = frame[0]
    length = frame[1]
    flags = frame[2]
    cmd_id = struct.unpack('<H', bytes(frame[3:5]))[0]
    reserved = struct.unpack('<H', bytes(frame[5:7]))[0]
    sequence = frame[7]
    payload = frame[8:-2]
    checksum = struct.unpack('<H', bytes(frame[-2:]))[0]

    result = {
        'sync': sync,
        'length': length,
        'flags': flags,
        'cmd_id': cmd_id,
        'reserved': reserved,
        'sequence': sequence,
        'payload': payload,
        'checksum': checksum,
        'raw': frame
    }

    return result

def analyze_frame(frame_data):
    """Analyze and print frame details"""
    cmd_id = frame_data['cmd_id']

    if cmd_id == 0xA0D0:
        # ESC Telemetry
        payload = frame_data['payload']
        values = []
        for i in range(0, len(payload), 2):
            if i+1 < len(payload):
                val = struct.unpack('<H', bytes(payload[i:i+2]))[0]
                values.append(val)

        print(f"  ESC Telemetry (0xA0D0) SEQ:{frame_data['sequence']}")
        if values:
            voltage = values[0] * 0.051
            print(f"    Voltage: {voltage:.2f}V (raw:{values[0]})")
            print(f"    Values: {values}")

    elif cmd_id == 0xA021:
        # FC Query
        payload = frame_data['payload']
        if len(payload) >= 10:
            timestamp = struct.unpack('<I', bytes(payload[0:4]))[0]
            val_u16 = struct.unpack('<H', bytes(payload[4:6]))[0]
            voltage_raw = struct.unpack('<H', bytes(payload[8:10]))[0]
            voltage = voltage_raw * 0.051

            print(f"  FC Query (0xA021)")
            print(f"    Timestamp: {timestamp}")
            print(f"    Value: {val_u16}")
            print(f"    FC Voltage: {voltage:.2f}V (raw:{voltage_raw})")

    else:
        print(f"  Unknown CMD: 0x{cmd_id:04X}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_hex_log.py <hex_log.txt>")
        print()
        print("Copy output from Arduino Serial Monitor to a text file,")
        print("then run this script to parse and decode the frames.")
        return 1

    log_file = sys.argv[1]

    print(f"Parsing {log_file}...")
    data = parse_hex_log(log_file)
    print(f"Found {len(data)} bytes")

    frames = extract_frames(data)
    print(f"Extracted {len(frames)} frames\n")

    # Analyze frames
    for i, frame in enumerate(frames):
        decoded = decode_frame(frame)
        if decoded:
            print(f"Frame {i+1}: {len(frame)} bytes")
            analyze_frame(decoded)

            # Print raw hex
            hex_str = ' '.join(f'{b:02X}' for b in frame)
            print(f"    Raw: {hex_str}")
            print()

    # Statistics
    cmd_counts = {}
    for frame in frames:
        decoded = decode_frame(frame)
        if decoded:
            cmd_id = decoded['cmd_id']
            cmd_counts[cmd_id] = cmd_counts.get(cmd_id, 0) + 1

    print("=" * 60)
    print("Statistics:")
    for cmd_id, count in sorted(cmd_counts.items()):
        cmd_name = "ESC Telemetry" if cmd_id == 0xA0D0 else "FC Query" if cmd_id == 0xA021 else "Unknown"
        print(f"  0x{cmd_id:04X} ({cmd_name}): {count} frames")

    return 0

if __name__ == '__main__':
    sys.exit(main())
