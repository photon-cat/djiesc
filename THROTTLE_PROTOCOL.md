# DJI ESC RS-485 Throttle Control Protocol

## Reverse-Engineered from Capture 3 Analysis

**Platform**: DJI Agras T40 (8-motor agricultural drone)
**Capture Source**: ONE serial port of ONE ESC (ESCs have 2 ports each)

⚠️ **IMPORTANT**: This analysis is based on monitoring a single ESC. The T40 has 8 motors total.
The 4 throttle values in the 0xA021 frame may represent:
- 4 ESCs (2 motors each), OR
- Multiplexed commands where each ESC uses a subset

See [T40_ARCHITECTURE.md](T40_ARCHITECTURE.md) for platform details.

This document describes the protocol structure observed on ONE ESC's RS-485 interface.

---

## Command Frame: 0xA021 (FC → ESC)

**Direction**: Flight Controller → ESC
**Frequency**: ~12.5 Hz (every 80ms)
**Total Length**: 36 bytes (header + 26 payload + CRC)

### Frame Structure

```
Offset | Size | Name           | Description
-------|------|----------------|--------------------------------------------
0x00   | 1    | Sync           | 0x55 (frame start marker)
0x01   | 1    | Length         | 0x24 (36 bytes total)
0x02   | 1    | Flags          | 0x00 (normal operation)
0x03   | 2    | Command ID     | 0xA021 (little-endian)
0x05   | 2    | Reserved       | 0x01 0x00 (ESC→FC), or varies
0x07   | 1    | Sequence       | 0x00 (not used in this command)
0x08   | 26   | Payload        | Command data (see below)
0x22   | 2    | CRC-16         | Checksum (little-endian)
```

---

## Payload Structure (26 bytes)

The 0xA021 payload contains motor throttle commands and status fields:

```
Byte Range | Type    | Name              | Description
-----------|---------|-------------------|--------------------------------------------
[0:1]      | uint16  | Unknown_A         | Varies (~5454), purpose unknown
[2:3]      | uint16  | Throttle_Motor_1  | Motor 1 throttle (0-65535)
[4:5]      | uint16  | Unknown_B         | Minor variation (~152-160)
[6:7]      | uint16  | Throttle_Motor_2  | Motor 2 throttle (0-65535)
[8:9]      | uint16  | Throttle_Motor_3  | Motor 3 throttle (0-65535)
[10:11]    | uint16  | Throttle_Motor_4  | Motor 4 throttle (0-65535)
[12:14]    | 3 bytes | Zeros             | 0x00 0x00 0x00 (constant)
[15]       | uint8   | ARM_FLAG          | 0x00 = disarmed, 0x80 = armed
[16:17]    | uint16  | Counter           | Incrementing counter (~1-2000)
[18:21]    | 4 bytes | Zeros             | 0x00 0x00 0x00 0x00 (constant)
[22]       | uint8   | State_Byte        | Flight phase indicator
[23:25]    | 3 bytes | Unknown_C         | Varies during flight
```

### All values are LITTLE-ENDIAN (LSB first)

---

## Key Fields

### ARM_FLAG (Byte 15)

Controls whether the ESC will respond to throttle commands:

- **0x00** = Disarmed (motors will NOT spin, even if throttle > 0)
- **0x80** = Armed (motors will spin according to throttle values)

### Throttle Values (16-bit each)

Four 16-bit throttle values are present in each frame:

| Field              | Byte Range | Observed Values                          |
|--------------------|------------|------------------------------------------|
| Throttle_Slot_1    | [2:3]      | Idle: 7, Flying: 0-5500+                 |
| Throttle_Slot_2    | [6:7]      | Idle: 0, Flying: 0-300+                  |
| Throttle_Slot_3    | [8:9]      | Idle: 944-945, Flying: 1000-1200+        |
| Throttle_Slot_4    | [10:11]    | Idle: 0, Flying: 3000-4000+              |

⚠️ **IMPORTANT**: The T40 has 8 motors, but we only see 4 throttle values. Possibilities:
1. This frame is broadcast to 4 ESCs, each ESC uses one value (2 motors per ESC)
2. This ESC uses 2 of the 4 values for its 2 motors
3. The other 4 motors are controlled via the second serial port

**Note**: When armed but idle (motors not spinning), throttle values are:
- Slot 1: ~7
- Slot 2: ~0
- Slot 3: ~944-945 ← **This is battery voltage (48.2V)!** May not be a motor.
- Slot 4: ~0

**Note 2**: The throttle scale appears to be 0-65535 (full 16-bit range), but actual flight values observed were in the 0-5500 range during normal flight.

**Testing Required**: Use `test_throttle.py` to determine which slots control which motors on your specific ESC.

### State_Byte (Byte 22)

Changes during different flight phases:

- **0x00, 0x40, 0x80, 0xC0**: Observed during armed/idle and low-throttle phases
- **0x01, 0x41, 0x81, 0xC1**: Observed during active flight

Likely a bitfield:
- Bit 0: Unknown
- Bit 6 (0x40): Toggles periodically
- Bit 7 (0x80): Related to throttle state

---

## Observed Protocol Sequences

### 1. Power-Up → Disarmed Idle

```
ARM_FLAG = 0x00
Throttle 1-4 = 0, 0, 0, 0
```

### 2. Arming Sequence (~69s in capture)

```
ARM_FLAG changes: 0x00 → 0x80
Throttle 1 = 7
Throttle 2 = 0
Throttle 3 = 944-945  (battery voltage)
Throttle 4 = 0
```

