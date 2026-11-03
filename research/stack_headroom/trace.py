#!/usr/bin/env python3
"""Discovery over existing static indexes; findings require fresh byte checks."""
from pathlib import Path
import argparse
import csv
import importlib.util
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('headroom_inspect', HERE/'inspect.py')
ins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ins)


def source(address):
    for p in (ROOT/'research/tooling_m32r/disasm').glob('ilaunch3-sec*-load-*.disasm.txt'):
        base = int(p.name.split('load-')[1].split('.')[0],16)
        sec = int(p.name.split('-sec')[1].split('-')[0])
        if sec == 15 and 0x05000c00 <= address < 0x0500f8fc:
            return p
        if base <= address < base+0x200000 and sec != 15:
            # Choose the greatest load address below this address.
            candidates = [(int(q.name.split('load-')[1].split('.')[0],16),q)
                for q in (ROOT/'research/tooling_m32r/disasm').glob('ilaunch3-sec*-load-*.disasm.txt')
                if 0x20000000 <= int(q.name.split('load-')[1].split('.')[0],16) <= address]
            return max(candidates)[1]
    raise ValueError(hex(address))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['refs','near','owner','calls'])
    ap.add_argument('addresses',nargs='+')
    ap.add_argument('--before',type=lambda s:int(s,0),default=64)
    ap.add_argument('--after',type=lambda s:int(s,0),default=80)
    a = ap.parse_args()
    ins.preflight()
    addresses = [int(x,16) for x in a.addresses]
    if a.action in ('refs','calls'):
        rows = list(csv.DictReader((ROOT/'research/hidden_processing/ilaunch3-refs.tsv').open(),delimiter='\t'))
        if a.action == 'calls':
            lo,hi=addresses
            print([(r['source_vma'],r['target']) for r in rows if r['kind']=='call' and lo<=int(r['source_vma'],16)<hi])
            return
        data = {hex(t):[r for r in rows if int(r['target'],16)==t] for t in addresses}
        stem = '-'.join(f'{x:08x}' for x in addresses)
        (HERE/'local'/f'refs-{stem}.json').write_text(json.dumps(data,indent=2)+'\n')
        for t, rr in data.items():
            print(t,[(r['source_vma'],r['kind']) for r in rr][:35])
        return
    for t in addresses:
        p = source(t)
        rows = list(ins.instructions(p.read_text()))
        if a.action == 'owner':
            ret = [pc for pc,_,op in rows if pc<t and re.search(r'\bjmp lr\b',op)]
            lo = max(ret,default=t)+4
            print(f'{t:#x}: previous return at {lo-4:#x}; candidate entry {lo:#x}')
            hi = min(lo+48,t+4)
        else:
            lo,hi = t-a.before,t+a.after
        for pc,code,op in rows:
            if lo<=pc<hi:
                print(f'{pc:08x} {code.hex()} {op}')


if __name__ == '__main__':
    main()
