# DJI Agras T40 Architecture Analysis

## Platform Overview

**Aircraft**: DJI Agras T40 (Agricultural Spray Drone)
**Motors**: 8 total (octocopter configuration)
**ESCs**: **8 ESCs** - ONE ESC per motor (confirmed by user)

## Capture Setup

Our analysis is based on sniffing **ONE serial port** of **ONE ESC**.

**Important**: Each ESC has **2 serial ports**. Since there are 8 ESCs (one per motor), the configuration is:

### Architecture: 8 Independent ESCs

```
T40 has 8 motors, each with its own ESC:

ESC 1 (Motor 1) ── Port A: RS-485
                └─ Port B: RS-485

ESC 2 (Motor 2) ── Port A: RS-485
                └─ Port B: RS-485

... (6 more ESCs) ...

ESC 8 (Motor 8) ── Port A: RS-485
                └─ Port B: RS-485
```

### Key Question: How does ONE ESC know which throttle value to use?

The 0xA021 frame contains **4 throttle values** but there are **8 ESCs**.

**Possible configurations:**

### Hypothesis 1: Bus Grouping (Most Likely)
```
ESCs are split into 2 groups of 4:

Bus A (Port A on ESCs 1-4):
  - FC sends 0xA021 with throttle values for motors 1-4
  - ESC 1 uses slot 1, ESC 2 uses slot 2, etc.

Bus B (Port B on ESCs 5-8, OR Port A on ESCs 5-8):
  - FC sends 0xA021 with throttle values for motors 5-8
  - ESC 5 uses slot 1, ESC 6 uses slot 2, etc.

We're monitoring ESC X on Bus A (one of motors 1-4)
```

### Hypothesis 2: ESC Addressing via Hardware
```
All 8 ESCs are on the same RS-485 bus (daisy-chained).
Each ESC has a hardware ID (DIP switches, solder jumpers, etc.).

When ESC receives 0xA021 frame:
  - Checks which slot corresponds to its ID
  - Uses only that throttle value
  - Ignores the other 3

Example: ESC with ID=3 always uses bytes [8:9] for throttle
```

### Hypothesis 3: Dual Frames per Update
```
FC sends TWO 0xA021 frames per update cycle:
  - Frame 1: Throttle for motors 1-4
  - Frame 2: Throttle for motors 5-8

Each ESC knows which frame to listen for based on hardware config.
Our capture only shows one of the two frames.
```

---

## What We Know

### From Capture 3 Analysis

We captured **ONE ESC's perspective** seeing these 0xA021 commands:

**Idle/Armed:**
```
Byte [2:3]  = 7      (Motor 1 or ESC slot 1)
Byte [6:7]  = 0      (Motor 2 or ESC slot 2)
Byte [8:9]  = 944    (Motor 3 or ESC slot 3) ← Battery voltage!
Byte [10:11]= 0      (Motor 4 or ESC slot 4)
```

**During Flight:**
```
Byte [2:3]  = 5477   (varying throttle)
Byte [6:7]  = 95     (varying throttle)
Byte [8:9]  = 1174   (varying throttle)
Byte [10:11]= 3848   (varying throttle)
```

### Key Observation: Byte [8:9] = 944 at Idle

At idle (armed but not flying), byte [8:9] = **944**, which converts to **48.14V** using the 0.051 scaling factor.

This suggests that when motors are not spinning:
- Slot 3 reports **battery voltage** instead of throttle
- OR this ESC's "Motor 3" assignment defaults to voltage reporting

**This could mean:**
1. This ESC doesn't control motor 3 - it's just monitoring voltage
2. The FC is sending voltage feedback in that field
3. Slot 3 is reserved for telemetry/status

---

## ESC Telemetry (0xA0D0)

We also see the ESC sending telemetry at **115 Hz**:

**Idle/Armed:**
```
All 8 channels = 0x03AC = 940 → 47.9V (battery voltage fill)
```

**During Flight (~90s):**
```
Channel 0: 0x848F = 33935
Channel 1: 0x848F = 33935
Channel 2: 0x448F = 17551
Channel 3: 0x448F = 17551
Channel 4: 0x848F = 33935
Channel 5: 0x848F = 33935
Channel 6: 0x448F = 17551
Channel 7: 0x448F = 17551
```

**Pattern**: 4 pairs of values (AABBCCDD pattern)

### Possible Interpretations:

1. **One ESC controls 2 motors, reports 2× 4-channel telemetry:**
   - Channels 0-3: Motor A (RPM, current, temp, voltage?)
   - Channels 4-7: Motor B (RPM, current, temp, voltage?)

2. **One ESC reports 8 channels for system-wide status:**
   - Each pair represents one motor's telemetry
   - This ESC aggregates data from multiple sources

