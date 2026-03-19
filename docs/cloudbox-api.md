# CloudBox Web API Reference

> Reverse-engineered from a live POLA XP CloudBox (firmware **SL 1.42.00**)
> on 2026-03-18. This is the complete endpoint map — there are no hidden routes.

## Authentication

The CloudBox uses a single shared password with Flask session cookies. No usernames.

### Login

```
POST / HTTP/1.1
Content-Type: application/x-www-form-urlencoded

password=<your_cloudbox_password>
```

**Success:** HTTP 200, body contains `<meta http-equiv='refresh' content='1; /status'>` and a `<div class='alert alert-success'>` element. A session cookie is set.

**Failure:** HTTP 200, body contains `<div class='alert alert-danger'><strong>Password fail!</strong></div>`.

> **Note:** The CloudBox password is displayed in plaintext on the `/status` page
> in the firmware version header: `System (SL 1.42.00 - <password>)`.
> The serial number of the XP80 unit appears to be the default password.

### Logout

```
GET /logout
```

Clears session cookie, redirects to login.

---

## Dashboard

### GET /status

System overview dashboard. Auto-refreshes every 30 seconds via `<meta http-equiv="refresh" content="30">`.

**System Card:**

| Field | HTML ID/Location | Description |
|-------|-----------------|-------------|
| Firmware | Card header | Format: `SL {version} - {password}` |
| Web | `text-success` / `text-danger` | Flask app status (cloud icon) |
| XLAN | `text-success` / `text-danger` | RS485 bus status (plug icon) |
| Script (run) | `text-success` / `text-danger` | Background polling script status |
| Reboot | Link to `/reboot` | Power-off icon |

**Per-XP Card** (one card per configured XP, linked to `/xp/{n}`):

| Field | HTML ID | Description |
|-------|---------|-------------|
| XP name | Card header | Configured name (e.g., "XP-1") |
| Handshake | `status_{n-1}` | "OK" or error string |
| Good packets | `good_{n-1}` | Cumulative successful RS485 reads |
| Failed packets | `fail_{n-1}` | Cumulative failed reads |
| Checksum errors | `check_{n-1}` | Cumulative CRC mismatches |

> **Important:** The HTML IDs use zero-based indexing (`status_0` for XP #1).

**Example (scraped 2026-03-18):**
```
XP-1:
  Status: OK
  Good: 55,868
  Failed: 1
  Checksum: 0
```

At ~1 read every 37 seconds, this represents approximately 24 days of uptime.

---

## XP Device Detail

### GET /xp/{n}

Returns device metadata for XP controller #n (1-32). Only configured and
reachable XPs return data — the rest return an error alert.

**When XP exists:**

| Field | Example | Notes |
|-------|---------|-------|
| Farm name | 0212b8aUb | From `/config` |
| Rooms name | House | From `/config` |
| Room | 1 | Shed number |
| Model | XP80 | Controller model string |
| XP name | XP-1 | Configured name |
| Network node | 1 | RS485 address (1-32) |
| Date | 19-03-26 | XP80 internal clock (DD-MM-YY) |
| Hour | 3:04:28 | XP80 internal clock (H:MM:SS) |
| Software level | 1.02 | XP80 firmware version |
| Serial number | 7881 | XP80 hardware serial |

**When XP does not exist:**
```html
<div class='alert alert-danger'><strong>XP not found!</strong></div>
```

> **CRITICAL:** This page shows metadata ONLY. No temperature, humidity, CO2,
> setpoints, or output states are displayed anywhere in the web UI despite
> being read over RS485.

---

## Configuration

### GET /config

Farm, room, and XP controller configuration form.

### POST /config

| Field | Type | Max Length | Description |
|-------|------|-----------|-------------|
| `farm` | text | 24 | Farm name |
| `rooms` | text | 16 | Rooms/house name |
| `num_xp` | select | 1-32 | Number of XP controllers on RS485 bus |
| `name[n]` | text | 12 | XP #n display name |
| `shed[n]` | number | 1-32 | XP #n room/shed assignment |
| `opts[n]` | text | 32 | XP #n options string (format: `"0,0,0"`) |

The form always renders slots for 32 XPs but hides those beyond `num_xp` via JavaScript.

---

## RS485 Settings

### GET /config_rs485

RS485 connection type configuration. The form has a `time_out` select field
but the options were empty on our unit (may be firmware-dependent).

### POST /config_rs485

| Field | Type | Description |
|-------|------|-------------|
| `time_out` | select | Connection timeout (options vary by firmware) |

### GET /config_speed_rs485

RS485 baud rate configuration.

### POST /config_speed_rs485

| Field | Type | Values |
|-------|------|--------|
| `speed` | select | `0` = 9600 baud, `1` = 19200 baud, `2` = 38400 baud |

> The baud rate set here **must match** the setting on all connected XP
> controllers. On the XP80 front panel, check the "PC NETWORK" (RETE PC) screen.
> If the "485 speed" option is not present, the XP firmware is too old and
> defaults to 9600 baud.

---

## Alarms / Notifications

### GET /alarms

Email and Telegram notification configuration.

### POST /alarms

| Field | Type | Description |
|-------|------|-------------|
| `send_email` | select | `"true"` or `"false"` — enable/disable notifications |
| `username[n]` | text (32) | Recipient #n display name (n=1-5) |
| `mail[n]` | email (48) | Recipient #n email address |
| `id[n]` | text (16) | Recipient #n Telegram chat ID |

Up to 5 notification recipients are supported.

---

## Timezone

### GET /timezone

Timezone selection form with region/city dropdowns.

### POST /timezone

| Field | Type | Description |
|-------|------|-------------|
| `region` | select | Timezone region (e.g., "America") |
| `city` | select | Timezone city (e.g., "New_York") |

Default is `Europe/London`.

---

## Language

### GET /lingua/{n}

Switches the web UI language. Returns HTTP 302 redirect.

| Value | Language |
|-------|----------|
| `0` | Italiano |
| `1` | English |

---

## System

### GET /reboot

Reboots the CloudBox. No confirmation prompt — triggers immediately on GET.

> **Warning:** This is a GET request with no CSRF protection. A simple
> `<img src="/reboot">` on any page would reboot the box.

---

## Server Details

| Header | Value |
|--------|-------|
| `Server` | nginx/1.22.1 |
| `Content-Type` | text/html; charset=utf-8 |

The Flask app runs behind nginx as a reverse proxy. No custom response headers.
No CORS headers. No API versioning.

---

## Endpoints That Do NOT Exist

We probed over 80 URL patterns. Everything not listed above returns HTTP 404:

- `/mqtt`, `/config_mqtt`, `/mqtt_config` — No MQTT configuration
- `/api/*`, `/json`, `/data`, `/values` — No JSON/REST API
- `/registers`, `/read`, `/write` — No register access
- `/stream`, `/events`, `/sse`, `/ws` — No real-time data
- `/history`, `/chart`, `/trend`, `/csv` — No historical data
- `/swagger`, `/docs`, `/openapi.json` — No API documentation
- `/backup`, `/export`, `/download` — No data export
- `/console`, `/debug`, `/_debug` — No debug interface (Flask debug mode is OFF)
