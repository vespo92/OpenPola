"""
POLA XP CloudBox Web Client

Authenticates with the CloudBox web UI and scrapes available data.
This is the only way to extract data from the CloudBox since POLA
provides no API, MQTT, or Modbus TCP access.

Usage:
    from cloudbox.client import CloudBoxClient

    client = CloudBoxClient("192.168.5.191", password="your_password")
    client.login()

    status = client.get_status()
    print(f"XP-1: {status['xp_units'][0]['status']} "
          f"({status['xp_units'][0]['good_packets']} good packets)")

    xp_info = client.get_xp_detail(1)
    print(f"Model: {xp_info['model']}, Serial: {xp_info['serial_number']}")

    config = client.get_config()
    print(f"Farm: {config['farm']}, {config['num_xp']} XP units")
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from html.parser import HTMLParser

import requests

logger = logging.getLogger(__name__)


@dataclass
class XPStatus:
    """Status of a single XP unit from the /status page."""
    name: str = ""
    status: str = "unknown"
    good_packets: int = 0
    failed_packets: int = 0
    checksum_errors: int = 0


@dataclass
class SystemStatus:
    """System-level status from the /status page."""
    firmware: str = ""
    web_ok: bool = False
    xlan_ok: bool = False
    script_running: bool = False
    xp_units: list = field(default_factory=list)
    scraped_at: str = ""


@dataclass
class XPDetail:
    """Device detail from the /xp/{n} page."""
    farm_name: str = ""
    rooms_name: str = ""
    room: int = 0
    model: str = ""
    xp_name: str = ""
    network_node: int = 0
    date: str = ""
    hour: str = ""
    software_level: str = ""
    serial_number: str = ""
    found: bool = False


@dataclass
class CloudBoxConfig:
    """Configuration from the /config page."""
    farm: str = ""
    rooms: str = ""
    num_xp: int = 0
    xp_configs: list = field(default_factory=list)


class CloudBoxClient:
    """HTTP client for the POLA XP CloudBox web interface."""

    def __init__(self, host: str, password: str, port: int = 80, timeout: int = 10):
        self.base_url = f"http://{host}:{port}"
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self._logged_in = False

    def login(self) -> bool:
        """Authenticate with the CloudBox. Returns True on success."""
        try:
            resp = self.session.post(
                self.base_url + "/",
                data={"password": self.password},
                timeout=self.timeout,
                allow_redirects=False,
            )
            # Success: page contains "alert-success" and refresh to /status
            if "alert-success" in resp.text or "/status" in resp.text:
                self._logged_in = True
                logger.info(f"Logged in to CloudBox at {self.base_url}")
                return True
            else:
                logger.warning("Login failed — wrong password?")
                return False
        except requests.RequestException as e:
            logger.error(f"Connection error: {e}")
            return False

    def _get(self, path: str) -> Optional[str]:
        """GET a page, returns HTML body or None."""
        if not self._logged_in:
            raise RuntimeError("Not logged in — call login() first")
        try:
            resp = self.session.get(
                self.base_url + path,
                timeout=self.timeout,
            )
            if "form-signin" in resp.text and "inputPassword" in resp.text:
                logger.warning("Session expired, re-authenticating...")
                if self.login():
                    resp = self.session.get(
                        self.base_url + path,
                        timeout=self.timeout,
                    )
                else:
                    return None
            return resp.text
        except requests.RequestException as e:
            logger.error(f"GET {path} failed: {e}")
            return None

    def get_status(self) -> Optional[SystemStatus]:
        """Scrape the /status page for system and XP connection status."""
        html = self._get("/status")
        if not html:
            return None

        status = SystemStatus(scraped_at=datetime.now().isoformat())

        # Firmware version from card header
        fw_match = re.search(r'System \(([^)]+)\)', html)
        if fw_match:
            status.firmware = fw_match.group(1)

        # Service status indicators
        status.web_ok = 'text-success' in html.split('Web')[0].split('XLAN')[0] if 'Web' in html else False
        status.xlan_ok = bool(re.search(r'XLAN.*?text-success', html, re.DOTALL))
        status.script_running = bool(re.search(r'Script.*?text-success', html, re.DOTALL))

        # XP unit cards
        xp_blocks = re.findall(
            r'card-header text-primary.*?<strong>([^<]+)</strong>.*?'
            r'status_\d+">([^<]*)<.*?'
            r'good_\d+">([^<]*)<.*?'
            r'fail_\d+">([^<]*)<.*?'
            r'check_\d+">([^<]*)<',
            html,
            re.DOTALL,
        )
        for name, stat, good, fail, check in xp_blocks:
            status.xp_units.append(XPStatus(
                name=name.strip(),
                status=stat.strip(),
                good_packets=int(good.strip()) if good.strip().isdigit() else 0,
                failed_packets=int(fail.strip()) if fail.strip().isdigit() else 0,
                checksum_errors=int(check.strip()) if check.strip().isdigit() else 0,
            ))

        return status

    def get_xp_detail(self, n: int) -> Optional[XPDetail]:
        """Scrape the /xp/{n} page for XP device metadata."""
        html = self._get(f"/xp/{n}")
        if not html:
            return None

        detail = XPDetail()

        if "XP not found" in html:
            detail.found = False
            return detail

        detail.found = True

        # Parse table rows: <th>Label</th><td>Value</td>
        rows = re.findall(r'<th[^>]*>([^<]+)</th>\s*<td>([^<]*)</td>', html)
        field_map = {
            "Rooms name": "rooms_name",
            "Room": "room",
            "Model": "model",
            "XP name": "xp_name",
            "Network node": "network_node",
            "Date": "date",
            "Hour": "hour",
            "Software level": "software_level",
            "Serial number": "serial_number",
            # Italian variants
            "Nome locali": "rooms_name",
            "Locale": "room",
            "Modello": "model",
            "Nome XP": "xp_name",
            "Nodo rete": "network_node",
            "Data": "date",
            "Ora": "hour",
            "Livello software": "software_level",
            "Numero di serie": "serial_number",
        }
        for label, value in rows:
            label = label.strip()
            value = value.strip()
            attr = field_map.get(label)
            if attr:
                if attr in ("room", "network_node"):
                    setattr(detail, attr, int(value) if value.isdigit() else 0)
                else:
                    setattr(detail, attr, value)

        # Farm name from card header
        farm_match = re.search(r'Farm name\s*<span>\s*:\s*([^<]+)', html)
        if not farm_match:
            farm_match = re.search(r'Nome allevamento\s*<span>\s*:\s*([^<]+)', html)
        if farm_match:
            detail.farm_name = farm_match.group(1).strip()

        return detail

    def get_config(self) -> Optional[CloudBoxConfig]:
        """Scrape the /config page for farm/XP configuration."""
        html = self._get("/config")
        if not html:
            return None

        config = CloudBoxConfig()

        # Farm name
        farm_match = re.search(r'name="farm"\s+value="([^"]*)"', html)
        if farm_match:
            config.farm = farm_match.group(1)

        # Rooms name
        rooms_match = re.search(r'name="rooms"\s+value="([^"]*)"', html)
        if rooms_match:
            config.rooms = rooms_match.group(1)

        # Number of XPs (selected option)
        num_match = re.search(r'name="num_xp".*?selected\s+value="(\d+)"', html, re.DOTALL)
        if num_match:
            config.num_xp = int(num_match.group(1))

        # Per-XP configs
        for i in range(1, config.num_xp + 1):
            xp = {}
            name_match = re.search(rf'name="name\[{i}\]"\s+value="([^"]*)"', html)
            shed_match = re.search(rf'name="shed\[{i}\]"\s+value="([^"]*)"', html)
            opts_match = re.search(rf'name="opts\[{i}\]"\s+value="([^"]*)"', html)
            xp["name"] = name_match.group(1) if name_match else f"XP-{i}"
            xp["shed"] = int(shed_match.group(1)) if shed_match else i
            xp["opts"] = opts_match.group(1) if opts_match else "0,0,0"
            config.xp_configs.append(xp)

        return config

    def get_rs485_speed(self) -> Optional[int]:
        """Get the current RS485 baud rate. Returns 9600, 19200, or 38400."""
        html = self._get("/config_speed_rs485")
        if not html:
            return None
        speed_match = re.search(r'selected\s+value="(\d)"', html)
        if speed_match:
            speed_map = {0: 9600, 1: 19200, 2: 38400}
            return speed_map.get(int(speed_match.group(1)), 9600)
        return 9600

    def reboot(self) -> bool:
        """Reboot the CloudBox. Use with caution."""
        html = self._get("/reboot")
        return html is not None

    def logout(self):
        """End the session."""
        try:
            self.session.get(self.base_url + "/logout", timeout=self.timeout)
        except requests.RequestException:
            pass
        self._logged_in = False


if __name__ == "__main__":
    import sys
    import json
    from dataclasses import asdict

    logging.basicConfig(level=logging.INFO)

    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.5.191"
    password = sys.argv[2] if len(sys.argv) > 2 else ""

    if not password:
        print(f"Usage: python -m cloudbox.client <host> <password>")
        sys.exit(1)

    client = CloudBoxClient(host, password)
    if not client.login():
        print("Login failed")
        sys.exit(1)

    print("=== System Status ===")
    status = client.get_status()
    if status:
        print(json.dumps(asdict(status), indent=2))

    print("\n=== XP Detail (unit 1) ===")
    detail = client.get_xp_detail(1)
    if detail:
        print(json.dumps(asdict(detail), indent=2))

    print("\n=== Configuration ===")
    config = client.get_config()
    if config:
        print(json.dumps(asdict(config), indent=2))

    print(f"\n=== RS485 Speed ===")
    speed = client.get_rs485_speed()
    print(f"{speed} baud")

    client.logout()