3. **Electrical measurements (not mechanical):**
   - Values like 33935, 17551 could be:
     - Electrical frequency (Hz)
     - Phase counts
     - PWM duty cycle
     - Back-EMF measurements

---

## Questions to Answer

### 1. How many motors does ONE ESC control?

**Test**: Apply throttle to one motor via the captured ESC. If 2 motors spin, it's a dual-motor ESC.

### 2. What are the 4 throttle values in 0xA021?

**Possibilities**:
- **Option A**: 4 throttle values sent to 4 different ESCs (we're seeing broadcasts)
- **Option B**: This ESC uses only 2 of the 4 values (for its 2 motors)
- **Option C**: All 4 values are for this ESC, but ESC only uses 2

### 3. What is the purpose of dual serial ports?

**Test scenarios**:
- Connect to both ports simultaneously, compare data
- Send commands to Port A only, see if motors respond
- Send commands to Port B only, see if motors respond
- Send different commands to A vs B, observe behavior

### 4. Is there ESC addressing?

Look at byte [0:1] in 0xA021 frames:
```
Idle:   0x1551 = 5457
Armed:  0x154E = 5454
Flying: 0x1502 = 5378
```

These values change slightly - could be:
- ESC address/ID (but varies over time - unlikely)
- Sequence number (but [16:17] is already a counter)
- Timestamp
- Unrelated field

---

## Revised Understanding

### Most Likely Architecture:

```
DJI Agras T40 (8 motors total)
├─ ESC 1 (2 motors: M1, M2)
│  ├─ Port A: RS-485 command/telemetry
│  └─ Port B: RS-485 redundant or motor-specific
├─ ESC 2 (2 motors: M3, M4)
│  ├─ Port A: RS-485
│  └─ Port B: RS-485
├─ ESC 3 (2 motors: M5, M6)
│  ├─ Port A: RS-485
│  └─ Port B: RS-485
└─ ESC 4 (2 motors: M7, M8)
   ├─ Port A: RS-485
   └─ Port B: RS-485

Flight Controller broadcasts 0xA021 frames containing:
  - 4× throttle pairs (8 motors total as 4× 16-bit values)
  - Each ESC extracts its assigned throttle values

OR:

Flight Controller sends separate 0xA021 to each ESC:
  - Each frame has 2-4 throttle values
  - We're only seeing frames sent to ONE ESC
```

---

## Next Steps for Validation

### 1. Identify which motors this ESC controls

**Experiment**: Send throttle commands via `test_throttle.py`:
```bash
# Test Motor 1 (byte [2:3])
python3 test_throttle.py /dev/cu.usbmodem14201
> Arm ESC
> Set throttle: M1=2000, M2=0, M3=944, M4=0
> Observe which physical motor spins

# Test Motor 2 (byte [6:7])
> Set throttle: M1=7, M2=2000, M3=944, M4=0

# etc.
```

### 2. Connect to the second serial port

**Setup**: Use a second Arduino/MAX485 on the ESC's Port B
- Log traffic on both ports simultaneously
- Compare: Are frames identical? Different? Related?

### 3. Decode the 8-channel telemetry

**Analysis**: During flight, correlate 0xA0D0 telemetry with throttle commands:
- Do channels 0-3 correspond to Motor 1?
- Do channels 4-7 correspond to Motor 2?
- What do the values represent? (RPM, current, temp?)

### 4. Test throttle response mapping

**Procedure**:
1. Arm ESC
2. Slowly ramp byte [2:3] from 1000 → 3000
3. Note which motor responds
4. Repeat for bytes [6:7], [8:9], [10:11]
5. Document mapping

### 5. Investigate byte [8:9] = 944 mystery

**Why does slot 3 default to voltage?**
- Could be a status/heartbeat field
- Could indicate this ESC doesn't use that slot
- Could be FC sending voltage reference to all ESCs

---

## Updated Safety Warnings

Since this is a **8-motor agricultural drone**:
- Motors are likely VERY powerful (T40 carries 40kg spray payload)
- ESCs are high-current (possibly 50A+ per motor)
- **EXTRA CAUTION** needed during testing
- Start with very low throttle values (1000-1200)
- Secure ESC/motor to bench to prevent movement
- Use current-limited power supply if possible

---

## Summary

We've successfully reverse-engineered the basic protocol, but the **full picture** requires understanding:
1. How many motors per ESC (likely 2)
2. Which throttle slots this ESC uses (likely 2 of the 4)
3. Purpose of dual serial ports per ESC
4. Whether commands are broadcast or addressed

The **test_throttle.py** script should still work, but we may find that only 2 of the 4 throttle values actually control motors on this particular ESC.

**Next Action**: Run controlled throttle tests (NO PROPS!) to map which bytes control which motors.
