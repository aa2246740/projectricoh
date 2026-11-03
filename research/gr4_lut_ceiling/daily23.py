"""Metadata audit of the earlier daily pairs; no inferred recipe is promoted."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from isp import model
from bridge import dng_module
from collections import Counter


def main():
    model();dng=dng_module()
    ar=rt.module('earlier_daily_metadata','research/hue_ring/analyze_ring.py')
    session=rt.module('earlier_daily_session','research/chart_session_20261024/session_runtime.py')
    session.patch_tiff(ar.s2d().Tiff)
    folder=rt.ROOT/'captures/a12-50/2026-10-23/stage2l-daily-R8051219-1228'
    rows=[]
    for raw in sorted(folder.glob('*.DNG')):
        jpeg=raw.with_suffix('.JPG');rt.inp(raw)
        if not jpeg.exists():
            d=dng.Dng(raw)
            rows.append(dict(id=raw.stem,iso=d.exif.get('iso'),paired_JPEG=False,
                             baseline_exposure=d.baseline_exposure,forward_matrix=any(v is not None for v in d.forward_matrix),
                             recipe_identity_confirmed=False,new_candidate_acceptance=False))
            continue
        rt.inp(jpeg)
        md=ar.read_meta(jpeg,raw,None);d=dng.Dng(raw)
        rows.append(dict(id=raw.stem,paired_JPEG=True,iso=md['iso'],selector=md['selector'],display=md['display'],
                         baseline_exposure=d.baseline_exposure,forward_matrix=any(v is not None for v in d.forward_matrix),
                         recipe_identity_confirmed=False,new_candidate_acceptance=False))
    rt.dump('bridge/earlier_daily_metadata.json',dict(pairs=rows,unknown_recipe_labels=True,
                source='existing daily pairs, retained for future actual-render calibration; not matched GR IV captures'))
    print('earlier daily',len(rows),'ISO',dict(Counter(r['iso'] for r in rows)),flush=True)


if __name__=='__main__':main()
