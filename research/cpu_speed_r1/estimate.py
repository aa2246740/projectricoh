#!/usr/bin/env python3
"""Recompute conditional estimates. No result is a measured camera frequency."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent

def main():
    n1,n2,t1,t2=1<<22,1<<24,111,585
    tau=.001
    loops=[]
    for c in (4,5,6):
        loops.append(dict(cycles_per_iteration_assumed=c,
            short_effective_mhz=n1*c/(t1*tau)/1e6,
            long_effective_mhz=n2*c/(t2*tau)/1e6,
            difference_effective_mhz=(n2-n1)*c/((t2-t1)*tau)/1e6,
            short_quantization_only_mhz=[n1*c/((t1+1)*tau)/1e6,n1*c/((t1-1)*tau)/1e6],
            difference_quantization_only_mhz=[(n2-n1)*c/((t2-t1+2)*tau)/1e6,(n2-n1)*c/((t2-t1-2)*tau)/1e6]))
    w,h=4288,2848;p=w*h//2
    f_lo,f_hi=150e6,230e6;u_lo,u_hi=.7,1.
    scenarios=[]
    for grid,cyc in [(17,(450,1200)),(33,(450,2000))]:
        for size,pairs in [('main',p),('playback_640x480_assumed',640*480//2)]:
            scenarios.append(dict(grid=grid,size=size,pairs=pairs,
                cycles_per_pair_assumed=list(cyc),frequency_hz_assumed=[f_lo,f_hi],
                runnable_cpu_fraction_assumed=[u_lo,u_hi],
                time_seconds_conditional=[pairs*cyc[0]/(f_hi*u_hi),pairs*cyc[1]/(f_lo*u_lo)],
                main_162mhz_full_cpu_seconds=[pairs*cyc[0]/162e6,pairs*cyc[1]/162e6]))
    result=dict(scope='Conditional engineering estimates; not measured camera timings or a proven physical-clock interval.',
        supplied_camera_measurements=dict(short_n=n1,long_n=n2,short_ticks=t1,long_ticks=t2),
        tick_seconds_static_inference=tau,ratio=t2/t1,
        affine_fit_intercept_ticks=(t1*n2-t2*n1)/(n2-n1),
        excess_long_ticks_over_four_short=t2-4*t1,
        loop_models=loops,pixels=w*h,pairs=p,table_bytes={str(n):n**3*6 for n in (17,33)},
        table_size_ratio=(33/17)**3,
        logical_non_stack_traffic_bytes=p*72,
        scenarios=scenarios,
        physical_clock_proven=False,finite_physical_clock_upper_bound_proven=False,
        end_to_end_save_time_proven=False,table33_current_abi_single_lease_fits=False,
        costs_exclude=['LUT initial loading','CRC verification','DMA/cache synchronization','JPEG decode/encode','SD save','other image consumers'])
    out=HERE/'evidence/estimates.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
