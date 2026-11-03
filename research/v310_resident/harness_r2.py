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


def run(args):
    signal.alarm(1800)
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    os.environ['GXR_HARNESS_BACKEND']=args.side
    fixture=F.prepare(args.name)
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
    H.RESIDENT=Path(fixture['elf']);H.ENGINE=F.ENGINE;H.BODY_SHA=fixture['body_sha256']
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
    start=time.monotonic()
    cam=G153Camera(args.unit)
    PB.CACHE=work/'decode'
    entries=[];registered=set();codeword=0x20054700+112
    raw=H.DAT.read_bytes();codeoff=int.from_bytes(raw[132:136],'big')
    entryoff=int.from_bytes(raw[112:116],'big')
    def entry(current):
        entries.append(dict(pc=hex(current.get_reg('pc')),state=cam.h.u(0x20054705,1)))
        return False
    def code_published(event):
        address=cam.h.u(codeword)
        if cam.h.u(0x20054705,1) in (1,2,3) and 0x20000000<=address<0x21000000:
            target=address+entryoff-codeoff
            if target not in registered:
                registered.add(target);cam.h.b.add_breakpoint(target,entry)
    cam.h.b.add_write_trace(codeword,codeword+4,code_published)
    files=cam.p.files
    expected_ready=args.case in ('flow','irom','irom-second','fallback')
    if args.case=='irom':
        files.paths.pop('/ATA1/GXRCE.DAT',None);files.present=False
        files.paths['/IROM/GXRCE0.DAT']=raw
    elif args.case=='irom-second':
        files.paths.pop('/ATA1/GXRCE.DAT',None);files.present=False
        files.paths['/IROM/GXRCE1.DAT']=raw
    elif args.case=='fallback':
        bad=bytearray(raw);bad[300]^=1
        files.paths['/ATA1/GXRCE.DAT']=bytes(bad)
        files.paths['/IROM/GXRCE0.DAT']=raw
    elif args.case=='file-crc':
        bad=bytearray(raw);bad[300]^=1;files.paths['/ATA1/GXRCE.DAT']=bytes(bad)
    elif args.case=='identity':
        bad=bytearray(raw);bad[80]^=1
        struct.pack_into('>I',bad,20,zlib.crc32(bad[:20]+bytes(4)+bad[24:256]))
        files.paths['/ATA1/GXRCE.DAT']=bytes(bad)
    elif args.case=='dirty':
        expected_ready=False
    elif args.case!='flow':
        raise ValueError(args.case)
    if args.name.startswith('card_') and args.case in ('irom','irom-second','fallback'):
        expected_ready=False
    if args.name.startswith('one_irom_') and args.case=='irom-second':
        expected_ready=False
    detail={}
    if args.case=='dirty':
        frame=cam.m.pe.SCRATCH+0x800
        cam.h.b.write(frame,bytes(68))
        before=len(files.log)
        count=0
        for offset in range(244):
            for bit in range(8):
                cam.h.b.write(0x20054700,b'\xff'*244)
                cam.h.b.write(0x20054700+offset,bytes([255^(1<<bit)]))
                result=cam.p.call(cam.h.symbols['rv_hook_observe'],(0x20054700,1,frame),steps=100000)
                assert result['ok'],result
                assert cam.h.u(0x20054705,1)==6
                assert cam.h.u(0x2022f5ac,1)==7
                count+=1
        assert len(files.log)==before and not entries
        detail['dirty_bit_cases']=count
    else:
        if expected_ready:
            opened=cam.open_menu()
        else:
            cam.h.parent()
            opened,_,error=cam.m.fr.publish(cam.h,cam.p,cam.w)
            assert opened.get('ok') and error is None,(opened,error)
        state=cam.h.u(0x20054705,1);rows=cam.h.u(0x2022f5ac,1)
        if expected_ready:
            assert state==3 and rows==8,(state,rows,opened)
            assert len(entries)==1,entries
            assert entries[0]['state']==2,entries
            first=cam.check_frame();detail['first_frame']=first
            block=cam.h.u(0x20054700+56)
            source=cam.h.u(block+328);detail['selected_source']=source
            assert source==(2 if args.case=='irom-second' else 1 if args.case in ('irom','fallback') else 3)
            if args.case=='flow':
                frames=[]
                for row in (0,7,1):frames.append(cam.goto(row));cam.check_frame()
                current=cam.unit_rows()
                digest=hashlib.sha256(b''.join(current[0])+struct.pack('>I',current[1])).hexdigest()
                s=bytearray(cam.s_bytes(0,4096));s[0xfd4+28:0xfd4+40]=bytes(12)
                record=cam.record()
                expected_record=record[:28]+raw[20:28]
                expected_record+=struct.pack('>I',zlib.crc32(expected_record))
                assert record==expected_record,(record.hex(),expected_record.hex())
                detail.update(frames=frames,unit_rows_sha256=digest,settings_sha256=F.sha(bytes(s)),
                              record_prefix=record[:28].hex(),record=record.hex(),record_identity_and_crc_verified=True)
                cam.press('OK');assert cam.h.u(0x2022f5ac,1)==7
                cam.open_menu();cam.check_frame()
                cam.press('ADJ');assert cam.h.u(0x2022f5ac,1)==7
                detail['native_close_rows']=7
        else:
            assert state==6 and rows==7,(state,rows,opened)
            assert not entries,entries
            assert cam.h.u(0x2022f5a8)==0x2022d610
            assert cam.writes()==0
    assert not files.live,files.live
    stats=dict(getattr(cam.h.b,'native_stats',{}))
    if args.side=='c':assert stats.get('instructions',0)>0,stats
    result=dict(status='PASS',name=args.name,case=args.case,unit=args.unit,side=args.side,
                ready=expected_ready,entries=entries,detail=detail,files_opened=files.log,
                rpc_writes=cam.writes(),native_stats=stats,adapters=adapters,
                seconds=time.monotonic()-start,nice=os.getpriority(os.PRIO_PROCESS,0),timeout=1800,
                runner_sha256=RUNNER_SHA256,layout_sha256=F.sha(ROOT/'research/v39_g153/layout.json'),
                timeout_enforced=True,pid=os.getpid(),
                fixture_sha256=dict(elf=fixture['elf_sha256'],body=fixture['body_sha256'],dat=fixture['dat_sha256']))
    (out/('harness-'+args.case+'-'+args.unit+'-'+args.side+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['status','name','case','unit','side','seconds']}),flush=True)
    signal.alarm(0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('name')
    parser.add_argument('--case',default='flow',choices=['flow','irom','irom-second','fallback','identity','file-crc','dirty'])
    parser.add_argument('--unit',default='50mm',choices=['50mm','28mm','mount'])
    parser.add_argument('--side',default='c',choices=['c','python'])
    parser.add_argument('--matrix',choices=['flow','routes'])
    args=parser.parse_args()
    if args.matrix:
        import gc
        for name in args.name.split(','):
            for item in (['50mm','28mm','mount']if args.matrix=='flow'else ['irom','fallback','identity','file-crc']):
                options=vars(args).copy();options['name']=name
                options['unit'if args.matrix=='flow'else 'case']=item
                run(argparse.Namespace(**options));gc.collect()
    else:run(args)
