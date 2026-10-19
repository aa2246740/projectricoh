# Stage 2d phase-1 candidate

Four recipes: `01 Posi`, `02 Nega`, `03 HC BW`, `04 Std`. Slots 5..16 are empty.
The ADJ type-5 count byte is `0x04`. Deep profiles are stock restore, Posi, Nega
and HC. `04 Std` publishes native Standard (`S+0x36E = 0x01`) and restores the
stock lens tables. Posi and Nega keep stock colour row 1 in this build.

The category gate still allows only 0 and 4. The seven-mode guard is unchanged.
`jlaunch3` stays official. This directory does not touch the camera or an SD card.

Regenerate `deep_tables.c` with `python3 -I tools/generate_deep_tables.py` after
an official firmware download. That file is gitignored.

The host report is `research/stage2d_phase1/REPORT.md`.
The package is `artifacts/stage2d-packages/stage2d-phase1/`.
