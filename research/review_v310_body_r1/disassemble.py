#!/usr/bin/python3
"""Decode limited official instruction ranges into review-local files."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-v310-body-r1')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    raw=(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    tool=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    directory=HERE/'local/disassembly';directory.mkdir(exist_ok=True)
    rows=[]
    for start,end in [(0x2008d000,0x2008d300),(0x20087af0,0x20087b80),(0x2007774c,0x200778d4),
        (0x2005a06c,0x2005a29c),(0x200562a8,0x20056378),
        (0x2036db00,0x2036dc20),(0x2036fa20,0x2036fac8)]:
        for i in range(16):
            pos,lo,n,_,_=struct.unpack_from('>5I',raw,32+20*i)
            if lo<=start and end<=lo+n:
                data=raw[512+pos+start-lo:512+pos+end-lo];break
        else:raise ValueError(hex(start))
        source=TEMP/('native-'+hex(start)+'.bin');source.write_bytes(data)
        target=directory/(hex(start)+'.txt')
        with target.open('w') as out:
            subprocess.run([str(tool),'-D','-b','binary','-m','m32r','-EB',
                '--adjust-vma='+hex(start),str(source)],stdout=out,check=True,timeout=120)
        rows.append(dict(start=hex(start),end=hex(end),bytes_sha256=hashlib.sha256(data).hexdigest(),
            decoded_file=str(target.relative_to(ROOT))))
    (HERE/'evidence/disassembly.json').write_text(json.dumps(dict(status='PASS',
        official_MAIN_sha256=hashlib.sha256(raw).hexdigest(),tool_sha256=hashlib.sha256(tool.read_bytes()).hexdigest(),
        ranges=rows),indent=2)+'\n')


if __name__=='__main__':main()
