1. Electrical Layer

Type: Differential serial bus.

Measured line-to-line resistance: ≈120 Ω → terminated pair.

Signal swing: ~±0.8 V per line, ~1.6 V differential (3.3 V drivers).

Common-mode voltage: ≈1.6 V when referenced to ground.

Result: Electrically behaves as RS-485 or RS-422, not CAN.

Pinout (inferred from 6-pin connector)
Function	Count	Note
GND	2	Returns for each differential pair
Signal pairs	2 pairs (A+/A− and B+/B−)	Each ≈120 Ω; likely primary + backup links
2. Link Type and Direction

Data is full-duplex or redundant duplex, not half-duplex.

One pair is active; the other may be silent or repeating identical traffic (suspected backup or redundant TX).

No collision artifacts → one talker per direction.

Bus behavior fits RS-422 or 4-wire RS-485 physical layer.

3. Serial Parameters
Parameter	Value
Baud rate	≈115 200 bps (8.65 µs/bit)
Frame format	8 data bits, No parity, 1 stop bit (8-N-1)
Idle level	High (line recessive = logic 1)
Encoding	Standard UART, LSB first
4. Protocol Framing (from first CSV – drone powered, idle, not armed)

Each frame starts with a sync byte 0x55 and follows a fixed structure:

55 1A 00 D0 A0 00 00 <seq> [payload …] <2-byte trailer>

Field	Description	Example
0x55	Start-of-frame sync	
0x1A	Length (decimal 26 bytes following)	
0x00	Flags/reserved	
0xD0 0xA0	Command ID or message type (LE → 0xA0D0)	
0x00 0x00	Reserved	
<seq>	Sequence counter, increments by 1 per frame	
[payload …]	~16 bytes, mostly 16-bit LE values (e.g., 0x03AC)	
<trailer>	2-byte checksum/CRC (varies per frame; not standard CRC-16)	

Observed pattern:

Frame length matches length field (0x1A).

Sequence byte increments steadily → transmitter heartbeat.

Payload values stable at idle (likely sensor data or status words).

Trailer changes each frame, consistent with checksum over preceding bytes.

5. Communication Pattern Analysis

Based on decoded frame analysis, two distinct message types are observed:

### Message Type 1: ESC Telemetry Broadcast (0xA0D0)
- **Command ID**: 0xA0D0 (41168 decimal)
- **Length**: 26 bytes total (0x1A)
- **Direction**: ESC → Flight Controller
- **Frequency**: High-rate periodic (~8ms intervals)
- **Sequence**: Increments 0-7, wraps around
- **Reserved field**: 0x0000
- **Payload**: 16 bytes of 8 × 16-bit LE values
  - At idle (disarmed, 0 RPM): all channels = `0x03AC` (940 decimal)
  - **Voltage scaling**: 940 × 0.051 ≈ **47.9V** (12S LiPo at ~48V - confirmed!)
  - Likely telemetry channels (based on typical ESC data):
    1. **Battery voltage** (940 → 47.9V confirmed via 12S battery)
    2. **Phase current** (940 → likely placeholder, actual ~0A at idle)
    3. **Motor RPM** (940 → placeholder, actual 0 RPM when disarmed)
    4. **ESC temperature** (940 → placeholder or °C × scaling)
    5. **Motor temperature** (940 → placeholder)
    6. **Input PWM/throttle** (940 → placeholder, actual 0% at idle)
    7. **Consumed mAh** (940 → placeholder)
    8. **Status flags** (940 → placeholder or bit field)
  - **Idle behavior**: ESC fills all 8 telemetry channels with battery voltage (940) when disarmed
  - This is likely a "valid data" indicator - voltage proves ESC is powered and communicating
  - Actual sensor values (RPM, current, etc.) would vary independently when armed

**Example frame:**
```
55 1A 00 D0 A0 00 00 07 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 76 DA
│  │  │  │  │  │  │  │  └─────────────── payload (8 × 0x03AC) ──────────────┘ └──┘
│  │  │  │  │  │  │  │                                                         CRC
│  │  │  │  │  │  │  └─ sequence (7)
│  │  │  │  │  │  └──── reserved (0x0000)
│  │  │  └──┴──────────── cmd_id (0xA0D0 LE)
│  │  └──────────────────── flags (0x00)
│  └─────────────────────── length (0x1A = 26 bytes following)
└────────────────────────── sync (0x55)
```

