# RS-485 Interface Debugging Guide

## Problem: Garbage Output

When you see garbage like `y@U P @ @ @ @ @ @` in the serial monitor, it indicates one of these issues:

### 1. Baud Rate Mismatch (Most Common)

**Symptoms:** Consistent garbage characters, sometimes recognizable patterns

**Solutions:**

Edit line 15 in `busprint.ino`:
```cpp
#define RS485_BAUD 115200  // Try: 9600, 19200, 38400, 57600, 115200, 230400
```

Common DJI ESC baud rates:
- **115200** (most common for DJI)
- 57600
- 38400
- 19200

Try each one systematically.

### 2. Wiring Issues

**Check these connections:**

```
SAMD21 Pin    →    MAX485 Pin
---------------------------------
D7 (RX)       →    RO (Receiver Output)
D6 (TX)       →    DI (Driver Input)
D2            →    DE + RE (tied together)
3.3V          →    VCC
GND           →    GND

MAX485        →    DJI ESC Cable
---------------------------------
A             →    A+ or D+ (differential positive)
B             →    A- or D- (differential negative)
GND           →    Signal Ground
```

**Critical checks:**
- ✓ RX/TX not swapped
- ✓ A/B polarity correct (try swapping if still garbage)
- ✓ Common ground between SAMD21, MAX485, and ESC
- ✓ DE/RE pins are tied together and connected to D2

### 3. Signal Polarity (A/B Swap)

If baud rate is correct but still garbage, try **swapping A and B** on the MAX485:

```
Try #1: A→A+, B→A-
Try #2: A→A-, B→A+  (swap these if first doesn't work)
```

### 4. Missing Termination

If you see intermittent garbage or missing bytes:

Add **120Ω resistor** across A and B terminals if you're at the end of the bus.

### 5. Voltage Levels

**Check:**
- MAX485 VCC should be 3.3V (matches SAMD21)
- DJI bus might be 3.3V or 5V
- Most MAX485 modules tolerate both

## Debugging Steps

### Step 1: Upload Updated `busprint.ino`

The updated version prints clean hex output:

```
========================================
SAMD21 RS-485 Bus Monitor (Hex Mode)
========================================
RS-485 Baud: 115200
DE/RE Pin: 2 (LOW = RX mode)

Waiting for data...

[1] 0x55 0x1a 0x00 0xd0 0xa0 0x00 0x00 0x07 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03
[17] 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03 0x76 0xda
```

### Step 2: Test Loopback

Type `TEST` in Serial Monitor. This sends 0x55 on the bus.

**Expected behavior:**
- If you see `0x55` in the output → wiring is correct, check baud rate
- If you don't see anything → wiring problem or DE/RE control issue

### Step 3: Try Different Baud Rates

Edit `busprint.ino` line 15 and try each:

```cpp
#define RS485_BAUD 9600     // Upload and test
#define RS485_BAUD 19200    // Upload and test
#define RS485_BAUD 38400    // Upload and test
#define RS485_BAUD 57600    // Upload and test
#define RS485_BAUD 115200   // Upload and test (default)
```

**What to look for:**
- Correct baud: You'll see `0x55` sync bytes and patterns
- Wrong baud: Random garbage or all zeros

### Step 4: Check Signal with Logic Analyzer (if available)

If you have a logic analyzer or oscilloscope:

1. Probe RO pin on MAX485
2. Set analyzer to UART, try different baud rates
3. Look for clean square waves with proper timing

**Expected signal:**
- ~8.68 µs per bit @ 115200 baud
- Idle high, start bit low

## Expected Good Output

When working correctly, you should see:

```
[1] 0x55 0x1a 0x00 0xd0 0xa0 0x00 0x00 0x07 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03
[17] 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03 0x76 0xda 0x55 0x1a 0x00 0xd0 0xa0 0x00
[33] 0x00 0x00 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03 0xac 0x03
[49] 0xac 0x03 0x5b 0xaa
```

**Markers of success:**
- ✓ `0x55` sync byte appears regularly (start of frame)
- ✓ Repeating patterns (`0xac 0x03`)
- ✓ Frame structure matches protocol (26-36 bytes per frame)

## Commands in Serial Monitor

Type these in the Serial Monitor input:

- `HELP` - Show available commands
- `STATS` - Show byte count and uptime
- `RESET` - Reset byte counter
- `TEST` - Send 0x55 test byte (check loopback)

## Common Issues & Fixes

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| All zeros `0x00 0x00 0x00` | No signal / disconnected | Check wiring, ensure ESC is powered |
| Garbage like `y@U P @` | Wrong baud rate | Try different baud rates |
| Some good frames, some bad | Loose connection | Check solder joints, connectors |
| Nothing at all | DE/RE stuck high | Check D2 control, ensure LOW for RX |
| Intermittent dropout | Missing termination | Add 120Ω resistor A-B |
| Half the data wrong | A/B polarity | Swap A and B wires |

## Verify Hardware Setup

### Multimeter Tests:

1. **Power:** Measure VCC on MAX485 (should be 3.3V)
2. **Ground:** Continuity between all GND points
3. **DE/RE control:** Measure D2 voltage (should be ~0V in receive mode)
4. **A-B resistance:** ~120Ω if terminated, higher if not

### Visual Inspection:

- ✓ No cold solder joints
- ✓ Wires not crossed
- ✓ MAX485 chip not overheating
- ✓ All connections secure

## Next Steps After Success

Once you see clean hex output:

1. **Decode frames:** Use `decode.py` with captured data
2. **Identify patterns:** Look for `0x55` sync bytes
3. **Parse protocol:** Match against protocol.md
4. **Test transmission:** Use `interface.ino` to send frames

## Still Not Working?

### Check these less common issues:

1. **Wrong Serial1 pins:** Verify your SAMD21 board's Serial1 TX/RX pins
2. **MAX485 variant:** Some modules have different pinouts (check datasheet)
3. **Bus capacitance:** Very long wires need slower baud rates
4. **EMI/noise:** Add ferrite beads or shielded cable
5. **Multiple talkers:** If multiple devices transmit simultaneously, collision causes garbage

### Last resort:

Try a different MAX485 module - some cheap ones have poor quality receivers.
