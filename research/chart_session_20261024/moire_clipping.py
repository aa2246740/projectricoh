"""Refine clipping at ROI/channel level; compute diagnostics from fixed cached predictions."""
import collections
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import session_runtime as s
from moire_review import flagged, stats


def category(c):
    affected=np.array(c['low_fractions'])+np.array(c['high_fractions'])>.01
    if c['any_fraction']<=.01:return 'not-flagged'
    if c['all_dark_fraction']>.01:return 'all-channel-dark'
    if c['all_bright_fraction']>.01:return 'all-channel-bright'
    if sum(affected)==1:return 'single-channel-color'
    return 'multiple-or-sparse-channel-color'


def main():
    s.guard();sys.addaudithook(s.audit)
    out=s.LOCAL/'moire-review-v2'
    rows={(r['frame'],r['patch_id']):r for r in (json.loads(line)for line in(out/'roi_metrics.jsonl').read_text().splitlines())}
    frames={f['frame']:f for f in (json.loads(p.read_text())for p in(s.LOCAL/'analysis-final/frames').glob('*.json'))}
    scored=json.loads((out/'scored/mean.json').read_text())
    a,chain,p=s.setup(s.LOCAL/'extraction',freeze=False)
    final=[]
    for policy in ('strict','recipe-single-channel','mild-single-channel','ignore-diagnostic'):
        for slot in ('04','01','02','03','05','06'):
            de,bd=[],[]
            for key,q in scored.items():
                f=frames[key]
                if f['slot']!=slot:continue
                b=frames[q['matched04']]
                mask=np.array(q['valid'],bool)
                for i,patch in enumerate(f['patches']):
                    r,br=rows[(key,patch['patch_id'])],rows[(b['frame'],patch['patch_id'])]
                    mask[i]&=not flagged(r,'jpeg6')and not flagged(br,'jpeg6')
                    for item,baseline in ((r,False),(br,True)):
                        c=item['clipping'];cat=category(c)
                        ok=cat=='not-flagged'or policy=='ignore-diagnostic'
                        if policy=='recipe-single-channel'and not baseline and cat=='single-channel-color':ok=True
                        if policy=='mild-single-channel'and cat=='single-channel-color':
                            mean=np.array(item['jpeg']['mean'])
                            ok=c['any_fraction']<=.05 and np.all((mean>=5)&(mean<=250))
                        mask[i]&=ok
                de.extend(np.array(q['de00'])[mask]);bd.extend(np.array(q['baseline_de00'])[mask])
            final.append({'policy':policy,'slot':slot,'n':len(de),'similarity':chain.measure.similarity(de,bd)['value'],'de00':stats(de)})
    summary={}
    for group in ('C','M'):
        selected=[r for r in rows.values()if r['group']==group]
        summary[group]={cat:{'patches':sum(category(r['clipping'])==cat for r in selected),
            'raw_unsaturated':sum(category(r['clipping'])==cat and r['raw_saturation_fraction']<=.001 for r in selected),
            'unclipped_channel_observations':sum(sum(r['clipping']['unclipped_channel_mask'])for r in selected if category(r['clipping'])==cat)}
            for cat in sorted({category(r['clipping'])for r in selected})}
    with(out/'clipping_by_patch.csv').open('w',newline='')as f:
        w=csv.writer(f);w.writerow(('frame','group','slot','page','patch_id','category','affected_channels','unclipped_channel_mask','raw_saturation_fraction'))
        for r in rows.values():
            c=r['clipping'];affected=(np.array(c['low_fractions'])+np.array(c['high_fractions'])>.01).tolist()
            w.writerow((r['frame'],r['group'],r['slot'],r['page'],r['patch_id'],category(c),json.dumps(affected),json.dumps(c['unclipped_channel_mask']),r['raw_saturation_fraction']))
    s.dump(out/'clipping_review.json',{'definition':'affected channel means >1% of that ROI channel is <=2 or >=253; exactly one affected channel is single-channel-color',
        'refinement_note':'initial sampling categories counted simultaneous clipping per pixel; final categories count affected channels across the whole ROI',
        'counts':summary,'mean_jpeg6_sensitivity':final})
    for unit in ('50mm','mount'):
        path=out/'exchange-jpeg6'/unit/'patches.jsonl'
        if path.exists():
            exported=[json.loads(line)for line in path.read_text().splitlines()]
            for row in exported:
                row['review']['clipping_category']=category(rows[(row['frame'],row['patch_id'])]['clipping'])
            path.write_text(''.join(json.dumps(s.plain(row),ensure_ascii=False,allow_nan=False)+'\n'for row in exported))
    print(json.dumps({'counts':summary,'cases':final},ensure_ascii=False))


if __name__=='__main__':main()
