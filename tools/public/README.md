# GXR public rebuild tools

> ## ⚠️ 风险警告 / Risk warning
>
> **中文**
> - 这些工具能在你自己的电脑上生成改过的 GXR 机身固件和 28mm（GR LENS A12 28mm F2.5）单元固件。
> - **刷写单元固件可能让单元无法开机，而且没有已验证的救法。** 机身固件同样有风险。
> - 这里的改动只在作者自己的相机上、按经过独立复审的步骤测试过，不保证适用于你的相机。
> - 只有在你完全理解并自愿承担变砖风险时才使用。作者不对任何损坏负责。
> - 不要刷没有经过复审的补丁。
>
> **English**
> - These tools rebuild modified RICOH GXR body firmware and GR LENS A12 28mm F2.5 camera-unit firmware on your own computer.
> - **Flashing camera-unit firmware can leave the unit unable to boot, and there is no verified recovery path.** Flashing body firmware also carries risk.
> - The changes were tested only on the author's own camera, following independently reviewed steps. They are not guaranteed to work on yours.
> - Use them only if you fully understand and accept the risk of bricking. The authors accept no liability for any damage.
> - Do not flash patches that have not been reviewed.

## What this is

Ricoh's firmware is not redistributed here. Every machine downloads the official GXR 1.51 package from Ricoh and rebuilds our variants locally from public patches.

- Official package: `https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/exe/gxr-151.zip`
  - 11,277,528 bytes
  - SHA-256 `3705984b8433c40d2ed4fd2600c11f03ed8a6de7dbe7f66efd38ee5ca15fc898`
- Patch format `gxr-public-patch/1`. Each change records:
  - an offset and a length;
  - the SHA-256 of the official bytes it replaces;
  - either our new bytes (`literal`) or a copy from another offset of the official image (`copy`).

  The firmware checksum is recomputed by the tool and is not stored in the patch. The patch never contains a run of 12 or more official bytes.

## Usage

```sh
python3 -I -B tools/public/fetch_official.py --download        # or: --from <local gxr-151.zip>
python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/xpan-28mm.json --audit --out <dir>
python3 -I -B tools/public/rebuild.py --patch research/public_rebuild_r1/patches/body-r5.json  --audit --out <dir>
```

The tools need only the Python 3 standard library. Expected result SHA-256 values and sizes are inside each patch. See `research/public_rebuild_r1/REPORT.md` for the full verification record.

The downloaded package and every rebuilt image contain Ricoh's code. Keep them local, and do not commit or redistribute them.
