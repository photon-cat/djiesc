# Power-Up Logging Guide

Complete system for logging DJI ESC frames from power-up for analysis.

## Quick Start

### 1. Upload Firmware

Upload `busprint.ino` to your SAMD21 board (only need to do this once).

### 2. Start Logger

```bash
python3 buslog.py
```

Or specify port and output name:

```bash
python3 buslog.py -p /dev/cu.usbmodem14201 -o powerup_test1
```

### 3. Power Up Drone

Once you see:
```
============================================================
FRAME LOGGER RUNNING
============================================================
Power up your drone now to capture from startup
Press Ctrl+C to stop logging
============================================================
```

**NOW power up your drone!** The logger will capture all frames from the moment power is applied.

### 4. Stop Logging

Press `Ctrl+C` when done.

## Output Files

The logger creates two files:

### 1. `.log` - Human-readable log with timestamps

```
[0000000523ms +000000ms] #00001 ESC_TELEM seq=0 V=47.94V
[0000000531ms +000008ms] #00002 ESC_TELEM seq=1 V=47.94V
[0000000539ms +000016ms] #00003 ESC_TELEM seq=2 V=47.94V
[0000000723ms +000200ms] #00004 FC_QUERY timestamp=464229 V=48.20V
```

**Format:**
- `[timestamp_ms]` - Arduino milliseconds since power-on
- `+elapsed_ms` - Time since first frame
- `#frame_num` - Sequential frame number
- Description with decoded values

### 2. `.csv` - Structured data for analysis

```csv
frame_num,timestamp_ms,elapsed_ms,cmd_id,sequence,length,payload_hex,raw_hex
1,523,0,0xA0D0,0,26,AC 03 AC 03 AC 03...,55 1A 00 D0 A0...
2,531,8,0xA0D0,1,26,AC 03 AC 03 AC 03...,55 1A 00 D0 A0...
```

**Columns:**
- `frame_num` - Sequential number
- `timestamp_ms` - Arduino timestamp
- `elapsed_ms` - Time since first frame
- `cmd_id` - Command ID (0xA0D0, 0xA021, etc.)
- `sequence` - Frame sequence number
- `length` - Frame length
- `payload_hex` - Payload bytes in hex
- `raw_hex` - Complete frame in hex

## Usage Examples

### Capture 30 seconds after power-up

```bash
python3 buslog.py -d 30
```

### Capture with custom name

```bash
python3 buslog.py -o "drone_powerup_test1"
```

Creates:
- `drone_powerup_test1.log`
- `drone_powerup_test1.csv`

### Specify serial port

```bash
python3 buslog.py -p /dev/cu.usbmodem14201
```

## Analyzing Captures

### View summary in terminal

```bash
# Count frames by type
grep "ESC_TELEM" capture_*.log | wc -l
grep "FC_QUERY" capture_*.log | wc -l

# Find first FC query
grep "FC_QUERY" capture_*.log | head -1

# Look for voltage changes
grep "V=" capture_*.log | head -20
```

### Analyze with Python

```python
import pandas as pd

# Load CSV
df = pd.read_csv('capture_20250104_182000.csv')

# Show first 10 frames
print(df.head(10))

# Filter by command
esc_frames = df[df['cmd_id'] == '0xA0D0']
fc_frames = df[df['cmd_id'] == '0xA021']

print(f"ESC telemetry: {len(esc_frames)} frames")
print(f"FC queries: {len(fc_frames)} frames")

# Plot timing
import matplotlib.pyplot as plt
plt.plot(df['elapsed_ms'] / 1000, df['frame_num'])
plt.xlabel('Time (seconds)')
plt.ylabel('Frame Number')
plt.title('Frame Rate Over Time')
plt.show()
```

### Use existing tools

```bash
# Decode with decode.py (if you have scope CSV format)
python3 decode.py capture.csv decoded_frames.csv

# Analyze telemetry
python3 analyze_telemetry.py decoded_frames.csv
```

## What to Look For

### Power-Up Sequence

1. **First frames** (0-500ms): Watch for initialization messages
2. **Voltage ramp** (0-2s): Battery voltage should stabilize
3. **FC handshake** (0-5s): First 0xA021 query from flight controller
4. **Steady state** (5s+): Regular telemetry pattern established

### Interesting Events

- **Power-on reset**: First few frames after power
- **ESC initialization**: Watch sequence numbers reset
- **FC connection**: First 0xA021 frame indicates FC is alive
- **Arming sequence**: Changes in telemetry when armed (need to capture armed state)

### Frame Rate Analysis

**Expected rates:**
- ESC Telemetry (0xA0D0): ~115Hz (every 8-9ms)
- FC Query (0xA021): ~5Hz (every 200ms, interleaved with ~8 telemetry frames)

**Anomalies to watch:**
- Missing sequence numbers (dropped frames)
- Timing gaps (communication issues)
- Burst vs steady rate (startup vs running)

## Tips

### Get clean power-up capture

1. Start logger first
2. **Then** power drone (battery or bench supply)
3. Let it run for at least 10 seconds
4. Stop logger

### Capture multiple tests

```bash
python3 buslog.py -o test1 -d 30
# Power cycle drone
python3 buslog.py -o test2 -d 30
# Power cycle drone
python3 buslog.py -o test3 -d 30
```

Compare logs to see if power-up is consistent.

### Watch console

The logger prints every 50 frames:
```
  Logged 50 frames... [0.4s] ESC_TELEM seq=2 V=47.94V
  Logged 100 frames... [0.9s] ESC_TELEM seq=4 V=47.94V
  Logged 150 frames... [1.3s] ESC_TELEM seq=6 V=47.94V
```

This confirms data is flowing and shows current state.

## Troubleshooting

### "ERROR: No serial device found"

```bash
# List available ports
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"

# Then specify manually
python3 buslog.py -p /dev/cu.usbmodem14201
```

### No frames logged

1. Check busprint.ino is uploaded and running
2. Verify RS-485 wiring (A, B, GND)
3. Check baud rate (should be 115200)
4. Ensure drone is powered on

### Partial frames / errors

```
ERROR,523,TIMEOUT,55 1A 00
```

Indicates:
- Bus noise or interference
- Wrong baud rate
- Loose connections
- Start capture in middle of frame (normal for first frame)

### Too many frames (disk space)

Stop and restart logger, or use duration limit:

```bash
python3 buslog.py -d 60  # Stop after 60 seconds
```

Typical rates:
- 115Hz × 60s = ~7000 frames
- ~200KB per minute

## Next Steps

Once you have captures:

1. **Compare idle vs armed** - Capture with motor stopped vs spinning
2. **Identify all channels** - See which telemetry values change
3. **Decode checksums** - Reverse engineer CRC algorithm
4. **Test commands** - Use interface.py to send frames
5. **Build controller** - Create your own ESC interface

Good luck! 🚀
