"""Full host acceptance: parity, immutable defaults, envelopes, combinations, T1."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import support as s
s.dependencies()
import collections
import csv
import hashlib
import json
import random
import struct
import subprocess
import time
import numpy as np
import knobs as k
from bridge import C,compare,CRequest,CStats
import ctypes as ct
from checks import inspect,changed,rpc,level_request
from model_adapter import Model,synthetic


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        if not rows:return
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def equivalence(model,modules):
    grid=np.linspace(0,4095,17);cube=np.array(np.meshgrid(grid,grid,grid,indexing='ij')).reshape(3,-1).T
    x=np.vstack((np.repeat(np.arange(4096)[:,None],3,axis=1),cube))
    rows=[]
    for m in modules:
        for slot,base in m['entries'].items():
            a=bytearray(base);a[379:445]=a[82:115]*2;a[1]|=6;struct.pack_into('>H',a,445,0);k.checksum(a)
            b=bytearray(a);b[1]&=~6;struct.pack_into('>H',b,445,2);k.checksum(b)
            for half in (0,1):
                ra=model.predict(a,x,half=half);rb=model.predict(b,x,half=half)
                pre_error=float(np.max(np.abs(model.pre(a,x)-model.pre(b,x))));assert pre_error==0
                err=float(np.max(np.abs(ra-rb)));assert err<1e-10
                code_diffs=int(np.count_nonzero(np.floor(ra+.5).astype(np.uint8)!=np.floor(rb+.5).astype(np.uint8)))
                assert code_diffs==0
                rows.append(dict(unit=m['name'],slot=slot,half=half,samples=len(x),max_pre_error=pre_error,
                                 max_RGB_error=err,display_code_differences=code_diffs))
            # Compare the adapter to the existing Engine shared-curve path.
            rr=[bytes(b[at:at+n]) for at,n in zip(s.OFFSETS,s.LENGTHS)]
            colour=b''.join(model.fs.encode_word(k.dec(z[0],128),k.dec(z[1],128)) for z in
                            (rr[2][i:i+4] for i in range(0,96,4)))
            packed=(rr[0],rr[1],colour,rr[3],rr[4],rr[5],rr[6]+rr[7])
            key=f'{slot:02d}';old=model.engine.entries.get(key)
            model.engine.entries[key]=dict(mask=0,control=2,written=packed,rows=packed)
            try:er=model.engine.predict(key,x)
            finally:
                if old is None:del model.engine.entries[key]
                else:model.engine.entries[key]=old
            err=float(np.max(np.abs(model.predict(b,x)-er)))
            assert err<1e-10,('Engine adapter mismatch',m['name'],slot,err)
            rows[-1]['existing_Engine_max_RGB_error']=err
    return rows


def sanitized(modules):
    fixtures=bytearray()
    for m in modules:
        for slot in range(1,9):fixtures+=m['entries'][4]+m['entries'][slot]
    fixture=s.LOCAL/'test_inputs.bin';fixture.write_bytes(fixtures)
    binary=s.LOCAL/'test_sanitized'
    cmd=['/usr/bin/clang','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-pedantic',
         '-fno-modules','-fno-implicit-modules','-fsanitize=address,undefined','-fno-sanitize-recover=all',
         str(s.HERE/'src/knobs.c'),str(s.HERE/'src/test_sanitized.c'),'-o',str(binary)]
    build=subprocess.run(cmd,text=True,capture_output=True)
    (s.LOCAL/'sanitize_build.log').write_text(' '.join(cmd)+'\n'+build.stdout+build.stderr);build.check_returncode()
    run=subprocess.run([str(binary),str(fixture)],text=True,capture_output=True)
    (s.LOCAL/'sanitize.log').write_text(run.stdout+run.stderr);run.check_returncode()
    return run.stdout.strip()


def main():
    s.guard();s.verify_inputs();modules=s.parse();byunit={m['name']:m for m in modules};c=C();model=Model();start=time.monotonic()
    import test_goldens
    golden_checks=test_goldens.run(c)
    cal=json.loads((s.LOCAL/'calibration.json').read_text());groups=cal['groups']
    assert cal['code_inputs']=={name:s.sha(s.HERE/'src'/name) for name in cal['code_inputs']},'stale calibration source'
    alts=json.loads((s.LOCAL/'alternatives.json').read_text());binary=(s.LOCAL/'variants.bin').read_bytes()
    variants=json.loads((s.LOCAL/'variants.json').read_text());assert len(variants)==3870 and len(binary)==552*3870
    gi={(g['unit'],g['slot'],g['param']):g for g in groups}
    baselines=[];curve_rows=[];limit_rows=[];limit_events=[];deltas=[];errors=[];parity=0;default_checks=0
    for m in modules:
        stock=m['entries'][4]
        for slot,base in m['entries'].items():
            info=inspect(base,True);assert not info['errors'],info
            baselines.append(dict(unit=m['name'],slot=slot,**info))
            for wm in (0,1):
                for tm in (0,1):
                    assert compare(c,stock,base,k.Request(wb_method=wm,tone_method=tm))[0]==base
                    assert compare(c,stock,base,k.Request(amount=0,wb_method=wm,tone_method=tm))[0]==stock
                    default_checks+=2;parity+=2
    for v in variants:
        m=byunit[v['unit']];base=m['entries'][v['slot']];g=gi[v['unit'],v['slot'],v['param']]
        b=binary[v['offset']:v['offset']+552]
        assert hashlib.sha256(b).hexdigest()==v['sha256']
        assert compare(c,m['entries'][4],base,level_request(g,v['level']))[0]==b;parity+=1
        if (v['param']=='amount' and v['level']==100) or (v['param']!='amount' and v['level']==0):assert b==base
        info=inspect(b,True)
        tag={q:v[q] for q in ('unit','slot','param','level')};tag.update(wb_method=0,tone_method=0)
        if any(v['stats'].values()):limit_events.append(dict(**tag,**v['stats']))
        for e in info['errors']:errors.append(dict(**tag,error=e))
        for q in info['curves']:curve_rows.append(dict(**tag,**q))
        for q in info['limits']:limit_rows.append(dict(**tag,**q))
    for g in groups+alts:
        m=byunit[g['unit']];base=m['entries'][g['slot']];prev=None
        for level in sorted(int(x) for x in g['doses']):
            b,stats=compare(c,m['entries'][4],base,level_request(g,level));parity+=1
            if g in alts:
                info=inspect(b,True)
                tag=dict(unit=g['unit'],slot=g['slot'],param=g['param'],level=level,
                         wb_method=g.get('wb_method',0),tone_method=g.get('tone_method',0))
                if any(stats.values()):limit_events.append(dict(**tag,**stats))
                for error in info['errors']:errors.append(dict(**tag,error=error))
                for q in info['curves']:curve_rows.append(dict(**tag,**q))
                for q in info['limits']:limit_rows.append(dict(**tag,**q))
            if prev is not None:
                change=changed(prev[1],b);cost=rpc(prev[1],b,m['addresses']);basechange=changed(base,b)
                deltas.append(dict(unit=g['unit'],slot=g['slot'],param=g['param'],wb_method=g.get('wb_method',0),
                                   tone_method=g.get('tone_method',0),from_level=prev[0],to_level=level,
                                   rows=','.join(r['row'] for r in change['rows']),row_byte_details=json.dumps(change['rows'],separators=(',',':')),
                                   changed_row_bytes=change['changed_row_bytes'],changed_entry_bytes=change['changed_entry_bytes'],
                                   base_changed_rows=','.join(r['row'] for r in basechange['rows']),
                                   base_changed_row_bytes=basechange['changed_row_bytes'],base_changed_entry_bytes=basechange['changed_entry_bytes'],**cost))
            prev=(level,b)
    print('individual parity and hardware envelopes',parity,'errors',len(errors),flush=True)
    assert not errors,errors[:10]
    combos=[];combo_limits=[];combo_count=0;combo_errors=[];x=synthetic();combo_model_count=0

    def run_combo(m,slot,label,amount=100,levels=None,model_check=False,wm=0,tm=0):
        nonlocal parity,combo_count,combo_model_count
        levels=levels or {};doses=[0]*10
        for param,level in levels.items():doses[k.PARAMS.index(param)]=gi[m['name'],slot,param]['doses'][str(level)]
        rq=k.Request(amount,tuple(doses),wm,tm);b,stats=compare(c,m['entries'][4],m['entries'][slot],rq)
        parity+=1;combo_count+=1;info=inspect(b)
        tag=dict(case=label,unit=m['name'],slot=slot,amount=amount,levels=json.dumps(levels,sort_keys=True,separators=(',',':')),wb_method=wm,tone_method=tm)
        for error in info['errors']:combo_errors.append(dict(**tag,error=error))
        for lim in info['limits']:combo_limits.append(dict(**tag,**lim))
        item=dict(**tag,clamps=stats['clamps'],node_repairs=stats['node_repairs'],monotone_repairs=stats['monotone_repairs'],
                  slope_repairs=stats['slope_repairs'],
                  colour_cap=stats['colour_cap'],matrix_cap=stats['matrix_cap'],rowsum_cap=stats['rowsum_cap'],
                  limit_count=len(info['limits']),max_12bit_lsb_jump_bound=info['max_12bit_lsb_jump_bound'],max_node_jump=info['max_node_jump'])
        if model_check:
            rgb=model.predict(b,x,quantize=True);assert np.isfinite(rgb).all();combo_model_count+=1
            item['rgb_boundary_fraction']=float(np.any((rgb==0)|(rgb==255),axis=1).mean())
        combos.append(item)

    for m in modules:
        for slot in range(1,9):
            for a in (-9,9):
                for b in (-9,9):
                    run_combo(m,slot,'contrast_highlight',levels={'contrast':a,'highlight':b},model_check=True)
                    run_combo(m,slot,'fade_shadow',levels={'fade':a,'shadow':b},model_check=True)
                    if slot!=3:run_combo(m,slot,'saturation_split',levels={'saturation':a,'split':b},model_check=True)
            if slot!=3:
                for param in ('contrast','highlight','shadow','fade','saturation','warmth','tint','split'):
                    for amount in range(0,151,10):
                        for level in range(-9,10):
                            run_combo(m,slot,'amount_all_levels',amount,{param:level},
                                      model_check=amount in (0,10,50,100,150) and level in (-9,0,9))
        print('extreme combinations',m['name'],combo_count,flush=True)
    rng=random.Random(0x6b327231)
    for n in range(1600):
        m=modules[n%3];slot=1+rng.randrange(8)
        params=('contrast','highlight','shadow','fade','filter','tone') if slot==3 else ('contrast','highlight','shadow','fade','saturation','warmth','tint','split')
        levels={p:rng.randrange(-9,10) for p in params}
        run_combo(m,slot,'all_knobs_seeded',100 if slot==3 else rng.randrange(16)*10,levels,
                  model_check=n<96,wm=n%2,tm=(n//2)%2)
    assert not combo_errors,combo_errors[:10]
    print('combinations passed',combo_count,'modelled',combo_model_count,flush=True)
    eq=equivalence(model,modules);print('T1 exact model equivalence',len(eq),'cases',flush=True)
    san=sanitized(modules);print(san,flush=True)
    # C boundary validation must leave output unchanged on invalid requests.
    invalid=0
    for amount,dose,wm,tm in ((-10,0,0,0),(160,0,0,0),(1,0,0,0),(100,4097,0,0),(100,-4097,0,0),(100,0,2,0),(100,0,0,2)):
        rq=CRequest(amount,(ct.c_int32*10)(dose,*([0]*9)),wm,tm);out=(ct.c_uint8*552)(*([0xa5]*552));st=CStats()
        assert c.lib.kv_apply(modules[0]['entries'][4],modules[0]['entries'][1],ct.byref(rq),out,ct.byref(st))==-1
        assert bytes(out)==bytes([0xa5]*552);invalid+=1
    filter_rows=[]
    for m in modules:
        g=gi[m['name'],3,'filter']
        for level in range(-9,10):
            b,_=c.apply(m['entries'][4],m['entries'][3],level_request(g,level));w=k.words(b)
            for half in (0,1):
                weights=w[half*14:half*14+3]
                assert sum(weights)==(1023 if level==0 and half==1 else 1024)
                filter_rows.append(dict(unit=m['name'],level=level,half=half,R=weights[0],G=weights[1],B=weights[2],sum=sum(weights)))
    write_csv(s.LOCAL/'filter_weights.csv',filter_rows)
    write_csv(s.LOCAL/'row_bytes_rpc.csv',deltas);write_csv(s.LOCAL/'curve_checks.csv',curve_rows)
    write_csv(s.LOCAL/'coefficient_limits.csv',limit_rows);write_csv(s.LOCAL/'combination_limits.csv',combo_limits)
    write_csv(s.LOCAL/'limit_events.csv',limit_events)
    event_keys=('case','unit','slot','amount','levels','wb_method','tone_method','clamps','node_repairs',
                'monotone_repairs','slope_repairs','colour_cap','matrix_cap','rowsum_cap')
    combo_events=[{key:r[key] for key in event_keys} for r in combos if any(r[key] for key in event_keys[7:])]
    write_csv(s.LOCAL/'combination_limit_events.csv',combo_events)
    s.dump(s.LOCAL/'combinations.json',combos)
    summary=dict(status='PASS_HOST_STRUCTURE',parity_cases=parity+golden_checks,default_endpoint_checks=default_checks,
                 literal_mathematical_fixtures=golden_checks,
                 variants=len(variants),alternatives=len(alts)*19,hardware_errors=errors,combination_errors=combo_errors,
                 combinations=combo_count,combination_model_predictions=combo_model_count,invalid_request_checks=invalid,
                 sanitizer=san,T1_equivalence=eq,
                 max_curve_12bit_lsb_jump=max(r['max_12bit_lsb_jump_exact'] for r in curve_rows),
                 max_curve_node_jump=max(r['max_node_jump'] for r in curve_rows),
                 max_combo_curve_12bit_lsb_jump_bound=max(r['max_12bit_lsb_jump_bound'] for r in combos),
                 max_combo_curve_node_jump=max(r['max_node_jump'] for r in combos),
                 limit_records=len(limit_rows),combination_limit_records=len(combo_limits),limit_events=len(limit_events),
                 combination_limit_events=len(combo_events),baseline_checks=baselines,
                 conditional_BW_Tone=True,elapsed_seconds=time.monotonic()-start)
    s.dump(s.LOCAL/'verification.json',summary)
    s.dump(s.LOCAL/'model_inputs_verification.json',model.provenance());s.verify_inputs()
    print(json.dumps({key:value for key,value in summary.items() if key not in ('T1_equivalence','baseline_checks')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
