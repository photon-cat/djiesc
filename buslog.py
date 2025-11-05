#!/usr/bin/env python3
"""
RS-485 Frame Logger for DJI ESC Protocol
Logs frames from power-up with timestamps for later analysis
"""

import serial
import serial.tools.list_ports
import sys
import time
import struct
from datetime import datetime
from pathlib import Path


class FrameLogger:
    """Log RS-485 frames with timestamps"""

    def __init__(self, port=None, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.log_file = None
        self.csv_file = None
        self.frame_count = 0
        self.start_time = None

    def find_device(self):
        """Auto-detect SAMD21 device"""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            if 'SAMD21' in port.description or 'Arduino' in port.description:
                return port.device
            # Seeeduino XIAO SAMD21
            if port.vid == 0x2886 and port.pid == 0x802F:
                return port.device

        # Fallback: return first available port
        if ports:
            return ports[0].device

        return None

    def connect(self):
        """Connect to device"""
        if not self.port:
            self.port = self.find_device()
            if not self.port:
                print("ERROR: No serial device found")
                return False

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset

            # Wait for LOGGER_READY signal
            timeout = time.time() + 5
            while time.time() < timeout:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line == 'LOGGER_READY':
                        print(f"✓ Connected to {self.port}")
                        return True

            print(f"✓ Connected to {self.port} (no ready signal)")
            return True

        except serial.SerialException as e:
            print(f"ERROR: Cannot open {self.port}: {e}")
            return False

    def open_log_files(self, base_name=None):
        """Open log files for writing"""
        if not base_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"capture_{timestamp}"

        log_path = Path(base_name + ".log")
        csv_path = Path(base_name + ".csv")

        self.log_file = open(log_path, 'w')
        self.csv_file = open(csv_path, 'w')

        # Write CSV header
        self.csv_file.write("frame_num,timestamp_ms,elapsed_ms,cmd_id,sequence,length,payload_hex,raw_hex\n")
        self.csv_file.flush()

        print(f"✓ Logging to: {log_path}")
        print(f"✓ CSV output: {csv_path}")

        return True

    def decode_frame(self, hex_str):
        """Decode frame from hex string"""
        try:
            bytes_list = [int(b, 16) for b in hex_str.split()]
            if len(bytes_list) < 8:
                return None

            frame = {
                'sync': bytes_list[0],
                'length': bytes_list[1],
                'flags': bytes_list[2],
                'cmd_id': bytes_list[3] | (bytes_list[4] << 8),
                'reserved': bytes_list[5] | (bytes_list[6] << 8),
                'sequence': bytes_list[7],
                'payload': bytes_list[8:-2] if len(bytes_list) > 10 else [],
                'checksum': bytes_list[-2] | (bytes_list[-1] << 8) if len(bytes_list) >= 2 else 0,
                'raw': bytes_list
            }
            return frame

        except (ValueError, IndexError):
            return None

    def analyze_frame(self, frame):
        """Analyze frame and return description"""
        cmd_id = frame['cmd_id']

        if cmd_id == 0xA0D0:
            # ESC Telemetry
            payload = frame['payload']
            if len(payload) >= 16:
                values = []
                for i in range(0, 16, 2):
                    val = payload[i] | (payload[i+1] << 8)
                    values.append(val)

                voltage = values[0] * 0.051
                return f"ESC_TELEM seq={frame['sequence']} V={voltage:.2f}V"

        elif cmd_id == 0xA021:
            # FC Query
            payload = frame['payload']
            if len(payload) >= 10:
                timestamp = payload[0] | (payload[1] << 8) | (payload[2] << 16) | (payload[3] << 24)
                voltage_raw = payload[8] | (payload[9] << 8)
                voltage = voltage_raw * 0.051
                return f"FC_QUERY timestamp={timestamp} V={voltage:.2f}V"

        return f"CMD_0x{cmd_id:04X}"

    def log_frame(self, timestamp_ms, hex_str):
        """Log a frame"""
        self.frame_count += 1

        if self.start_time is None:
            self.start_time = timestamp_ms

        elapsed = timestamp_ms - self.start_time

        # Decode frame
        frame = self.decode_frame(hex_str)

        if frame:
            description = self.analyze_frame(frame)

            # Write to log file with timestamp
            log_line = f"[{timestamp_ms:010d}ms +{elapsed:06d}ms] #{self.frame_count:05d} {description}\n"
            self.log_file.write(log_line)

            # Write to CSV
            payload_hex = ' '.join(f'{b:02X}' for b in frame['payload'])
            csv_line = f"{self.frame_count},{timestamp_ms},{elapsed},0x{frame['cmd_id']:04X},{frame['sequence']},{frame['length']},{payload_hex},{hex_str}\n"
            self.csv_file.write(csv_line)

            # Console output (rate-limited to not spam)
            if self.frame_count % 50 == 0:
                print(f"  Logged {self.frame_count} frames... [{elapsed/1000:.1f}s] {description}")

        else:
            # Log raw data even if decode failed
            log_line = f"[{timestamp_ms:010d}ms +{elapsed:06d}ms] #{self.frame_count:05d} DECODE_ERROR\n"
            self.log_file.write(log_line)

        # Flush periodically
        if self.frame_count % 100 == 0:
            self.log_file.flush()
            self.csv_file.flush()

    def run(self, duration=None):
        """Run logger"""
        if not self.ser or not self.ser.is_open:
            print("ERROR: Not connected")
            return False

        print("\n" + "="*60)
        print("FRAME LOGGER RUNNING")
        print("="*60)
        print("Power up your drone now to capture from startup")
        print("Press Ctrl+C to stop logging")
        print("="*60 + "\n")

        start = time.time()

        try:
            while True:
                if duration and (time.time() - start > duration):
                    break

                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                    if line.startswith('FRAME,'):
                        # Parse: FRAME,<timestamp>,<hex_bytes>
                        parts = line.split(',', 2)
                        if len(parts) == 3:
                            try:
                                timestamp_ms = int(parts[1])
                                hex_str = parts[2]
                                self.log_frame(timestamp_ms, hex_str)
                            except ValueError:
                                pass

                    elif line.startswith('ERROR,'):
                        # Log errors
                        self.log_file.write(f"[ERROR] {line}\n")
                        print(f"! {line}")

                    elif line.startswith('STATUS,'):
                        # Log status
                        self.log_file.write(f"[STATUS] {line}\n")

                time.sleep(0.001)  # Small delay to prevent CPU spin

        except KeyboardInterrupt:
            print("\n\nStopping logger...")

        # Final flush
        self.log_file.flush()
        self.csv_file.flush()

        print(f"\n✓ Logged {self.frame_count} frames")
        print(f"✓ Duration: {(time.time() - start):.1f}s")

        return True

    def close(self):
        """Close connections and files"""
        if self.ser and self.ser.is_open:
            self.ser.close()

        if self.log_file:
            self.log_file.close()

        if self.csv_file:
            self.csv_file.close()

        print("✓ Closed")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='DJI ESC Frame Logger')
    parser.add_argument('-p', '--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('-o', '--output', help='Output file base name (default: capture_TIMESTAMP)')
    parser.add_argument('-d', '--duration', type=float, help='Duration in seconds (default: unlimited)')

    args = parser.parse_args()

    logger = FrameLogger(port=args.port, baudrate=args.baud)

    try:
        if not logger.connect():
            return 1

        if not logger.open_log_files(args.output):
            return 1

        if not logger.run(duration=args.duration):
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        logger.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
