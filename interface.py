#!/usr/bin/env python3
"""
DJI ESC RS-485 Interface via SAMD21 + MAX485
Communicates with Arduino over USB serial to send/receive RS-485 frames
"""

import serial
import serial.tools.list_ports
import struct
import time
import sys
from typing import List, Optional


class DJIFrame:
    """DJI ESC Protocol Frame"""
    SYNC = 0x55

    def __init__(self, cmd_id: int, reserved: int, sequence: int, payload: bytes):
        self.cmd_id = cmd_id
        self.reserved = reserved
        self.sequence = sequence
        self.payload = payload
        self.flags = 0x00

    def encode(self) -> bytes:
        """Encode frame to bytes"""
        length = 6 + len(self.payload) + 2  # header(6) + payload + checksum(2)

        frame = bytearray()
        frame.append(self.SYNC)
        frame.append(length)
        frame.append(self.flags)
        frame.extend(struct.pack('<H', self.cmd_id))      # LE 16-bit
        frame.extend(struct.pack('<H', self.reserved))    # LE 16-bit
        frame.append(self.sequence)
        frame.extend(self.payload)

        # Calculate checksum (placeholder - replace with actual DJI algorithm)
        checksum = sum(frame) & 0xFFFF
        frame.extend(struct.pack('<H', checksum))

        return bytes(frame)

    @classmethod
    def decode(cls, data: bytes) -> Optional['DJIFrame']:
        """Decode frame from bytes"""
        if len(data) < 10:  # Min frame size
            return None

        if data[0] != cls.SYNC:
            return None

        length = data[1]
        flags = data[2]
        cmd_id = struct.unpack('<H', data[3:5])[0]
        reserved = struct.unpack('<H', data[5:7])[0]
        sequence = data[7]

        payload_end = length + 2 - 2  # +2 for sync+length, -2 for checksum
        payload = data[8:payload_end]

        # Checksum validation (not used currently, but extracted for future use)
        # checksum = struct.unpack('<H', data[payload_end:payload_end+2])[0]

        frame = cls(cmd_id, reserved, sequence, payload)
        frame.flags = flags
        return frame

    def __repr__(self):
        return (f"DJIFrame(cmd=0x{self.cmd_id:04X}, reserved=0x{self.reserved:04X}, "
                f"seq={self.sequence}, payload={len(self.payload)}B)")


