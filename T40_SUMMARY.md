# DJI Agras T40 - ESC Control Summary

## Confirmed Architecture

**Platform**: DJI Agras T40 Agricultural Drone
**Configuration**: 8 motors, 8 ESCs (one ESC per motor)
**Capture**: Monitoring ONE serial port of ONE of the 8 ESCs

---

## How 8 ESCs Work with 4 Throttle Slots

### The Setup

Each 0xA021 command frame contains **4 throttle values** (16-bit each):
- Slot 1: Bytes [2:3]
- Slot 2: Bytes [6:7]
- Slot 3: Bytes [8:9]
- Slot 4: Bytes [10:11]

But there are **8 ESCs** total!

### Most Likely Configuration: Dual Bus Architecture

```
Flight Controller
├─ Bus A (RS-485) ────┬── ESC 1 (Motor 1) - uses Slot 1
│                     ├── ESC 2 (Motor 2) - uses Slot 2
│                     ├── ESC 3 (Motor 3) - uses Slot 3
│                     └── ESC 4 (Motor 4) - uses Slot 4
│
└─ Bus B (RS-485) ────┬── ESC 5 (Motor 5) - uses Slot 1
                      ├── ESC 6 (Motor 6) - uses Slot 2
                      ├── ESC 7 (Motor 7) - uses Slot 3
                      └── ESC 8 (Motor 8) - uses Slot 4
```

**How it works:**
1. FC sends same 0xA021 frame format to both buses
2. Bus A carries throttle commands for motors 1-4
3. Bus B carries throttle commands for motors 5-8
4. Each ESC is hardcoded/configured to use one of the 4 slots
5. ESC extracts its throttle value and ignores the other 3

### Each ESC's Dual Ports

Each ESC has 2 RS-485 ports. Possible uses:

**Option A: Daisy-chain connection**
```
FC ─→ [ESC 1] ─→ [ESC 2] ─→ [ESC 3] ─→ [ESC 4]
        Port A   Port B   Port A   Port B   Port A   Port B
```
Ports connect ESCs in series on the bus.

**Option B: Redundancy**
```
ESC receives same signal on both ports for fault tolerance
```

**Option C: Different data streams**
```
Port A: Command input (0xA021)
Port B: Telemetry output (0xA0D0) OR forwarding to next ESC
```

---

## What We Captured

We're monitoring **ONE ESC** on what's likely **Bus A** (motors 1-4).

### Observed Behavior

**At Idle (Armed, Not Flying):**
```
Slot 1: 7
Slot 2: 0
Slot 3: 944      ← Battery voltage (48.2V)!
Slot 4: 0
```

**During Flight (~90s):**
```
Slot 1: 5477
Slot 2: 95
Slot 3: 1174
Slot 4: 3848
```

All 4 slots vary independently during flight, confirming they control different motors.

### The Mystery: Slot 3 = Voltage at Idle

Why does slot 3 show **944** (battery voltage) when idle?

**Possible explanations:**
1. **Voltage reference**: FC sends battery voltage in slot 3 for calibration
2. **This ESC doesn't use slot 3**: ESC uses slot 1, 2, or 4; slot 3 is for another ESC
3. **Motor-specific idle**: Motor 3 has different idle behavior
4. **Feedback loop**: FC echoes voltage measurement in unused slots

---

## How to Identify Your ESC

Run the identification script to determine which slot controls your motor:

```bash
python3 identify_esc.py /dev/cu.usbmodem14201
```

The script will:
1. Arm the ESC
2. Test each slot (1-4) with throttle = 1500
3. Ask you to observe which slot makes the motor respond
4. Report which slot this ESC uses

**Example outcome:**
```
Slot 1: Motor responds ✓
Slot 2: No response
Slot 3: No response
Slot 4: No response

→ This ESC uses Slot 1 (bytes [2:3])
→ This is Motor 1 (or Motor 5 if on Bus B)
```

---

## Protocol Summary

### To Control ONE Motor via This ESC:

1. **Identify the slot** (using `identify_esc.py`)
2. **Send 0xA021 frames** at 12.5 Hz with:
   - ARM_FLAG = 0x80 (byte 15)
   - Your slot's throttle = desired value (0-65535)
   - Other slots = idle values (7, 0, 944, 0)
3. **ESC will respond** to only its assigned slot

### Frame Structure:

```python
# Example for ESC using Slot 2 (bytes [6:7])
payload = bytearray(26)
payload[0:2] = struct.pack('<H', 5454)      # Unknown (constant-ish)
payload[2:4] = struct.pack('<H', 7)         # Slot 1 (idle)
payload[4:6] = struct.pack('<H', 152)       # Unknown (constant)
payload[6:8] = struct.pack('<H', 2000)      # ← Slot 2 THROTTLE (THIS ESC)
payload[8:10] = struct.pack('<H', 944)      # Slot 3 (voltage)
payload[10:12] = struct.pack('<H', 0)       # Slot 4 (idle)
payload[12:15] = b'\x00\x00\x00'
payload[15] = 0x80                          # ARM FLAG
payload[16:18] = struct.pack('<H', counter)
payload[18:22] = b'\x00\x00\x00\x00'
payload[22] = 0x40                          # State byte
payload[23:26] = b'\x00\x00\x00'
```

---

## Next Steps

1. **Run `identify_esc.py`** to determine which slot controls your motor
2. **Map the motor number** (physical motor 1-8 on the drone)
3. **Test throttle range** - find min/max safe values
4. **Monitor telemetry** (0xA0D0) to understand ESC feedback
5. **Connect to Port B** (if possible) to see what's on the other port

---

## Safety Reminders

- ⚠️ **NO PROPELLERS** during ALL testing
- ⚠️ **Secure motor/ESC** to prevent movement
- ⚠️ **Start with low throttle** (1000-1500)
- ⚠️ **Monitor temperature** - ESCs can overheat quickly
- ⚠️ **Have kill switch ready** (battery disconnect)

The T40 is a **heavy-lift agricultural drone** - motors are extremely powerful!

---

## Files for Testing

- **[test_throttle.py](test_throttle.py)** - Manual throttle control
- **[identify_esc.py](identify_esc.py)** - Determine which slot controls your motor
- **[THROTTLE_PROTOCOL.md](THROTTLE_PROTOCOL.md)** - Full protocol specification
- **[T40_ARCHITECTURE.md](T40_ARCHITECTURE.md)** - Detailed architecture analysis
