# OpenPola

Open-source documentation and tooling for the **POLA XP CloudBox** and **XP80** climate controller.

POLA Srl manufactures BMS (Building Management System) controllers for agricultural climate control — primarily poultry and livestock, but also used in mushroom cultivation and HVAC applications. Their hardware is solid. Their software and documentation? Not so much.

This project exists because:
- POLA provides **zero API documentation** to customers
- The CloudBox reads sensor data but **does not expose it** through any API
- There is **no MQTT support** despite vendor claims
- There is **no Modbus TCP** despite the hardware supporting it
- Customers who paid for this equipment deserve access to their own data

## What's Here

```
OpenPola/
├── docs/
│   ├── cloudbox-api.md          # Complete reverse-engineered web API
│   ├── cloudbox-architecture.md # System internals and infrastructure
│   ├── xp80-device-info.md      # XP80 controller specs and findings
│   └── rs485-protocol.md        # RS485 protocol analysis + decode plan
├── cloudbox/
│   ├── client.py                # Python client for CloudBox web API
│   ├── scraper.py               # Automated status scraper (JSONL output)
│   └── mqtt_bridge.py           # CloudBox → MQTT bridge (what POLA promised)
├── tools/
│   ├── sniffer.py               # RS485 passive bus sniffer
│   └── analyze_capture.py       # Capture file analyzer (frame stats, checksums)
└── README.md
```

## CloudBox Quick Reference

| Property | Value |
|----------|-------|
| Hardware | Raspberry Pi 4 in POLA enclosure |
| Web Server | nginx 1.22.1 → Flask (Python) |
| RS485 Adapter | FTDI FT232 USB (`0403:6001`) |
| Default Baud | 9600 (configurable: 9600/19200/38400) |
| Authentication | Single shared password, no usernames |
| SSH | Port 22 open, non-default credentials (locked down) |

### Web Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | No | Login (`password` field) |
| GET | `/status` | Yes | Dashboard — XP status, packet counters |
| GET | `/xp/{n}` | Yes | XP detail — model, serial, firmware, time |
| GET | `/config` | Yes | Farm/room/XP configuration |
| POST | `/config` | Yes | Update configuration |
| GET | `/alarms` | Yes | Alarm notification settings |
| POST | `/alarms` | Yes | Update alarm settings |
| GET | `/config_rs485` | Yes | RS485 connection type |
| GET | `/config_speed_rs485` | Yes | RS485 baud rate |
| GET | `/timezone` | Yes | Timezone settings |
| GET | `/lingua/{n}` | Yes | Language (0=IT, 1=EN) |
| GET | `/reboot` | Yes | Reboot CloudBox |
| GET | `/logout` | Yes | End session |

### What the CloudBox Does NOT Expose

Despite reading the XP80 every ~37 seconds over RS485:

- ❌ Temperature readings
- ❌ Humidity readings
- ❌ CO2 levels
- ❌ Setpoints
- ❌ Output states (heating/cooling/ventilation)
- ❌ Alarm values
- ❌ Historical data
- ❌ JSON API
- ❌ MQTT
- ❌ Modbus TCP
- ❌ WebSocket

## XP80 Controller

| Property | Value |
|----------|-------|
| Model | XP80 |
| Firmware | 1.02 |
| Serial | 7881 |
| RS485 Node | 1 |
| Protocol | Proprietary POLA (NOT Modbus, NOT Siemens XNet) |

## RS485 Protocol Decode (Help Wanted!)

The CloudBox sends **~126 RS485 transactions every 15 seconds** to the XP80.
We need to sniff this traffic to decode the proprietary POLA protocol.

See [docs/rs485-protocol.md](docs/rs485-protocol.md) for the full decode plan.

**What you need to help:**
- Any POLA controller (XP80, XP40, HP, LP)
- A USB-RS485 adapter ($5-15)
- Python 3 + pyserial

```bash
# Sniff the bus (connect adapter RX-only to the RS485 bus)
python3 tools/sniffer.py --port /dev/ttyUSB0 --baud 9600 --analyze --output capture.bin

# Analyze the capture
python3 tools/analyze_capture.py capture.bin
```

## Contributing

If you have a POLA XP CloudBox or XP80 controller and want to help reverse engineer the RS485 protocol, please open an issue. The more units we can compare, the faster we can decode the protocol.

## Disclaimer

This project is an independent reverse-engineering effort. It is not affiliated with, endorsed by, or supported by POLA Srl. All trademarks are property of their respective owners. This documentation was created through legitimate observation of network traffic and authenticated web interface access on equipment owned by the authors.

## License

MIT
