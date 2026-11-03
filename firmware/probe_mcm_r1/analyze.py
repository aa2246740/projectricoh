"""Validate transcribed raw readings and calculate conditional CPU/LUT rates."""
from pathlib import Path
import argparse
import json
import math
import statistics
import sys

HERE=Path(__file__).resolve().parent
MASK=0xffffffff


def unsigned(value):
    if type(value) is not int or not 0<=value<=MASK:raise ValueError('expected uint32')
    return value


def delta(row):
    result=(unsigned(row['end'])-unsigned(row['start']))&MASK
    if result>=0x80000000:raise ValueError('half-wrap or backwards time')
    return result


def stats(values):
    return dict(min=min(values),median=statistics.median(values),max=max(values),n=len(values))


def analyze(data,seconds,manifest):
    if data.get('protocol')!='MCMR0001' or data.get('dat_sha256')!=manifest['sha256']:
        raise ValueError('protocol or DAT SHA mismatch')
    state=data['state']
    if state['phase']!=6 or state['error']!=0:raise ValueError('run is not DONE without error')
    refs=data['references'];samples=data['samples']
    if not 2<=len(refs)<=3 or len(refs)!=len(seconds):raise ValueError('need paired seconds for 2 or 3 references')
    if len(samples)!=state['used'] or not 0<len(samples)<=48 or len(samples)%2:raise ValueError('incomplete sample list')
    tau=[];runs=[]
    for row,s in zip(refs,seconds):
        if not math.isfinite(s) or s<=0:raise ValueError('seconds must be positive and finite')
        d=delta(row)
        if not row.get('valid') or not d or d!=row['delta']:raise ValueError('invalid reference')
        runs.append(unsigned(row['run']));tau.append(s/d)
    if runs!=sorted(set(runs)) or runs[0]==0:raise ValueError('reference run ids must increase within one power cycle')
    budget=refs[-1]['delta']//600
    if not budget or state['budget']!=budget:raise ValueError('budget does not match the latest reference')
    groups={1:{},2:{}};raw={}
    allowed={1:(16384,65536,262144,1048576),2:(4,64,512,4096)}
    crc_map={count:(manifest['input_crcs'][index],manifest['output_crcs'][index])
             for index,count in enumerate((4096,4,64,512))}
    for row in samples:
        d=delta(row);kind=unsigned(row['kind']);target=unsigned(row['target']);count=unsigned(row['count'])
        if row.get('valid')!=1 or target not in allowed or count not in allowed[target] or kind not in (0,target):
            raise ValueError('invalid sample identity or validity')
        if d>budget:raise ValueError('sample exceeds soft budget')
        expect=crc_map[count][kind==2] if target==2 else 0
        if unsigned(row['crc'])!=expect:raise ValueError('output or input CRC mismatch')
        raw.setdefault((target,kind,count),[]).append(d)
    for i in range(0,len(samples),2):
        x,y=samples[i:i+2]
        if (x['target'],x['count'])!=(y['target'],y['count']) or {x['kind'],y['kind']}!={0,x['target']}:
            raise ValueError('empty and work samples are not paired')
        e=x if x['kind']==0 else y;work=y if x['kind']==0 else x
        groups[x['target']].setdefault(x['count'],[]).append(delta(work)-delta(e))
    if len(groups[1])!=state['admit_d'] or len(groups[2])!=state['admit_l']:
        raise ValueError('sample lengths do not match admission')
    for target,by_count in groups.items():
        if len(by_count)<2 or sorted(by_count)!=list(allowed[target][:len(by_count)]):raise ValueError('missing length or admission level')
        if any(len(values)!=3 for values in by_count.values()):raise ValueError('need exactly three paired repetitions per length')
    if len(samples)!=6*(state['admit_l']+state['admit_d']):raise ValueError('run is incomplete')
    tau_med=statistics.median(tau)
    spread=(max(tau)-min(tau))/tau_med
    result=dict(protocol='MCMR0001',dat_sha256=manifest['sha256'],seconds_per_tick=stats(tau),
                nominal_tick_ms=1,reference_relative_spread=spread,reference_consistent=spread<=0.05,
                nominal_tick_consistent=all(abs(t-0.001)<=0.00005 for t in tau),
                assumed_hand_error_seconds=0.3,raw_ticks={f'{target}:{kind}:{count}':stats(values) for (target,kind,count),values in raw.items()},
                net_ticks={str(target):{str(count):stats(values) for count,values in by_count.items()} for target,by_count in groups.items()},
                camera_or_clock_hardware_verified=False)
    derived={}
    for target,by_count in groups.items():
        lo,hi=sorted(by_count)[-2:]
        b=(statistics.median(by_count[hi])-statistics.median(by_count[lo]))/(hi-lo)
        low_res=any(value<16 for value in by_count[hi]) or b<=0
        eps=4/(hi-lo)
        intervals={str(count):[(statistics.median(values)-2)/count,(statistics.median(values)+2)/count]
                   for count,values in by_count.items()}
        common=[max(bounds[0] for bounds in intervals.values()),min(bounds[1] for bounds in intervals.values())]
        consistent=max(common[0],b-eps)<=min(common[1],b+eps)
        derived[str(target)]=dict(low_resolution=low_res,ticks_per_iteration_slope=b,
            quantization_bound_ticks_per_iteration=eps,lengths=[lo,hi],length_consistent=consistent,
            per_length_quantization_intervals=intervals,common_length_interval=common,
            ticks_per_iteration_by_length={str(count):statistics.median(values)/count for count,values in by_count.items()})
    l=derived['2'];d=derived['1'];result['derived']=derived
    if result['reference_consistent'] and result['nominal_tick_consistent'] and l['length_consistent'] and not l['low_resolution'] and not state.get('low_res'):
        b=l['ticks_per_iteration_slope'];eps=l['quantization_bound_ticks_per_iteration']
        tau_lo=min((s-0.3)/(row['delta']+1) for row,s in zip(refs,seconds))
        tau_hi=max((s+0.3)/(row['delta']-1) for row,s in zip(refs,seconds))
        result['L17']=dict(ticks_per_pixel_pair=b,seconds_per_pixel_pair=b*tau_med,
            main_pixel_pairs=6106112,main_pixels=12212224,main_model_seconds=6106112*b*tau_med,
            display_640x480_seconds=153600*b*tau_med,
            main_quantization_and_hand_interval_seconds=[6106112*max(0,b-eps)*max(0,tau_lo),6106112*(b+eps)*tau_hi],
            scope='private synthetic pairs; extrapolation excludes DMA, actual photo buffers and concurrent image processing')
    else:result['L17']=dict(status='LOW RES' if l['low_resolution'] or state.get('low_res') else 'REFERENCE INCONSISTENT' if not result['reference_consistent'] else 'NOMINAL TICK MISMATCH' if not result['nominal_tick_consistent'] else 'LENGTH INCONSISTENT')
    if result['reference_consistent'] and result['nominal_tick_consistent'] and d['length_consistent'] and not d['low_resolution']:
        slope=d['ticks_per_iteration_slope']
        result['decrement_effective_MHz_scenarios']={str(c):c/(slope*tau_med)/1e6 for c in (4,5,6)}
    else:result['decrement_effective_MHz_scenarios']=None
    result['physical_CPU_MHz']=None
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readings',type=Path)
    parser.add_argument('--seconds',type=float,nargs='+',required=True)
    args=parser.parse_args()
    data=json.loads(args.readings.read_text());manifest=json.loads((HERE/'local/manifest.json').read_text())
    print(json.dumps(analyze(data,args.seconds,manifest),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
