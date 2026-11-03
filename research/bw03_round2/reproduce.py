#!/usr/bin/env python3
"""Re-run this exact research task in the foreground. Requires the local inputs."""
import sys
sys.dont_write_bytecode=True
import argparse
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument("--plan",action="store_true");args=p.parse_args()
    steps=[]
    def add(phase,start=None,stop=None,fold=None):
        command=[sys.executable,"-I","-B",str(HERE/"run.py"),phase]
        if start is not None:command.extend(["--start",str(start),"--stop",str(stop)])
        if fold is not None:command.extend(["--fold",str(fold)])
        steps.append(command)
    add("prepare");add("mixfit",0,10);add("integer_near",0,100000);add("lattice_prepare")
    for n in range(0,23262,5000):add("lattice",n,min(23262,n+5000))
    add("pareto_grid",0,4000);add("pareto_grid",4000,5000);add("summarize_mix")
    add("t1_prepare");add("t1fit",0,107);add("t1_free");add("additive_bound")
    add("loo_frames",0,2)
    for n in range(0,308,6):add("loo_bins",n,min(308,n+6))
    for fold in range(2):
        for n in range(0,107,40):add("t1_loo_grid",n,min(107,n+40),fold)
    add("characterize")
    steps.append([sys.executable,"-I","-B",str(HERE/"finish.py")])
    if args.plan:
        print(f"{len(steps)} foreground stages; all 308 bin refits; 2 held-out scenes; writes only bw03_round2 and /tmp/bw03_r2")
        return
    env=os.environ.copy();env["OPENBLAS_NUM_THREADS"]="1"
    for n,command in enumerate(steps,1):
        print(f"stage {n}/{len(steps)}: {' '.join(command[4:]) or Path(command[3]).name}",flush=True)
        subprocess.run(command,cwd=ROOT,env=env,check=True)


if __name__=="__main__":main()
