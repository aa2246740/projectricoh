"""Independent final-DAT spot checks through native constructors and keys."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import sys
import time
import traceback
import types

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/review_g153'
SOURCE = ROOT / 'research/v39_g153'
SCRATCH = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-g153-r1')
sha = lambda b: hashlib.sha256(b).hexdigest()

def load(name, path, replacements=()):
    original = path.read_text()
    text = original
    for left, right in replacements:
        assert left in text, left
        text = text.replace(left, right)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(text, str(path), 'exec'), module.__dict__)
    return module

def initialize(side, name):
    scratch = SCRATCH / name
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1', GXR_HARNESS_BACKEND=side)
    sys.path.insert(0, str(ROOT / 'tools/native_harness_c'))
    import python_backend
    import harness
    import field_replay
    import product_execute
    import engine_bridge
    sys.path.insert(0, str(SOURCE))
    support = load('native_support', SOURCE/'native_support.py', [
        ("TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g153')", 'TMP=Path('+repr(str(scratch))+')'),
        ("H.LOCAL=HERE/'local/native'/('p'+str(os.getpid()))", 'H.LOCAL=TMP/\'host\''),
    ])
    return support, python_backend, scratch

def ui_audit(cam):
    spans=((0x2022f71c,0x2022f740),(0x2022f5a8,0x2022f5b0),(0x205a279c,0x205a27dc),
           (0x205a280f,0x205a2810),(0x205d9bf8,0x205d9c04),(0x205a2944,0x205a2945))
    writes=[e for e in cam.h.writes if any(int(e['address'],16)<hi and int(e['address'],16)+e['size']>lo for lo,hi in spans)]
    bad=[e for e in writes if e['origin'] not in ('cpu','model:native_memset')]
    assert not bad, bad
    assert not [e for e in cam.p.native_log if e.get('op') in ('create','write','rename','delete')]
    stats=dict(getattr(cam.h.b,'native_stats',{}))
    if os.environ['GXR_HARNESS_BACKEND']=='c':
        assert cam.h.b.native_api == 5 and stats['instructions'] > 0, stats
    return dict(native_UI_writes=len(writes), host_UI_writes=len(bad),
                backend_module=type(cam.h.b).__module__, native_stats=stats)

def set_rows(cam, entry):
    raw=cam.dat_path.read_bytes()
    d=int.from_bytes(raw[156:160],'big')+64*S.H.UNITS[cam.unit]
    at=int.from_bytes(raw[d+12:d+16],'big');mapping=raw[at:at+152]
    for row in range(9):
        address=int.from_bytes(mapping[32+12*row:36+12*row],'big')
        size=int.from_bytes(mapping[36+12*row:38+12*row],'big')
        offset=int.from_bytes(mapping[38+12*row:40+12*row],'big')
        for k,value in enumerate(entry[offset:offset+size]):
            p=address+k;word=p&~1;old=cam.p.rpc.half(word)
            assert old is not None
            cam.p.rpc.overlay[word]=(old&0xff00)|value if p&1 else (value<<8)|(old&0xff)
    cam.p.rpc.t=int.from_bytes(entry[445:447],'big')

def save_state(prefix, cam):
    rows,t=cam.unit_rows()
    unit=b''.join(rows)+t.to_bytes(2,'big')
    settings=cam.s_bytes(0,4096)
    (OUT/'results'/(prefix+'-unit.bin')).write_bytes(unit)
    (OUT/'results'/(prefix+'-S.bin')).write_bytes(settings)
    return dict(unit_sha256=sha(unit), S_sha256=sha(settings), W=cam.writes(), T=t,
                live_verified=cam.engine_bytes(S.H.LAYOUT['g.live_verified'],1).hex())

def cross_exit(unit, slot):
    cam=S.Camera(unit);raw=cam.dat_path.read_bytes();u=S.H.UNITS[unit]
    first=F.expand(raw,u,2);later=F.expand(raw,u,slot)
    set_rows(cam,first);cam.put_s(0x36e,b'\x04');cam.open_menu()
    assert cam.engine_bytes(S.H.LAYOUT['g.baseline'],1)==b'\0'
    cam.set_lock(0);cam.press('DOWN')
    assert cam.unit_rows()==S.expected(cam,first) and cam.writes()==0
    assert cam.engine_bytes(S.H.LAYOUT['g.live_verified'],1)==b'\0'
    S.exit_menu(cam,'ok');assert cam.h.u(0x2022f5ac,1)==7
    set_rows(cam,later);cam.set_lock(-1);cam.open_menu()
    assert cam.unit_rows()==S.expected(cam,later) and cam.writes()==0
    label=f'exit-{unit}-{slot}-{os.environ["GXR_HARNESS_BACKEND"]}'
    before=save_state(label+'-before',cam)
    cam.h.b.core.psw|=0x40;calls=[];stores=[];taken=[]
    def observe(b):
        if b.core.r[0]==6 and b.core.r[1] in (2,5,6):
            op=b.core.r[1]
            if op==2 and not taken:
                assert b.core.psw&0x40
                cam.set_lock(0);taken.append(True)
            row=dict(op=op);calls.append(row)
            L.callback_return(cam,b,lambda current:row.update(result=current.core.r[0] if current.core.r[0]<2**31 else current.core.r[0]-2**32))
        return False
    cam.h.b.add_breakpoint(cam.symbol('rv_call'),observe)
    cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:stores.append(e.address-cam.s) if e.origin=='cpu' else None)
    cam.press('DOWN');after=save_state(label+'-after',cam)
    assert cam.unit_rows()==S.expected(cam,later)
    assert [(x['op'],x['result']) for x in calls]==[(6,0),(2,-2)],calls
    assert taken and not stores and not cam.check_frame()['failed']
    assert cam.engine_bytes(S.H.LAYOUT['g.live_verified'],1)==b'\0'
    S.exit_menu(cam,'ok');cam.open_menu();reopened=save_state(label+'-reopened',cam)
    for field in ('unit_sha256','S_sha256'):
        assert before[field]==after[field]==reopened[field],field
    assert not stores and not cam.check_frame()['failed']
    return dict(unit=unit, actual_prior_slot=slot, before=before, after=after,
                reopened=reopened, calls=calls, S_stores=stores, audit=ui_audit(cam))

def busy(unit, transition, timing, exit_kind):
    cam=S.Camera(unit);cam.open_menu();active=L.configure(cam)
    L.HERE=OUT
    result=L.one(cam,active,transition,timing,exit_kind,'review')
    result['audit']=ui_audit(cam)
    return result

def looks(unit):
    cam=S.Camera(unit);cam.open_menu();cam.open_looks()
    previous=(ROOT/'firmware/package_v38_g152_test/local/SD_ROOT/GXRCE.DAT').read_bytes()
    raw=cam.dat_path.read_bytes();results=[]
    for number in (1,3,10):
        before=cam.s_bytes(0,4096)
        frame=cam.select_effect(number)
        expected=F.expand_effect(previous,number-1)
        live=cam.engine_bytes(S.H.LAYOUT['g.live'],552)
        assert live==expected==F.expand_effect(raw,number-1)
        assert cam.unit_rows()==S.expected(cam,expected)
        settings=bytearray(before);settings[0x36e]=1;settings[0x6dd:0x6df]=b'\x09\x09';settings[0xfd4:0xffc]=bytes(40)
        assert cam.s_bytes(0,4096)==settings
        if number==3:
            assert cam.unit_rows()[0][2]==bytes(96)
            # Every encoded chroma coefficient is zero, so each Y gives R=G=B=Y.
            for y in (0,31,128,255,4095):
                cb=cr=0
                assert (y+1402*cr,y-344136*cb-714136*cr,y+1772*cb)==(y,y,y)
        (OUT/'results'/f'look-{unit}-{number}.entry').write_bytes(live)
        results.append(dict(effect=number, live_552_sha256=sha(live), frame=frame))
    cam.goto(0);cam.press('DISP');cam.goto(3)
    stock=F.expand(raw,S.H.UNITS[unit],4)
    assert cam.unit_rows()==S.expected(cam,stock)
    assert cam.engine_bytes(S.H.LAYOUT['g.live'],552)==stock
    if unit=='mount':assert stock!=F.expand(raw,0,4)
    saved=cam.s_bytes(0,4096)
    fresh=S.Camera(unit);initial=fresh.unit_rows();fresh.put_s(0,saved);fresh.open_menu()
    assert fresh.unit_rows()==initial and fresh.writes()==0
    assert fresh.check_frame()['effect']==0 and fresh.check_frame()['slot']==4
    return dict(unit=unit, effects=results, stock_04_sha256=sha(stock),
                cold_model_unit_W=0, audit=ui_audit(cam), fresh_audit=ui_audit(fresh))

def identity(version):
    H=S.H
    new_dat=ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT'
    package=ROOT/'firmware'/('package_v39_g151' if version=='g151' else
                            'package_v38_g139' if version=='v38' else 'package_v39_g153_test')/'local/SD_ROOT'
    H.PACKAGE=package;H.BODY=package/'ilaunch3';H.DAT=package/'GXRCE.DAT';H.BODY_SHA=sha(H.BODY.read_bytes())
    H.RESIDENT=ROOT/('firmware/resident_v39/local/resident/build/resident.elf' if version=='g151' else
                    'firmware/resident_v38/local/resident/build/resident.elf' if version=='v38' else
                    'research/v39_g153/local/body/local/resident/build/resident.elf')
    H.ENGINE=ROOT/('firmware/engine_v59_g151' if version=='g151' else
                  'firmware/engine_v56_g139' if version=='v38' else
                  'firmware/engine_v62_g153')/'candidate/local/full-r13/engine.elf'
    H.setup();cam=S.Camera('50mm')
    dat=ROOT/'firmware/package_v39_g151/local/SD_ROOT/GXRCE.DAT' if version=='g153' else new_dat
    cam.p.files.paths['/ATA1/GXRCE.DAT']=dat.read_bytes()
    entered=[];cam.h.b.add_breakpoint(cam.h.symbols['rv_invoke'],lambda b:entered.append(True) or False)
    stores=[];before=cam.s_bytes(0,4096);unit=cam.unit_rows()
    cam.h.b.add_write_trace(cam.s,cam.s+4096,lambda e:stores.append(e.address) if e.origin=='cpu' else None)
    cam.h.parent();result=cam.m.fr.native(cam.h,0x20287080,steps=30000000)
    assert result['ok'],result
    assert cam.h.u(H.R+5,1)==6 and cam.h.u(0x2022f5ac,1)==7
    assert cam.h.u(0x2022f5a8)==0x2022d610
    assert not entered and cam.h.u(H.R+148)==0
    assert not stores and cam.s_bytes(0,4096)==before and cam.unit_rows()==unit and cam.writes()==0
    return dict(body_version=version, body_sha256=H.BODY_SHA, DAT_sha256=sha(dat.read_bytes()),
                DAT_entries=0, root_state=6, rows=7, unit_W=0, S_stores=0, audit=ui_audit(cam))

def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('case',choices=('cross-exit','busy','looks','identity'))
    parser.add_argument('--unit',default='mount',choices=('mount','50mm','28mm'))
    parser.add_argument('--slot',type=int,default=8)
    parser.add_argument('--transition',default='effect-other-base')
    parser.add_argument('--timing',default='race-at-s')
    parser.add_argument('--exit',default='half')
    parser.add_argument('--version',default='g153',choices=('g153','g151','v38'))
    parser.add_argument('--side',default='c',choices=('c','python'))
    parser.add_argument('--timeout',type=int,default=3600)
    parser.add_argument('--run-tag',default='')
    args=parser.parse_args()
    if args.run_tag:
        assert args.run_tag.replace('-','').isalnum()
        OUT=OUT/'reruns'/args.run_tag
        (OUT/'results').mkdir(parents=True,exist_ok=True)
    assert os.getpriority(os.PRIO_PROCESS,0)==10
    suffix=f'{args.case}-{args.unit}-{args.slot}-{args.transition}-{args.timing}-{args.exit}-{args.version}-{args.side}'
    receipt=OUT/'results'/(suffix+'.json')
    assert not receipt.exists(),receipt
    start=time.time_ns();tick=time.monotonic()
    record=dict(arguments=vars(args),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),started_ns=start,
                script_sha256=sha(Path(__file__).read_bytes()))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError(suffix)))
    signal.alarm(args.timeout)
    global S,F,L
    try:
        S,backend,scratch=initialize(args.side,args.run_tag+'-'+suffix)
        F=load('dat_format',SOURCE/'dat_format.py')
        L=load('lock_checks',SOURCE/'lock_checks.py')
        A=load('apply_checks',SOURCE/'apply_checks.py');A.ui_audit=ui_audit
        (OUT/'evidence').mkdir(exist_ok=True)
        if args.case=='cross-exit':details=cross_exit(args.unit,args.slot)
        elif args.case=='busy':details=busy(args.unit,args.transition,args.timing,args.exit)
        elif args.case=='looks':details=looks(args.unit)
        else:details=identity(args.version)
        record.update(status='PASS',details=details)
    except BaseException:
        record.update(status='FAIL',error=traceback.format_exc())
        raise
    finally:
        signal.alarm(0)
        record.update(seconds=time.monotonic()-tick,ended_ns=time.time_ns())
        receipt.write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps({k:v for k,v in record.items() if k!='details'}),flush=True)

if __name__=='__main__':main()
