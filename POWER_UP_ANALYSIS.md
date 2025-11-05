# Power-Up Sequence Analysis

Analysis of `capture_20251104_183751.csv` - Drone power-on for ~14 seconds.

## Summary Statistics

- **Total frames**: 1,517
- **Duration**: 13.7 seconds
- **Start timestamp**: 331675ms (Arduino already running when drone powered on)

## Frame Distribution

| Command ID | Count | % of Total | Description |
|------------|-------|------------|-------------|
| **0xA0D0** | 1290 | 85.0% | ESC Telemetry (expected) |
| **0xA021** | 162 | 10.7% | FC Query (expected) |
| **0x0303** | 16 | 1.1% | **NEW - Initialization message** |
| **0x0333** | 16 | 1.1% | **NEW - Unknown** |
| **0x8866** | 16 | 1.1% | **NEW - Unknown** |
| **0x4833** | 7 | 0.5% | **NEW - Unknown** |
| **0x0C84** | 1 | 0.1% | **NEW - Unknown** |
| **0x0C8A** | 1 | 0.1% | **NEW - Unknown** |
| **0x0C36** | 3 | 0.2% | **NEW - Unknown** |
| **0x0C03** | 2 | 0.1% | **NEW - Initialization related** |
| **0x9E00** | 3 | 0.2% | **NEW - Unknown** |

## Key Discoveries

### 1. Initialization Self-Test Pattern (0-160ms)

The first frames show a **rotating 0x01F4** pattern in ESC telemetry:

```
Frame #1  [0ms]:   0xA0D0: F4 01 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03
Frame #3  [12ms]:  0xA0D0: AC 03 F4 01 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03
Frame #6  [32ms]:  0xA0D0: AC 03 AC 03 F4 01 AC 03 AC 03 AC 03 AC 03 AC 03
Frame #8  [52ms]:  0xA0D0: AC 03 AC 03 AC 03 F4 01 AC 03 AC 03 AC 03 AC 03
...
Frame #16 [132ms]: 0xA0D0: AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 F4 01 AC 03
Frame #17 [142ms]: 0xA0D0: AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 AC 03 F4 01
```

**Analysis:**
- `0x01F4` = 500 decimal
- Rotates through all 8 telemetry channels
- **This is a power-on self-test (POST) walking bit pattern**
- Confirms all 8 telemetry channels are functional
- After sequence completes (~160ms), normal operation begins

### 2. Reserved Field State Change

The 0xA0D0 frames have two different **reserved field** values:

- **0x00 0x40** (first 17 frames, 0-152ms) - **Initialization mode**
- **0x00 0x00** (all subsequent frames) - **Normal operation**

The `0x40` bit (bit 6 of first reserved byte) appears to be a **startup flag**.

### 3. New Command Types During Initialization

**Command 0x0303** - Initialization Message (16 frames total)
```
Frame #20 [162ms]: 55 13 04 03 03 0C 01 00 40 0C C0 01 02 01 00 00 00 AB 94
Frame #22 [177ms]: 55 13 04 03 03 2C 02 00 40 0C C0 01 02 01 00 00 00 A8 41
...
```
- Appears from 162ms to 282ms
- Fixed length: 19 bytes (0x13)
- **Flags byte: 0x04** (different from 0x00 in normal traffic!)
- Sequence field increments in payload (0x0C, 0x2C, 0x4C, 0x6C, 0x8C, 0xAC, 0xCC, 0xEC)
- Likely: **ESC firmware version / capabilities announcement**

**Command 0x0C03** - Rare Initialization (2 frames)
```
Frame #21 [164ms]: 55 13 04 03 0C 03 01 00 C0 0C C0 00 02 01 00 00 00 08 E9
```
- Only 2 occurrences
- Very similar to 0x0303
- Appears to be a **response or acknowledgment**

**Other Commands:**
- 0x0333, 0x8866, 0x4833 - Appear later during operation (need more analysis)
- 0x9E00, 0x0C84, 0x0C8A, 0x0C36 - Rare, may be configuration or status

## Power-Up Timeline

```
T+0ms       Power applied to drone
├─ 0-3ms    First 0xA0D0 telemetry + 0xA021 query
├─ 0-150ms  Self-test: 0x01F4 walks through all 8 channels
├─ 160ms    Self-test complete, normal 0x03AC pattern begins
├─ 162-282ms ESC sends 0x0303 initialization messages
└─ 300ms+   Normal operation: steady 0xA0D0 + 0xA021 pattern
```

## Implications

### Reserved Field Bits (Byte 5-6 of 0xA0D0)

| Bit | Mask | Meaning |
|-----|------|---------|
| Bit 6 | 0x40 | Initialization/POST mode |
| Others | ? | Unknown (all zero in captured data) |

### Telemetry Channel Self-Test

The rotating `0x01F4` (500) proves:
1. **All 8 channels are independently addressable**
2. **Channels can report different values simultaneously**
3. **ESC performs a walking-bit POST on power-up**
4. **Normal value 0x03AC (940) is the "idle" placeholder**

### New Commands Discovered

**0x0303 Structure (19 bytes):**
```
55 13 04 03 03 [SEQ] [VER?] 00 40 0C C0 01 02 01 00 00 00 [CRC]
│  │  │  │  │   │     │
│  │  │  │  │   │     └─ Unknown field
│  │  │  │  │   └─────── Incrementing sequence
│  │  │  │  └─────────── Command ID (LE): 0x0303
│  │  │  └────────────── Command ID byte 1
│  │  └───────────────── Flags: 0x04 (not 0x00!)
│  └──────────────────── Length: 0x13 (19 bytes)
└─────────────────────── Sync: 0x55
```

Payload appears to contain:
- `40 0C` - Possibly firmware version
- `C0 01 02 01` - Configuration flags or capabilities
- `00 00 00` - Reserved

## Comparison: Startup vs Normal Operation

### Startup (0-300ms):
- Reserved field = 0x0040 (initialization flag)
- Telemetry shows rotating 0x01F4 self-test
- 0x0303 initialization messages broadcast
- 0x0C03 acknowledgment messages

### Normal Operation (300ms+):
- Reserved field = 0x0000
- Telemetry shows constant 0x03AC (idle voltage)
- Only 0xA0D0 and 0xA021 messages
- Steady-state communication established

## Recommendations for Further Analysis

1. **Decode 0x0303 payload completely** - likely contains:
   - ESC firmware version
   - Motor type/configuration
   - Capability flags

2. **Monitor reserved field bits** during:
   - Arming sequence
   - Motor spin-up
   - Error conditions

3. **Capture armed operation** to see:
   - Real telemetry values (RPM, current, temp)
   - Whether new command types appear
   - How reserved field changes

4. **Test hypothesis**: Try sending 0x0303 message format to query ESC info

5. **Analyze rare commands** (0x0333, 0x8866, 0x4833, 0x9E00):
   - When do they occur?
   - What triggers them?
   - Are they errors or normal status?

## Next Experiments

1. ✅ **Power-up capture** - DONE
2. **Armed idle capture** - Drone armed but motors not spinning
3. **Motor spin capture** - Throttle applied, motors running
4. **Power-down capture** - See if there's a shutdown sequence
5. **Error injection** - Disconnect/reconnect during operation

---

Excellent capture! The rotating 0x01F4 self-test and reserved field changes are smoking guns that prove the protocol has initialization states we can decode! 🎉
