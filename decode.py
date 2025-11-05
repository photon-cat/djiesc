import csv
import sys

def extract_frames(path):
    frames = []
    current = []

    with open(path, newline="") as f:
        rdr = csv.reader(f)
        next(rdr, None)  # skip header row

        for row in rdr:
            if not row or len(row) < 3:
                continue

            # Rx column is at index 2
            rx_value = row[2].strip()
            if not rx_value:
                continue

            try:
                b = int(rx_value, 0)  # handles 0x prefix
            except ValueError:
                continue

            if b == 0x55:
                if current:
                    frames.append(current)
                current = [b]
            else:
                current.append(b)
        if current:
            frames.append(current)
    return frames


def decode_frame(frame):
    """Decode RS-485 frame according to protocol spec."""
    if len(frame) < 8:
        return None

    result = {
        'sync': frame[0],
        'length': frame[1] if len(frame) > 1 else None,
        'flags': frame[2] if len(frame) > 2 else None,
        'cmd_id': (frame[4] << 8 | frame[3]) if len(frame) > 4 else None,
        'reserved': (frame[6] << 8 | frame[5]) if len(frame) > 6 else None,
        'sequence': frame[7] if len(frame) > 7 else None,
        'payload_hex': ' '.join(f'{b:02X}' for b in frame[8:-2]) if len(frame) > 10 else '',
        'checksum': (frame[-1] << 8 | frame[-2]) if len(frame) >= 2 else None,
        'raw_hex': ' '.join(f'{b:02X}' for b in frame)
    }
    return result


def write_frames_csv(frames, output_path):
    """Write decoded frames to CSV."""
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['frame_num', 'total_bytes', 'sync', 'length', 'flags',
                      'cmd_id', 'reserved', 'sequence', 'payload_hex',
                      'checksum', 'raw_hex']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, frame in enumerate(frames):
            decoded = decode_frame(frame)
            if decoded:
                row = {
                    'frame_num': i,
                    'total_bytes': len(frame),
                    **decoded
                }
                writer.writerow(row)


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "t40esc.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "decoded_frames.csv"

    print(f"Reading from: {input_file}")
    frames = extract_frames(input_file)
    print(f"Extracted {len(frames)} frames")

    print(f"Writing to: {output_file}")
    write_frames_csv(frames, output_file)
    print("Done!")