**Timeline**:
- Flight controller sets ARM_FLAG = 0x80
- ESCs perform beep-beep-beep confirmation (~71-72s)
- Motors click 3 times (~75s) - alignment test
- Props can now spin if throttle > idle threshold

### 3. Motor Engagement (~75s)

```
ARM_FLAG = 0x80
Throttles remain at armed-idle values
Motors click (partial rotation) - cogging/alignment
Props begin to spin at low speed
```

### 4. Active Flight (~90s)

```
ARM_FLAG = 0x80
Throttle 1 = 5477
Throttle 2 = 95
Throttle 3 = 1174
Throttle 4 = 3848
```

All 4 throttle values vary independently to control attitude and altitude.

---

## Telemetry Response: 0xA0D0 (ESC → FC)

**Direction**: ESC → Flight Controller
**Frequency**: ~115 Hz (every 8-10ms)
**Total Length**: 26 bytes (header + 26 payload + CRC)

### Payload Structure (26 bytes)

```
8 channels × 16-bit little-endian values

Observed during flight (90s):
  Channel 0: 0x848F = 33935
  Channel 1: 0x848F = 33935
  Channel 2: 0x448F = 17551
  Channel 3: 0x448F = 17551
  Channel 4: 0x848F = 33935
  Channel 5: 0x848F = 33935
  Channel 6: 0x448F = 17551
  Channel 7: 0x448F = 17551
```

**Note**: These values are NOT voltage! They appear to be:
- **RPM** (most likely)
- Possibly ESC phase counts or electrical frequency
- Pattern shows 4 pairs of values (matching 4 motors with dual measurements?)

### Idle/Armed Telemetry

When armed but motors not spinning:
```
All 8 channels = 0x03AC = 940 → 47.9V (battery voltage)
```

This confirms that when motors are idle, the ESC fills telemetry channels with battery voltage.

---

## Summary: Controlling the ESC

### To ARM the ESC:

Send 0xA021 commands at ~12.5 Hz with:
```
ARM_FLAG (byte 15) = 0x80
Throttle 1-4 = idle values (e.g., 7, 0, 944, 0)
```

### To DISARM the ESC:

```
ARM_FLAG (byte 15) = 0x00
Throttle 1-4 = 0, 0, 0, 0
```

### To Control Motor Speed:

1. Ensure ARM_FLAG = 0x80
2. Set Throttle values (bytes [2:3], [6:7], [8:9], [10:11])
3. Send continuously at ~12.5 Hz

**IMPORTANT**:
- Never stop sending 0xA021 commands while armed - the ESC expects continuous updates
- If commands stop, ESC will likely enter failsafe mode
- Use watchdog/failsafe in your code

### Throttle Calibration Recommendations:

Based on observed values:
- **Idle/Armed**: ~0-1000
- **Low throttle**: 1000-2000
- **Medium throttle**: 2000-4000
- **High throttle**: 4000-6000
- **Maximum**: Up to 65535 (theoretical), but flight data suggests ~6000-8000 is practical max

**Test carefully with props OFF first!**

---

## Example Frame Construction

### Armed, Idle Motors

```python
import struct

payload = bytearray(26)
payload[0:2] = struct.pack('<H', 5454)   # Unknown_A
payload[2:4] = struct.pack('<H', 7)      # Throttle Motor 1 (idle)
payload[4:6] = struct.pack('<H', 152)    # Unknown_B
payload[6:8] = struct.pack('<H', 0)      # Throttle Motor 2 (idle)
payload[8:10] = struct.pack('<H', 944)   # Throttle Motor 3 (idle)
payload[10:12] = struct.pack('<H', 0)    # Throttle Motor 4 (idle)
payload[12:15] = b'\x00\x00\x00'         # Zeros
payload[15] = 0x80                        # ARM_FLAG = Armed
payload[16:18] = struct.pack('<H', counter)  # Incrementing counter
payload[18:22] = b'\x00\x00\x00\x00'     # Zeros
payload[22] = 0x40                        # State byte
payload[23:26] = b'\x00\x00\x00'         # Unknown_C

# Wrap in frame with 0xA021 command ID and checksum
```

### Flying, Throttle Applied

```python
payload[2:4] = struct.pack('<H', 3000)   # Throttle Motor 1
payload[6:8] = struct.pack('<H', 150)    # Throttle Motor 2
payload[8:10] = struct.pack('<H', 2000)  # Throttle Motor 3
payload[10:12] = struct.pack('<H', 3500) # Throttle Motor 4
payload[15] = 0x80                        # ARM_FLAG = Armed
```

---

## Safety Warnings

1. **NEVER test with propellers attached** until you've validated the protocol
2. **Always have a physical kill switch** (disconnect battery)
3. **Implement failsafe** - if FC stops responding, ESC should disarm
4. **Start with very low throttle values** (~1000-1500) for initial testing
5. **Monitor battery voltage** - ESCs may shut down on low voltage
6. **Respect the communication timing** - send commands at consistent 12.5 Hz rate

---

## Next Steps for Implementation

1. **Create test script** using `interface.py` to send 0xA021 commands
2. **Validate arming** - confirm ESC beeps when ARM_FLAG=0x80 is sent
3. **Test throttle response** - gradually increase throttle values (NO PROPS!)
4. **Monitor telemetry** - decode 0xA0D0 responses to verify ESC state
5. **Implement safety features** - watchdog, failsafe, emergency stop

Good luck and fly safe! 🚁