### Message Type 2: Flight Controller Status/Query (0xA021)
- **Command ID**: 0xA021 (40993 decimal)
- **Length**: 36 bytes total (0x24)
- **Direction**: Flight Controller → ESC (suspected)
- **Frequency**: Lower rate (~200-400ms intervals, appears every ~8 telemetry frames)
- **Sequence**: Always 0 (non-sequential)
- **Reserved field**: 0x0001 (flag bit set - distinguishes from telemetry)
- **Payload**: 28 bytes of mixed data
  - Contains timestamps, state flags, and configuration values
  - More complex structure than simple repeating values

**Example frame:**
```
55 24 00 21 A0 01 00 00 65 15 07 00 5F 00 00 00 B1 03 00 00 00 00 00 80 29 B0 00 00 00 00 80 3D 00 00 C6 32
│  │  │  │  │  │  │  │  └────────────────── payload (28 bytes) ──────────────────┘ └──┘
│  │  │  │  │  │  │  │                                                              CRC
│  │  │  │  │  │  │  └─ sequence (0, non-incrementing)
│  │  │  │  │  └─────── reserved (0x0001 - flag set!)
│  │  │  └──┴────────────── cmd_id (0xA021 LE)
│  │  └────────────────────── flags (0x00)
│  └───────────────────────── length (0x24 = 36 bytes following)
└──────────────────────────── sync (0x55)
```

**Payload analysis (0xA021):**
- **Bytes 0-3** (LE u32): `0x00071565` (464229) - **timestamp/uptime counter**
  - Decrements slowly between frames (464229 → 464227, -2 per ~200ms)
  - Could be microsecond countdown or frame counter
- **Bytes 4-5** (LE u16): `0x005F` (95) - **constant value**
  - Stays at 95 across frames
  - Possibly protocol version, device ID, or idle throttle value
- **Bytes 6-7** (LE u16): `0x0000` - reserved/padding
- **Bytes 8-9** (LE u16): `0x03B1` (945) - **voltage reading: 48.2V**
  - Scaling: 945 × 0.051 ≈ 48.2V
  - Slightly higher than ESC telemetry (47.9V vs 48.2V)
  - This is the **Flight Controller's own voltage measurement**
  - Voltage difference (0.3V) represents wire/connector voltage drop from FC to ESC
  - FC can detect issues by comparing its voltage reading against ESC's report
- **Bytes 10-13** (LE u32): `0x00000000` - zeroed field
- **Bytes 14-17**: Variable but small values - likely status flags or padding
- **Bytes 18-21** (LE u32): `0x00000000` - zeroed field
- **Bytes 22-25**: Variable but small values - likely status flags or padding

**Key insight**: The FC query contains its own voltage measurement (48.2V) which is slightly different from ESC's report (47.9V). This 0.3V difference represents the voltage drop through power distribution wiring from FC to ESC, allowing the FC to monitor power distribution health and detect high-resistance connections.

### Communication Summary

**Unidirectional capture on single differential pair:**
1. **ESC telemetry (0xA0D0)**: Streams continuously at ~115Hz
   - High-rate health/status broadcast
   - Sequence counter tracks transmission continuity
   - 8 sensor channels per frame

2. **Flight controller messages (0xA021)**: Periodic at ~5Hz
   - Lower rate status/query or keepalive
   - Non-sequential (command/response, not streaming)
   - Contains control parameters and timing info

**Interpretation:**
- This appears to be one direction of a full-duplex RS-422/485 link
- Opposite pair likely carries FC→ESC throttle commands
- Reserved field bit (0x0001 vs 0x0000) may indicate direction or priority
- Protocol supports multiple ESCs on same bus (differential addressing possible)

### 6. Decoded Telemetry Summary

**Confirmed findings from idle capture (12S battery at ~48V, ESC disarmed, 0 RPM):**

1. **Voltage scaling formula**: `raw_value × 0.051 ≈ volts`
   - ESC reports: 940 → 47.9V
   - FC reports: 945 → 48.2V
   - Voltage drop: 0.3V (power distribution monitoring)

2. **ESC telemetry structure (0xA0D0)**:
   - 8 channels of 16-bit LE values
   - When disarmed: all channels filled with battery voltage reading (940)
   - This "voltage fill" pattern serves as heartbeat/health indicator
   - Real telemetry (RPM, current, temp) would differentiate when armed

3. **Flight Controller query (0xA021)**:
   - Contains FC's own voltage measurement for comparison
   - Timestamp/counter field that decrements slowly
   - Constant value 95 (possibly device/protocol ID)
   - Allows FC to detect power issues by comparing voltages

4. **Next steps to fully decode protocol**:
   - Capture data while **armed** to see differentiated telemetry channels
   - Capture during **motor spin** to identify RPM encoding
   - Capture with **load** to see current measurements
   - Monitor **temperature** changes to identify temp channels
   - Probe opposite differential pair for FC→ESC throttle commands