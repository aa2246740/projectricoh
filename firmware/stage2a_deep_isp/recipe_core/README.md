# Recipe core host prototype

This directory contains the host prototype for 16 independent GXR recipe slots. It is not integrated into `ilaunch3` or `jlaunch3`. It does not read or write a camera, an SD card mount, or an official firmware image.

`recipe_core.h` is the fixed public contract. A caller can read, save, or explicitly delete one slot. A successful read returns one opaque name and 13 opaque color bytes. The API has no Picture Quality, exposure, focus, white balance, or general camera configuration pointer.

`recipe_storage.h` is the private storage boundary. A platform adapter supplies slot-based `read`, `write`, and `remove` callbacks. Reads report the actual stored length. Writes report the written length. The core keeps no library cache and does not allocate memory.

Each slot uses this 64-byte private record:

| Offset | Size | Value |
| ---: | ---: | --- |
| 0 | 8 | `GXRRCP01` |
| 8 | 1 | Version `1` |
| 9 | 1 | Slot `1..16` |
| 10 | 1 | Zero flags |
| 11 | 1 | Name length `1..32` |
| 12 | 32 | Opaque name bytes, then zero bytes |
| 44 | 13 | Opaque color bytes |
| 57 | 3 | Zero reserved bytes |
| 60 | 4 | Big-endian CRC-32/ISO-HDLC over bytes `0..59` |

The format is not a My Settings `.IFO` record. The test `.bin` and `.rcp` files are not firmware updates or film presets for a camera.

## Run the host checks

Run the complete check from the repository root:

```sh
sh firmware/recipe_core/run_tests.sh
```

The script compiles `recipe_core.c` as a freestanding object with no undefined symbols. It then runs the behavior tests with strict Clang warnings and with AddressSanitizer plus UndefinedBehaviorSanitizer. `verify.py` uses Python `zlib.crc32` to check a fixed C-generated record and the actual host file round trip.

The script writes review artifacts to `artifacts/recipe-core/`:

- `test-results.txt` records the host and sanitizer test results.
- `verification.json` records the independent byte and CRC checks with SHA-256 values.
- `golden.bin` is the fixed 64-byte test vector.
- `host-files/slot-16.rcp` is the 64-byte file store round-trip sample.
- `recipe_core.freestanding.o` is a host object. It is not linked to the GXR firmware ABI.

The host file adapter overwrites one slot directly. The prototype verifies the write by reading it back, but it does not claim atomic save or power-loss recovery.
