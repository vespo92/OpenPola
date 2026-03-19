# POLA RS485 Protocol Analysis

> **Status: Work in Progress**
> The proprietary POLA protocol has not yet been decoded. This document
> tracks what we know and the plan for reverse engineering.

## Bus Configuration

| Parameter | Value |
|-----------|-------|
| Physical Layer | RS485 half-duplex |
| Baud Rate | 9600 (default), 19200, 38400 |
| Data Bits | 8 (assumed) |
| Parity | None (assumed, needs verification) |
| Stop Bits | 1 (assumed) |
| Max Nodes | 32 |
| Addressing | 1-32 (set on XP front panel) |
| Topology | Multi-drop bus with single master (CloudBox) |
| Wiring | +, -, C (common ground) |

## Protocol Characteristics

### What We Know
- **Master/slave polling model** — XP80 does not transmit unless polled
- **Proprietary framing** — NOT Modbus RTU, NOT Siemens XNet
- **POLA calls it "XNet"** but it bears no resemblance to Siemens XNet
- **CloudBox polls at ~37 second intervals** (55,868 reads in ~24 days)
- **Reliable** — only 1 failed packet in 55,868 attempts on a healthy bus
- **Read/write capable** — CloudBox reads sensor data; unclear if it writes setpoints

### What We Don't Know
- Frame structure (header, address, function, data, checksum)
- Checksum/CRC algorithm
- Register map
- Whether the protocol supports write commands
- Frame timing requirements (inter-character, inter-frame gaps)

## Decode Plan

### Phase 1: Passive Capture

Connect a second RS485 adapter to the bus in **receive-only mode** (TX line
disconnected or held high) while the CloudBox polls the XP80.

```
CloudBox ──RS485──┬──── XP80
                  │
                  └──── Sniffer (receive only)
                        USB-RS485 adapter
                        /dev/ttyUSB1
```

Capture tool:
```bash
# Raw hex dump of bus traffic
stty -F /dev/ttyUSB1 9600 raw -echo
xxd /dev/ttyUSB1
```

Or with Python:
```python
import serial

port = serial.Serial('/dev/ttyUSB1', 9600, timeout=1)
while True:
    data = port.read(256)
    if data:
        print(' '.join(f'{b:02X}' for b in data))
```

### Phase 2: Frame Identification

Look for repeating patterns:
- **Fixed header bytes** — most protocols start with a sync byte or address
- **Length fields** — variable-length frames usually encode their size
- **Address byte** — should match the configured RS485 address (1)
- **Request/response pairing** — shorter request, longer response
- **Checksum** — last 1-2 bytes, try XOR, CRC-8, CRC-16/Modbus, sum

### Phase 3: Register Mapping

Once frames are decoded:
- Change XP80 setpoints via front panel, observe which response bytes change
- Correlate temperature display changes with response data
- Map each byte/word to its physical meaning

### Phase 4: Active Communication

With the protocol decoded:
- Build a Python client that can poll the XP80 directly
- Bypass the CloudBox entirely
- Expose data via MQTT, REST API, or database

## Related Protocols to Compare

The POLA protocol may share characteristics with:

| Protocol | Why Compare |
|----------|------------|
| Modbus RTU | Most common RS485 BMS protocol |
| BACnet MS/TP | Common in HVAC/BMS |
| N2 (Johnson Controls) | Proprietary HVAC protocol |
| P1/P2 (Daikin) | Proprietary HVAC protocol |
| LonTalk | Building automation |

If anyone has POLA protocol documentation, firmware dumps, or captures from
other POLA models, please contribute.
