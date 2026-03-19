# POLA XP80 Climate Controller

## Overview

The POLA XP80 is a building management system (BMS) climate controller designed
for agricultural environments (poultry houses, livestock barns, greenhouses,
mushroom grow rooms). It monitors temperature, humidity, and CO2, and controls
heating, cooling, humidification, and ventilation outputs.

## Known Specifications

| Property | Value | Source |
|----------|-------|--------|
| Model | XP80 | CloudBox `/xp/1` page |
| Firmware | 1.02 | CloudBox `/xp/1` page |
| Serial Number | 7881 | CloudBox `/xp/1` page |
| RS485 Address | 1 (configurable 1-32) | CloudBox config |
| RS485 Protocol | Proprietary POLA | Empirical testing |
| RS485 Baud Rate | 9600 (configurable: 9600/19200/38400) | CloudBox config |
| Max Units per Bus | 32 | CloudBox config (num_xp max) |

## Front Panel

The XP80 has an LCD display and button interface. Key menus include:

- **RETE PC** (PC Network) — RS485 address and speed settings
- **Main display** — Current temperature, humidity, setpoints
- **Alarm display** — Active alarm conditions

> If the "485 speed" setting is NOT present in the RETE PC menu, the XP80
> firmware is too old for variable baud rate and defaults to 9600.

## Sensor Inputs

Based on the register definitions in the companion Modbus client (which was
written speculatively — the XP80 does NOT speak standard Modbus):

| Sensor | Expected Range | Notes |
|--------|---------------|-------|
| Temperature | -40°C to +80°C | Main probe |
| Temperature (aux) | -40°C to +80°C | Secondary probe |
| Humidity | 0-100% RH | |
| CO2 | 0-10000 ppm | Optional external sensor |

## Control Outputs

| Output | Type | Notes |
|--------|------|-------|
| Heating | Staged (1-3 stages) | On/Off or proportional |
| Cooling | Staged (1-3 stages) | On/Off or proportional |
| Humidification | Proportional | 0-100% |
| Ventilation | Proportional | CO2-based or timer-based |
| Minimum ventilation | Timer-based | Configurable cycle |

## RS485 Communication

### What We Know

- The XP80 communicates over RS485 half-duplex
- It uses a **proprietary POLA protocol** — NOT Modbus RTU, NOT Siemens XNet
- The POLA CloudBox successfully polls it at 9600/8N1
- The XP80 does NOT broadcast — it only responds to polls
- Up to 32 XP controllers can share a single RS485 bus

### What We Tested (and Failed)

| Protocol | Addresses | Baud Rates | Parity | Result |
|----------|-----------|------------|--------|--------|
| Modbus RTU (FC 0x03) | 0-10 | 9600/19200/38400/57600 | N/E/O | No response |
| Modbus RTU (FC 0x04) | 0-10 | 9600/19200/38400/57600 | N/E/O | No response |
| IEC 870-5 style | Various | 9600 | N | TX echo only |
| Raw poll bytes | Various | 9600 | N | TX echo only |

### Next Steps for Protocol Decode

1. **Passive sniffing** — Put a second RS485 adapter on the bus in listen-only
   mode while the CloudBox polls the XP80. Capture the request/response pairs.

2. **Frame analysis** — Look for patterns in the captured data:
   - Start/stop bytes
   - Address field
   - Function codes
   - Data payload
   - CRC/checksum algorithm

3. **Timing analysis** — Measure inter-frame gaps to determine protocol framing.

4. **Comparative analysis** — If other POLA models (HP, LP) use similar protocols,
   cross-reference frame structures.

## Manufacturer

| | |
|---|---|
| Company | POLA Srl |
| Country | Italy |
| Email | pola@pola.it |
| Phone | +39-0374-85602 |
| Website | https://www.pola.it |
| Downloads | https://www.pola.it/area-download (login required) |
