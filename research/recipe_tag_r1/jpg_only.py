"""A fixed JPG-only histogram baseline, tested across different scenes.

This is a diagnostic baseline, not a calibrated recipe classifier.
No RAW, exposure fitting, or target labels enter the feature extractor.
"""
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
c.guard(600)
sys.path.insert(0,str(c.ROOT/'studio/src'))
import numpy as np
from PIL import Image,ImageOps
from gxr_studio.engine.colour import lab_from_codes


def feature(path):
    with Image.open(path) as im:
        rgb=np.asarray(ImageOps.exif_transpose(im).convert('RGB').resize((192,128),Image.Resampling.BOX))
    lab=lab_from_codes(rgb.reshape(-1,3))
    hist=[np.histogram(lab[:,i],bins=16,range=span)[0]/len(lab) for i,span in enumerate(((0,100),(-128,128),(-128,128)))]
    return np.concatenate(hist)


def main():
    rows=list(csv.DictReader((c.HERE/'labels.csv').open()))
    rows=[r for r in rows if r['group'] in ('street-g137','chart-g150') and r['truth'].isdigit()]
    vectors={}
    for r in rows:
        base=c.ROOT/r['folder']
        p=base/('jpg' if r['group']=='street-g137' else '')/(r['file']+'.JPG')
        vectors[r['file']]=feature(p)
    results=[]
    for row in rows:
        refs=[q for q in rows if q['group']!=row['group']]
        dist={q['truth']:float(np.linalg.norm(vectors[row['file']]-vectors[q['file']])) for q in refs}
        best=min(dist,key=dist.get)
        results.append(dict(file=row['file'],group=row['group'],truth=row['truth'],prediction=best,
                            correct=best==row['truth'],distances=dist))
    from collections import Counter
    counts=Counter((r['group'],r['truth'],r['prediction']) for r in results)
    with (c.HERE/'jpg_only_confusion.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['group','truth','predicted','count'])
        for k,n in sorted(counts.items()):w.writerow([*k,n])
    summary={g:dict(n=sum(r['group']==g for r in results),correct=sum(r['group']==g and r['correct'] for r in results))
             for g in sorted({r['group'] for r in results})}
    c.dump('jpg_only_results.json',dict(method='16-bin Lab histograms; nearest other-scene prototype; no tuning',
           results=results,summary=summary,confidence='not calibrated',
           limitation='One street scene and one chart page; source generation also differs'))
    c.finish('jpg-only')
    print(json.dumps(summary))


if __name__=='__main__':main()
