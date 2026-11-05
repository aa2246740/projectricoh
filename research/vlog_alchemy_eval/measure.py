"""Measure route differences, isolated imports and creator input hypotheses."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,ROOT,HERE,DATA,SCRATCH,digest,dump,check_time
setup()
import hashlib
import json
import zipfile
import numpy as np
from data import (Cube,Target,encode,decode,matrix,xyz_to_encoded,rgb_out,de,stats,
                  scenes,synthetic,creator_jobs,input_receipts,camera_model)
from gxr_studio.lut.library import LutLibrary

FGC=((.7347,.2653),(.0263,.9737),(.1173,-.0224))

def rgb_matrix(primaries,white=(.3127,.3290)):
    xy=np.array(primaries)
    xyz=np.stack([xy[:,0]/xy[:,1],np.ones(3),(1-xy.sum(axis=1))/xy[:,1]])
    w=np.array([white[0]/white[1],1,(1-sum(white))/white[1]])
    return xyz*np.linalg.solve(xyz,w)[None,:]

def fg_input(xyz,kind):
    mat=rgb_matrix(FGC) if kind=='flog2c' else matrix('rec2020')
    return encode(xyz@np.linalg.inv(mat).T,'flog' if kind=='flog' else 'flog2')

def official_cubes():
    path=ROOT/'artifacts/downloads/fuji-luts/gfx-eterna-55-3d-lut-v110.zip'
    out={}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not n.endswith('.cube') or '/33Grid/' not in n:
                continue
            kind='flog2c' if '/F-Log2C/' in n else 'flog2' if '/F-Log2/' in n else 'flog'
            style=n.split('_to_')[-1].split('_33grid')[0]
            raw=z.read(n)
            out[kind,style]=(Cube.parse(raw.decode('utf-8-sig'),hashlib.sha256(raw).hexdigest()),
                             {'archive':str(path.relative_to(ROOT)),'member':n,
                              'sha256':hashlib.sha256(raw).hexdigest()})
    return out

def compare_fuji(samples):
    official=official_cubes()
    names=['PROVIA','Velvia','ASTIA','CLASSIC-CHROME','REALA-ACE','PRO-Neg.Std',
           'CLASSIC-Neg.','ETERNA','ETERNA-BB','ACROS']
    rows=[]
    for name in names:
        check_time()
        token={'PRO-Neg.Std':'PRO-Neg_Std','CLASSIC-Neg.':'CLASSIC-Neg'}.get(name,name)
        path=DATA/'Luts/Fujifilm'/('FLog2C_to_'+token+'_VLog.cube')
        target=Cube.read(path)
        row={'style':name,'alchemy':str(path.relative_to(ROOT)),'alchemy_sha256':digest(path),'splits':{}}
        for split,xyz in samples.items():
            via_vlog=target.apply(xyz_to_encoded(xyz,'vlog'))
            r={}
            for kind in ('flog2c','flog2','flog'):
                if (kind,name) not in official:
                    continue
                direct=official[kind,name][0].apply(fg_input(xyz,kind))
                r[kind]={space:stats(de(rgb_out(direct,space),rgb_out(via_vlog,space)))
                         for space in ('gamma24','srgb','rec709')}
                r[kind]['input_outside_cube_share']=float(np.any((fg_input(xyz,kind)<0)|(fg_input(xyz,kind)>1),axis=1).mean())
            r['vlog_input_outside_cube_share']=float(np.any((xyz_to_encoded(xyz,'vlog')<0)|(xyz_to_encoded(xyz,'vlog')>1),axis=1).mean())
            row['splits'][split]=r
        row['official']={kind:official[kind,name][1] for kind in ('flog2c','flog2','flog') if (kind,name) in official}
        rows.append(row)
        print('Fuji',name,'photos matched-C',row['splits']['photos_all']['flog2c']['gamma24'],flush=True)
        dump('fuji_accuracy.json',rows)
    return rows

def per_photo_fuji(scene_rows):
    official=official_cubes()
    names=['PROVIA','Velvia','ASTIA','CLASSIC-CHROME','REALA-ACE','PRO-Neg.Std',
           'CLASSIC-Neg.','ETERNA','ETERNA-BB','ACROS']
    cubes={}
    for name in names:
        token={'PRO-Neg.Std':'PRO-Neg_Std','CLASSIC-Neg.':'CLASSIC-Neg'}.get(name,name)
        cubes[name]=Cube.read(DATA/'Luts/Fujifilm'/('FLog2C_to_'+token+'_VLog.cube'))
    rows=[]
    for arrays,meta in scene_rows:
        xyz=arrays['xyz'][arrays['valid']]
        row={'path':meta['path'],'sha256':meta['sha256'],'unit':meta['unit'],
             'n':len(xyz),'common_output_interpretation':'gamma24','styles':{}}
        for name in names:
            via_vlog=cubes[name].apply(xyz_to_encoded(xyz,'vlog'))
            row['styles'][name]={}
            for kind in ('flog2c','flog2','flog'):
                if (kind,name) not in official: continue
                direct=official[kind,name][0].apply(fg_input(xyz,kind))
                row['styles'][name][kind]=stats(de(rgb_out(direct),rgb_out(via_vlog)))
        rows.append(row)
    dump('fuji_per_photo.json',rows)
    print('Fuji per-photo cases',len(rows)*len(names),flush=True)

def imports():
    home=SCRATCH/'lut-library'
    lib=LutLibrary(home)
    rows=[]
    paths=sorted((DATA/'Luts').rglob('*.cube'))
    paths=[p for p in paths if 'Panasonic-Standard' not in p.parts]
    paths += [x['path'] for x in creator_jobs()]
    for path in paths:
        check_time()
        raw=path.read_bytes()
        item=lib.add(raw,path.name)
        cube=lib.load(item['cube_id'])
        actual=(home/'luts'/item['file']).read_bytes()
        row={'path':str(path.relative_to(ROOT)),'sha256':digest(path),'bytes':len(raw),
             'raw_bytes_preserved':actual==raw,
             'input_space':item['input_space'],'input_space_state':item['input_space_state'],
             'input_space_guess':item['input_space_guess'],'evidence':item['space_evidence'],
             'output_space':item['output_space'],'size_3d':item['size_3d']}
        if path.is_relative_to(DATA):
            output='srgb' if '_sRGB' in path.name else 'rec709' if path.parent.name=='Hasselblad' else 'gamma24'
            changes={'input_space':'vlog','input_gamut':'vgamut','output_space':output}
        else:
            changes={'input_space':'srgb','output_space':'srgb'}
        fixed=lib.patch(item['cube_id'],changes)
        tgt,_=lib.target(item['cube_id'])
        dummy=np.array([[.1,.2,.3],[.18,.18,.18],[1,1,1]])
        rendered=tgt.render(dummy*255,dummy@matrix('rec709').T)
        row['manual_selection']=changes
        row['manual_roundtrip']=all(lib.get(item['cube_id'])[k]==v for k,v in changes.items())
        row['finite_render']=bool(np.isfinite(rendered).all())
        rows.append(row)
    dump('studio_imports.json',rows)
    print('Isolated imports',len(rows),flush=True)
    return rows

def creator_inputs(scene_rows):
    model,dat,provenance=camera_model()
    out=[]
    for job in creator_jobs():
        cube=Cube.read(job['path'])
        ramp=np.repeat(np.array([0,.02,.05,.1,.18,.25,.5,.75,1.])[:,None],3,axis=1)
        gray=cube.apply(ramp)
        record={'name':job['name'],'path':str(job['path'].relative_to(ROOT)),
                'sha256':digest(job['path']),'gray_input':ramp[:,0].tolist(),
                'gray_output':gray.tolist(),'photos':[],
                'input_conclusion':job['space_status'],
                'ground_truth':'没有创作者配对原图与目标图，输入空间只能按标记和行为推断'}
        for arrays,meta in scene_rows:
            unit=0 if meta['unit']=='a12-50' else 2
            model, _, _ = camera_model(unit)
            valid=arrays['valid']
            codes=arrays['codes'][valid]
            xyz=arrays['xyz'][valid]
            stock=model.predict(dat.entry_of(unit,4),codes)
            std,si=Target(cube,'srgb','srgb').render(stock,xyz,info=True)
            log,li=Target(cube,'vlog','srgb').render(stock,xyz,info=True)
            def behavior(rgb):
                light=rgb@np.array([.2126,.7152,.0722])/255
                return {'luma_percentiles':np.percentile(light,[1,5,50,95,99]).tolist(),
                        'luma_range_p95_p5':float(np.percentile(light,95)-np.percentile(light,5)),
                        'near_black_share':float((rgb.max(axis=1)<3).mean()),
                        'near_white_share':float((rgb.min(axis=1)>252).mean())}
            record['photos'].append({'path':meta['path'],'unit':meta['unit'],
                'standard_input':behavior(std),'vlog_input':behavior(log),
                'hypotheses_de00':stats(de(std/255,log/255))})
        out.append(record)
    dump('creator_input_checks.json',{'model':provenance,'luts':out})

def hasselblad(scene_rows):
    manifest=json.loads((DATA/'Tools/hasselblad_x2d100c_standard_cc.json').read_text())
    assets=[]
    for name,rec in manifest['assets'].items():
        path=DATA/'Tools'/rec['path']
        actual=digest(path)
        if actual!=rec['sha256']:
            raise ValueError('Hasselblad asset checksum differs')
        dtype='<u2' if 'u16' in path.stem else '<f4'
        a=np.fromfile(path,dtype=dtype)
        assets.append({'name':name,'sha256':actual,'bytes':path.stat().st_size,
                       'elements':a.size,'finite':bool(np.isfinite(a).all()),
                       'min':float(a.min()),'max':float(a.max())})
    xyz=np.vstack([a['xyz'][a['valid']] for a,_ in scene_rows])
    vg=xyz_to_encoded(xyz,'vlog')
    rows=[]
    for style in ('Standard','Nature'):
        root=DATA/'Luts/Hasselblad'
        cubes={k:Cube.read(root/('Hasselblad_'+style+'_Phocus_X2D_VLog_'+suffix+'.cube'))
               for k,suffix in (('srgb33','sRGB'),('srgb65','sRGB_65'),('rec33','Rec709'),('rec65','Rec709_65'))}
        outputs={k:c.apply(vg) for k,c in cubes.items()}
        rows.append({'style':style,
            '33_vs_65_srgb_de00':stats(de(outputs['srgb33'],outputs['srgb65'])),
            'rec709_vs_srgb_65_de00_after_transfer':stats(de(rgb_out(outputs['rec65'],'rec709'),outputs['srgb65'])),
            'wrong_rec709_as_srgb_de00':stats(de(outputs['rec65'],outputs['srgb65']))})
    dump('hasselblad_checks.json',{'assets':assets,'variants':rows,
        'reference_status':'未运行真实 Phocus，也没有 X2D 原始文件与 Phocus 导出配对；真实 HNCS 接近度未定',
        'scope':'对已发布表的数值与自洽性核对；不等于对真实 Phocus 的验证'})

def self_checks():
    a=np.array([[50,2.6772,-79.7751],[50,0,-82.7485]])
    value=float(__import__('gxr_studio.engine.colour',fromlist=['delta_e00']).delta_e00(a[:1],a[1:])[0])
    if abs(value-2.0425)>0.00005:
        raise ValueError('CIEDE2000 reference pair differs')
    rng=np.random.default_rng(48)
    v=rng.uniform(.0001,2,(64,3))
    err=float(np.max(abs(decode(encode(v,'vlog'),'vlog')-v)))
    if err>1e-12:
        raise ValueError('V-Log round trip differs')
    text='LUT_3D_SIZE 2\n'+'\n'.join(f'{r} {g} {b}' for b in (0,1) for g in (0,1) for r in (0,1))
    identity=Cube.parse(text)
    probe=rng.uniform(0,1,(100,3))
    cube_error=float(np.max(abs(identity.apply(probe)-probe)))
    if cube_error>1e-12:
        raise ValueError('Cube ordering differs')
    dump('metric_checks.json',{'CIEDE2000_expected':2.0425,'CIEDE2000_measured':value,
                               'vlog_roundtrip_max':err,'cube_identity_max':cube_error})

def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--sections',default='fuji,perphoto,imports,creator,hasselblad')
    parts=parser.parse_args().sections.split(',')
    self_checks()
    ss=scenes()
    dump('selected_dngs.json',[m for _,m in ss])
    dump('input_hashes.json',input_receipts(ss))
    samples=synthetic()
    samples['photos_all']=np.vstack([a['xyz'][a['valid']] for a,_ in ss])
    for unit in ('a12-50','mount-a12'):
        samples[unit]=np.vstack([a['xyz'][a['valid']] for a,m in ss if m['unit']==unit])
    if 'fuji' in parts: compare_fuji(samples)
    if 'perphoto' in parts: per_photo_fuji(ss)
    if 'imports' in parts: imports()
    if 'creator' in parts: creator_inputs(ss)
    if 'hasselblad' in parts: hasselblad(ss)
    print('Measurements complete',flush=True)

if __name__=='__main__':
    main()
