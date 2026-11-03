#!/usr/bin/python3
"""Exercise the real first ADJ entry and g153 DAT with the selected host backend."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import types
import zlib
import signal

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'research/v310_resident'
TEMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-resident-r1')
sys.path.insert(0,str(HERE))
import fixtures_r2 as F
RUNNER_SHA256=F.sha(Path(__file__))


def setup(args,fixture_override=None):
    signal.alarm(1800)
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    os.environ['GXR_HARNESS_BACKEND']=args.side
    fixture=fixture_override or F.prepare(args.name)
    out=HERE/'evidence_r2'/args.name;out.mkdir(parents=True,exist_ok=True)
    work=TEMP/'harness'/args.name/args.case/args.unit/args.side
    work.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    import python_backend as PB
    PB.CACHE=work/'decode'
    import harness,field_replay,product_execute,engine_bridge
    source=ROOT/'research/body_v39/tests/v39_host.py'
    H=F.module(source,'v39_host')
    H.LAYOUT=json.loads((ROOT/'research/v39_g153/layout.json').read_text());H.UI=H.LAYOUT['ui']
    class G153Camera(H.Camera):
        def labels(self):
            base=self.adapter+H.UI+H.LAYOUT['ui.text']
            return [bytes(self.h.b.read(base+14*i,14)).split(b'\0')[0].decode('ascii')for i in range(8)]
        def state(self):
            result=super().state();result['effect']=self.ui('effect');return result
    H.LOCAL=out;H.TMP=work
    H.PACKAGE=Path(fixture['dat']).parent
    H.DAT=Path(fixture['dat']);H.BODY=Path(fixture['body'])
    H.RESIDENT=Path(fixture['elf']);H.ENGINE=Path(fixture['engine']);H.BODY_SHA=fixture['body_sha256']
    H.setup=lambda:None
    adapters=[]

    def adapted_module(path,name,old,new):
        text=path.read_text();assert text.count(old)==1
        text=text.replace(old,new)
        if name=='accept_integration':
            observer='h.b.visits[h.symbols["rv_load"]]'
            assert observer in text
            text=text.replace(observer,'h.b.visits.get(h.symbols.get("rv_load"),0)')
        mod=types.ModuleType(name);mod.__file__=str(path);sys.modules[name]=mod
        exec(compile(text,str(path),'exec'),mod.__dict__)
        adapters.append(dict(source=str(path.relative_to(ROOT)),original_sha256=F.sha(path),
                             executed_sha256=hashlib.sha256(text.encode()).hexdigest(),
                             change='Optional internal observations when the compiler has inlined the function; actual DAT entry remains counted.'))
        return mod

    def accepted():
        path=ROOT/'research/g135_v37/accept.py'
        old=adapted_module(path,'v39_accept_base',
            "    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)",
            "    if 'rv_invoke' in h.symbols:\n        h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)")
        old.HERE=work;old.PACKAGE=H.PACKAGE;old.BODY=H.BODY;old.DAT=H.DAT
        old.RESIDENT=H.RESIDENT;old.ENGINE=H.ENGINE
        old.GENERATION=int.from_bytes(H.DAT.read_bytes()[28:32],'big');old.TAG=''
        old.freeze=lambda:None;old.save=lambda name,value:None
        previous=old.load
        def loaded(path,name):
            if name=='accept_integration':
                mod=adapted_module(path,name,
                    '        self.h.b.add_breakpoint(self.h.symbols["rv_header"], header_seen)',
                    '        if "rv_header" in self.h.symbols:\n            self.h.b.add_breakpoint(self.h.symbols["rv_header"], header_seen)')
                defaults=list(mod.v.V35Harness.__init__.__defaults__)
                defaults[1]=PB.PythonBackend
                mod.v.V35Harness.__init__.__defaults__=tuple(defaults)
                mod.v.python_backend.CACHE=work/'decode'
                return mod
            return previous(path,name)
        old.load=loaded
        return old
    H.accept_module=accepted
    return G153Camera(args.unit),H,fixture,work,adapters,PB
