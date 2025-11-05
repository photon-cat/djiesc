import csv
import struct
import sys

def analyze_0xa0d0(frame):
    """Analyze ESC telemetry frame (0xA0D0)."""
    if len(frame) < 26:
        return None

    # Extract 8 x 16-bit LE values from payload
    payload = frame[8:-2]  # Skip header and checksum
    values = []
    for i in range(0, len(payload), 2):
        if i+1 < len(payload):
            val = payload[i] | (payload[i+1] << 8)
            values.append(val)

    result = {
        'type': '0xA0D0 (ESC Telemetry)',
        'sequence': frame[7],
    }

    # Interpret values (guessing based on typical ESC telemetry)
    if len(values) >= 8:
        result.update({
            'voltage_v': values[0] / 100.0,  # 0x03AC = 948 = 9.48V
            'current_a': values[1] / 100.0,
            'rpm': values[2] * 10,  # Or could be different scaling
            'temp_c': values[3] / 10.0,
            'value_4': values[4],
            'value_5': values[5],
            'value_6': values[6],
            'value_7': values[7],
        })

    return result

def analyze_0xa021(frame):
    """Analyze Flight Controller frame (0xA021)."""
    if len(frame) < 36:
        return None

    payload = frame[8:-2]  # Skip header and checksum

    result = {
        'type': '0xA021 (FC Status)',
        'timestamp': struct.unpack('<I', bytes(payload[0:4]))[0],
        'value_u16': struct.unpack('<H', bytes(payload[4:6]))[0],
        'reserved': struct.unpack('<H', bytes(payload[6:8]))[0],
        'voltage_v': struct.unpack('<H', bytes(payload[8:10]))[0] / 100.0,
    }

    return result

def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "decoded_frames.csv"

    with open(input_file, 'r', newline='') as f:
        reader = csv.DictReader(f)

        print("Frame Analysis")
        print("=" * 80)

        for row in reader:
            # Reconstruct frame from raw_hex
            raw_hex = row['raw_hex']
            frame = [int(b, 16) for b in raw_hex.split()]

            cmd_id = int(row['cmd_id'])

            if cmd_id == 41168:  # 0xA0D0
                analysis = analyze_0xa0d0(frame)
            elif cmd_id == 40993:  # 0xA021
                analysis = analyze_0xa021(frame)
            else:
                continue

            if analysis:
                print(f"\nFrame {row['frame_num']}: {analysis['type']}")
                for key, val in analysis.items():
                    if key != 'type':
                        if isinstance(val, float):
                            print(f"  {key:15s}: {val:.3f}")
                        else:
                            print(f"  {key:15s}: {val}")

if __name__ == "__main__":
    main()
