#!/usr/bin/env python3
"""Planning estimates for effects at the pre-encode hook (arithmetic only, no measurement).

Formula and CPU assumptions follow research/cpu_speed_r1/REPORT.md:
T = pixel pairs x cycles/pair / (CPU Hz x usable share), CPU 150-230 MHz, share 70-100 %.
The 3D LUT cycle ranges are copied from that report; every other cycle range below is this
task's own engineering guess for an M32R scalar loop over 4:2:2 pixel pairs, not a measurement.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard import HERE, mount_guard, install_write_fence, dump

FRAMES = {'main 4288x2848': 4288*2848//2, 'display 640x480': 640*480//2, 'thumbnail 160x120': 160*120//2}
MHZ, SHARE = (150e6, 230e6), (.70, 1.0)
# name, (low, high) cycles per pixel pair, fraction of frame touched, source / note
EFFECTS = [
    ('hook passthrough', (0, 0), 1, 'returns immediately; only call overhead'),
    ('read-only checksum', (6, 25), 1, 'one 32-bit load + add per pair; memory waits dominate'),
    ('identity read/write', (10, 40), 1, 'load + store per pair'),
    ('1D tone curve on Y + chroma gain', (20, 60), 1, 'two Y table loads, one chroma multiply'),
    ('vignette (radial gain)', (25, 80), 1, 'incremental r^2 per row, gain table, multiply Y and C'),
    ('grain, noise tile', (20, 60), 1, 'precomputed 256x256 noise tile, Y-dependent amplitude table'),
    ('grain, per-pixel PRNG', (30, 90), 1, 'LCG per pixel, amplitude table'),
    ('light leak overlay', (30, 90), 1, 'bilinear upsample of a 1/16 colour field, additive blend'),
    ('halation / bloom / black mist, 1/8 scale blur', (40, 140), 1,
     'threshold + downsample, separable box blur at 1/8, upsample + screen blend'),
    ('date stamp burn-in', (200, 600), 0.006, 'only a ~300x60 px area; native imprint routine also exists'),
    ('border inside frame', (4, 12), 0.15, 'overwrite edge band; canvas size unchanged'),
    ('border expanding canvas / scaled into frame', (120, 300), 1, 'full resample; JPEG geometry change unproven'),
    ('half-frame diptych', (30, 80), 1, '2:1 decimate previous + current; needs a second full buffer (blocker)'),
    ('shaper 1D + 3x3 + 1D (reduced LUT)', (60, 160), 1, 'per-pixel matrix on shared pair chroma'),
    ('2D CbCr table + Y gain (reduced LUT)', (80, 220), 1, '64x64 chroma table, bilinear, per pair'),
    ('3D LUT 9^3', (400, 900), 1, 'cpu_speed_r1 kernel shape, smaller table, better locality (guess)'),
    ('3D LUT 17^3', (450, 1200), 1, 'research/cpu_speed_r1 scenario'),
    ('3D LUT 33^3', (450, 2000), 1, 'research/cpu_speed_r1 scenario; table 215,622 B does not fit current lease'),
]


def seconds(pairs, cyc, frac):
    lo = pairs*frac*cyc[0]/(MHZ[1]*SHARE[1])
    hi = pairs*frac*cyc[1]/(MHZ[0]*SHARE[0])
    return lo, hi


def main():
    mount_guard(); install_write_fence()
    rows = []
    for name, cyc, frac, note in EFFECTS:
        row = {'effect': name, 'cycles_per_pair': cyc, 'frame_fraction': frac, 'note': note}
        for f, pairs in FRAMES.items():
            row[f] = seconds(pairs, cyc, frac)
        rows.append(row)
        print(f"{name:48s} " + '  '.join(f"{row[f][0]:7.2f}-{row[f][1]:7.2f}s" for f in FRAMES))
    dump(HERE/'local/costs.json', {'assumptions': {'cpu_hz': MHZ, 'usable_share': SHARE, 'frames_pixel_pairs': FRAMES,
                                                   'formula': 'pairs*fraction*cycles/(Hz*share)',
                                                   'evidence': 'planning estimate, not a camera measurement'},
                                   'effects': rows})


if __name__ == '__main__':
    main()
