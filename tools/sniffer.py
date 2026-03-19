#!/usr/bin/env python3
"""
POLA XNet RS485 Bus Sniffer

Passively captures RS485 traffic between a POLA CloudBox and XP80 controller.
Logs raw bytes with microsecond timestamps for protocol analysis.

Frames are delimited by silence gaps (>3ms at 9600 baud = ~3 character times).

Usage:
    python3 sniffer.py --port /dev/ttyUSB0 --baud 9600
    python3 sniffer.py --port /dev/ttyUSB0 --baud 9600 --output capture.bin --duration 300

Output format (text mode, default):
    [timestamp_ms] HEX_BYTES  (length)  direction_guess

Output format (binary mode, --output):
    Binary file with framed packets and timestamps for offline analysis.

Requirements:
    pip install pyserial
"""

import argparse
import json
import struct
import sys
import time
from datetime import datetime

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial")
    sys.exit(1)


# At 9600 baud, 1 byte = ~1.04ms (10 bits: start + 8 data + stop)
# 3 character times = ~3.1ms — standard inter-frame gap
FRAME_GAP_CHARS = 3.5


def calc_frame_gap(baud: int) -> float:
    """Calculate inter-frame gap in seconds."""
    char_time = 10.0 / baud  # 10 bits per character (8N1)
    return FRAME_GAP_CHARS * char_time


def guess_direction(frame: bytes, prev_frame: bytes | None) -> str:
    """Guess if a frame is a request (TX from master) or response (RX from slave)."""
    if prev_frame is None:
        return "REQ?"  # First frame is likely a request
    # Heuristic: requests tend to be shorter than responses
    if len(frame) <= len(prev_frame):
        return "REQ?"
    else:
        return "RSP?"


def check_modbus_crc(data: bytes) -> bool:
    """Check if last 2 bytes are a valid Modbus CRC-16."""
    if len(data) < 3:
        return False
    crc = 0xFFFF
    for byte in data[:-2]:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    expected = struct.unpack('<H', data[-2:])[0]
    return crc == expected


def check_xor_checksum(data: bytes) -> bool:
    """Check if last byte is XOR of all previous bytes."""
    if len(data) < 2:
        return False
    xor = 0
    for byte in data[:-1]:
        xor ^= byte
    return xor == data[-1]


def check_sum_checksum(data: bytes) -> bool:
    """Check if last byte is sum mod 256 of all previous bytes."""
    if len(data) < 2:
        return False
    s = sum(data[:-1]) & 0xFF
    return s == data[-1]


def analyze_frame(frame: bytes) -> list[str]:
    """Run checksum analysis on a frame."""
    notes = []
    if check_modbus_crc(frame):
        notes.append("MODBUS_CRC_OK")
    if check_xor_checksum(frame):
        notes.append("XOR_CHKSUM_OK")
    if check_sum_checksum(frame):
        notes.append("SUM_CHKSUM_OK")
    return notes


def run_sniffer(port: str, baud: int, output: str | None, duration: int,
                analyze: bool):
    """Main sniffer loop."""
    gap = calc_frame_gap(baud)
    print(f"POLA XNet RS485 Sniffer")
    print(f"Port: {port}, Baud: {baud}, Frame gap: {gap*1000:.1f}ms")
    print(f"Started: {datetime.now().isoformat()}")
    if duration:
        print(f"Duration: {duration}s")
    print("-" * 80)

    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.001,  # 1ms timeout for non-blocking reads
    )

    outfile = None
    if output:
        outfile = open(output, 'wb')

    frame_buf = bytearray()
    last_byte_time = 0.0
    frame_count = 0
    byte_count = 0
    start_time = time.time()
    prev_frame = None

    try:
        while True:
            # Check duration limit
            elapsed = time.time() - start_time
            if duration and elapsed > duration:
                break

            data = ser.read(256)
            now = time.time()

            if data:
                # Check for frame gap
                if frame_buf and (now - last_byte_time) > gap:
                    # Frame complete — process it
                    frame = bytes(frame_buf)
                    frame_time = last_byte_time
                    frame_count += 1
                    direction = guess_direction(frame, prev_frame)

                    # Text output
                    hex_str = ' '.join(f'{b:02X}' for b in frame)
                    ts = f"{frame_time - start_time:10.3f}"
                    line = f"[{ts}s] {hex_str}  ({len(frame)} bytes)  {direction}"

                    if analyze:
                        notes = analyze_frame(frame)
                        if notes:
                            line += f"  *** {', '.join(notes)} ***"

                    print(line)

                    # Binary output
                    if outfile:
                        # Format: [8-byte timestamp][2-byte length][frame bytes]
                        outfile.write(struct.pack('<dH', frame_time, len(frame)))
                        outfile.write(frame)

                    prev_frame = frame
                    frame_buf.clear()

                frame_buf.extend(data)
                last_byte_time = now
                byte_count += len(data)

            else:
                # No data — check if we have a pending frame
                if frame_buf and (now - last_byte_time) > gap:
                    frame = bytes(frame_buf)
                    frame_count += 1
                    direction = guess_direction(frame, prev_frame)

                    hex_str = ' '.join(f'{b:02X}' for b in frame)
                    ts = f"{now - start_time:10.3f}"
                    line = f"[{ts}s] {hex_str}  ({len(frame)} bytes)  {direction}"

                    if analyze:
                        notes = analyze_frame(frame)
                        if notes:
                            line += f"  *** {', '.join(notes)} ***"

                    print(line)

                    if outfile:
                        outfile.write(struct.pack('<dH', now, len(frame)))
                        outfile.write(frame)

                    prev_frame = frame
                    frame_buf.clear()

    except KeyboardInterrupt:
        pass
    finally:
        elapsed = time.time() - start_time
        if outfile:
            outfile.close()
        ser.close()

        print("-" * 80)
        print(f"Capture complete: {frame_count} frames, {byte_count} bytes "
              f"in {elapsed:.1f}s")
        if output:
            print(f"Binary capture saved to: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="POLA XNet RS485 Bus Sniffer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--port", "-p", required=True,
                        help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=9600,
                        help="Baud rate (default: 9600)")
    parser.add_argument("--output", "-o",
                        help="Binary output file for offline analysis")
    parser.add_argument("--duration", "-d", type=int, default=0,
                        help="Capture duration in seconds (0=unlimited)")
    parser.add_argument("--analyze", "-a", action="store_true",
                        help="Run checksum analysis on each frame")
    args = parser.parse_args()

    run_sniffer(args.port, args.baud, args.output, args.duration, args.analyze)


if __name__ == "__main__":
    main()
