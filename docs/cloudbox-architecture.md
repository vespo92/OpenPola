# CloudBox Architecture

> Inferred from external observation of a live POLA XP CloudBox unit.
> No filesystem access was obtained.

## Hardware

The XP CloudBox is a **Raspberry Pi 4** packaged inside a POLA-branded
DIN-rail or panel-mount enclosure with a USB-RS485 adapter board.

| Component | Detail |
|-----------|--------|
| SBC | Raspberry Pi 4 Model B |
| WiFi MAC | `88:A2:9E:04:83:9A` |
| Ethernet MAC | `88:A2:9E:04:83:99` |
| RS485 Adapter | FTDI FT232 USB (`0403:6001`) |
| RS485 Device | `/dev/ttyUSB0` (inferred) |
| RS485 Wiring | +, -, C (common/ground) terminals |
| Storage | MicroSD card (POLA OEM image) |
| Power | 5V via Pi USB-C (powered from enclosure) |

## Software Stack

```
┌─────────────────────────────────────────────┐
│  Raspberry Pi OS (Debian Bookworm, arm64)   │
│                                              │
│  ┌──────────┐    ┌────────────────────────┐ │
│  │ nginx    │───►│ Flask web application   │ │
│  │ :80      │    │ (gunicorn or uwsgi)     │ │
│  └──────────┘    │                          │ │
│                  │ Routes:                   │ │
│  ┌──────────┐    │   / (login)              │ │
│  │ OpenSSH  │    │   /status                │ │
│  │ :22      │    │   /config*               │ │
│  │ (locked) │    │   /xp/{n}                │ │
│  └──────────┘    │   /alarms                │ │
│                  │   /timezone               │ │
│                  │   /lingua/{n}             │ │
│                  └────────────────────────── │ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ Background polling script              │ │
│  │ - Reads XP80 over RS485 every ~37s     │ │
│  │ - Stores data in memory (not on disk?) │ │
│  │ - Updates /status page counters        │ │
│  │ - Feeds /xp/{n} device metadata        │ │
│  │ - Does NOT expose sensor readings      │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ RS485 serial connection                │ │
│  │ - FTDI FT232 at /dev/ttyUSB0          │ │
│  │ - 9600 baud (configurable)             │ │
│  │ - Proprietary POLA protocol            │ │
│  │ - NOT Modbus, NOT Siemens XNet         │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Network Configuration

| Interface | IP | Notes |
|-----------|-----|-------|
| WiFi (`wlan0`) | DHCP (192.168.5.191 on our network) | Primary interface |
| Ethernet (`eth0`) | 192.168.2.16/24 (static) | Secondary, no gateway |

The CloudBox defaults to DHCP on WiFi. The Ethernet interface has a hardcoded
static IP on a private 192.168.2.0/24 subnet with no gateway — likely intended
for direct point-to-point connection during commissioning.

## Open Ports

| Port | Service | Status |
|------|---------|--------|
| 22 | SSH (OpenSSH) | Open, password auth enabled, non-default credentials |
| 80 | HTTP (nginx → Flask) | Open, password-protected web UI |
| 443 | HTTPS | Closed |
| 502 | Modbus TCP | Closed |
| 1883 | MQTT | Closed |
| 8883 | MQTT TLS | Closed |
| 9001 | MQTT WS | Closed |

## Frontend Stack

The web UI is entirely server-rendered. No SPA, no custom JavaScript, no AJAX.

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 4.x | CSS framework |
| jQuery | 3.3.1 (slim) | Bootstrap dependency |
| Popper.js | 1.x | Bootstrap dependency |
| Font Awesome | 5.14.0 | Icons |

Custom CSS is minimal (~3 lines in `boot_pola.css`): reduced margins on
headings, card headers, and horizontal rules.

## Security Observations

1. **Single shared password** — no usernames, no roles, no session timeout observed
2. **Password in page source** — displayed in `/status` header as firmware string
3. **GET /reboot with no CSRF** — any authenticated request to `/reboot` triggers restart
4. **No HTTPS** — all traffic including password is plaintext HTTP
5. **Sensitive info in form values** — password used as "Farm name" default
6. **No rate limiting** — login form can be brute-forced
7. **SSH locked but open** — attack surface; should be firewall-filtered if not needed

## Data Flow (What We Know)

```
XP80 Controller                  CloudBox                      Web Browser
      │                              │                              │
      │◄─── RS485 poll ──────────────│                              │
      │──── RS485 response ──────────►│                              │
      │                              │ stores:                      │
      │                              │  - connection status          │
      │                              │  - good/fail/check counters  │
      │                              │  - XP metadata (model, s/n)  │
      │                              │  - sensor data (HIDDEN)      │
      │                              │                              │
      │                              │◄─── GET /status ─────────────│
      │                              │──── HTML (counters only) ────►│
      │                              │                              │
      │                              │◄─── GET /xp/1 ──────────────│
      │                              │──── HTML (metadata only) ────►│
      │                              │                              │
```

The CloudBox reads the XP80 approximately once every 37 seconds (calculated
from 55,868 successful reads over ~24 days of uptime). This data includes
sensor readings (temperature, humidity, CO2) and output states, but the web
UI only exposes connection status and device metadata.

## Firmware Versioning

| Component | Version |
|-----------|---------|
| CloudBox software | SL 1.42.00 |
| XP80 firmware | 1.02 |

The CloudBox firmware version includes the device password in its display
string, suggesting the password may be derived from the serial number or
set during manufacturing.
