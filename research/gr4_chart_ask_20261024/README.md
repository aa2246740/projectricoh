# GR IV screen chart ask (2026-10-24)

The helper is a plain GR IV owner, not the HDF owner, and cannot do in-camera RAW development. A first build addressed to the HDF owner was never sent and has been deleted (sha 24a0b0b2…). The user clarified "是给 GR4 的用户帮我，不是 GR4HDF". This is probably the plain GR IV owner recruited on 2026-10-22, who has no private template or dense package.

- Sent package: `~/Downloads/GR4色卡拍摄包_给GR4机主_20261024.zip`, sha256 `449e1f9778f28dd05736700b9fd10e20577ccddbd63968778fc51b0e9d8296c3`, 26,040 B.
- Inside: `GR4_chart_20261024/README_ZH.txt`, which is the same text as `拍摄说明.txt` here, plus `pages/00_white.png`–`06_chart.png`. The pages are byte-identical to `research/chart_v2/pages`, the sealed chart v2 that the GXR already shot.
- Zip entry names are ASCII only, because macOS zip does not set the UTF-8 flag.

## Expected return

About 20 DNGs (~650 MB), all from one tripod position. Fixed settings: M mode, f/4, ISO 200, manual WB on the white page, AA filter simulator High (A3 menu, manual p.93), and a slight MF defocus.

| Order | Content | Style |
|---|---|---|
| 1 | page 00 (white) | Standard |
| 2–7 | pages 01–06 | Standard |
| 8–13 | pages 01–06 | Positive Film |
| 14–19 | pages 01–06 | Negative Film |
| 20 | page 01 (drift check) | Standard |

Test shots may arrive too. Identify the style from MakerNote ImageTone (262 = positive, 267 = negative) and the page from the chart page code, not from file order. The screen is unknown: the instructions prefer an Apple display with Preview, and the helper reports the screen model. A non-P3 or non-colour-managed screen narrows the gamut, but the RAW → in-camera JPEG pairs stay valid.

## Notes for analysis

- Each DNG carries a full-size in-camera JPEG in the selected style. That gives a same-raw pair (RAW → GR IV Standard/Positive/Negative) for every patch, so no separate JPEG is needed (memory gr-reference-dng-only).
- Normalise the screen against the GXR session (the user's MacBook screen) using the white page and the gray steps. The leftover difference in screen spectrum is a known error source.
- The chart v2 analyzer was written for GXR files. It needs a GR IV DNG / embedded-JPEG front end before scoring.
- These DNGs are ordinary ISO 200 shots from this body. If they are landscape, they also qualify as templates should a dense-card round with this owner ever become possible (onboard.py).
