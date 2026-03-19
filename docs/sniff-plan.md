# RS485 Sniff Plan — Next Session

> **Date:** 2026-03-19 (tomorrow)
> **Goal:** Capture live RS485 traffic between CloudBox and XP80, decode the POLA protocol

## What You Need

- [ ] USB-RS485 adapter (FTDI FT232 or CH340-based, $5-15)
- [ ] The thermostat-pi (already on-site, Tailscale-accessible)
- [ ] 3 jumper wires

If the thermostat-pi's USB port is occupied, any Pi with a free USB port works.

## Known Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Baud rate | 9600 | CloudBox config_speed_rs485 |
| Data format | 8N1 | Standard for POLA |
| Node address | 1 | CloudBox /xp/1 ("Network node: 1") |
| XP80 serial | 7881 (0x1EC9) | CloudBox /xp/1 |
| XP80 firmware | 1.02 | CloudBox /xp/1 |
| Polling pattern | ~126 packets every ~15 seconds | Measured via packet counter |
| Bus reliability | 99.998% | 1 failure in 67,712 packets |

## Wiring (5 minutes)

```
XP80 RS485 terminals        USB-RS485 adapter on Pi
┌─────────────────┐        ┌──────────────────┐
│  + (A)  ────────┼────────┤  A / D+ / +      │
│  - (B)  ────────┼────────┤  B / D- / -      │
│  C (GND) ───────┼────────┤  GND             │
└─────────────────┘        │  TX → LEAVE      │
                           │       DISCONNECTED│
        CloudBox stays     └──────────────────┘
        connected as-is         ↓
                           Pi USB port
```

**DO NOT connect TX** — we're listening only. The CloudBox stays plugged in
and keeps polling normally. We just tap into the same bus.

The + and - wires from the CloudBox are already connected to the XP80.
Just add the sniffer adapter in parallel (same terminals).

## Steps

### 1. Install pyserial on the Pi

```bash
ssh -i ~/.ssh/tony_thermostat_ed25519 vinnie@100.123.188.60
pip3 install pyserial
```

### 2. Copy sniffer to the Pi

```bash
# From your Mac:
scp -i ~/.ssh/tony_thermostat_ed25519 \
  ~/Projects/Mushrooms/Pola/tools/sniffer.py \
  ~/Projects/Mushrooms/Pola/tools/analyze_capture.py \
  vinnie@100.123.188.60:~/
```

### 3. Plug in adapter, find the device

```bash
# On the Pi — plug in the USB-RS485 adapter, then:
ls /dev/ttyUSB*
# Should show /dev/ttyUSB0 (or /dev/ttyUSB1 if something else is on USB0)
```

### 4. Run the sniffer (5 minutes is plenty)

```bash
python3 sniffer.py --port /dev/ttyUSB0 --baud 9600 --analyze --output capture.bin --duration 300
```

This captures 5 minutes of traffic. You'll see frames scrolling in real-time.
Look for alternating short/long frames (request/response pairs).

### 5. Analyze the capture

```bash
python3 analyze_capture.py capture.bin
```

This prints:
- Frame length distribution (which sizes repeat)
- First byte analysis (likely the address byte)
- Byte position patterns (fixed headers, variable data)
- Timing (burst structure)
- Known value search (serial 7881 / 0x1EC9)

### 6. Copy capture back to Mac for deeper analysis

```bash
# From your Mac:
scp -i ~/.ssh/tony_thermostat_ed25519 \
  vinnie@100.123.188.60:~/capture.bin \
  ~/Projects/Mushrooms/Pola/captures/
```

## What to Look For

1. **Address byte `0x01`** in request frames — confirms we're reading correctly
2. **Serial `0x1E 0xC9`** (or `0xC9 0x1E`) in response frames — that's 7881
3. **Repeating request patterns** — same register reads every burst
4. **Temperature values** — if the room is ~22°C, look for `0x00DC` (220 = 22.0°C × 10)
5. **Frame checksums** — the analyzer tests Modbus CRC, XOR, and sum automatically

## After the Capture

Bring the `capture.bin` back and we'll:
1. Fully decode the frame structure
2. Map every register to its meaning
3. Build a direct Python client for the XP80
4. Bypass the CloudBox entirely
5. Push it all to OpenPola
