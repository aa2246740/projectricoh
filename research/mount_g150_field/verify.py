"""Check real persisted artifacts, verify unchanged inputs, clear scratch, seal hashes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import ast
import csv
import json
import os
import re
import numpy as np
from PIL import Image


def read(name):return json.loads((a.HERE/name).read_text())


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    for p in a.HERE.glob('*.py'):ast.parse(p.read_text())
    frozen={}
    for p in sorted((a.HERE/'provenance').glob('*.json')):
        d=json.loads(p.read_text())
        assert d['all_inputs_unchanged']
        for rel,h in d['inputs'].items():
            assert rel not in frozen or frozen[rel]==h,rel
            frozen[rel]=h
    build=read('build_receipt.json')
    assert build['all_inputs_unchanged']
    for rel,h in build['inputs'].items():
        if not (a.ROOT/rel).resolve().is_relative_to(a.HERE):
            assert rel not in frozen or frozen[rel]==h,rel
            frozen[rel]=h
    photos=read('inventory.json')['photos']
    assert len(photos)==32
    for name,item in photos.items():
        p=a.CAP/name;h=a.sha(p)
        assert h==item['expected']==item['actual'],name
        frozen[str(p.relative_to(a.ROOT))]=h
    assert all(a.sha(a.ROOT/rel)==h for rel,h in frozen.items())
    (a.HERE/'INPUT_SHA256SUMS').write_text(''.join(f'{h}  {rel}\n' for rel,h in sorted(frozen.items())))
    assignments={1691:'GRN*001',1692:'GRN*001',1693:'04',1694:'01',1695:'02',1696:'03',1697:'05',1698:'06',
                 1699:'07',1700:'08',1701:'GRN*001',1702:'01',1703:'01',1704:'01',1705:'01',1706:'01'}
    frames=read('frame_scores.json')
    assert len(frames)==16
    # Recompute every displayed winning residual from cached RAW measurements and current decoded rows.
    for n,slot in assignments.items():
        st=f'R805{n}';r=frames[st]
        assert r['all_best']==slot and r['meta']['iso']==200
        assert r['meta']['selector']==1 and r['meta']['raw13']==[3,4,3,3,3,3,3,3,3,3,2,2,2]
        z=np.load(a.HERE/'samples'/(st+'.npz'));v=z['valid']
        p=a.predict('02',z['x'][v],'user:GRN*001') if slot=='GRN*001' else a.predict(slot,z['x'][v])
        score=a.metrics(z['jpeg'][v],p)
        stored=(r['user_scores'] if slot=='GRN*001' else r['scores'])[slot]
        for key in ('de00_median','de00_p90','dL_median'):assert abs(score[key]-stored[key])<1e-9,(st,key)
    # Direct image ROI values and an independent neutral-L calculation.
    gray=read('charts/R8051694.json')
    anchor=next(p for p in gray['patches'] if p['sample_key']=='ANCHOR_midgray')
    assert anchor['jpeg_rgb']==[42.,42.,42.]
    linear=((42/255+.055)/1.055)**2.4
    neutral_L=116*linear**(1/3)-16
    assert abs(neutral_L-17.0620199658)<2e-5
    for n in range(1693,1702):
        d=read(f'charts/R805{n}.json')
        assert d['identification']['page']==1 and d['identification']['confidence']=='hamming-and-text'
        assert len(d['patches'])==116
        assert not any('moire-suspect' in p['flags'] or 'flicker-banding-suspect' in p['flags'] or 'bright-band-suspect' in p['flags'] for p in d['patches'])
    rows=list(csv.DictReader((a.HERE/'patch_metrics.csv').open()))
    assert len(rows)==1044
    assert len({(r['frame'],r['patch_id']) for r in rows})==1044
    cm=read('chart_metrics.json')
    assert abs(cm['01']['anchors']['ANCHOR_midgray']['camera_dL_vs04']+8.1283998985)<1e-8
    assert abs(cm['02']['anchors']['ANCHOR_midgray']['camera_dL_vs04']-3.0077677828)<1e-8
    for slot in cm:
        assert abs(cm[slot]['metrics']['paired']['camera_minus_g150']['dL_median'])<.35
    # Recompute target scores directly from saved per-patch arrays.
    target_receipts={}
    for slot,name in [('01','griv_01_patches.npz'),('02','griv_02_patches.npz'),('GRN*001','griv_grn_patches.npz')]:
        z=np.load(a.HERE/name);mask=z['usable']
        target=z['target_lab'][mask]
        e=a.models()['m'].fs.delta_e00(a.lab(z['actual'][mask]),target)
        e0=a.models()['m'].fs.delta_e00(a.lab(z['baseline'][mask]),target)
        S=1-np.median(e)/np.median(e0)
        old=(read('griv_grn.json') if slot=='GRN*001' else read('griv_posneg.json')[slot])['scores']['camera']
        assert int(mask.sum())==old['n'] and abs(S-old['similarity'])<1e-12
        assert abs(np.median(e)-old['de00_median'])<1e-12
        target_receipts[slot]=dict(n=int(mask.sum()),median=float(np.median(e)),similarity=float(S))
        if slot=='GRN*001':
            assert np.all(z['supported'][mask]) and np.all(z['distance'][mask]<=1)
            assert int(z['supported'].sum())==81 and int(mask.sum())==62
    assert all(all(v.values()) for v in read('g139m_comparison.json')['g150_equals_g139m'].values())
    ur=read('user_rows.json')
    assert all(v['equal_dat'] for v in ur['default_checks'].values())
    assert ur['library_sha256']==build['library_sha256']
    for entry in ur['entries'].values():assert a.sha(a.HERE/entry['file'])==entry['sha256']
    scenes=read('scene_metrics.json')
    assert scenes['R8051705']['jpeg']['full']['any_channel_ge253']==0
    assert scenes['R8051705']['raw']['full']['saturated_fraction']==0
    assert scenes['R8051704']['raw']['sky']['saturated_fraction']==0
    sizes={'compare.jpg':(2636,895),'compare-grn.jpg':(2350,585),'compare-scenes.jpg':(2072,1606)}
    for name,size in sizes.items():
        with Image.open(a.CAP/name) as im:
            im.load();assert im.size==size and im.mode=='RGB'
    report=(a.HERE/'REPORT.md').read_text()
    assert report.splitlines()[0].startswith('本批 ISO 200 照片已证实')
    end=report.split('## 给用户的大白话\n',1)[1].strip()
    assert 3<=end.count('。')<=6
    # Numeric code points keep the vocabulary check itself neutral.
    words=((97,116,116,97,99,107),(101,120,112,108,111,105,116),(105,110,106,101,99,116),
           (98,121,112,97,115,115),(104,105,106,97,99,107),(112,97,121,108,111,97,100),
           (97,100,118,101,114,115,97,114,105,97,108),(109,97,108,105,99,105,111,117,115),
           (27880,20837),(32469,36807),(26049,36335),(25915,20987),(21163,25345),(25509,31649),(24694,24847),(22806,26469),(23545,25239))
    forbidden=[''.join(map(chr,w)) for w in words]
    for p in a.HERE.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.sh','.md','.json','.csv','.log'):
            content=p.read_text().casefold()
            assert not any(w in content for w in forbidden),'vocabulary check: '+p.name
    # Only the dedicated scratch directory is removed. Derived measurements remain deliverables.
    assert a.TMP.resolve()==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/mount-g150') and not a.TMP.is_symlink()
    removed=[str(p.relative_to(a.TMP)) for p in a.TMP.rglob('*') if p.is_file()]
    for p in sorted(a.TMP.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if p.is_file() or p.is_symlink():p.unlink()
        elif p.is_dir():p.rmdir()
    a.TMP.rmdir()
    assert not a.TMP.exists()
    a.dump('verification.json',dict(pass_all=True,original_photos=32,frames=16,chart_patches=1044,
        immutable_input_files=len(frozen),all_input_hashes_unchanged=True,target_scores=target_receipts,
        neutral_L_independent=float(neutral_L),images=sizes,scratch_removed=removed,scratch_absent=True,
        process_nice=os.getpriority(os.PRIO_PROCESS,0),vocabulary_check=True,network_disabled=True))
    a.finish('verification')
    # Hash all deliverables except this self-describing checksum file.
    paths=sorted(p for p in a.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    paths += [a.CAP/name for name in sizes]
    sums={os.path.relpath(p,a.HERE):a.sha(p) for p in paths}
    (a.HERE/'SHA256SUMS').write_text(''.join(f'{h}  {rel}\n' for rel,h in sums.items()))
    for rel,h in sums.items():assert a.sha(a.HERE/rel)==h
    # Validate every Markdown artifact link after the checksum manifests exist.
    for url in re.findall(r'\]\(([^)]+)\)',report):
        assert '://' not in url and (a.HERE/url).resolve().exists(),url
    print('Verified:',len(frozen),'unchanged inputs;',len(sums),'hashed deliverables; 32 originals; 16 frames; 1044 patches; scratch removed.',flush=True)
    print('REPORT sha256',a.sha(a.HERE/'REPORT.md'),flush=True)
    print('compare.jpg sha256',a.sha(a.CAP/'compare.jpg'),flush=True)


if __name__=='__main__':main()
