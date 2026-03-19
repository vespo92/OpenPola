"""
CloudBox Status Scraper

Periodically scrapes the CloudBox web UI and logs status data.
Useful for monitoring XP80 connection health over time.

Usage:
    python -m cloudbox.scraper 192.168.5.191 <password> [--interval 60] [--output status.jsonl]
"""

import argparse
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime

from cloudbox.client import CloudBoxClient

logger = logging.getLogger(__name__)


def scrape_loop(client: CloudBoxClient, interval: int, output_file: str):
    """Scrape status at regular intervals and append to JSONL file."""
    logger.info(f"Scraping every {interval}s, writing to {output_file}")

    while True:
        try:
            status = client.get_status()
            if status:
                record = {
                    "timestamp": datetime.now().isoformat(),
                    "firmware": status.firmware,
                    "web_ok": status.web_ok,
                    "xlan_ok": status.xlan_ok,
                    "script_running": status.script_running,
                    "xp_units": [asdict(xp) for xp in status.xp_units],
                }

                # Also grab XP detail for any active units
                for i, xp in enumerate(status.xp_units, 1):
                    if xp.status == "OK":
                        detail = client.get_xp_detail(i)
                        if detail and detail.found:
                            record[f"xp_{i}_detail"] = asdict(detail)

                with open(output_file, "a") as f:
                    f.write(json.dumps(record) + "\n")

                # Log summary
                for xp in status.xp_units:
                    logger.info(
                        f"{xp.name}: {xp.status} "
                        f"(good={xp.good_packets}, fail={xp.failed_packets})"
                    )
            else:
                logger.warning("Failed to get status")

        except Exception as e:
            logger.error(f"Scrape error: {e}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="CloudBox status scraper")
    parser.add_argument("host", help="CloudBox IP address")
    parser.add_argument("password", help="CloudBox web password")
    parser.add_argument("--interval", type=int, default=60, help="Scrape interval (seconds)")
    parser.add_argument("--output", default="cloudbox_status.jsonl", help="Output JSONL file")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    client = CloudBoxClient(args.host, args.password)
    if not client.login():
        logger.error("Login failed — check password")
        return

    try:
        scrape_loop(client, args.interval, args.output)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        client.logout()


if __name__ == "__main__":
    main()
