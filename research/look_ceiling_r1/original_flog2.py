"""Recover the historical 05/06 F-Log2 65-grid targets alongside the requested C controls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import copy
import hashlib
import shutil
import zipfile
import runtime as rt
from runtime import np,ROOT,LOCAL
from run import load_arrays

BASE=LOCAL/'original_flog2'
INDICES=(31,32,39,40,47,48)

def prepare():
    BASE.mkdir(exist_ok=True)
    measure=rt.module('ceiling_original_fuji_measure',ROOT/'research/vlog_alchemy_eval/measure.py')
    archive=ROOT/'artifacts/downloads/fuji-luts/gfx-eterna-55-3d-lut-v110.zip'
    cubes={};sources={}
    with zipfile.ZipFile(archive) as z:
        for slot,style in ((5,'CLASSIC-CHROME'),(6,'CLASSIC-Neg.')):
            member=next(n for n in z.namelist() if '/65Grid/F-Log2/' in n and '/FLog2_to_'+style+'_65grid_' in n and n.endswith('.cube'))
            raw=z.read(member);digest=hashlib.sha256(raw).hexdigest()
            cubes[slot]=rt.upstream.Cube.parse(raw.decode('utf-8-sig'),digest)
            sources[slot]=dict(archive=str(archive.relative_to(ROOT)),archive_sha256=rt.sha(archive),member=member,sha256=digest)
    for group in ('train','synthetic','a12-50','a12-28','mount-a12'):
        shutil.copyfile(LOCAL/('samples_'+group+'.npz'),BASE/('samples_'+group+'.npz'))
    shutil.copyfile(LOCAL/'protocol_private.json',BASE/'protocol_private.json')
    for i in INDICES:
        meta=rt.read(LOCAL/f'target_{i:02d}.json');data=load_arrays(LOCAL/f'target_{i:02d}.npz');slot=meta['builtin_slot']
        original=copy.deepcopy(meta);original['target_variant']='original_FLog2_FGamut_65'
        original['target_scope']='Historical official F-Log2 / F-Gamut 65-grid, direct display-code convention'
        original['official_LUT']=sources[slot];original['name']=meta['name']+' original F-Log2'
        original['scores']={};original['group_files']={};shift={}
        for group in ('train','synthetic','a12-50','a12-28','mount-a12'):
            filename=meta.get('group_files',{}).get(group,'samples_'+group+'.npz')
            original['group_files'][group]='../'+filename
            g=load_arrays(LOCAL/filename)
            if not len(g['x']):original['scores'][group]=None;continue
            target=cubes[slot].apply(measure.fg_input(g['xyz'],'flog2'))*255
            shift[group]=rt.stats(rt.delta_e00(rt.lab_from_codes(target),rt.lab_from_codes(data[group+'_target'])))
            data[group+'_target']=target
            original['scores'][group]=rt.score(data[group+'_base'],data[group+'_published'],target)
        original['target_shift_from_requested_FLog2C33_de00']=shift
        np.savez_compressed(BASE/f'target_{i:02d}.npz',**data)
        rt.dump(BASE/f'target_{i:02d}.json',original)
        # Retain exactly the same bounded C-control parameter starts, never their scores.
        for source in (LOCAL/'fits'/f'{i:02d}').glob('L*.json'):
            if source.stem in ('L0','L1') or source.stem.endswith(('_fullfields','_physical')):continue
            destination=BASE/'fits'/f'{i:02d}'/source.name
            rt.dump(destination,dict(theta=rt.read(source)['theta'],starting_seed_only=True,
                source=str(source.relative_to(rt.HERE)),source_sha256=rt.sha(source)))
    rt.dump(BASE/'sources.json',sources)
    rt.finish('original_flog2_prepare')

def fit(indices):
    import run
    finish=rt.finish;rt.finish=lambda tag:finish('original_flog2_'+tag)
    run.LOCAL=BASE
    sys.argv=['run.py','--indices',indices,'--keys','L0,L1'];run.main()
    sys.argv=['run.py','--indices',indices,'--full-fields'];run.main()

def infinite_fit():
    import infinite
    finish=rt.finish;rt.finish=lambda tag:finish('original_flog2_'+tag)
    infinite.LOCAL=BASE
    sys.argv=['infinite.py','--indices',','.join(map(str,INDICES))]
    # Original infinite parser accepts a range; invoke each requested profile.
    for i in INDICES:
        sys.argv=['infinite.py','--indices',f'{i}:{i+1}'];infinite.main()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('prepare','fit','infinite'))
    ap.add_argument('--indices',default='31:33');args=ap.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='fit':fit(args.indices)
    else:infinite_fit()

if __name__=='__main__':main()
