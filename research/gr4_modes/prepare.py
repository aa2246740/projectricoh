#!/usr/bin/env python3
"""Decode every DNG + camera JPEG pair used by research/gr4_modes into .npz caches.

Read-only on all inputs. Contributor pairs cache into local/ (git-ignored);
public downloads cache into /tmp/gr4modes_work/cache. Also writes
local/input_hashes_<tag>.json with SHA-256 of every input file.

    python3 -I research/gr4_modes/prepare.py before
    ... analysis ...
    python3 -I research/gr4_modes/prepare.py after --hash-only

Public inputs (downloaded by hand into their own new directories, never run):
  /tmp/gr4dl_gruser/x/            GR III / GR IV pairs from the gruserforum
                                  thread 11607 Dropbox folder (zip SHA-256 in REPORT)
  /tmp/gxr_color_refs/downloads/  bastibe GR III chart (fetched by an earlier task;
                                  hashes match research/color_references/source_manifest.json)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gr4io  # noqa: E402

ROOT = HERE.parents[1]
CAPS = ROOT / 'captures' / 'contrib' / '2026-10-19'
PUBLIC_CACHE = '/tmp/gr4modes_work/cache'
GRUSER = Path('/tmp/gr4dl_gruser/x')
BASTIBE = Path('/tmp/gxr_color_refs/downloads')

CONTRIB = [
    (CAPS / 'gr4-modes/hc_bw', 'hc_bw'),
    (CAPS / 'gr4-modes/positive', 'positive'),
    (CAPS / 'gr4-modes/negative', 'negative'),
    (CAPS / 'gr4hdf-set/R0003009_standard', 'hdf_std'),
    (CAPS / 'gr4hdf-set/R0003004_positive', 'hdf_pos'),
    (CAPS / 'gr4hdf-set/R0003006_negative', 'hdf_neg'),
    (CAPS / 'gr4hdf-set/R0003007_bw', 'hdf_hc'),
    (CAPS / 'gr4hdf-set/R0003010_cinema_yellow', 'hdf_cy'),
    (CAPS / 'gr4hdf-set/R0003011_cinema_green', 'hdf_cg'),
]
GXR_READ = [ROOT / 'captures/a12-50/2026-10-19/stage2d-colorchecker/R8051150.DNG']


def public_pairs():
    out = []
    for stem in ['G40000' + n for n in ('30', '31', '32', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57')] + \
                ['GR0028' + n for n in ('09', '10', '11', '12', '13', '14', '15', '16', '17')]:
        out.append((GRUSER / f'{stem}.DNG', GRUSER / f'{stem}.JPG', f'gruser_{stem}'))
    for mode, jpg in (('std', 'bastibe_gr3_standard/standard.JPG'), ('pos', 'bastibe_gr3_positive/positive.JPG'),
                      ('neg', 'bastibe_gr3_negative/negative.JPG')):
        out.append((BASTIBE / 'bastibe_gr3_dng/Target.DNG', BASTIBE / jpg, f'gr3chart_{mode}'))
    return out


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'run'
    hash_only = '--hash-only' in sys.argv
    hashes = {}
    for base, _ in CONTRIB:
        for ext in ('.DNG', '.JPG'):
            p = base.with_suffix(ext)
            hashes[str(p.relative_to(ROOT))] = gr4io.sha256(p)
    for p in GXR_READ:
        hashes[str(p.relative_to(ROOT))] = gr4io.sha256(p)
    (gr4io.LOCAL).mkdir(exist_ok=True)
    (gr4io.LOCAL / f'input_hashes_{tag}.json').write_text(json.dumps(hashes, indent=1))
    if hash_only:
        print('hashed', len(hashes))
        return
    for base, key in CONTRIB:
        gr4io.load_pair(base.with_suffix('.DNG'), base.with_suffix('.JPG'), cache_name=key)
        print('cached', key, flush=True)
    for dng, jpg, key in public_pairs():
        if dng.exists() and jpg.exists():
            gr4io.load_pair(dng, jpg, cache_name=key, cache_dir=PUBLIC_CACHE)
            print('cached', key, flush=True)
        else:
            print('missing public input', dng, jpg)


if __name__ == '__main__':
    main()
