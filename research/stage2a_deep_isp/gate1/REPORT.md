# Stage 2a Gate 1: RPC 8 bookkeeping and contiguous-write audit

Static audit of official `jlaunch3` SHA-256 `951be1c659c85af58ae3e4ce98707c52f0b4514fc2075256854d59f822671673`.  It did not execute firmware, connect a camera, or establish SDRAM writability.

## Result

Gate 1 remains open.  The premise that `0x2024615c..0x20246168` are boot-zeroed BSS is false.  They are initialized bytes at the end of loaded segment 12: `0x20246150=0000ffff`; `0x20246154`, cursor `0x20246158`, and counters `0x2024615c..68` begin as zero in the image.  The actual BSS clear runs over `[0x2029db8c, 0x204b5424)`, which does not include any of these addresses.

The requested “global cursor `0x20246150/54`” premise is also wrong.  `0x20246150` is byte-read/written at `0x202410ac`/`0x20241188`; adjacent byte `0x20246151` is read at `0x202410b8` and `0x20241180`, then written at `0x20241190`.  `0x20246154` is a distinct 32-bit field accessed at `0x202413a4` and `0x2024144c`.  This static evidence does not establish either as the RPC cursor.  The V/W cursor is `0x20246158`.  X uses a different high-page base, `0x204a5aec`, written at `0x20243148` and `0x20243154`; it is in the loader-cleared BSS range.

`V` has a side effect when a counter is nonzero.  At `0x202429c8`, each nonzero counter selects a halfword in `T+0x3f0c` or `T+0x3f10`, rewrites that word, and decrements the counter.  Therefore `V` cannot safely prove the counters are zero before the first injection read.

Each counter has a dedicated increment helper: `0x20242b28`, `0x20242b38`, `0x20242b48`, and `0x20242b58`.  The instruction census resolves one direct constructed `jl` for each from the U dispatcher: `U21→0x20242000→0x20242b28`, `U22→0x20242010→0x20242b38`, `U31→0x20242070→0x20242b48`, and `U32→0x20242080→0x20242b58`.  Those are U-labelled commands, but the static label does not prove they are factory-only; it also does not exclude indirect writers.  It therefore cannot prove normal shooting/live view never reaches a writer.  `U60` is identified separately: it calls `cursor_set(0)` and does not increment or clear a counter.

## Reproducible direct-reference boundary

The rerun script parses all 16 loader records, checks every copied GNU-disassembly instruction byte against the official image, searches raw BE32 pointers, decodes direct BL8/BL24 branches, then follows the actual `seth/or3/mv/add3` register construction into every recovered `ld/st` of the eight bookkeeping locations plus X base.  It records construction instructions separately from load/store instruction addresses in JSON.  This remains a bounded direct-reference census, not a whole-program indirect-reachability proof.

The verified windows are in [evidence.txt](evidence.txt), and machine-readable details are in [static_gate.json](static_gate.json).

## Minimum table transports

`X` is RPC-8 index 23, `V` is index 21, and `W` is index 22.  `X(hi16)` sets the high page; `V(low16)` sets the aligned cursor and reads one halfword; each `W(word)` writes one big-endian halfword and advances the cursor by two bytes.

| Payload | Correct minimum sequence | RPC calls |
| --- | --- | ---: |
| A5, 62 bytes at `0x2012f504` | `X(2012), V(f504), 31 × W` | 33 |
| B5, 33 bytes at `0x2012fffc` | With embedded verified official B6[0]: `X(2012), V(fffc), 17 × W`; otherwise read `X(2013), V(001c)` first, then that write sequence | 19 / 21 |
| 24-sector row, 96 bytes | `X(2012), V(low16(row)), 48 × W` | 50 |

B5 crosses from `0x2012fffe` to `0x20130000` while `W` advances the absolute cursor.  It does not need a mid-stream X.  Its final odd byte is at `0x2013001c`; the paired byte at `0x2013001d` is B6's first byte and must be preserved.  The 19-call form embeds the byte from the pinned official stock source and is correct only while SDRAM has that stock neighbor.  The 21-call form captures the current neighbor at runtime.  A blind final W corrupts B6.

## Implementation consequence

Keep the candidate's first-`V` interlock fail-closed.  A zero-valued initial image word is not a proof of normal-operation safety, and no static non-mutating counter-read primitive was recovered.  The host transport can verify every W readback, but that cannot close the pre-first-V bookkeeping gate.

Run again with:

```sh
python3 research/stage2a_deep_isp/gate1/rerun.py
```
