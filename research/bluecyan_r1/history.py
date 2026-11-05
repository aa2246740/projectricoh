#!/usr/bin/env python3
"""Read private paired photos; keep identities, regions and pixels in local/."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,np,dump,read,sha
import ast
import io
import struct
import collections
import argparse
import hashlib
import os
import time

LIBRARY=Path('/Users/wu/Pictures/GXR Studio/2026')
ARCHIVE=ROOT/'artifacts/card-b-archive-20261104/root'


def metadata_reader():
    source=ROOT/'research/recipe_redo_r1/inventory.py'
    tree=ast.parse(source.read_text())
    selected=[]
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('TYPES','DISPLAY','SELECTORS') for t in n.targets):selected.append(n)
        if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('Tiff','jpeg_tiff','scalar','metadata'):selected.append(n)
    ns=dict(np=np,struct=struct,io=io,Path=Path)
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),ns)
    return ns['metadata']


def inventory():
    metadata=metadata_reader();rows=[]
    for day in ('2026-10-31','2026-11-01','2026-11-02'):
        folder=LIBRARY/day
        for p in sorted(folder.glob('*')):
            if p.suffix.lower()!='.dng' or p.is_symlink() or p.name.startswith('.'):continue
            jp=next((q for q in (p.with_suffix('.JPG'),p.with_suffix('.jpg')) if q.is_file()),None)
            if jp is None:continue
            try:dm,jm=metadata(p),metadata(jp)
            except Exception as e:
                rows.append(dict(path=str(p),jpeg=str(jp),day=day,error=str(e)))
                continue
            pair=all(dm.get(k)==jm.get(k) and dm.get(k) is not None for k in ('when','iso','exposure'))
            row=dict(path=str(p),jpeg=str(jp),day=day,metadata=dm,jpeg_metadata=jm,
                pair_metadata_agrees=pair,raw_stat=[p.stat().st_size,p.stat().st_mtime_ns],
                jpeg_stat=[jp.stat().st_size,jp.stat().st_mtime_ns])
            rows.append(row)
    dump('history/inventory.json',rows)
    failures=[r for r in rows if 'error' in r];rows=[r for r in rows if 'error' not in r]
    dump('history/inventory_errors.json',failures)
    dump('history/inventory.json',rows)
    summary={day:dict(n=sum(r['day']==day for r in rows),
        units=dict(collections.Counter(r['metadata']['unit'] for r in rows if r['day']==day)),
        selectors=dict(collections.Counter(r['metadata'].get('selector') for r in rows if r['day']==day)),
        isos=dict(collections.Counter(r['metadata']['iso'] for r in rows if r['day']==day)),
        color_controls=dict(collections.Counter(str(r['metadata'].get('color_raw13')) for r in rows if r['day']==day)),
        pair_conflicts=sum(not r['pair_metadata_agrees'] for r in rows if r['day']==day))
        for day in ('2026-10-31','2026-11-01','2026-11-02')}
    dump('history/inventory_summary.json',summary)
    print(summary,flush=True)


def bank():
    # Parser is frozen, read-only, and understands older v1/v2 catalogs.
    snap=ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'
    sys.path.insert(0,str(snap))
    from gxr_studio.camdata.datcodec import parse,PROFILES
    from gxr_studio.camdata import knob_table
    from gxr_studio.engine import menu,knobs
    groups={};rejected=[]
    def add(entry,unit,label,name,dat):
        digest=hashlib.sha256(entry).hexdigest();key=f'{unit}-{digest}'
        out=LOCAL/'history/records'/(key+'.record552')
        out.parent.mkdir(parents=True,exist_ok=True)
        if not out.exists():out.write_bytes(entry)
        item=groups.setdefault(key,dict(unit=unit,slot=entry[0],labels=[],sha256=digest,
            record=str(out.relative_to(LOCAL)),catalogs=[]))
        if label not in item['labels']:item['labels'].append(label)
        c=dict(name=name,sha256=sha(ARCHIVE/name),generation=dat.generation,label=label)
        if c not in item['catalogs']:item['catalogs'].append(c)
    for name in ('G137.DAT','G150T.DAT','G152T.DAT','G153T.DAT','G154T.DAT','G154L.DAT'):
        p=ARCHIVE/name;raw=p.read_bytes()
        try:dat=parse(raw)
        except Exception as e:rejected.append(dict(name=name,error=str(e)));continue
        for unit in range(3):
            for slot in range(1,9):
                entry=dat.entry_of(unit,slot)
                add(entry,unit,f'{slot:02d}',name,dat)
            table=menu.load()
            if dat.kv2_block is not None:
                table=knob_table.read(dat.kv2_block,table,mount_knobs_from_50mm=PROFILES[dat.generation].mount_knobs_from_50mm)
            for uname,user in zip(dat.user_names,dat.users):
                slot=user['base'];levels=user['levels'][:4]
                rec=next(r for r in table['recipes'] if r['unit']==unit and r['slot']==slot)
                its=table['items'][rec['first_item']:rec['first_item']+rec['item_count']]
                values=[it['default_level'] for it in its]
                controls={table['controls'][it['control']]['name']:i for i,it in enumerate(its)}
                for k,v in zip(('contrast','highlight','shadow','saturation'),levels):
                    if k in controls:values[controls[k]]=v
                req=menu.request(table,unit,slot,values)
                result,_=knobs.apply(dat.entry_of(unit,4),dat.entry_of(unit,slot),req)
                add(bytes(result),unit,'user:'+uname,name,dat)
            for look in dat.looks:
                if look.unit_mask&(1<<unit):add(look.entry,unit,'look:'+look.name,name,dat)
        print(name,dat.generation,'users',len(dat.users),flush=True)
    dump('history/bank.json',dict(records=list(groups.values()),rejected_catalogs=rejected,
        equality='full 552-byte expanded record, before any inference'))
    print('unique builtin records',len(groups),'catalogs rejected',len(rejected),flush=True)


def sample():
    sys.path.insert(0,str(ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'))
    from gxr_studio.raw.dng import Dng
    from PIL import Image
    rows=read(LOCAL/'history/inventory.json');out=[]
    for i,row in enumerate(rows):
        stem=Path(row['path']).stem;target=LOCAL/'history/samples'/(stem+'-shiftm1.npz')
        if target.exists():
            out.append(read(target.with_suffix('.json')));continue
        try:
            d=Dng(row['path'])
            with Image.open(row['jpeg']) as im:rgb=np.asarray(im.convert('RGB'))
            cy,cx,h,w=d.crop_window()
            if rgb.shape[:2]!=(h,w):raise ValueError('DNG/JPEG default crop dimensions disagree')
            xx,yy=np.meshgrid(np.linspace(18,w-20,48).astype(int)//2*2,
                             np.linspace(18,h-20,36).astype(int)//2*2)
            centers=np.c_[xx.ravel(),yy.ravel()]
            by,bx=np.meshgrid(np.arange(-6,6),np.arange(-6,6),indexing='ij')
            xs=centers[:,0,None]+bx.ravel();ys=centers[:,1,None]+by.ravel()
            block=rgb[ys,xs].astype(float);obs=block.mean(1);sd=block.std(1)
            raw=d.normalised_at(cy+ys,cx+xs-1);cfa=d.cfa_at(cy+ys,cx+xs-1)
            codes=np.column_stack([np.sum(np.where(cfa==c,raw,0),1)/np.sum(cfa==c,1) for c in range(3)])
            rawsd=np.column_stack([np.sqrt(np.sum(np.where(cfa==c,(raw-codes[:,c,None])**2,0),1)/np.sum(cfa==c,1)) for c in range(3)])
            valid=(sd.max(1)<=12)&(obs.min(1)>3)&(obs.max(1)<252)&(raw.max(1)<.985)&(rawsd.max(1)<.04)
            wb_codes=codes/d.as_shot_neutral*4095
            cells=np.c_[centers[:,0]//max(1,w//4),centers[:,1]//max(1,h//4)]
            if not valid.any():raise ValueError('No smooth unsaturated blocks')
            target.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(target,raw_codes=wb_codes[valid],observed=obs[valid],
                centers=centers[valid],cells=cells[valid],sd=sd[valid],rawsd=rawsd[valid])
            info=dict(row,raw_sha256=d.sha256,jpeg_sha256=sha(row['jpeg']),
                samples_file=str(target.relative_to(LOCAL)),grid_points=len(valid),valid_points=int(valid.sum()),
                original_stat_unchanged=(list(row['raw_stat'])==[Path(row['path']).stat().st_size,Path(row['path']).stat().st_mtime_ns]
                and list(row['jpeg_stat'])==[Path(row['jpeg']).stat().st_size,Path(row['jpeg']).stat().st_mtime_ns]),
                original_read_only=True,raw_jpeg_shift_xy=[-1,0],
                registration_source='existing independently checked GXR carrier offset, fixed before analysis')
            assert info['original_stat_unchanged']
            dump(target.with_suffix('.json').relative_to(LOCAL),info);out.append(info)
            d.release()
        except Exception as e:out.append(dict(row,error=repr(e)))
        if (i+1)%20==0:
            dump('history/sample_index.json',out)
            print('sampled',i+1,'/',len(rows),'valid',sum('error' not in r for r in out),flush=True)
    dump('history/sample_index.json',out)
    print('sampling complete',len(out),'errors',sum('error' in r for r in out),flush=True)


class Models:
    def __init__(self):
        sys.path.insert(0,str(ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'))
        from gxr_studio.engine.model import Model
        from gxr_studio.engine import colour as fs,matrix_model as mm
        self.Model=Model;self.fs=fs;self.mm=mm;self.cache={}
        self.bank=read(LOCAL/'history/bank.json')['records']
        self.official=read(ROOT/'research/module_adapt/local/official_parameters.json')['units']
        self.input_maps={}
        for unit in ('a12-50','a12-28','mount-a12'):
            self.input_maps[unit]=np.array(read(ROOT/f'research/recipe_redo_r1/local/inputs/{unit}/definition.json')['calibration_coefficients'])
    def input(self,raw,unit,calibrated=True):
        if not calibrated:return raw
        u=raw/4095;C=self.input_maps[unit]
        if C.size==0:return raw
        H=np.c_[np.ones(len(u)),u]
        if len(C)==10:
            r,g,b=u.T;H=np.c_[H,r*r,g*g,b*b,r*g,r*b,g*b]
        return raw+4095*(H@C)
    def model(self,unit,iso,raw13):
        ui=('a12-50','a12-28','mount-a12').index(unit)
        key=(ui,200 if iso<566 else 1600,tuple(raw13))
        if key not in self.cache:
            display={v:i for i,v in enumerate((0,7,6,1,2,3,4,5,8,9))}
            levels=[display[v] for v in raw13]
            official=self.official[('50mm','28mm','mount')[ui]]
            d0=np.zeros(24);d1=np.zeros(24)
            for j,color in enumerate(('orange','green','blue','red','magenta')):
                ix=np.array([bool(int(official['mask'][j])&(1<<s)) for s in range(24)])
                d0[ix]=np.array(official['d0_levels'])[levels[8+j]-1,ix]
                d1[ix]=np.array(official['d1_levels'])[levels[8+j]-1,ix]
                sat=np.broadcast_to(np.array(official['sat_levels'])[levels[3+j]-1],(24,))
                if not np.all(sat[ix]==100):raise ValueError('Nondefault five-colour saturation')
            if official['vividness_levels'][levels[2]-1]!=100:raise ValueError('Nondefault vividness')
            b=(LOCAL/next(r['record'] for r in self.bank if r['unit']==ui and '04' in r['labels'])).read_bytes()
            stock=np.array([self.fs.decode_word(b[o:o+4]) for o in range(115,211,4)])
            ring=read(ROOT/'research/hue_ring/local'/('ring_model_v2.json' if key[1]==200 else 'ring_model_v2_iso1600.json'))
            self.cache[key]=self.Model(stock,d0,d1,ring)
        return self.cache[key]


def identify():
    models=Models();rows=read(LOCAL/'history/sample_index.json');out=[]
    for i,row in enumerate(rows):
        if 'error' in row:out.append(row);continue
        try:
            meta=row['metadata'];unit=meta['unit'];ui=('a12-50','a12-28','mount-a12').index(unit)
            model=models.model(unit,meta['iso'],meta['color_raw13'])
            with np.load(LOCAL/row['samples_file'],allow_pickle=False) as z:val=dict(z)
            x=models.input(val['raw_codes'],unit);obs=val['observed'];cells=val['cells']
            fit=(cells.sum(1)%2==0);held=~fit
            if fit.sum()<32 or held.sum()<32:raise ValueError('Insufficient independent spatial halves')
            catalogs={'G137.DAT'} if row['day']=='2026-10-31' else {'G150T.DAT'} if row['day']=='2026-11-01' else {'G150T.DAT','G152T.DAT','G153T.DAT','G154T.DAT'}
            bank=[]
            for original in models.bank:
                allowed=[c for c in original['catalogs'] if c['name'] in catalogs]
                if original['unit']!=ui or not allowed:continue
                bank.append(dict(original,catalogs=allowed,labels=sorted(set(c['label'] for c in allowed))))
            errors={};predictions={}
            for rec in bank:
                b=(LOCAL/rec['record']).read_bytes()
                pred=model.predict(b,x,bw_chroma='discard' if b[0]==3 else 'conditional')
                err=a.de(pred,obs);errors[rec['sha256']]=err;predictions[rec['sha256']]=pred
            rank=sorted(bank,key=lambda r:float(np.median(errors[r['sha256']][fit])))
            best=rank[0];bkey=best['sha256'];second=rank[1]
            med=float(np.median(errors[bkey][fit]));gap=float(np.median(errors[second['sha256']][fit]))-med
            # Spatial block bootstrap on identity half only.
            blocks=[np.flatnonzero(fit & np.all(cells==cell,axis=1)) for cell in np.unique(cells[fit],axis=0)]
            rng=np.random.default_rng(411);wins=0
            for _ in range(120):
                ix=np.concatenate([blocks[j] for j in rng.integers(0,len(blocks),len(blocks))])
                wins+=all(np.median(errors[bkey][ix])<np.median(errors[r['sha256']][ix]) for r in rank[1:])
            stable=wins/120
            accepted=med<=5 and gap>=.75 and stable>=.95 and fit.sum()>=48 and held.sum()>=48
            out.append(dict(row,identity=dict(accepted=bool(accepted),record=best,
                identity_median_de00=med,gap_de00=gap,spatial_bootstrap_win=stable,
                candidates=[dict(labels=r['labels'],sha256=r['sha256'],median=float(np.median(errors[r['sha256']][fit]))) for r in rank],
                used_pixels='checkerboard parity zero in 4x4 spatial blocks',
                iso200_primary=meta['iso']==200,iso_boundary_open=meta['iso']!=200),
                holdout_old=a.stats(errors[bkey][held])))
        except Exception as e:out.append(dict(row,identity_error=repr(e)))
        if (i+1)%20==0:
            dump('history/identities.json',out)
            print('classified',i+1,'/',len(rows),'accepted',sum(r.get('identity',{}).get('accepted',False) for r in out),flush=True)
    dump('history/identities.json',out)
    for day in ('2026-10-31','2026-11-01','2026-11-02'):
        subset=[r for r in out if r['day']==day and r.get('identity',{}).get('accepted')]
        print(day,collections.Counter(tuple(r['identity']['record']['labels']) for r in subset),flush=True)


def guard():
    def audit(event,args):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system'):
            raise PermissionError('No network, devices, or subprocesses in private photo research')
        mutations=[]
        if event=='open' and isinstance(args[0],(str,bytes,Path)):
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            if str(p).startswith('/dev/') and str(p) not in ('/dev/null','/dev/urandom','/dev/random'):
                raise PermissionError('No device access')
            if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):mutations=[p]
        elif event in ('os.mkdir','os.remove','os.rmdir','os.chmod','os.utime','os.truncate'):mutations=[args[0]]
        elif event in ('os.rename','os.link','os.symlink'):mutations=args[:2]
        for p in mutations:
            if isinstance(p,(str,bytes,Path)) and not Path(os.fsdecode(p)).resolve().is_relative_to(LOCAL):
                raise PermissionError('Write outside bluecyan local/: '+str(p))
    sys.addaudithook(audit)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('inventory','bank','sample','identify'))
    args=ap.parse_args();guard();globals()[args.phase]()
