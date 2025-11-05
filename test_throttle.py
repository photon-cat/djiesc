#!/usr/bin/env python3
"""
Test script for sending throttle commands to DJI ESC via RS-485.

WARNING: DO NOT RUN WITH PROPELLERS ATTACHED!
         TEST ON BENCH ONLY!
"""

import serial
import struct
import time
import sys

class DJIThrottleController:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.counter = 0

    def connect(self):
        """Open serial connection to Arduino/MAX485 interface."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            print(f"Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"Error connecting: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.ser:
            self.ser.close()
            print("Disconnected")

    def calculate_crc16(self, data):
        """Calculate CRC-16 for DJI protocol (same as in interface.py)."""
        crc = 0x3692
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0x8005
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def build_frame(self, cmd_id, reserved, sequence, payload):
        """Build complete DJI protocol frame."""
        length = len(payload) + 10  # Header overhead
        flags = 0x00

        # Build frame without CRC
        frame = bytearray()
        frame.append(0x55)  # Sync
        frame.append(length)
        frame.append(flags)
        frame.extend(struct.pack('<H', cmd_id))      # Little-endian
        frame.extend(struct.pack('<H', reserved))    # Little-endian
        frame.append(sequence)
        frame.extend(payload)

        # Calculate and append CRC
        crc = self.calculate_crc16(frame)
        frame.extend(struct.pack('<H', crc))

        return bytes(frame)

    def build_a021_payload(self, armed, throttle1, throttle2, throttle3, throttle4, state_byte=0x40):
        """
        Build 0xA021 command payload (26 bytes).

        Args:
            armed: True = armed (0x80), False = disarmed (0x00)
            throttle1-4: Throttle values for 4 motors (0-65535)
            state_byte: State/phase indicator (default 0x40)

        Returns:
            26-byte payload
        """
        payload = bytearray(26)

        # Fixed/unknown fields
        payload[0:2] = struct.pack('<H', 5454)      # Unknown_A (observed value)
        payload[2:4] = struct.pack('<H', throttle1) # Motor 1 throttle
        payload[4:6] = struct.pack('<H', 152)       # Unknown_B (observed value)
        payload[6:8] = struct.pack('<H', throttle2) # Motor 2 throttle
        payload[8:10] = struct.pack('<H', throttle3)# Motor 3 throttle
        payload[10:12] = struct.pack('<H', throttle4)# Motor 4 throttle
        payload[12:15] = b'\x00\x00\x00'            # Zeros
        payload[15] = 0x80 if armed else 0x00       # ARM_FLAG
        payload[16:18] = struct.pack('<H', self.counter % 65536)  # Counter
        payload[18:22] = b'\x00\x00\x00\x00'        # Zeros
        payload[22] = state_byte                     # State byte
        payload[23:26] = b'\x00\x00\x00'            # Unknown_C

        self.counter += 1
        return bytes(payload)

    def send_command(self, armed, throttle1=7, throttle2=0, throttle3=944, throttle4=0, state_byte=0x40):
        """
        Send 0xA021 throttle command to ESC.

        Args:
            armed: True to arm ESC, False to disarm
            throttle1-4: Throttle values (default = idle values)
            state_byte: State indicator
        """
        payload = self.build_a021_payload(armed, throttle1, throttle2, throttle3, throttle4, state_byte)
        frame = self.build_frame(0xA021, 0x0001, 0x00, payload)

        # Send via Arduino interface (using TX: prefix)
        hex_str = ' '.join(f'{b:02X}' for b in frame)
        cmd = f'TX:{hex_str}\n'

        if self.ser:
            self.ser.write(cmd.encode())
            self.ser.flush()
            return True
        return False

    def arm(self):
        """Arm the ESC (motors can spin)."""
        print("Arming ESC...")
        for _ in range(5):  # Send 5 arming commands
            self.send_command(armed=True, throttle1=7, throttle2=0, throttle3=944, throttle4=0)
            time.sleep(0.08)  # 12.5 Hz
        print("ESC armed! Listen for beep-beep-beep confirmation.")

    def disarm(self):
        """Disarm the ESC (motors cannot spin)."""
        print("Disarming ESC...")
        for _ in range(5):  # Send 5 disarming commands
            self.send_command(armed=False, throttle1=0, throttle2=0, throttle3=0, throttle4=0)
            time.sleep(0.08)
        print("ESC disarmed.")

    def set_throttle(self, throttle1=7, throttle2=0, throttle3=944, throttle4=0, duration=1.0):
        """
        Set throttle values for specified duration.

        Args:
            throttle1-4: Throttle values for 4 motors
            duration: How long to maintain throttle (seconds)
        """
        print(f"Setting throttle: M1={throttle1}, M2={throttle2}, M3={throttle3}, M4={throttle4}")
        start_time = time.time()

        while time.time() - start_time < duration:
            self.send_command(armed=True, throttle1=throttle1, throttle2=throttle2,
                            throttle3=throttle3, throttle4=throttle4)
            time.sleep(0.08)  # 12.5 Hz

    def ramp_test(self, motor_index, min_throttle=1000, max_throttle=3000, step=100, step_duration=0.5):
        """
        Slowly ramp up and down one motor for testing.

        Args:
            motor_index: Which motor to test (1-4)
            min_throttle: Starting throttle value
            max_throttle: Peak throttle value
            step: Increment per step
            step_duration: Time at each step (seconds)

        WARNING: NO PROPS!
        """
        print(f"\n{'='*60}")
        print(f"RAMP TEST - Motor {motor_index}")
        print(f"Range: {min_throttle} → {max_throttle} → {min_throttle}")
        print(f"Step: {step}, Duration: {step_duration}s per step")
        print(f"{'='*60}\n")

        throttles = [7, 0, 944, 0]  # Default idle values

        # Ramp up
        for throttle in range(min_throttle, max_throttle + 1, step):
            throttles[motor_index - 1] = throttle
            print(f"Motor {motor_index} throttle: {throttle:5d}")
            self.set_throttle(*throttles, duration=step_duration)

        # Ramp down
        for throttle in range(max_throttle, min_throttle - 1, -step):
            throttles[motor_index - 1] = throttle
            print(f"Motor {motor_index} throttle: {throttle:5d}")
            self.set_throttle(*throttles, duration=step_duration)

        # Return to idle
        throttles[motor_index - 1] = 7 if motor_index == 1 else (944 if motor_index == 3 else 0)
        self.set_throttle(*throttles, duration=1.0)
        print(f"Motor {motor_index} returned to idle\n")


def main():
    print("=" * 80)
    print("DJI ESC THROTTLE CONTROL TEST")
    print("=" * 80)
    print()
    print("WARNING: DO NOT RUN WITH PROPELLERS ATTACHED!")
    print("         BENCH TEST ONLY!")
    print()

    # Check for serial port argument
    if len(sys.argv) < 2:
        print("Usage: python3 test_throttle.py <serial_port>")
        print("Example: python3 test_throttle.py /dev/cu.usbmodem14201")
        sys.exit(1)

    port = sys.argv[1]

    # Create controller
    controller = DJIThrottleController(port)

    if not controller.connect():
        print("Failed to connect. Exiting.")
        sys.exit(1)

    try:
        print("\nTest Menu:")
        print("1. Arm ESC")
        print("2. Disarm ESC")
        print("3. Set specific throttle values")
        print("4. Ramp test (one motor)")
        print("5. Emergency stop (disarm)")
        print("q. Quit")
        print()

        while True:
            choice = input("\nEnter choice: ").strip().lower()

            if choice == '1':
                controller.arm()

            elif choice == '2':
                controller.disarm()

            elif choice == '3':
                print("Enter throttle values (0-65535):")
                t1 = int(input("  Motor 1: ") or "7")
                t2 = int(input("  Motor 2: ") or "0")
                t3 = int(input("  Motor 3: ") or "944")
                t4 = int(input("  Motor 4: ") or "0")
                duration = float(input("  Duration (seconds): ") or "1.0")
                controller.set_throttle(t1, t2, t3, t4, duration)

            elif choice == '4':
                motor = int(input("Which motor (1-4): "))
                min_throttle = int(input("Min throttle (default 1000): ") or "1000")
                max_throttle = int(input("Max throttle (default 3000): ") or "3000")
                step = int(input("Step size (default 100): ") or "100")
                step_duration = float(input("Step duration (default 0.5s): ") or "0.5")

                confirm = input(f"\nRamp motor {motor} from {min_throttle} to {max_throttle}? (yes/no): ")
                if confirm.lower() == 'yes':
                    controller.ramp_test(motor, min_throttle, max_throttle, step, step_duration)

            elif choice == '5':
                print("\n!!! EMERGENCY STOP !!!")
                controller.disarm()

            elif choice == 'q':
                print("\nExiting...")
                controller.disarm()
                break

            else:
                print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\n!!! KEYBOARD INTERRUPT - EMERGENCY STOP !!!")
        controller.disarm()

    finally:
        controller.disconnect()

if __name__ == '__main__':
    main()
