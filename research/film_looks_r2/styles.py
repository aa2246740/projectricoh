"""Compare shared and independent curves for the existing non-film g157 Looks."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import np,rt,ROOT,LOCAL,UNITS,read,dump,sha,predict,arrays
import library as L

INDICES=(0,1,2,3,6,9,10,15,16,17,18,23)


def definitions():
    out=[read(ROOT/'research/look_ceiling_r1/local'/f'target_{i:02d}.json') for i in INDICES]
    base=ROOT/'research/film_look_routes/local/luts/leica'
    names=(('Leica Natural official','Natural_Rec709.cube'),
        ('Leica Pure official','Leica_Pure_Rec2020_LLog_to_Rec709_Gamma24_65.cube'),
        ('Leica Cine official','Leica_Cine_Rec2020_LLog_to_Rec709_Gamma24_65_.cube'))
    for i,(name,filename) in enumerate(names,50):
        p=next(p for p in base.rglob(filename) if '__MACOSX' not in p.parts)
        dest=LOCAL/'style_sources'/filename;dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(p.read_bytes())
        out.append(dict(index=i,name=name,source=str(dest.relative_to(ROOT)),source_sha256=sha(dest),
            input='llog',output='gamma24',interpretation='declared',
            manufacturer='Leica Camera AG',permission='Local research only; no redistribution permission inferred'))
    return out


def prepare():
    rows=[]
    for original in definitions():
        oldindex=original['index']
        name=original['name']
        assert sha(ROOT/original['source'])==original['source_sha256']
        for ui,unit in enumerate(UNITS):
            camera=rt.Camera(ui)
            oldmeta=read(ROOT/'research/recipe_redo_r1/local/targets'/unit/f'{oldindex:02d}.json') if oldindex<50 else None
            root=LOCAL/'styles'/f'{oldindex:02d}'/unit;root.mkdir(parents=True,exist_ok=True)
            groups={}
            source_meta=read(LOCAL/'targets'/unit/'14/profile.json')
            for group,source in source_meta['groups'].items():
                # Existing digital targets keep their declared input interpretation.
                # Re-render on the same frozen native-C040 inputs instead of reusing an old 04 mapping.
                v=arrays(source)
                v={k:x for k,x in v.items() if k not in ('alchemy_want','want')}
                from gxr_studio.lut.cube import Cube
                from gxr_studio.lut.spaces import Target
                target=Target(Cube.read(ROOT/original['source']),original['input'],original['output'])
                if original.get('interpretation')=='scene':
                    from gxr_studio.lut.spaces import xyz_to_encoded
                    v['want']=np.clip(target.cube.apply(xyz_to_encoded(v['xyz'],'srgb')),0,1)*255
                else:v['want']=target.render(v['base_new'],v['xyz'])
                out=root/(group+'.npz');np.savez_compressed(out,**v);groups[group]=str(out)
            planned=read(LOCAL/'g157_layouts/release/manifest.json')['records']
            oldrow=next((r for r in planned if r['unit']==unit and r['kind']=='look' and r['name']==name),None)
            current=Path(oldrow['record_file']).read_bytes() if oldrow else (bytes.fromhex(oldmeta['template_hex']) if oldmeta else L.template(camera,ui,False))
            if current[1]&4:
                params=L.parameters_of(current);params['curve_y_u8']=np.array([list(current[82:115])])
                current=C.codec.encode(current,params,level=0,look_unit_mask=1<<ui)
            for level in (0,1):
                index=3000+10*oldindex+level;folder=LOCAL/'targets'/unit/f'{index:02d}'
                folder.mkdir(parents=True,exist_ok=True)
                b=bytearray(current);b[0]=6 if level else current[0]
                b=C.codec.encode(bytes(b),L.parameters_of(current),level=level,
                    look_unit_mask=None if level else 1<<ui)
                p=folder/'current.record552';p.write_bytes(b)
                (folder/'photos.json').write_bytes((LOCAL/'inputs'/unit/'photos.json').read_bytes())
                seeds=[str(p)]
                if level:seeds.append(str(LOCAL/'fits'/unit/f'{index-1:02d}/exact.record552'))
                meta=dict(unit=unit,index=index,ui=ui,name=name,kind='builtin' if level else 'look',level=level,
                    current_record=str(p),current_sha256=sha(p),groups=groups,seeds=seeds,
                    additional_gate_reference=None,target_definition_sha256=original['source_sha256'],
                    absent_from_g156=oldrow is None,restore_from_g154=oldrow is not None,
                    original_target=original,original_index=oldindex,source_groups=source_meta['source_groups'],
                    c040_geometry='native',route='digital_shared' if not level else 'digital_rgb')
                dump(folder/'profile.json',meta);rows.append(meta)
            print('STYLE PREPARED',name,unit,flush=True)
    dump('styles.json',rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','iterate','exact'))
    p.add_argument('--index',type=int);p.add_argument('--unit',choices=UNITS);p.add_argument('--nfev',type=int,default=240)
    args=p.parse_args()
    if args.stage=='prepare':return prepare()
    C.load_fit().run(args.unit,args.index,args.stage,args.nfev)


if __name__=='__main__':main()
