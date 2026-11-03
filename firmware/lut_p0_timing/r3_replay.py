"""Run the frozen reviewer's numeric oracle against the r3 packed kernel.

Only the output directory, task helpers and freeze callback are rebound.
The oracle, input vectors, instruction checks and assertions remain verbatim.
"""
import hashlib
import importlib.util
from pathlib import Path
import random
import struct
from types import SimpleNamespace
import zlib

s=importlib.util.spec_from_file_location('r3_replay_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)


def main():
    c.guard();review=c.ROOT/'research/review_lut_p0/independent_kernel.py'
    out=c.LOCAL/'r3/independent';out.mkdir(parents=True,exist_ok=True)
    def freeze():c.run(['/usr/bin/python3','-I','-B',c.HERE/'freeze.py'],'r3-independent-freeze')
    r=c.load(c.HERE/'replay.py','r3_instruction_replay')
    raw=review.read_text();body=raw[raw.index('def location('):]
    namespace=dict(__name__='r3_frozen_oracle',HERE=out,c=c,r=r,driver=SimpleNamespace(freeze=freeze),
                   hashlib=hashlib,random=random,struct=struct,zlib=zlib)
    exec(compile(body,str(review),'exec'),namespace)
    namespace['main']()
    for name in ('mixed','identity','extremes','random'):
        assert (out/(name+'-output.bin')).read_bytes()==(review.parent/(name+'-output.bin')).read_bytes(),('r2 kernel output changed',name)
    c.save(c.LOCAL/'independent-kernel-results.json',dict(
        __import__('json').loads((out/'independent-kernel-results.json').read_text()),
        frozen_reviewer_source_sha256=c.sha(review),runner_sha256=c.sha(Path(__file__)),r2_output_bytes_equal=True))


if __name__=='__main__':main()
