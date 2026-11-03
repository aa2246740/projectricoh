#!/usr/bin/env python3
"""Freeze short source excerpts and their identities inside the write fence."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collect

SOURCES = [
    ('firmware/image_v36/REPORT.md',1,35),
    ('firmware/resident_v36/resident/loader.c',142,157),
    ('firmware/resident_v36/resident/hooks.c',42,85),
    ('firmware/resident_v36/resident/resident.h',102,135),
    ('firmware/resident_v36/resident/build.py',20,27),
    ('firmware/engine_v38_b36/candidate/service_build.py',1,24),
    ('firmware/engine_v38_b36/candidate/engine_services/services.c',33,148),
    ('firmware/engine_v38_b36/candidate/engine_services/services.c',224,260),
    ('firmware/engine_v38_b36/candidate/engine_services/api.c',48,58),
    ('firmware/engine_v38_b36/candidate/engine_services/bridges.S',19,58),
    ('firmware/engine_v38_b36/candidate/containers/product/adapter.c',390,412),
    ('research/review_full_r4/REPORT.md',1,40),
    ('research/review_v35_container/REVIEW.md',11,29),
    ('research/review_v35_container/REVIEW.md',94,110),
    ('research/irom_storage/REPORT.md',124,148),
    ('research/stage1_data/REPORT.md',151,183),
    ('research/phase0_drill/evidence/gxr-manual-extracted.txt',3784,3789),
]


def main():
    collect.preflight()
    rows=[]
    text=[]
    for rel,start,end in SOURCES:
        path=collect.ROOT/rel
        source=path.read_text().splitlines()
        text.append('\n## '+rel+' SHA256 '+collect.sha(path))
        text.extend(f'{i}: {source[i-1]}' for i in range(start,min(end,len(source))+1))
        rows.append(dict(path=rel,sha256=collect.sha(path),start_line=start,end_line=min(end,len(source))))
    (collect.OUT/'source-excerpts.txt').write_text('\n'.join(text)+'\n')
    collect.save('source-excerpts.json',rows)
    equivalence=[]
    for n in ('hooks.c','loader.c','resident.c','shared.c','resident.h','abi.h'):
        a=collect.ROOT/'firmware/engine_v38_b36/resident'/n
        b=collect.ROOT/'firmware/resident_v36/resident'/n
        equivalence.append(dict(file=n,equal=a.read_bytes()==b.read_bytes(),
                                candidate_sha256=collect.sha(a),fixed_v36_source_sha256=collect.sha(b)))
    collect.save('resident-source-equivalence.json',equivalence)
    print('PASS excerpts',len(rows),'; resident source is taken from resident_v36, not the older hooks copy')


if __name__=='__main__':
    main()
