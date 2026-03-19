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
| Addressing | 1-32 (set on XP front panel "RETE PC" menu) |
| Topology | Multi-drop bus with single master (CloudBox) |
| Wiring | + (A), - (B), C (common ground) |

## Polling Behavior (Measured 2026-03-18)

We measured the CloudBox's RS485 polling pattern by monitoring packet counters:

| Metric | Value |
|--------|-------|
| Packets per burst | ~126 |
| Burst interval | ~15 seconds |
| Effective rate | ~8 packets/second during burst |
| Total throughput | ~504 packets/minute |
| Reliability | 99.998% (1 failure in 67,712 packets over ~24 days) |

**Key insight:** The CloudBox does NOT send a single request per poll cycle.
It sends **~126 individual RS485 transactions** in rapid succession every
~15 seconds. This suggests the protocol uses small register reads (similar
to Modbus FC 0x03/0x04) to read individual data points from the XP80.

At 9600 baud, 126 request/response pairs in <2 seconds means each
transaction is likely 10-20 bytes total (request + response).

## Protocol Characteristics

### What We Know
- **Master/slave polling model** — XP80 does not transmit unless polled
- **Proprietary framing** — NOT Modbus RTU, NOT Siemens XNet
- **POLA calls it "XNet"** but it bears no resemblance to Siemens XNet
- **Burst polling** — ~126 packets every ~15 seconds (NOT one-shot reads)
- **Highly reliable** — 99.998% success rate on a healthy bus
- **Small transactions** — ~8/sec at 9600 baud = ~10-20 bytes per transaction
- **Read + metadata** — CloudBox extracts model, serial, firmware, date, time from XP80
- **Sensor data captured** — temperature, humidity, CO2 are read but not exposed via web

### What We Don't Know
- Frame structure (header, address, function, data, checksum)
- Checksum/CRC algorithm
- Register map (which of the 126 reads maps to which sensor)
- Whether the protocol supports write commands
- Frame timing requirements (inter-character, inter-frame gaps)
- Exact parity/stop bit configuration

## Hardware Needed for Sniffing

### Minimum: Passive Sniffer

| Item | Example | Cost |
|------|---------|------|
| USB-RS485 adapter | FTDI FT232 or CH340-based | $5-15 |
| Raspberry Pi (any) | Pi Zero W, Pi 3/4, or even the i5 box | Already have |
| Jumper wires | Connect to +, -, C terminals | $0 |

### Wiring

```
CloudBox ──RS485──┬──── XP80 Controller
   (master)       │       (slave, node 1)
                  │
                  └──── Sniffer Pi
                        USB-RS485 adapter
                        /dev/ttyUSB0
                        RX ONLY (do not connect TX)
```

**Critical:** Connect only the **RX** (receive), **A/+**, **B/-**, and **GND** lines.
Do NOT connect TX — we want to listen passively without interfering with the
CloudBox's communication.

On most USB-RS485 adapters:
- **A / D+ / +** → Connect to bus A/+
- **B / D- / -** → Connect to bus B/-
- **GND** → Connect to bus C/ground
- **TX enable** → Leave disconnected or tie LOW (receive only)

## Decode Plan

### Phase 1: Passive Capture

```bash
# Install pyserial on the sniffer Pi
pip3 install pyserial

# Run the capture script
python3 sniffer.py --port /dev/ttyUSB0 --baud 9600 --output capture.bin
```

The sniffer script (included in this repo at `tools/sniffer.py`) captures
raw bytes with microsecond timestamps. Inter-frame gaps >3 character times
(~3.1ms at 9600 baud) indicate frame boundaries.

**Expected capture volume:** ~126 transactions × 2 (request + response) ×
~15 bytes average = ~3,780 bytes per 15-second burst ≈ 250 bytes/sec average.

### Phase 2: Frame Identification

With captured data, look for:

1. **Frame boundaries** — silence gaps >3ms separate frames
2. **Request vs response** — alternating short (request) and longer (response) frames
3. **Address byte** — should contain `0x01` (XP80 node address = 1)
4. **Repeating patterns** — same register reads every 15 seconds
5. **Checksum** — last 1-2 bytes; try:
   - XOR of all bytes
   - Sum modulo 256
   - CRC-8
   - CRC-16 (Modbus polynomial 0xA001)
   - CRC-16 (CCITT polynomial 0x1021)

### Phase 3: Register Mapping

Once frames are decoded:
1. **Identify sensor registers** — change XP80 temperature setpoint via front
   panel, observe which response bytes change
2. **Map metadata registers** — serial number (7881 = 0x1EC9), firmware (1.02),
   date/time fields should appear in responses
3. **Map output registers** — turn outputs on/off and observe changes
4. **Document the full register map** — create a table of address → meaning

### Phase 4: Active Communication

With the protocol fully decoded:
1. Build a Python XP80 client that polls directly (bypass CloudBox)
2. Implement read AND write commands
3. Expose data via MQTT, REST API, and PostgreSQL
4. Open-source everything

## Known Data Points to Look For

The XP80 exposes at least these values (based on CloudBox behavior and controller type):

| Category | Data Points |
|----------|------------|
| Identity | Model string, serial number, firmware version, date, time |
| Sensors | Temperature (main), temperature (aux), humidity, CO2 |
| Setpoints | Temp setpoint, humidity setpoint, CO2 threshold |
| Outputs | Heating stage, cooling stage, humidification %, ventilation % |
| Alarms | Door open, probe failure, general alarm |
| Status | Operating mode, connection state |

The serial number `7881` in hex is `0x1EC9` — look for these bytes in responses.
The firmware `1.02` might appear as `0x01 0x02` or as ASCII `"1.02"`.

## Related Protocols to Compare

| Protocol | Why Compare | Similarity |
|----------|------------|------------|
| Modbus RTU | Most common RS485 BMS protocol | ~126 reads/burst suggests register-based |
| BACnet MS/TP | Common in HVAC/BMS | Token-passing, unlikely given master/slave |
| CAREL pCO | Italian HVAC manufacturer, similar market | Proprietary RS485, worth comparing |
| Dixell XWeb | Italian climate controllers | Similar product category |

Italian BMS manufacturers (POLA, CAREL, Dixell, Eliwell) often use
proprietary protocols. If anyone has protocol captures from these vendors,
cross-referencing frame structures would help.

## Contributing

If you have:
- A POLA XP80, XP40, HP, or LP controller
- RS485 captures from any POLA device
- POLA protocol documentation (even partial)
- Firmware dumps from a POLA CloudBox

Please open an issue or PR. The more data points we have, the faster
we can decode this protocol.
