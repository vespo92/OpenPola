"""
CloudBox → MQTT Bridge

Scrapes the CloudBox web UI and publishes data to an MQTT broker.
This is the MQTT integration POLA promised but never delivered.

Publishes to:
    openpola/{device_id}/status    — System status (JSON)
    openpola/{device_id}/xp/{n}    — XP device detail (JSON)
    openpola/{device_id}/config    — Configuration (JSON)
    openpola/{device_id}/online    — LWT (Last Will and Testament)

Usage:
    python3 -m cloudbox.mqtt_bridge \\
        --cloudbox-host 192.168.5.191 \\
        --cloudbox-password 0212b8aUb \\
        --mqtt-broker 10.0.10.10 \\
        --interval 30

Requires:
    pip install requests paho-mqtt
"""

import argparse
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime

from cloudbox.client import CloudBoxClient

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

logger = logging.getLogger(__name__)


class MQTTBridge:
    """Bridges CloudBox web data to MQTT."""

    def __init__(
        self,
        cloudbox_host: str,
        cloudbox_password: str,
        cloudbox_port: int = 80,
        mqtt_broker: str = "localhost",
        mqtt_port: int = 1883,
        mqtt_user: str | None = None,
        mqtt_password: str | None = None,
        device_id: str = "cloudbox-1",
        interval: int = 30,
    ):
        self.device_id = device_id
        self.interval = interval
        self.topic_prefix = f"openpola/{device_id}"

        # CloudBox client
        self.cloudbox = CloudBoxClient(
            cloudbox_host, cloudbox_password, port=cloudbox_port
        )

        # MQTT client
        if not PAHO_AVAILABLE:
            raise ImportError(
                "paho-mqtt not installed. Run: pip install paho-mqtt"
            )

        self.mqtt = mqtt.Client(
            client_id=f"openpola-bridge-{device_id}",
            protocol=mqtt.MQTTv311,
        )
        if mqtt_user:
            self.mqtt.username_pw_set(mqtt_user, mqtt_password)

        # LWT — publish "offline" if bridge disconnects unexpectedly
        self.mqtt.will_set(
            f"{self.topic_prefix}/online",
            payload="false",
            qos=1,
            retain=True,
        )

        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port

    def _publish(self, topic: str, payload: dict, retain: bool = False):
        """Publish JSON to MQTT."""
        msg = json.dumps(payload, default=str)
        self.mqtt.publish(
            f"{self.topic_prefix}/{topic}",
            payload=msg,
            qos=0,
            retain=retain,
        )

    def connect(self) -> bool:
        """Connect to both CloudBox and MQTT broker."""
        # CloudBox
        if not self.cloudbox.login():
            logger.error("Failed to login to CloudBox")
            return False
        logger.info(f"Connected to CloudBox at {self.cloudbox.base_url}")

        # MQTT
        try:
            self.mqtt.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.mqtt.loop_start()
            self._publish("online", "true")
            self.mqtt.publish(
                f"{self.topic_prefix}/online",
                payload="true",
                qos=1,
                retain=True,
            )
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            return False

        return True

    def poll_and_publish(self):
        """Single poll cycle: scrape CloudBox and publish to MQTT."""
        # Status
        status = self.cloudbox.get_status()
        if status:
            self._publish("status", asdict(status), retain=True)

            # Per-XP status
            for i, xp in enumerate(status.xp_units, 1):
                self._publish(f"xp/{i}/status", asdict(xp), retain=True)

                # XP detail if unit is responsive
                if xp.status == "OK":
                    detail = self.cloudbox.get_xp_detail(i)
                    if detail and detail.found:
                        self._publish(f"xp/{i}/detail", asdict(detail), retain=True)

        # Config (less frequently — every 10th poll)
        if not hasattr(self, '_poll_count'):
            self._poll_count = 0
        self._poll_count += 1

        if self._poll_count % 10 == 1:
            config = self.cloudbox.get_config()
            if config:
                self._publish("config", asdict(config), retain=True)

    def run(self):
        """Main loop: poll CloudBox and publish to MQTT."""
        logger.info(f"Starting bridge loop (interval={self.interval}s)")
        try:
            while True:
                try:
                    self.poll_and_publish()
                except Exception as e:
                    logger.error(f"Poll error: {e}")
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            self.mqtt.publish(
                f"{self.topic_prefix}/online",
                payload="false",
                qos=1,
                retain=True,
            )
            self.mqtt.loop_stop()
            self.mqtt.disconnect()
            self.cloudbox.logout()


def main():
    parser = argparse.ArgumentParser(description="CloudBox → MQTT Bridge")
    parser.add_argument("--cloudbox-host", required=True, help="CloudBox IP")
    parser.add_argument("--cloudbox-password", required=True, help="CloudBox password")
    parser.add_argument("--cloudbox-port", type=int, default=80)
    parser.add_argument("--mqtt-broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-user", default=None)
    parser.add_argument("--mqtt-password", default=None)
    parser.add_argument("--device-id", default="cloudbox-1")
    parser.add_argument("--interval", type=int, default=30, help="Poll interval (seconds)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bridge = MQTTBridge(
        cloudbox_host=args.cloudbox_host,
        cloudbox_password=args.cloudbox_password,
        cloudbox_port=args.cloudbox_port,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_password,
        device_id=args.device_id,
        interval=args.interval,
    )

    if not bridge.connect():
        sys.exit(1)

    bridge.run()


if __name__ == "__main__":
    import sys
    main()
