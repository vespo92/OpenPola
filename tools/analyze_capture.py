#!/usr/bin/env python3
"""
POLA XNet Capture Analyzer

Reads a binary capture from sniffer.py and performs statistical analysis
to help decode the protocol.

Usage:
    python3 analyze_capture.py capture.bin
"""

import struct
import sys
from collections import Counter


def read_capture(filename: str) -> list:
    """Read frames from a binary capture file."""
    frames = []
    with open(filename, 'rb') as f:
        while True:
            header = f.read(10)  # 8-byte timestamp + 2-byte length
            if len(header) < 10:
                break
            ts, length = struct.unpack('<dH', header)
            data = f.read(length)
            if len(data) < length:
                break
            frames.append((ts, data))
    return frames


def analyze_lengths(frames: list):
    """Analyze frame length distribution."""
    lengths = Counter(len(f[1]) for f in frames)
    print("=== Frame Length Distribution ===")
    for length, count in sorted(lengths.items()):
        bar = '#' * min(count, 60)
        print(f"  {length:3d} bytes: {count:5d}  {bar}")
    print()


def analyze_first_bytes(frames: list):
    """Analyze first byte distribution (likely address or sync byte)."""
    first_bytes = Counter(f[1][0] for f in frames if len(f[1]) > 0)
    print("=== First Byte Distribution ===")
    for byte, count in sorted(first_bytes.items(), key=lambda x: -x[1]):
        pct = count / len(frames) * 100
        print(f"  0x{byte:02X} ({byte:3d}): {count:5d} ({pct:5.1f}%)")
    print()


def analyze_byte_positions(frames: list):
    """Analyze byte value distribution at each position."""
    max_len = max(len(f[1]) for f in frames)
    print("=== Byte Position Analysis (first 8 positions) ===")
    for pos in range(min(8, max_len)):
        values = Counter()
        for _, data in frames:
            if len(data) > pos:
                values[data[pos]] += 1
        unique = len(values)
        most_common = values.most_common(3)
        mc_str = ', '.join(f'0x{v:02X}({c})' for v, c in most_common)
        print(f"  Byte {pos}: {unique:3d} unique values. Top: {mc_str}")
    print()


def analyze_timing(frames: list):
    """Analyze inter-frame timing."""
    if len(frames) < 2:
        return
    gaps = []
    for i in range(1, len(frames)):
        gap = frames[i][0] - frames[i-1][0]
        gaps.append(gap)

    # Categorize gaps
    short_gaps = [g for g in gaps if g < 0.01]   # <10ms (same burst)
    medium_gaps = [g for g in gaps if 0.01 <= g < 1.0]  # 10ms-1s
    long_gaps = [g for g in gaps if g >= 1.0]     # >1s (between bursts)

    print("=== Timing Analysis ===")
    print(f"  Total frames: {len(frames)}")
    print(f"  Duration: {frames[-1][0] - frames[0][0]:.1f}s")
    print(f"  Short gaps (<10ms, intra-burst): {len(short_gaps)}")
    if short_gaps:
        print(f"    avg: {sum(short_gaps)/len(short_gaps)*1000:.2f}ms, "
              f"min: {min(short_gaps)*1000:.2f}ms, max: {max(short_gaps)*1000:.2f}ms")
    print(f"  Medium gaps (10ms-1s): {len(medium_gaps)}")
    print(f"  Long gaps (>1s, inter-burst): {len(long_gaps)}")
    if long_gaps:
        print(f"    avg: {sum(long_gaps)/len(long_gaps):.2f}s")
    print()


def analyze_request_response(frames: list):
    """Try to pair frames as request/response based on timing."""
    if len(frames) < 2:
        return

    print("=== Request/Response Pairing (first 20 frames) ===")
    for i in range(min(20, len(frames))):
        ts, data = frames[i]
        hex_str = ' '.join(f'{data[j]:02X}' for j in range(min(16, len(data))))
        if len(data) > 16:
            hex_str += ' ...'

        gap = ""
        if i > 0:
            g = ts - frames[i-1][0]
            if g > 1.0:
                gap = f"  <--- {g:.1f}s gap (new burst)"
            elif g > 0.01:
                gap = f"  <--- {g*1000:.0f}ms gap"

        print(f"  [{i:3d}] ({len(data):2d}B) {hex_str}{gap}")
    print()


def search_known_values(frames: list):
    """Search for known values in frame data."""
    print("=== Known Value Search ===")

    # XP80 serial number: 7881 = 0x1EC9
    serial_be = bytes([0x1E, 0xC9])  # Big-endian
    serial_le = bytes([0xC9, 0x1E])  # Little-endian

    # Node address: 1
    # Firmware: 1.02

    for i, (ts, data) in enumerate(frames):
        found = []
        if serial_be in data:
            pos = data.index(serial_be)
            found.append(f"serial(BE) at byte {pos}")
        if serial_le in data:
            pos = data.index(serial_le)
            found.append(f"serial(LE) at byte {pos}")

        if found:
            hex_str = ' '.join(f'{b:02X}' for b in data)
            print(f"  Frame {i} ({len(data)}B): {', '.join(found)}")
            print(f"    {hex_str}")

    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_capture.py <capture.bin>")
        sys.exit(1)

    filename = sys.argv[1]
    frames = read_capture(filename)
    print(f"Loaded {len(frames)} frames from {filename}\n")

    if not frames:
        print("No frames found!")
        sys.exit(1)

    analyze_lengths(frames)
    analyze_first_bytes(frames)
    analyze_byte_positions(frames)
    analyze_timing(frames)
    analyze_request_response(frames)
    search_known_values(frames)


if __name__ == "__main__":
    main()
