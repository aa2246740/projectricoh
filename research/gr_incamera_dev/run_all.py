#!/usr/bin/env python3
"""Rebuild the default offline artifacts and their complete verification trail."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shutil
from common import HERE, LOCAL, DELIVERY, GR3, GR4, ROOT, pin, initialize, dump
from inject import inject
from predict import predict
from analyze import metadata
from test_codec import run as test_codec
from dry_run import run as dry_run
from verify import verify


def run():
    initialize()
    for kind in ('tone', 'colour'):
        manifest = inject(GR3, kind, DELIVERY / f'GR3_{kind}.DNG')
        predict(manifest, LOCAL / f'predictions/GR3_{kind}', toy_bw=kind == 'colour')
    inject(GR4, 'colour', LOCAL / 'GR4_colour_PRIVATE.DNG', privacy='known-fields')
    audit = {}
    for mode in ('standard', 'positive', 'negative'):
        path = ROOT / f'artifacts/downloads/bastibe-gr3/downloads/bastibe_gr3_{mode}/{mode}.JPG'
        audit[mode] = metadata(pin(path), mode, 'camera')
    dump(LOCAL / 'bastibe_style_metadata_spotcheck.json', audit)
    shutil.copyfile(HERE / 'HELPER_ZH.md', DELIVERY / '给机主的说明.txt')
    test_codec()
    dry_run()
    verify(seal=True, record=True)


if __name__ == '__main__':
    run()
