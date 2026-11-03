#!/usr/bin/env python3
"""Convert two loop measurements under explicit, caller-supplied assumptions."""
import argparse
from fractions import Fraction
import json

N1=1<<22
N2=1<<24


def estimate(t1,t2,tick_ns,cycles):
    if not (0<=t1<(1<<32) and 0<=t2<(1<<32)):
        raise ValueError('tick 差必须是无符号 32 位数')
    delta=t2-t1
    if delta<=2 or tick_ns<=0 or cycles<=0:
        raise ValueError('长短循环差必须大于 2 tick，周期和每轮周期数必须大于 0')
    numerator=(N2-N1)*cycles*1_000_000_000
    return dict(short_count=N1,long_count=N2,short_ticks=t1,long_ticks=t2,
        tick_ns_assumed=tick_ns,cycles_per_iteration_assumed=str(cycles),
        estimated_hz_under_assumptions=float(numerator/(tick_ns*delta)),
        quantization_only_hz_interval=[float(numerator/(tick_ns*(delta+2))),
                                       float(numerator/(tick_ns*(delta-2)))],
        physical_cpu_frequency_proven=False,camera_executed=False,
        remaining_errors=['中断和任务抢占','取指等待和缓存状态','循环周期数的芯片假设',
                          '时间基准频率误差','两次读取开销的变化'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--short-ticks',type=int)
    parser.add_argument('--long-ticks',type=int)
    parser.add_argument('--tick-ns',type=int)
    parser.add_argument('--cycles-per-iteration',type=Fraction)
    parser.add_argument('--demo',action='store_true',help='仅检验合成数据，绝非相机测量')
    args=parser.parse_args()
    if args.demo:
        # A synthetic 3-tick fixed overhead cancels from the two durations.
        result=estimate(103,403,1_000_000,Fraction(4))
        assert result['estimated_hz_under_assumptions']==167_772_160
        assert estimate(100,400,1_000_000,Fraction(4))['estimated_hz_under_assumptions']==167_772_160
        result['synthetic_demo']=True
    else:
        if any(x is None for x in (args.short_ticks,args.long_ticks,args.tick_ns,args.cycles_per_iteration)):
            parser.error('本机 tick 周期与每轮周期数尚未证明；必须显式提供全部假设，或使用 --demo')
        result=estimate(args.short_ticks,args.long_ticks,args.tick_ns,args.cycles_per_iteration)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
