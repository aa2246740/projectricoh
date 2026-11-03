"""Black-box tests of reference validity, log provenance and timing formula."""
from pathlib import Path
import importlib.util
import json
import math
import struct
import zlib

HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('review_driver',HERE/'run_review.py')
r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
d=r.plain_load(r.SOURCE/'decode.py','decoder_under_review')
checks=[]

def fixed(data):
    b=bytearray(data);struct.pack_into('>I',b,52,zlib.crc32(b[128:]));struct.pack_into('>I',b,124,zlib.crc32(b[:124]));return bytes(b)

def mutate(data,offset,value):
    b=bytearray(data);struct.pack_into('>I',b,2432+offset,value);return fixed(b)

def rejected(name,raw,seconds=10):
    try:answer=d.decode(raw,seconds)
    except ValueError as e:checks.append(dict(case=name,rejected=str(e)));return
    raise AssertionError((name,'accepted',answer.get('complete'),answer.get('tick_hz')))

def incomplete(name,raw,seconds=10):
    answer=d.decode(raw,seconds)
    assert not answer['complete'] and 'tick_hz' not in answer and 'ns_per_pair' not in answer,name
    checks.append(dict(case=name,complete=False,error=answer['error'],has_tick_hz=False))

def main():
    r.freeze()
    for gen in (113,114):
        root=HERE/'trace'/str(gen);edges=HERE/'edges'/str(gen)
        valid=(root/'first-publish-retry.BIN').read_bytes();decoded=d.decode(valid,10)
        assert decoded['complete'] and decoded['tick_hz']==1000 and decoded['reference_start']==100000
        checks.append(dict(case=f'{gen}/first-publish-retry',complete=True,tick_hz=decoded['tick_hz'],reference_start=100000))
        for name in ('reference-reopen','menu-reference','h01-reference-retry'):
            rejected(f'{gen}/{name}',(root/(name+'.BIN')).read_bytes())
        for name in ('reference-zero','reference-half-wrap','reference-reversed'):
            rejected(f'{gen}/{name}',(edges/(name+'.BIN')).read_bytes())
        for k in range(4):incomplete(f'{gen}/over-budget{k}',(root/f'over-budget{k}.BIN').read_bytes())
        wrapped=d.decode((edges/'wrapped-valid.BIN').read_bytes(),10)
        assert wrapped['complete'] and wrapped['reference_start']==0xfffffff0 and wrapped['tick_hz']==1000
        reset=d.decode((root/'power-cycle-new-reference.BIN').read_bytes(),10)
        assert reset['complete'] and reset['reference_start']==50000 and reset['tick_hz']==1000
        # No P0R3 START record is flushed when a new reference appears.
        before=[(edges/f'new-reference-old-slot{k}.BIN').read_bytes() for k in (0,1)]
        old=max(before,key=lambda x:struct.unpack_from('>I',x,16)[0]);prior=d.decode(old,8)
        assert prior['complete'] and prior['tick_hz']==1250
        current=[(edges/f'interrupted-newest-slot{k}.BIN').read_bytes() for k in (0,1)]
        newest=max(current,key=lambda x:struct.unpack_from('>I',x,16)[0])
        rejected(f'{gen}/latest-invalid-reference',newest)
        older=min(current,key=lambda x:struct.unpack_from('>I',x,16)[0]);stale=d.decode(older,8)
        assert stale['complete'] and stale['tick_hz']==1250
        checks.append(dict(case=f'{gen}/stale-slot-provenance',latest_generation=struct.unpack_from('>I',newest,16)[0],
            older_generation=struct.unpack_from('>I',older,16)[0],older_complete=True,
            supplied_seconds_from_different_attempt=8,accepted_tick_hz=1250,model_hz=1000,
            limitation='Old valid reference reused; no new interrupted log was accepted as valid.'))
    for name in ('first-publish-retry','reference-reopen'):
        rejected('frozen-r2/'+name,(r.ROOT/'research/review_lut_p0'/(name+'.BIN')).read_bytes())
    template=(HERE/'trace/114/first-publish-retry.BIN').read_bytes()
    for flags in (0,1,2,4,5,6,7,8):rejected('flags='+str(flags),mutate(template,36,flags))
    for name,at,value in (('legacy-protocol',32,0),('zero-start',8,0),('reference-mismatch',16,10001),
                          ('wrong-budget',44,51),('too-many-admissions',40,5),('missed-admission',40,3),
                          ('admission-overflow',48,0x80000000),('admission-overbudget',48,51),
                          ('DONE-error',28,8),('DONE-missing-sample',20,71)):
        rejected(name,mutate(template,at,value))
    incomplete('partial17',mutate(mutate(template,20,17),24,2))
    incomplete('ERROR72',mutate(mutate(template,24,4),28,8))
    for seconds in (0,-1,float('nan'),float('inf'),3600,3601):rejected('seconds='+str(seconds),template,seconds)
    # Literal synthetic slopes independently chosen: empty=1, decrement=2, LUT=3.
    b=bytearray(template)
    counts=(4096,4,64,512)
    for i in range(72):
        rep=i//12;level=(i//3)&3;kind=(i%3+rep+level)%3
        start=1000000+i*100000;dt=(kind+1)*counts[level]+(5,7,13)[kind]
        struct.pack_into('>II',b,2432+64+20*i,start,start+dt)
    result=d.decode(fixed(b),10)
    assert result['complete'] and result['resolution_sufficient'] and result['tick_hz']==1000
    assert math.isclose(result['ticks_per_pair'],2,rel_tol=0,abs_tol=1e-12)
    assert math.isclose(result['ns_per_pair'],2000000,rel_tol=0,abs_tol=1e-6)
    assert math.isclose(result['extrapolated_4288x2848_seconds'],12212.224,rel_tol=0,abs_tol=1e-6)
    (HERE/'formula-synthetic.BIN').write_bytes(fixed(b))
    r.save(HERE/'formula-synthetic.json',dict(synthetic_host_ticks=True,**result))
    low=bytearray(b)
    for i in range(72):
        start=1000000+i*100000;struct.pack_into('>II',low,2432+64+20*i,start,start+7)
    answer=d.decode(fixed(low),10)
    assert answer['complete'] and not answer['resolution_sufficient'] and 'ns_per_pair' not in answer
    r.save(HERE/'decoder-results.json',dict(status='PASS',checks=checks,synthetic_formula=dict(tick_hz=1000,ticks_per_pair=2,ns_per_pair=2000000),
        low_resolution_no_ns_per_pair=True,new_interrupted_reference_never_complete=True,
        stale_complete_slot_still_decodable=True))
    print('PASS decoder checks='+str(len(checks))+'; synthetic formula tick_hz=1000 ns_per_pair=2000000; stale-slot caveat reproduced')
    r.freeze()

if __name__=='__main__':main()
