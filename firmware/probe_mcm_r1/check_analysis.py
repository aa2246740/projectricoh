"""A literal synthetic oracle for the raw-reader and timing formulas."""
from pathlib import Path
import copy
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze
import probe_common as c


def main():
    manifest=json.loads((c.LOCAL/'manifest.json').read_text())
    refs=[dict(start=0xfffff000,end=(0xfffff000+30000)&0xffffffff,delta=30000,valid=1,run=1),
          dict(start=100000,end=130000,delta=30000,valid=1,run=2)]
    samples=[];time=200000
    for rep in range(3):
        for target,counts in ((2,(4,64,512,4096)),(1,(16384,65536,262144,1048576))):
            for level,count in enumerate(counts):
                sequence=(0,target) if not ((rep+level)&1) else (target,0)
                for kind in sequence:
                    dt=1+(count//128 if kind==2 else count//32768 if kind==1 else 0)
                    index=(4096,4,64,512).index(count) if target==2 else None
                    crc=manifest['output_crcs' if kind==2 else 'input_crcs'][index] if target==2 else 0
                    samples.append(dict(start=time,end=time+dt,count=count,kind=kind,target=target,crc=crc,valid=1));time+=100
    data=dict(protocol='MCMR0001',dat_sha256=manifest['sha256'],references=refs,samples=samples,
        state=dict(phase=6,error=0,used=48,admit_d=4,admit_l=4,budget=50,low_res=0))
    result=analyze.analyze(data,[30.0,30.0],manifest)
    assert result['seconds_per_tick']['median']==0.001
    assert abs(result['L17']['ticks_per_pixel_pair']-1/128)<1e-15
    assert abs(result['L17']['main_model_seconds']-47.704)<1e-12
    assert result['L17']['main_pixels']==12212224
    assert abs(result['decrement_effective_MHz_scenarios']['4']-131.072)<1e-10
    assert result['physical_CPU_MHz'] is None
    rejected=[]
    for label,edit in (
        ('not-DONE',lambda d:d['state'].update(phase=5)),
        ('error',lambda d:d['state'].update(error=3)),
        ('old-protocol',lambda d:d.update(protocol='LUTP0001')),
        ('wrong-DAT',lambda d:d.update(dat_sha256='0'*64)),
        ('missing-sample',lambda d:d['samples'].pop()),
        ('bad-crc',lambda d:d['samples'][1].update(crc=0)),
        ('zero-ref',lambda d:d['references'][0].update(end=0xfffff000,delta=0)),
        ('half-wrap',lambda d:d['references'][0].update(end=(0xfffff000+0x80000000)&0xffffffff,delta=0x80000000)),
        ('invalid-sample',lambda d:d['samples'][0].update(valid=0)),
        ('bad-budget',lambda d:d['state'].update(budget=51))):
        bad=copy.deepcopy(data);edit(bad)
        try:analyze.analyze(bad,[30.0,30.0],manifest)
        except ValueError:rejected.append(label)
        else:raise AssertionError(label)
    low=copy.deepcopy(data)
    for row in low['samples']:row['end']=row['start']+1
    assert analyze.analyze(low,[30.0,30.0],manifest)['L17']['status']=='LOW RES'
    assert analyze.analyze(data,[30.0,36.0],manifest)['L17']['status']=='REFERENCE INCONSISTENT'
    assert analyze.analyze(data,[60.0,60.0],manifest)['L17']['status']=='NOMINAL TICK MISMATCH'
    nonlinear=copy.deepcopy(data)
    for row in nonlinear['samples']:
        if row['kind']==2 and row['count']==512:row['end']=row['start']+17
    assert analyze.analyze(nonlinear,[30.0,30.0],manifest)['L17']['status']=='LENGTH INCONSISTENT'
    nonlinear_d=copy.deepcopy(data)
    for row in nonlinear_d['samples']:
        if row['kind']==1 and row['count']==262144:row['end']=row['start']+21
    assert analyze.analyze(nonlinear_d,[30.0,30.0],manifest)['decrement_effective_MHz_scenarios'] is None
    c.save(c.RESEARCH/'evidence/formula-synthetic-input.json',data)
    c.save(c.RESEARCH/'evidence/formula-checks.json',dict(status='PASS',synthetic_only=True,dat_sha256=manifest['sha256'],
        exact_expected=dict(tau=0.001,lut_ticks_per_pair=1/128,main_seconds=47.704,effective_MHz_C4=131.072),result=result,rejected=rejected,
        low_resolution_refused=True,inconsistent_reference_refused=True,nominal_tick_mismatch_refused=True,
        nonlinear_L17_refused=True,nonlinear_D_refused=True))
    print('PASS formula oracle and',len(rejected),'invalid inputs; synthetic numbers are not camera measurements')


if __name__=='__main__':main()
