# Phase 1 tone curves (public summary)

Fits GXR type-26 row-5 replacements for GR Positive Film and GR Negative Film, and compares Hi-Contrast B&W curve candidates.

- Model, verified on GXR captures: `JPEG luma = curve(white-balanced 12-bit luminance)`, piecewise linear over `[0] + A31 + [4095]` → B33, with no post stage (median error ≈ 0.1 code, MAD ≈ 0.5).
- Target: GR III same-chart "mode minus Standard" at six neutral levels, applied on top of the GXR's own stock curve. Fitted residual at those levels ≤ 0.43 code. The transfer assumption leaves ≈ 2 codes of stock-shape difference.
- Hi-Contrast B&W: GXR native row 20 with the true B&W mode. There is no modern-GR numeric reference.
- Colour: GR Positive's colour change sits mainly in a 3×3 look matrix, which a tone curve cannot reproduce. Colour fitting needs on-camera sector measurements.

The full report, the fitted byte arrays and every firmware-derived value stay local (git-ignored), because they include numbers copied from Ricoh firmware tables. Regenerate them with `python3 -I research/phase1_curves/fit_phase1.py` from your own official firmware download.
