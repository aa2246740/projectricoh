# MyRec v2: decisions (orchestrator, 2026-10-30)

Answers to the four questions in DESIGN.md. The user may override any of them.

1. **Name length: 7 visible characters.** Column 0 holds the marker (`>` / `*`).
2. **v2 Default restores the entry's stored values**, not the recipe-table default. That is what a user means by "reset" on their own recipe.
3. **S0 (v1 four-knob write-back): not now.** Camera work comes first, and g135 (knobs v2) is about to replace the v1-era build. Do v2 write-back once g135 has passed review and the field test.
4. **Capacity: 32 first, 80 later.** Removing `saved[]` (needed for 80) is a separate risky change. Keep one risky change per build.

Order: g135 review + field test → camera M1–M5 (GXUI v2, gen 136) → studio S1–S5 write-back → user-confirmed card write.
