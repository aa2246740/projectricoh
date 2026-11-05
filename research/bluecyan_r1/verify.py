#!/usr/bin/env python3
"""Independent spelling of the pixel chain plus input and record readback."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT,LOCAL,NOON,np,read,dump,sha,stats,de
import history as h
import refit
import struct
import hashlib
import os
import subprocess


def predict_literal(model,b,x):
    xs=np.r_[0,struct.unpack_from('>31H',b,20),4095]
    q=(b[379:412],b[82:115],b[412:445]) if b[1]&4 else (b[82:115],)*3
    pre=np.column_stack([np.interp(np.clip(x[:,c],0,4095),xs,list(q[c])) for c in range(3)])
    w=np.array(struct.unpack_from('>14H',b,216))
    C=(w[:9]&2047)*np.where(w[:9]&2048,-1,1)
    ycc=pre@(C.reshape(3,3)/1024).T+w[9:12]
    y=ycc[:,0];ci=ycc[:,1]-128+1j*(ycc[:,2]-128)
    if b[0]==3:co=np.zeros_like(ci)
    else:
        words=np.frombuffer(b[115:211],np.uint8).reshape(24,4).astype(int)
        words=(words&127)*np.where(words&128,-1,1)
        assert np.array_equal(words[:,0],words[:,3]) and np.array_equal(words[:,1],-words[:,2])
        ctx=model.engine.ctx;S=ctx.S_eff
        Z=((words[:,0]+ctx.d0)-1j*(words[:,1]+ctx.d1))/32/S
        effective=np.abs(Z)*np.exp(1j*model.engine.table.k*np.angle(Z))
        table=model.engine.table;W=table.kernel_weights(np.angle(ci,deg=True)%360,abs(ci))
        multiplier=W@S+(W*table.gain)@(S*(effective-1))
        co=ci*multiplier
    return np.clip(np.column_stack([y+1.402*co.imag,y-.344136*co.real-.714136*co.imag,y+1.772*co.real]),0,255)


def main():
    # Import the archived model through the known read-only adapter.
    noon,ref,_=a.load();hw=read(LOCAL/'physical/hardware.json')
    from gxr_studio.engine.pretable import PreTable
    assert Path(sys.modules['gxr_studio.engine.model'].__file__).is_relative_to(
        ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src')
    official=read(ROOT/'research/module_adapt/local/official_parameters.json')['units']
    geometry=[];base_codes=None
    for unit,key in (('a12-50','50mm'),('a12-28','28mm'),('mount-a12','mount')):
        path=ROOT/'artifacts/firmware/gxr-1.51'/hw[unit]['firmware'];b=path.read_bytes()
        at=official[key]['rows']['colour1']['file_offset']-26*48
        assert at==hw[unit]['file_offset']
        block=b[at:at+48];codes=np.frombuffer(block,np.uint8)[::2].astype(int)
        assert np.array_equal(codes,hw[unit]['codes']) and sha(path)==hw[unit]['firmware_sha256']
        if base_codes is None:base_codes=codes
        for iso in (200,1600):
            original=read(ROOT/'research/hue_ring/local'/('ring_model_v2.json' if iso==200 else 'ring_model_v2_iso1600.json'))
            expected=np.array(original['nodes_unwrapped_deg'])+(codes-base_codes)*360/256
            fixed=read(LOCAL/f'physical/ring-{unit}-{iso}.json')
            assert np.max(abs(expected-fixed['nodes_unwrapped_deg']))<1e-12
        geometry.append(dict(unit=unit,bank_independently_located_from_C080_minus_26_rows=True,first_row_sha256=hashlib.sha256(block).hexdigest()))
    ref.model.engine.table=PreTable(read(LOCAL/'physical/ring-mount-a12-200.json'),ref.model.engine.ctx.S_eff)
    points=read(LOCAL/'physical/noon-patches.json');checks=[]
    for setting in ref.entries:
        rr=[r for r in points if r['setting']==setting];x=np.array([r['physical_input'] for r in rr])
        pred=predict_literal(ref.model,ref.entries[setting],x)
        saved=np.array([r['physical_predicted_rgb'] for r in rr]);obs=np.array([r['observed_rgb'] for r in rr])
        error=float(np.max(abs(pred-saved)));difference=float(np.max(abs(de(pred,obs)-np.array([r['physical_error'] for r in rr]))))
        assert error<1e-8 and difference<1e-8
        checks.append(dict(setting=setting,observations=len(rr),max_rgb=error,max_DE00=difference,
            conditioned_input_out_of_axis=int(((x<0)|(x>4095)).any(1).sum())))
    from gxr_studio.camdata.datcodec import CRC_FIELDS,OFFSETS,ROW_BYTES,_valid_look_row
    hm=h.Models();candidates=[]
    for item in read(LOCAL/'acceptance.json')['records']:
        unit=item['unit'];slot=item['slot'];record=LOCAL/item['record_file'];b=record.read_bytes()
        doc=read(record.with_suffix('.json'))
        assert len(b)==552 and sha(record)==item['record_sha256']==doc['record_sha256']
        assert all(struct.unpack_from('>I',b,co)[0]==__import__('zlib').crc32(b[o:o+n])&0xffffffff for o,n,co in CRC_FIELDS)
        assert all(_valid_look_row(b[o:o+n],j,b[1]) for j,(o,n) in enumerate(zip(OFFSETS,ROW_BYTES)))
        model=hm.model(unit,200,read(LOCAL/'history/inventory.json')[0]['metadata']['color_raw13'])
        model.engine.table=PreTable(read(LOCAL/f'physical/ring-{unit}-200.json'),model.engine.ctx.S_eff)
        v=refit.groups(unit,slot+26,True)['train']
        pred=predict_literal(model,b,v['x'])
        e=model.fs.delta_e00(model.fs.lab_from_codes(np.rint(pred)),model.fs.lab_from_codes(v['want']))
        objective=float(np.average(e*e,weights=v['sw']))
        assert abs(objective-doc['train_objective'])<1e-8
        assert doc['model_sha256']==sha(LOCAL/f'physical/ring-{unit}-200.json')
        if unit=='mount-a12':assert doc['input_map_sha256']==sha(LOCAL/'physical/input-map-mount-a12.json')
        candidates.append(dict(unit=unit,slot=slot,record_sha256=sha(record),row_crcs=9,
            literal_objective=objective,saved_objective=doc['train_objective'],fast_reference_equivalence=doc['equivalence'],
            reference_record_replay=doc['integer_record_reference_replay_max_rgb']))
    protected=read(LOCAL/'inputs.json')['inputs']
    assert all(sha(ROOT/p)==digest for p,digest in protected.items())
    # Check every original photo again. Do not trust an extraction cache receipt.
    private_rows=read(LOCAL/'history/sample_index.json');private_verified=[]
    for i,r in enumerate(private_rows):
        for key,digest_key in (('path','raw_sha256'),('jpeg','jpeg_sha256')):
            path=Path(r[key]);actual=sha(path);assert actual==r[digest_key],path
            private_verified.append(dict(path=str(path),sha256=actual))
        if (i+1)%60==0:print('private originals verified',i+1,'/',len(private_rows),flush=True)
    dump('private-original-hashes.json',private_verified)
    noon_count=0
    for line in (ROOT/'captures/noon-20261104/SHA256SUMS').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        digest,name=line.split(None,1);path=ROOT/'captures/noon-20261104'/name.lstrip('*')
        assert sha(path)==digest;noon_count+=1
    assert noon_count==168
    private_files=[p for p in LOCAL.rglob('*') if p.is_file()]
    relative=[str(p.relative_to(ROOT)) for p in private_files]
    ignored=subprocess.run(['git','check-ignore','--stdin'],input='\n'.join(relative)+'\n',text=True,cwd=ROOT,capture_output=True,check=True)
    assert set(ignored.stdout.splitlines())==set(relative)
    tracked=subprocess.check_output(['git','ls-files','research/bluecyan_r1/local'],cwd=ROOT,text=True)
    assert not tracked.strip()
    sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(a.HERE.glob('*.py'))}
    sources[str((a.HERE/'detect_faces.swift').relative_to(ROOT))]=sha(a.HERE/'detect_faces.swift')
    dump('verification.json',dict(status='PASS',geometry=geometry,literal_noon_chain=checks,
        candidate_readback=candidates,private_original_files_verified=len(private_verified),noon_original_files_verified=noon_count,
        protected_source_files_verified=len(protected),private_artifact_files_ignored=len(relative),
        no_private_artifacts_tracked=True,source_sha256=sources,
        nice=os.getpriority(os.PRIO_PROCESS,0),isolated=bool(sys.flags.isolated),
        physical_boundary='Existing captures and original firmware only; no live camera, card, register read, candidate exposure, or DAT build'))
    print('VERIFY PASS',len(geometry),'module banks,',len(candidates),'records,',len(private_verified)+noon_count,'original photo files',flush=True)


if __name__=='__main__':main()