class RS485Interface:
    """Interface to SAMD21+MAX485 over USB serial"""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port: Optional[str] = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.verbose = True

    def find_device(self) -> Optional[str]:
        """Auto-detect SAMD21 device"""
        ports = serial.tools.list_ports.comports()

        # Look for SAMD21 VID:PID or common names
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

    def connect(self) -> bool:
        """Connect to device"""
        if not self.port:
            self.port = self.find_device()
            if not self.port:
                print("Error: No serial device found")
                return False

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino reset

            # Clear any startup messages
            while self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore')
                if self.verbose:
                    print(f"[DEVICE] {line.strip()}")

            print(f"Connected to {self.port}")
            return True

        except serial.SerialException as e:
            print(f"Error opening {self.port}: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Disconnected")

    def send_frame(self, frame: DJIFrame) -> bool:
        """Send DJI frame on RS-485 bus"""
        if not self.ser or not self.ser.is_open:
            print("Error: Not connected")
            return False

        data = frame.encode()
        hex_str = ' '.join(f'{b:02X}' for b in data)
        cmd = f"TX:{hex_str}\n"

        if self.verbose:
            print(f"[SEND] {frame}")
            print(f"       {hex_str}")

        self.ser.write(cmd.encode('utf-8'))
        self.ser.flush()

        # Read response
        time.sleep(0.1)
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore')
            if self.verbose:
                print(f"[DEVICE] {line.strip()}")

        return True

    def send_raw(self, data: bytes) -> bool:
        """Send raw bytes on RS-485 bus"""
        if not self.ser or not self.ser.is_open:
            print("Error: Not connected")
            return False

        hex_str = ' '.join(f'{b:02X}' for b in data)
        cmd = f"TX:{hex_str}\n"

        if self.verbose:
            print(f"[SEND RAW] {hex_str}")

        self.ser.write(cmd.encode('utf-8'))
        self.ser.flush()

        time.sleep(0.1)
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore')
            if self.verbose:
                print(f"[DEVICE] {line.strip()}")

        return True

    def receive(self, timeout: float = 5.0) -> List[DJIFrame]:
        """Receive frames from RS-485 bus"""
        if not self.ser or not self.ser.is_open:
            print("Error: Not connected")
            return []

        frames = []
        start_time = time.time()

        print(f"Listening for {timeout}s...")

        while time.time() - start_time < timeout:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()

                if line.startswith('[RX<-485]'):
                    # Parse received frame
                    hex_data = line.split(']')[1].strip().replace(' ', '')
                    try:
                        data = bytes.fromhex(hex_data)
                        frame = DJIFrame.decode(data)
                        if frame:
                            frames.append(frame)
                            if self.verbose:
                                print(f"[RECV] {frame}")
                    except ValueError:
                        pass

                elif self.verbose and line:
                    print(f"[DEVICE] {line}")

            time.sleep(0.01)

        return frames

    def monitor(self, duration: Optional[float] = None):
        """Monitor RS-485 bus indefinitely or for duration"""
        if not self.ser or not self.ser.is_open:
            print("Error: Not connected")
            return

        print("Monitoring RS-485 bus... (Ctrl+C to stop)")
        start_time = time.time()

        try:
            while True:
                if duration and (time.time() - start_time > duration):
                    break

                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"[{time.strftime('%H:%M:%S')}] {line}")

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nMonitoring stopped")


def main():
    """Interactive CLI"""
    import argparse

    parser = argparse.ArgumentParser(description='DJI ESC RS-485 Interface')
    parser.add_argument('-p', '--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('-b', '--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('-m', '--monitor', action='store_true', help='Monitor mode')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')

    args = parser.parse_args()

    interface = RS485Interface(port=args.port, baudrate=args.baud)
    interface.verbose = not args.quiet

    if not interface.connect():
        return 1

    try:
        if args.monitor:
            interface.monitor()
        else:
            # Interactive mode
            print("\nInteractive mode. Commands:")
            print("  send <cmd_id> <seq> <payload_hex>  - Send frame")
            print("  recv [timeout]                      - Receive frames")
            print("  raw <hex_bytes>                     - Send raw bytes")
            print("  monitor                             - Monitor bus")
            print("  quit                                - Exit")
            print()

            while True:
                try:
                    cmd = input(">> ").strip()

                    if not cmd:
                        continue

                    parts = cmd.split()

                    if parts[0] == 'quit':
                        break

                    elif parts[0] == 'send' and len(parts) >= 3:
                        cmd_id = int(parts[1], 0)
                        seq = int(parts[2])
                        payload_hex = parts[3] if len(parts) > 3 else ''
                        payload = bytes.fromhex(payload_hex.replace(' ', ''))

                        frame = DJIFrame(cmd_id, reserved=0x0000, sequence=seq, payload=payload)
                        interface.send_frame(frame)

                    elif parts[0] == 'recv':
                        timeout = float(parts[1]) if len(parts) > 1 else 5.0
                        frames = interface.receive(timeout)
                        print(f"Received {len(frames)} frame(s)")

                    elif parts[0] == 'raw' and len(parts) > 1:
                        hex_data = ' '.join(parts[1:]).replace(' ', '')
                        data = bytes.fromhex(hex_data)
                        interface.send_raw(data)

                    elif parts[0] == 'monitor':
                        interface.monitor()

                    else:
                        print("Unknown command")

                except KeyboardInterrupt:
                    print()
                    break
                except Exception as e:
                    print(f"Error: {e}")

    finally:
        interface.disconnect()

    return 0


if __name__ == '__main__':
    sys.exit(main())
