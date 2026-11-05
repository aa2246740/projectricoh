"""Render the official Acros target and fit three native-C040 standalone records."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np, rt, ROOT, LOCAL, UNITS, read, dump, sha, predict, arrays
import hashlib
import shutil
import time


def prepare():
    from gxr_studio.lut.cube import Cube
    from gxr_studio.lut.spaces import encode, matrix
    source=next(r for r in C.FREEZE['sources'] if r['input']=='F-Log2')
    cube=Cube.read(Path(source['file']))
    assert sha(source['file'])==source['sha256'] and len(cube.table3)==65
    D=C.module('film_r2_format', C.frozen('research/v39_g153/dat_format.py'))
    archive=C.frozen('firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    D.sections(archive);D.strict_effects(archive)
    at,_=D.effect_area(archive)
    records={}
    for i in range(D.u16(archive,at+10)):
        desc=archive[at+32+i*32:at+64+i*32]
        if desc[20:32].split(b'\0')[0]!=b'Acros':continue
        for ui in range(3):
            if desc[18]>>ui&1:records[ui]=D.expand_effect(archive,i)
    assert len(records)==3
    jobs=[]
    for ui,unit in enumerate(UNITS):
        folder=LOCAL/'targets'/unit/'14';folder.mkdir(parents=True,exist_ok=True)
        current=records[ui]
        assert current[0]==3 and current[1]==1
        (folder/'current.record552').write_bytes(current)
        shutil.copyfile(LOCAL/'inputs'/unit/'photos.json',folder/'photos.json')
        groups={};sources={}
        if ui==0:
            source_folder=ROOT/'research/recipe_redo_r1/local/targets'/unit
            candidates={key:source_folder/('14_'+key+'.npz') for key in ('train','synthetic','photo_iso200','photo_other_iso')}
        else:
            source_folder=ROOT/'research/model_c040_r1/local/targets'/unit/'14'
            candidates={p.stem:p for p in source_folder.glob('*.npz')}
        stock=rt.release_dat().entry_of(ui,4)
        for key,path in sorted(candidates.items()):
            if not path.exists():continue
            v=arrays(path)
            if not len(v['x']):continue
            v['x']=C.input_codes(v['raw_codes'],unit)
            v['x_old']=v['x'].copy()
            v['base_new']=predict(stock,v['x'],ui)
            v['base']=v['base_new'].copy()
            v['alchemy_want']=v['want'].copy()
            fg=encode(v['xyz']@np.linalg.inv(matrix('rec2020')).T,'flog2')
            v['want']=np.clip(cube.apply(fg),0,1)*255
            assert np.ptp(v['want'],axis=1).max()<.5, 'Official Acros must be monochrome'
            dest=folder/(key+'.npz')
            np.savez_compressed(dest,**v)
            groups[key]=str(dest)
            sources[key]=dict(path=str(path),sha256=sha(path),n=len(v['x']),
                frozen_source_xyz_sha256=hashlib.sha256(v['xyz'].tobytes()).hexdigest())
        seed_paths=[]
        seeds=[current]
        old_exact=ROOT/'research/model_c040_r1/local/fits'/unit/'14/exact.record552'
        if old_exact.exists():seeds.append(old_exact.read_bytes())
        for j,b in enumerate(dict.fromkeys(seeds)):
            p=folder/f'seed-{j:02d}.record552';p.write_bytes(b);seed_paths.append(str(p))
        meta=dict(unit=unit,index=14,ui=ui,name='Acros official',kind='look',level=0,
            current_record=str(folder/'current.record552'),current_sha256=hashlib.sha256(current).hexdigest(),
            groups=groups,source_groups=sources,seeds=seed_paths,
            absent_from_g156=True,restore_from_g154=True,additional_gate_reference=None,
            additional_reference_not_reset=False,c040_geometry='native',official_target=source,
            target_scope='official Acros F-Log2/F-Gamut 65 grid from scene XYZ; direct display codes',
            old_target_scope='Alchemy Acros, a different target; never treated as official',
            target_definition_sha256=hashlib.sha256(Path(source['file']).read_bytes()).hexdigest(),
            no_holdout_target_selection=True,base_slot=3,expected_slot05_flags=1,
            required_base_flags=1,requires_companion_builtin='slot03 must retain flags=1; do not mix a flags=7 HC BW base')
        dump(folder/'profile.json',meta);jobs.append(meta)
        print('PREPARED',unit,{k:v['n'] for k,v in sources.items()},flush=True)
    dump('acros_profiles.json',jobs)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=('prepare','iterate','exact','assess'))
    p.add_argument('--unit',choices=UNITS)
    p.add_argument('--nfev',type=int,default=240)
    args=p.parse_args()
    if args.stage=='prepare':return prepare()
    assert args.unit
    if args.stage=='assess':return C.load_assess().run(args.unit,14)
    C.load_fit().run(args.unit,14,args.stage,args.nfev)


if __name__=='__main__':main()
