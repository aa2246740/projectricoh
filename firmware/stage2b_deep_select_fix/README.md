# Stage 2a Canonical GR candidate firmware

Two complete review packages are built from this directory. Camera acceptance is
not run. The safe build disables deep RPC operations and keeps all 16 surface
recipes usable. The deep build enables four compiled ISP profiles after the
specified runtime identity, connection, limit, and context checks.

Both builds remove `force_adj_image`, preserve the original ADJ dispatcher and
case table, and require native activity 8 for recipe UI actions. They embed the
16 Canonical names and recipes, with native color `04`, B&W `03`, and TE `06`.
Without usable card files, the UI loads the compiled bank. Recognized corrupt,
future, and conflicting banks remain non-applicable.

The safe build reads `/ATA1/RECIPE20.DAT` and `/ATA1/RECIPE21.DAT`. Its surface
values match the Canonical research DAT exactly. The accompanying v1
`RECIPES0.DAT` preserves the names with explicit color-only degradation. The v1
format cannot represent native B&W or TE, and this firmware reads the v2 banks.

The deep build reads `/ATA1/DEEPISP0.DAT` and `/ATA1/DEEPISP1.DAT`. Full recipe
identity binds slots 01, 02, 03, and 05 to Positive, Negative, HC B&W, and Bleach
Bypass tables. Their native contrast is 5, selecting the injected A5 and B5 rows
under the proven default selector conditions. Every other slot restores stock
A5, B5, and C5D4 row1 before changing S and requesting preview. HC retains the
stock color row and uses true `03` grayscale.

The transport positions each row with `X + V`, then streams consecutive `W`
commands. Every W return is its memory readback and must equal the written
halfword. The 33-byte B5 row crosses a 64 KiB page. Its last halfword preserves
the live neighbor at `0x2013001d`, captured once per resident session. The first
transfer uses 104 RPCs, including the two-command neighbor snapshot. Subsequent
transfers use 102 RPCs with three V calls. These counts are host observations,
not measured camera latency.

A possibly started write failure leaves sticky uncertainty across ADJ close and
reopen. The engine does not replay W, roll back blindly, publish S, or request
preview after such a failure. It checks the first old halfword of each row, not
the complete old row. W readback is immediate, not a later whole-row audit.

`rfw_deep_ownership()` returns zero in the safe binary. In the deep candidate,
it tail-calls preflight. The name does not imply a mutex or an ownership
protocol. Calibration counters, concurrent cursor senders, ISP reader exclusion,
running selector values, physical SDRAM writability, task-stack headroom, and
camera latency remain unverified. Screen fits retain their diagnostic WB-drift
status and do not replace native table bytes.

The target image has one read-only payload allocation, eight hooks, no mutable
globals, and a preserved 256-byte probe tail. Read-only target builds omit the
unused encoder and v1 importer. Native ABI wrappers share a tested bridge.

Build both packages and rerun their checks from the project root:

```sh
python3 -I -B research/stage2a_deep_isp/build_packages.py
```

Read back the existing packages without rebuilding:

```sh
python3 -I -B research/stage2a_deep_isp/verify_packages.py
```

Outputs are under `artifacts/stage2a-packages/`. Exact results and the remaining
camera checks are in `research/stage2a_deep_isp/PACKAGE_REPORT.md` and
`package_verification.json`. The workflow operates on local project files and
never accesses a mounted volume or installs firmware.
