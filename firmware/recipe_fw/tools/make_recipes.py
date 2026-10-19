#!/usr/bin/env python3
"""Build the v1 SD data file from display values; never builds firmware."""
import argparse
import json
from pathlib import Path
import struct
import zlib

PARAMETERS = (
    "contrast", "sharpness", "vividness",
    "orange_saturation", "green_saturation", "blue_saturation",
    "red_saturation", "magenta_saturation",
    "orange_hue", "green_hue", "blue_hue", "red_hue", "magenta_hue",
)
DISPLAY_TO_RAW = (7, 6, 1, 2, 3, 4, 5, 8, 9)


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")
    return value


def compile_recipes(document):
    if not isinstance(document, dict) or set(document) - {"generation", "recipes"}:
        raise ValueError("expected generation and recipes")
    generation = integer(document.get("generation", 1), 0, 0xffffffff, "generation")
    recipes = document.get("recipes")
    if not isinstance(recipes, list) or len(recipes) > 16:
        raise ValueError("recipes must be a list containing at most 16 entries")
    records = [bytearray(64) for _ in range(16)]
    occupied = set()
    for entry in recipes:
        if not isinstance(entry, dict) or set(entry) != {"slot", "name", "parameters", "wb"}:
            raise ValueError("each recipe needs slot, name, parameters and wb")
        slot = integer(entry["slot"], 1, 16, "slot")
        if slot in occupied:
            raise ValueError(f"duplicate slot {slot}")
        occupied.add(slot)
        name = entry["name"]
        if not isinstance(name, str) or not 1 <= len(name) <= 32 or not name.strip():
            raise ValueError(f"slot {slot}: name must contain 1..32 printable ASCII characters")
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in name):
            raise ValueError(f"slot {slot}: name must be printable ASCII")
        parameters = entry["parameters"]
        if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
            raise ValueError(f"slot {slot}: parameters must contain exactly {', '.join(PARAMETERS)}")
        wb = entry["wb"]
        if not isinstance(wb, list) or len(wb) != 2:
            raise ValueError(f"slot {slot}: wb must be [axis0, axis1]")
        record = records[slot - 1]
        record[1:3] = bytes((1, len(name)))
        record[4:4 + len(name)] = name.encode("ascii")
        record[36:49] = bytes(DISPLAY_TO_RAW[integer(parameters[key], 1, 9, key) - 1]
                              for key in PARAMETERS)
        record[49:51] = bytes(integer(value, -8, 8, "wb") & 0xff for value in wb)
    for slot, record in enumerate(records, 1):
        record[0] = slot
        struct.pack_into(">I", record, 60, zlib.crc32(record[:60]))
    payload = b"".join(records)
    header = struct.pack(">8s4H3I", b"GXRRV101", 1, 32, 64, 16,
                         generation, 1024, zlib.crc32(payload))
    return header + struct.pack(">I", zlib.crc32(header)) + payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("RECIPES0.DAT"))
    args = parser.parse_args()
    try:
        blob = compile_recipes(json.loads(args.json.read_text(encoding="utf-8")))
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.write_bytes(blob)
    print(json.dumps({"output": str(args.output), "bytes": len(blob),
                      "occupied": sum(blob[33 + i * 64] for i in range(16))}))


if __name__ == "__main__":
    main()
