# DJI ESC RS-485 Protocol Interface

Tools for interfacing with DJI ESC RS-485 communication using SAMD21 + MAX485.

## Hardware Setup

### Components
- **SAMD21 board** (e.g., Seeeduino XIAO SAMD21, Arduino Zero, MKR series)
- **MAX485 module** (RS-485 transceiver)
- **Connection to DJI ESC** (differential pair A+/A-, B+/B-)

### Wiring

```
SAMD21 XIAO          MAX485 Module
---------------------------------
D6 (TX)     ──────>  DI (Driver Input)
D7 (RX)     <──────  RO (Receiver Output)
D2          ──────>  DE + RE (tied together)
3.3V        ──────>  VCC
GND         ──────>  GND

MAX485               DJI ESC Connector
---------------------------------
A           ──────>  A+ (or B+, depending on pair)
B           ──────>  A- (or B-, corresponding pair)
GND         ──────>  GND (common ground)
```

**Important Notes:**
- Connect MAX485 DE and RE pins together to D2
- Use 120Ω termination resistor across A-B if you're at the end of the bus
- Ensure common ground between all devices
- 3.3V or 5V operation (MAX485 tolerates both)

## Software Setup

### 1. Arduino Firmware

Upload `interface.ino` to your SAMD21 board:

```bash
# Open Arduino IDE
# Select: Tools > Board > SAMD21 board (e.g., "Seeeduino XIAO")
# Select: Tools > Port > /dev/cu.usbmodem... (your device)
# Upload interface.ino
```

The firmware provides:
- RS-485 frame transmission with automatic DE/RE control
- Frame reception with 0x55 sync byte detection
- USB serial interface for host communication
- Frame parsing and logging

### 2. Python Interface

Install dependencies:

```bash
pip install pyserial
```

Run the interface:

```bash
python3 interface.py
```

Or with auto-detection:

```bash
python3 interface.py --monitor  # Monitor mode
```

## Usage

### Python API

```python
from interface import RS485Interface, DJIFrame

# Connect to device
iface = RS485Interface()
iface.connect()

# Send ESC telemetry request frame (0xA0D0)
payload = bytes.fromhex('AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03')
frame = DJIFrame(cmd_id=0xA0D0, reserved=0x0000, sequence=0, payload=payload)
iface.send_frame(frame)

# Send Flight Controller query (0xA021)
payload = bytes.fromhex('65 15 07 00 5F 00 00 00 B1 03 00 00 00 00 00 80 29 B0 00 00 00 00 80 3D 00 00')
frame = DJIFrame(cmd_id=0xA021, reserved=0x0001, sequence=0, payload=payload)
iface.send_frame(frame)

# Receive frames
frames = iface.receive(timeout=5.0)
for frame in frames:
    print(frame)

# Monitor bus continuously
iface.monitor()

# Cleanup
iface.disconnect()
```

### Interactive CLI

```bash
python3 interface.py
```

Commands:
- `send <cmd_id> <seq> <payload_hex>` - Send DJI frame
- `recv [timeout]` - Receive frames for timeout seconds
- `raw <hex_bytes>` - Send raw bytes
- `monitor` - Monitor bus indefinitely
- `quit` - Exit

Examples:

```
>> send 0xA0D0 0 AC03AC03AC03AC03AC03AC03AC03AC03
>> recv 5
>> raw 55 1A 00 D0 A0 00 00 01 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 00 00
>> monitor
```

### Monitor Mode

```bash
python3 interface.py --monitor
```

Continuously displays all RS-485 traffic with timestamps.

## Protocol Documentation

See [protocol.md](protocol.md) for detailed protocol analysis including:
- Frame structure (sync, length, command ID, sequence, payload, checksum)
- Message types (0xA0D0 ESC telemetry, 0xA021 FC query)
- Voltage scaling (raw × 0.051 ≈ volts)
- Communication patterns

## Decode Tools

### decode.py

Converts scope CSV captures to decoded frame CSV:

```bash
python3 decode.py input.csv output.csv
```

Input: Scope CSV with UART bytes in "Rx" column
Output: CSV with parsed frame fields

### analyze_telemetry.py

Analyzes telemetry values from decoded frames:

```bash
python3 analyze_telemetry.py decoded_frames.csv
```

Shows voltage, sequence, and identifies frame types.

## Troubleshooting

### No frames received
- Check DE/RE control on D2 (should be LOW for receive)
- Verify RS-485 A/B polarity
- Check baud rate (115200 8N1)
- Ensure common ground

### Garbled data
- Wrong baud rate
- Swapped TX/RX pins
- Missing ground connection
- Bus termination issues

### Arduino not detected
```bash
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

Then specify port manually:
```bash
python3 interface.py -p /dev/cu.usbmodem14201
```

## Next Steps

1. **Capture real traffic** - Connect to actual DJI ESC/FC and monitor
2. **Decode checksum** - Reverse engineer the CRC/checksum algorithm
3. **Test commands** - Send throttle commands and observe responses
4. **Implement bidirectional** - Capture both differential pairs
5. **Build simulator** - Create ESC/FC simulator for testing

## License

Educational/Research use. DJI protocol is proprietary - use for analysis and compatibility purposes only.
