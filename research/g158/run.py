"""Cold MAIN, real GPIO menu selection, record observations. No DAT building."""
from pathlib import Path
import argparse
import json
import os
import signal
import struct
import sys
import time
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

C.FAST=C.ROOT/'tools/gxr_emulator_fast/strict_r4'
C.DATASET=sys.argv[sys.argv.index('--dataset')+1] if '--dataset' in sys.argv else 'control'
_field=C.load(C.ROOT/'research/g156_field_issues_r1/local/common.py','g158_medium_helper')
C.medium_bytes=_field.medium_bytes
_load=lambda name,path:C.load(path,name)
C.VERSIONS={}
for _profile,_package in C.PACKAGES.items():
    _variant=C.artifact(_profile);_folder=_variant['build']
    C.VERSIONS[_profile]=dict(dat=str(_variant['dat'].relative_to(C.ROOT)),
        sha=__import__('json').loads(_variant['manifest'].read_text())['dat_sha256'],
        elf=str((_folder/'engine.elf').relative_to(C.ROOT)),engine=str(C.ENGINE.relative_to(C.ROOT)),
        body='firmware/image_v310/local/ilaunch3',resident=C.BODY)

p = argparse.ArgumentParser()
p.add_argument('--dataset',choices=('control','model'),default='control')
p.add_argument('--version', choices=tuple(C.VERSIONS), default='test')
p.add_argument('--unit', choices=C.UNITS, default='mount')
p.add_argument('--backend', choices=('native', 'reference'), required=True)
p.add_argument('--reference-oracle', choices=('strict_r4','legacy'), default='strict_r4')
p.add_argument('--label', required=True)
p.add_argument('--action', choices=('sweep', 'menu', 'restore', 'session'), default='sweep')
p.add_argument('--session-row', type=int, default=2, help='zero-based flat-list row selected by native GPIO')
p.add_argument('--close-key', choices=('OK','ADJ'), default='OK')
p.add_argument('--settings', type=Path)
p.add_argument('--require-vivid',action='store_true',help='require persistent valid native Vivid code 09 from the declared S input')
p.add_argument('--fault',choices=('none','rpc-once','rpc-persistent','preview-once','alloc-main','manual-persistent','manual-once'),default='none')
p.add_argument('--expect-final',type=Path,help='complete record after explicit session apply')
p.add_argument('--expected', type=Path, help='expected complete 552-byte state after BOOT, before first menu')
p.add_argument('--expected-stock04',action='store_true',help='require the unit-specific complete stock 04 after BOOT')
p.add_argument('--root-index', type=int, default=0)
p.add_argument('--upgrade-files', type=Path, help='existing directory with 29 upgrade files; does not execute update mode')
p.add_argument('--fragmented', action='store_true')
p.add_argument('--timestamp', type=lambda s:int(s, 0), default=0)
p.add_argument('--only', help='comma-separated Look ordinals, zero based')
p.add_argument('--order', help='explicit permutation of selected Look ordinals')
p.add_argument('--dial',choices=('AUTO','P','A','M','S'),default='M')
p.add_argument('--raw-mode',type=lambda x:int(x,0))
p.add_argument('--submode',type=lambda x:int(x,0))
p.add_argument('--selection',type=lambda x:int(x,0))
p.add_argument('--my',type=int,default=0)
p.add_argument('--pending',type=int,default=0)
p.add_argument('--challenge', choices=('none','boot-activity6','boot-raw255','boot-mode4','boot-both','boot-vivid','boot-wb','no-dispatch','list6','absent'), default='none')
a = p.parse_args()
assert not (a.expected and a.expected_stock04)
assert a.label.isascii() and '/' not in a.label and '\\' not in a.label
C.setup();C.compute_gate('cold-'+a.label)
signal.alarm(5000)
os.environ.update(GXR_FAST_BACKEND=a.backend, GXR_FAST_POLICY='strict', GXR_EMULATOR_BATCH='1', GXR_FAST_MODEL_FIXES='nand-word,preview-link,sd-long-response,nand-read-tail')
sys.path.insert(0, str(C.FAST))
if a.reference_oracle=='legacy':
    assert a.backend=='reference'
    # The independent reference import route already used by
    # strict_r4_final/scripts/runner.py and field_gate_r1/local/run.py.
    import importlib,importlib.util
    legacy=C.ROOT/'tools/gxr_emulator_fast/fix_r1'
    sys.path.remove(str(C.FAST));sys.path.insert(0,str(legacy));sys.path.append(str(C.FAST))
    for name in ('backend','devices','models','board','peripherals','sdcard','unit_link','unit_peer','m2','observe','lazy_state','panel','storage_run','outputs','snapshots'):
        importlib.import_module(name)
    spec=importlib.util.spec_from_file_location('input_run',C.FAST/'input_run.py')
    module=importlib.util.module_from_spec(spec);sys.modules['input_run']=module;spec.loader.exec_module(module)
    sys.path.remove(str(C.FAST));sys.path.insert(1,str(C.FAST))
# Both backends use the r4 entrypoint. The reference backend executes Python devices.
import storage_run, outputs, native_controls as N
v = C.VERSIONS[a.version]
raw = (C.ROOT/v['dat']).read_bytes()
assert C.sha(raw) == v['sha']
E = _load('g158_field_elf', C.ROOT/'firmware/stage2l_switch/tools/build.py').Elf(C.ROOT/v['elf'])
syms = {n:r['value'] for n,r in E.symbols.items()}
eng_section = next(r for r in E.sections if r['name']=='.engine')
assert E.content(eng_section) == raw[256:256+C.D.u32(raw, 136)]
offsets = json.loads((C.LOCAL/'layout.json').read_text())['offsets']
out = C.LOCAL/'runs'/a.label
out.mkdir(parents=True, exist_ok=False)
outputs.declare_media(out)
storage_run.OUT = out
medium = out/'medium.img'
medium_data=C.medium_bytes(raw, a.root_index, a.fragmented, a.timestamp)
upgrade_manifest=None
if a.upgrade_files:
    assert not a.root_index and not a.fragmented and a.challenge=='none'
    medium_data,upgrade_manifest=C.upgrade_medium(raw,a.upgrade_files)
if a.challenge=='absent':
    F=_load('g158_absent_fat',C.ROOT/'tools/gxr_emulator_standby/fat_image.py')
    entry=(F.START+1+2*F.FAT_SECTORS)*512+32*a.root_index
    assert medium_data[entry:entry+11]==b'GXRCE   DAT'
    medium_data[entry:entry+11]=b'MISSING DAT'
medium.write_bytes(medium_data)
settings = a.settings
if settings is None:
    block = bytearray((C.ROOT/'research/field_gate_r1/local/inputs-v3-auto/g156-test-A.bin').read_bytes())
    block[0xfd4:0xffc] = bytes(40)
    block[-4:] = (sum(struct.unpack('>2046H', block[:4092])) & 0xffffffff).to_bytes(4, 'big')
    settings = out/'input-S.bin'
    settings.write_bytes(block)
result = dict(status='RUNNING', version=a.version, unit=a.unit, backend=a.backend,reference_oracle=a.reference_oracle,
    cold_start=True, snapshots=False, dataset=C.DATASET, dat_sha256=C.sha(raw), body_sha256=C.sha((C.ROOT/v['body']).read_bytes()),
    settings_sha256=C.sha(settings.read_bytes()), input_medium_sha256=C.sha(medium.read_bytes()),
    action=a.action, session_row=a.session_row, close_key=a.close_key,
    root_index=a.root_index, fragmented=a.fragmented, timestamp=a.timestamp, challenge=a.challenge,
    keys=[], samples=[], model_fixes=os.environ['GXR_FAST_MODEL_FIXES'],fault=a.fault,fault_events=[])
if upgrade_manifest:
    result['upgrade_files']=upgrade_manifest
    result['upgrade_boundary']='Normal MAIN with existing upgrade filenames on media. No firmware updater, flash, or post-update reset is simulated.'
(out/'driver.py').write_bytes(Path(__file__).read_bytes())
(out/'common.py').write_bytes(Path(C.__file__).read_bytes())
m = None
base = None
start = time.monotonic()
def save(): C.save(out/'result.json', result)
try:
    m = storage_run.Machine(str(medium))
    c = m.cpu
    c.set_mode('fast')
    c.set_batch(True)
    N.prepare(m, body=C.ROOT/v['body'], unit=a.unit, settings=settings, late_ready=True)
    N.extend_keys(m)
    resident = {}
    for line in (C.ROOT/v['resident']/'local/resident/symbols.log').read_text().splitlines():
        cols = line.split()
        if len(cols)>=5:
            try: resident[cols[-1]] = int(cols[0], 16)
            except ValueError: pass
    N.engine_watch(m, resident['rv_engine'], a.version!='g154')
    challenge_at=resident['rv_engine'] if a.challenge=='none' else None
    if a.challenge in ('boot-activity6','boot-raw255','boot-mode4','boot-both','boot-vivid','boot-wb','no-dispatch'):
        challenge_at=resident['rv_hook_51'] if a.challenge=='no-dispatch' else resident['rv_engine']
    elif a.challenge=='list6':
        challenge_at=0x20287080
    challenge_previous=c.breakpoints.get(challenge_at) if challenge_at is not None else None
    if challenge_at is not None:N.stop_at(c,challenge_at,task=6)
    def u(at, n=4): return int.from_bytes(c.read(at, n), 'big')
    def at(name):
        if name.startswith('g.'):return u(base+syms['g'])+offsets[name]
        return base+syms[name.split('.')[0]]+offsets[name]
    def state():
        s = u(0x200c0dac)
        d = dict(steps=c.steps, state=u(0x205d9c00), activity=u(0x205d9bf8), word=u(0x200547ec),
            root_state=u(0x20054705, 1), inflight=u(0x20054706, 1), flags=u(0x200547d4),
            fault=u(0x2005475c), check_failure=u(0x20054798), rows=u(0x2022f5ac, 1),
            raw_mode=u(0x205d9a7f,1),submode=u(0x205d9a9f,1),MY=u(0x205d9aa3,1),pending=u(0x205da00b,1),
            settings_bytes=u(0x200c0db0),native_selection=u(s+0x2fc) if s else None,
            selector=u(s+0x36e, 1) if s else None, wb=list(c.read(s+0x6dd, 2)) if s else None,
            record=c.read(s+0xfd4, 40).hex() if s else None)
        if base:
            d.update(screen=u(at('n.ui.screen'),1), cur=u(at('n.ui.cur'),1), count=u(at('n.ui.count'),1),
                cursor=u(0x2022f726,1), cached=u(0x205a2944,1), physical=u(at('n.ui.physical'),1), top=u(at('n.ui.top'),1),
                current=list(c.read(at('g.current'),2)), levels=list(struct.unpack('>10h', c.read(at('g.tweak'),20))),
                memory_dirty=u(at('g.memory_dirty'),1), memory_blocked=u(at('g.memory_blocked'),1),
                # Contiguous uint8 members in the frozen Engine declaration,
                # anchored to independently compiled layout fields.
                restore_done=u(at('g.restore_done'),1),baseline=u(at('g.baseline'),1),
                boot_committed=u(at('g.boot_committed'),1),
                memory_result=u(at('g.memory_result'),1),memory_error=u(at('g.memory_error'),1),
                saved_levels=list(struct.unpack('>10h',c.read(at('g.saved.levels'),20))),
                saved_reference=list(c.read(at('g.saved.ref'),2)),saved_user=u(at('g.saved.user'),1),
                settings_pending=u(at('g.settings_pending'),1), uncertain=u(at('g.uncertain'),1),
                text=[b.split(b'\0')[0].decode('ascii','replace') for b in struct.unpack('14s'*8,c.read(at('n.ui.text'),112))],
                live_sha256=C.sha(c.read(at('g.live'),552)))
            if 'd' in syms:
                diagnostic=u(base+syms['d'])
                if diagnostic:d['diagnostic']={k:u(diagnostic+offsets['diag.'+k],1 if k in ('mode','submode','my','pending','seen','entry','reason','stage','shown','record') else 4) for k in ('failed','activity','state','selection','settings','length','mode','submode','my','pending','seen','entry','reason','stage','shown','record')}
        return d
    def capture_published(label):
        st=state()
        if not base or st['rows']!=8:return
        table=u(0x2022f5a8);rows=[]
        for i,text in enumerate(st['text']):
            descriptor=u(table+4*i);pointer=u(descriptor);glyphs=c.read(pointer,70).split(b'\0')[0]
            encoded=text.encode('ascii');assert len(glyphs)==2*len(encoded),(label,i,text,glyphs)
            rows.append(dict(row=i,text=text,ascii_hex=encoded.hex(),glyphs_hex=glyphs.hex(),
                characters=[dict(column=j,character=ch,ascii=ord(ch),glyph=glyphs[2*j:2*j+2].hex()) for j,ch in enumerate(text)],
                row_descriptor=descriptor,lcd_text_pointer=pointer))
        C.save(out/('ui-'+label+'.json'),dict(status='CAPTURED',run=a.label,DAT_sha256=C.sha(raw),
            backend=a.backend,screen=st['screen'],rows=rows,pixel_screenshot=False,
            source='Read-only capture of the eight published native row descriptors and their actual glyph buffers.'))
    def unit_readback(expected):
        actual=bytearray(c.read(at('g.live'),552))
        peer=m.devices['startup'].rpc_state
        overlay=dict(peer.get('overlay',{}))
        rom=(C.ROOT/'artifacts/firmware/gxr-1.51'/('jlaunch3','qlaunch3','l08firm3')[C.UNITS.index(a.unit)]).read_bytes()
        sections=[struct.unpack_from('>5I',rom,32+20*i) for i in range(16)]
        directory=C.D.u32(raw,156)+64*C.UNITS.index(a.unit)
        mapping=C.D.u32(raw,directory+12)
        for i in range(9):
            address,size,offset=struct.unpack_from('>IHH',raw,mapping+32+12*i)
            data=[]
            for addr in range(address,address+size):
                if (addr&~1) in overlay:
                    byte=overlay[addr&~1]>>(0 if addr&1 else 8)&255
                else:
                    off,start,n,_,_=next(row for row in sections if row[1]<=addr<row[1]+row[2])
                    byte=rom[512+off+addr-start]
                data.append(byte)
            actual[offset:offset+size]=bytes(data)
        struct.pack_into('>H',actual,445,peer.get('t',2))
        actual=C.D.refresh_entry(actual)
        if expected is None:
            def colour(record):
                parts=[]
                for i in range(9):
                    offset=C.D.u16(raw,mapping+32+12*i+6);size=C.D.u16(raw,mapping+32+12*i+4)
                    parts.append(record[offset:offset+size])
                return parts+[record[445:447]]
            stock=C.D.expand(raw,C.UNITS.index(a.unit),4)
            target=(C.LOCAL/'settings/test-mount-HC1.record552').read_bytes()
            return dict(record552_hex=bytes(actual).hex(),sha256=C.sha(actual),equals_stock_owned_rows_T=colour(actual)==colour(stock),equals_HC1_owned_rows_T=colour(actual)==colour(target),RPC_entries=len(peer.get('log',[])))
        assert actual==expected
        return dict(complete_552_equal=True,nine_rows_and_T_from_unit_peer=True,
            metadata_from_engine=True,sha256=C.sha(actual),rpc_entries=len(peer.get('log',[])))
    fault_points={};fault_writes=0
    def fault_arm(address,phase):
        previous=c.breakpoints.get(address);fault_points[address]=(phase,previous);N.stop_at(c,address,task=26 if phase=='capture' else 6)
    def fault_drop(address):
        phase,previous=fault_points.pop(address);c.breakpoints.pop(address)
        if previous is not None:c.breakpoints[address]=previous
        return phase
    if a.fault not in ('none','manual-persistent','manual-once'):fault_arm(resident['rv_native_alloc'] if a.fault=='alloc-main' else resident['rv_engine'],'alloc' if a.fault=='alloc-main' else 'arm')
    def run(count):
        global fault_writes
        began=c.steps
        while True:
            stop=c.run(count-(c.steps-began))
            if stop.reason=='breakpoint' and stop.pc in fault_points:
                address=stop.pc;phase=fault_drop(address)
                if phase=='alloc':
                    size=c.get_reg('r0')
                    if size==7628+C.D.align4(len(raw)+C.D.u32(raw,116)):
                        result['fault_events'].append(dict(phase=phase,requested=size,declared_return=0,step=c.steps))
                        c.set_reg('r0',0);c.set_reg('pc',c.get_reg('r14'))
                    else:
                        assert c.run(1).reason=='max_steps';fault_arm(address,phase)
                elif phase=='arm':
                    if u(c.get_reg('r2')+40)==0x101:
                        loaded=u(0x20054770)-256
                        assert loaded>=0x20000000
                        target=loaded+syms['rv_native_preview' if a.fault=='preview-once' else 'write_word']
                        fault_arm(target,'entry' if a.fault=='preview-once' else 'write-entry')
                        assert c.run(1).reason=='max_steps'
                    else:
                        assert c.run(1).reason=='max_steps';fault_arm(address,phase)
                elif phase=='write-entry':
                    fault_writes+=1
                    qualifies=fault_writes>=8 if a.fault in ('rpc-persistent','manual-persistent') else fault_writes==8
                    if qualifies:
                        loaded=u(0x20054770)-256
                        fault_arm(loaded+syms['rv_rpc8_native'],'wire-entry')
                    assert c.run(1).reason=='max_steps'
                    if a.fault in ('rpc-persistent','manual-persistent') or not qualifies:fault_arm(address,'write-entry')
                elif phase=='wire-entry':
                    assert c.get_reg('r0')==22
                    fault_arm(c.get_reg('r14'),'return')
                    assert c.run(1).reason=='max_steps'
                elif phase=='entry':
                    if a.fault=='preview-once':qualifies=True
                    elif c.get_reg('r0')==22:
                        fault_writes+=1;qualifies=fault_writes>=8 if a.fault=='rpc-persistent' else fault_writes==8
                    else:qualifies=False
                    if qualifies:fault_arm(c.get_reg('r14'),'return')
                    assert c.run(1).reason=='max_steps'
                    if a.fault=='rpc-persistent' or not qualifies:fault_arm(address,'entry')
                elif phase=='capture':
                    result.setdefault('manual_at_H40',[]).append(dict(state=state(),unit=unit_readback(None),step=c.steps))
                else:
                    actual=c.get_reg('r0');replacement=1 if a.fault=='preview-once' else 0xffffffff
                    result['fault_events'].append(dict(phase='after-actual-native-call',native_return=actual,declared_return=replacement,W_position=fault_writes,step=c.steps))
                    c.set_reg('r0',replacement)
                continue
            if stop.reason=='breakpoint' and stop.pc==challenge_at and 'challenge_applied' not in result:
                before=state()
                premature=(a.challenge=='no-dispatch' and not (before['word']==1 and before['state']==5 and before['root_state']!=255))
                if challenge_at==resident['rv_engine'] and u(c.get_reg('r2')+40)!=0x101:premature=True
                if premature:
                    c.breakpoints.pop(challenge_at)
                    if challenge_previous is not None:c.breakpoints[challenge_at]=challenge_previous
                    assert c.run(1).reason=='max_steps'
                    N.stop_at(c,challenge_at,task=6)
                    continue
                if a.challenge=='none':
                    mode,sub,selection={'AUTO':(0,0,0x8001),'P':(4,0,0x8010),'A':(4,1,0x8020),'M':(4,2,0x8008),'S':(4,3,0x8800)}[a.dial]
                    if a.raw_mode is not None:mode=a.raw_mode
                    if a.submode is not None:sub=a.submode
                    if a.selection is not None:selection=a.selection
                    c.write(0x205d9a7f,bytes([mode]));c.write(0x205d9a9f,bytes([sub]))
                    c.write(0x205d9aa3,bytes([a.my]));c.write(0x205da00b,bytes([a.pending]))
                    c.write(u(0x200c0dac)+0x2fc,selection.to_bytes(4,'big'))
                    result['declared_dial']=dict(dial=a.dial,mode=mode,submode=sub,N=selection,MY=a.my,pending=a.pending,
                        source='PASM mode/submode/N measured on g157 MOUNT. Emulated RAM boundary declaration; no physical dial or camera claim.')
                if a.challenge=='boot-activity6':c.write(0x205d9bf8,(6).to_bytes(4,'big'))
                elif a.challenge=='boot-raw255':c.write(0x205d9a7f,b'\xff')
                elif a.challenge=='boot-mode4':c.write(0x205d9a7f,b'\x04')
                elif a.challenge=='boot-both':
                    c.write(0x205d9bf8,(6).to_bytes(4,'big'));c.write(0x205d9a7f,b'\x04')
                elif a.challenge=='boot-vivid':c.write(u(0x200c0dac)+0x36e,b'\x09')
                elif a.challenge=='boot-wb':c.write(u(0x200c0dac)+0x6dd,b'\x0a')
                elif a.challenge=='no-dispatch':c.write(0x200547ec,(2).to_bytes(4,'big'))
                elif a.challenge=='list6':c.write(0x2022f5ac,b'\x06')
                result['challenge_applied']=dict(before=before,after=state(),layer='Explicit RAM boundary challenge; not a physical camera observation')
                c.breakpoints.pop(challenge_at)
                if challenge_previous is not None:c.breakpoints[challenge_at]=challenge_previous
                continue
            return stop
    if a.require_vivid and a.backend=='reference':
        result['Vivid_selector_stores']=[]
        followed=set()
        def attach_selector(s):
            if 0x20000000<=s<=0x207ff000 and s not in followed:
                followed.add(s)
                def wrote(address,data):
                    target=s+0x36e
                    if address<=target<address+len(data):
                        result['Vivid_selector_stores'].append(dict(step=c.steps,pc=c.get_reg('pc'),S=s,value=data[target-address]))
                c.add_write_trace(s,s+4096,wrote)
        def pointer_changed(address,data):attach_selector(u(0x200c0dac))
        c.add_write_trace(0x200c0dac,0x200c0db0,pointer_changed)
        attach_selector(u(0x200c0dac));attach_selector(0x204b0b94)
    for _ in range(13):
        stop = run(50000000)
        assert stop.reason in ('max_steps','breakpoint'), stop
        result['cold_progress']=state()
        save()
        if stop.reason=='breakpoint' or (a.fault!='none' and state()['state']==5 and state()['root_state']==6) or (a.version=='g154' and state()['state']==5 and c.steps>=50000000) or (a.challenge=='absent' and state()['state']==5 and state()['root_state']==6) or (a.challenge=='no-dispatch' and state()['state']==5 and c.steps>=50000000): break
    else: raise RuntimeError('cold start budget exhausted')
    result['cold'] = state()
    base = u(0x20054770)-256
    if base<0x20000000: base = None
    result['after_boot'] = state()
    if a.fault not in ('none','manual-persistent','manual-once'):
        assert result['fault_events'],a.fault
        if state()['word']&4:
            result['before_H51_guard_latch']=state()
            assert run(2000000).reason=='max_steps'
            result['after_boot']=state()
        result['fault_safety']=dict(boot_word=state()['word'],root_state=state()['root_state'],guarded=bool(state()['word']&12))
        if a.fault!='alloc-main' and state()['word']&4:assert state()['word']&8
        if a.fault in ('rpc-once','preview-once'):
            result['compensation_unit_rows']=unit_readback(C.D.expand(raw,C.UNITS.index(a.unit),4))
    if a.challenge in ('boot-vivid','boot-wb'):
        after=state();snapshot=after['diagnostic']
        result['BOOT_W']=sum(r['cmd']==22 for r in m.devices['startup'].rpc_state.get('log',[]))
        assert snapshot['reason']==20 and snapshot['failed']&128 and after['memory_result']==1 and not after['boot_committed'] and result['BOOT_W']==0
        assert after['selector']==9 if a.challenge=='boot-vivid' else after['wb'][0]==10
    if a.require_vivid:
        after=state();snapshot=after['diagnostic']
        assert settings.read_bytes()[0x36e]==9
        assert after['selector']==9 and after['memory_result']==1 and not after['boot_committed']
        assert snapshot['failed']&128 and not snapshot['seen']&8
        assert after['saved_levels']==list(struct.unpack('>10h',settings.read_bytes()[0xfdc:0xff0]))
        assert after['record']==settings.read_bytes()[0xfd4:0xffc].hex()
        result['BOOT_W']=sum(r['cmd']==22 for r in m.devices['startup'].rpc_state.get('log',[]))
        assert result['BOOT_W']==0
        result['persistent_vivid_BOOT_skip']=True

    if u(0x200c0dac):
        (out/'cold-S.bin').write_bytes(c.read(u(0x200c0dac),4096))
    (out/'cold-root.bin').write_bytes(c.read(0x20054700,256))
    if base:
        (out/'cold-live-552.bin').write_bytes(c.read(at('g.live'),552))
    if a.expected or a.expected_stock04:
        expected=a.expected.read_bytes() if a.expected else C.D.expand(raw,C.UNITS.index(a.unit),4)
        assert len(expected)==552 and base
        assert c.read(at('g.live'),552)==expected
        result['BOOT_expected_552_equal']=True
        result['BOOT_expected_sha256']=C.sha(expected)
        result['BOOT_unit_readback']=unit_readback(expected)
    save()
    if a.backend=='reference' and base:
        # Read-only call/return observers. No simulated result is changed.
        result['memory_calls']=[]
        trace_pending={}
        trace_returns=set()
        def trace_entry(name):
            def entered(current):
                ret=current.get_reg('lr')
                key=(m.task(),ret,current.get_reg('spu'))
                row=dict(name=name,step=current.steps,argument=current.get_reg('r0'))
                if name=='owned_record':
                    record=current.read(current.get_reg('r0'),40)
                    row.update(record_sha256=C.sha(record),record_code=record[5],record_unit=record[6])
                trace_pending.setdefault(key,[]).append(row)
                if ret not in trace_returns:
                    trace_returns.add(ret)
                    previous=c.breakpoints.get(ret)
                    def returned(cpu,ret=ret,previous=previous):
                        prior=previous(cpu) if previous else False
                        stack=trace_pending.get((m.task(),ret,cpu.get_reg('spu')))
                        if stack:
                            item=stack.pop()
                            value=cpu.get_reg('r0')
                            item.update(return_step=cpu.steps,result=value-(1<<32) if value&(1<<31) else value)
                            result['memory_calls'].append(item)
                        return prior
                    c.add_breakpoint(ret,returned)
                return False
            return entered
        for name in ('memory_op','owned_record'):
            assert name in syms
            c.add_breakpoint(base+syms[name],trace_entry(name))
    def key(name):
        old = state()
        N.key(m.panel, name, True)
        assert run(400000).reason=='max_steps'
        N.key(m.panel, name, False)
        windows = []
        for _ in range(90):
            stop = run(10000000)
            assert stop.reason=='max_steps', stop
            windows.append(10000000)
            st = state()
            stable = ((st['state']==5 and st['activity']==0) or (st['state']==56 and st['activity']!=0)) and st['word'] in (2,6,14) and st['inflight']==0
            if st['state']==56 and st['rows']==8 and base:
                stable &= st['cursor']==st['cached']==st['physical']+1 and st['cur']==st['top']+st['physical']
            changed = any(st.get(k)!=old.get(k) for k in ('state','activity','screen','cur','count','rows'))
            if stable and changed:
                assert run(2000000).reason=='max_steps'
                windows.append(2000000)
                final=state()
                if not ((final['state']==5 and final['activity']==0) or (final['state']==56 and final['activity']!=0)) or final['word'] not in (2,6,14) or final['inflight']:continue
                if final['state']==56 and final['rows']==8 and base:
                    if not (final['cursor']==final['cached']==final['physical']+1 and final['cur']==final['top']+final['physical']):continue
                break
        else: raise RuntimeError('key did not settle '+name)
        st = state()
        result['keys'].append(dict(key=name, windows=windows, state=st))
        save()
        return st
    for name in ('ADJ', *['ADJ_RIGHT']*6):
        st = key(name)
        if st['state']==56 and st['activity']==8: break
    # Do not treat activity 8 as a completed load.
    result['publication_wait']=[]
    for _ in range(60):
        current=state()
        result['publication_wait'].append({k:current[k] for k in ('steps','root_state','inflight','rows')})
        if current['root_state'] in (5,6) or (current['root_state'] not in (1,2) and not current['inflight']):break
        assert run(10000000).reason=='max_steps'
    else:raise RuntimeError('first ADJ publication did not finish')
    assert run(10000000).reason=='max_steps'
    if base is None:
        b = u(0x20054770)-256
        if b>=0x20000000: base = b
    result['first_menu'] = state()
    capture_published('first-adj')
    if base and state()['rows']==8:
        context=u(base+syms['n']+4);engine_state=u(base+syms['g']);diagnostic=u(base+syms['d'])
        private=u(context+24);ui=u(context+64);capacity=u(context+72)
        main=u(0x20054700+offsets['root.block_bytes'])
        assert engine_state==private and diagnostic==private+5120 and engine_state+5004<=diagnostic
        assert diagnostic+60<=private+6144 and ui==private+6144 and ui+capacity<=u(0x20054700+offsets['root.block'])+main
        result['private_ranges']=dict(engine=engine_state,diagnostic=diagnostic,ui=ui,ui_capacity=capacity,main_request=main,disjoint=True)
        fixture=out/'service-fixture';fixture.mkdir(exist_ok=True)
        regions=[(0x05000000,0x20000),(0x20000000,0x800000)]
        root=0x20054700
        block=u(root+offsets['root.block']);amount=u(root+offsets['root.block_bytes'])
        if not (0x20000000<=block and block+amount<=0x20800000):regions.append((block-12,amount+12))
        ui_block=u(root+offsets['root.ui_block'])
        if ui_block and not any(lo<=ui_block and ui_block+1968<=lo+n for lo,n in regions):regions.append((ui_block-12,1980))
        manifest=[]
        for i,(lo,n) in enumerate(regions):
            content=c.read(lo,n);file=fixture/(str(i)+'.bin');file.write_bytes(content)
            manifest.append(dict(address=lo,bytes=n,file=str(file.relative_to(C.ROOT)),sha256=C.sha(content)))
        C.save(fixture/'manifest.json',dict(regions=manifest,image_base=base,DAT_sha256=C.sha(raw),root=root,block=block,
            scope='Declared function-call input captured after a new MAIN. Not a CPU/device checkpoint and never used to resume an emulator.'))
    assert st['state']==56 and st['activity']==8
    if state()['rows']==8 and state()['screen']==5:
        result['diagnostic_page']=state()
        assert len(state()['text'])==8 and state()['text'][0].startswith('G158B')
        key('OK');assert state()['screen']==0 and state()['state']==56
        result['list_after_diagnostic']=state()
        capture_published('list-after-diagnostic')
    if a.require_vivid:
        st=state();assert st['selector']==9 and not st['baseline'] and not st['boot_committed']
        assert st['record']==settings.read_bytes()[0xfd4:0xffc].hex()
        assert st['saved_levels']==list(struct.unpack('>10h',settings.read_bytes()[0xfdc:0xff0]))
        assert result.get('diagnostic_page',{}).get('diagnostic',{}).get('reason')==20
        assert result['diagnostic_page']['selector']==9
        assert not any(text.startswith('>04') for text in st['text'])
        result['persistent_vivid_menu_not_04']=True
        if a.backend=='reference':
            stores=result['Vivid_selector_stores'];first=next(i for i,row in enumerate(stores) if row['value']==9)
            assert all(row['value']==9 for row in stores[first:]),stores
            result['Vivid_unchanged_since_valid_load']=True
    if a.fault in ('manual-persistent','manual-once'):
        result['manual_before']=state()
        result['unit_before_manual']=unit_readback(None)
        assert state()['rows']==8 and state()['screen']==0 and state()['cur']==2
        assert state()['memory_result']==1 and state()['selector']==9 and not state()['baseline']
        fault_arm(base+syms['write_word'],'write-entry')
        key('OK')
        result['manual_after_failure']=state();capture_published('manual-error')
        result['unit_after_manual_failure']=unit_readback(None)
        assert result['fault_events']
        result['manual_partial_rows']=dict(live_sha256=state()['live_sha256'],stock_sha256=C.sha(C.D.expand(raw,C.UNITS.index(a.unit),4)),expected_sha256=C.sha((C.LOCAL/'settings/test-mount-HC1.record552').read_bytes()))
        if state()['state']!=5:key('ADJ')
        result['manual_error_dismissed']=state()
        result['shutter_boundary']='Actual unchanged H52 instructions are exercised by the separate C/Python shutter probe; no physical JPEG claim.'
        before=result['unit_before_manual'];after=result['unit_after_manual_failure']
        assert before['equals_stock_owned_rows_T']
        guarded=bool(state()['word']&12)
        assert after['equals_stock_owned_rows_T'] or guarded, (after,state())
        if a.fault=='manual-once':assert len(result['fault_events'])==1
        if a.fault=='manual-once':assert after['equals_stock_owned_rows_T'],after
        result['manual_unguarded_partial_standby']=False
        result['manual_safety_PASS']=True
        result['compensated_to_complete04']=after['equals_stock_owned_rows_T']
        result['guard_latched']=guarded
        result['physical_JPEG_verified']=False
        exported=N.export_state(m)
        flow=exported.get('flow',{})
        result['manual_capture_flow']=dict(counts=flow.get('counts'),rows=[row for row in flow.get('rows',[]) if row.get('kind') in ('H52-point','MANUAL_H40-point')])
        result['status']='OBSERVED'
    elif state()['rows'] != 8:
        result['status']='FACTORY_LIST'
    elif a.action=='session':
        assert 0<=a.session_row<state()['count']
        for _ in range(50):
            st=state()
            if st['cur']==a.session_row:break
            down=(a.session_row-st['cur'])%st['count']
            up=(st['cur']-a.session_row)%st['count']
            key('RIGHT' if down<=up else 'UP')
        else:raise RuntimeError('session target not reached')
        result['selected']=state()
        (out/'selected-S.bin').write_bytes(c.read(u(0x200c0dac),4096))
        key(a.close_key)
        result['after_close_key']=state()
        if a.close_key=='OK' and state()['state']==56:key('OK')
        result['after_close']=state()
        assert state()['state']==5,result['after_close']
        (out/'final-S.bin').write_bytes(c.read(u(0x200c0dac),4096))
        (out/'final-root.bin').write_bytes(c.read(0x20054700,256))
        (out/'final-live-552.bin').write_bytes(c.read(at('g.live'),552))
        result['status']='OBSERVED'
    elif a.action=='sweep':
        area,_ = C.D.effect_area(raw)
        unit_index = C.UNITS.index(a.unit)
        looks = []
        for i in range(C.D.u16(raw, area+10)):
            e = raw[area+32+32*i:area+64+32*i]
            if e[18]>>unit_index&1:
                looks.append(dict(index=i, name=e[20:].split(b'\0')[0].decode()))
        selected = set(map(int,a.only.split(','))) if a.only else set(range(len(looks)))
        order=list(map(int,a.order.split(','))) if a.order else sorted(selected)
        assert set(order)==selected and len(order)==len(selected)
        def select_flat(target):
            for _ in range(50):
                st=state()
                if st['cur']==target:return
                down=(target-st['cur'])%st['count'];up=(st['cur']-target)%st['count']
                key('RIGHT' if down<=up else 'UP')
            raise RuntimeError('flat row not reached')
        def assert_record(code):
            st=state();record=c.read(u(0x200c0dac)+0xfd4,40)
            wire=b'GXR2'+bytes((3,code,unit_index,1))+struct.pack('>10h',*st['levels'])+raw[20:28]
            wire+=__import__('zlib').crc32(wire).to_bytes(4,'big')
            assert record==wire and not st['memory_dirty'] and not st['memory_error']
            assert st['cursor']==st['cached']==st['physical']+1
        if not a.only:
            result['builtin_samples']=[]
            for slot in range(1,9):
                select_flat(slot-1);expected=C.D.expand(raw,unit_index,slot)
                assert c.read(at('g.live'),552)==expected;assert_record(slot)
                result['builtin_samples'].append(dict(slot=slot,full_40_equal=True,state=state(),unit_readback=unit_readback(expected)))
                save()
        for ordinal in order:
            look=looks[ordinal]
            target = 8+ordinal
            if a.only and state()['cur']==target:
                # A remembered row can have focus while release intentionally
                # leaves 04 active. Leave and return through actual GPIO so
                # the selected recipe is explicitly applied in either policy.
                key('UP');key('RIGHT')
                result['explicit_reselect']=True
            for _ in range(50):
                st = state()
                if st['cur']==target: break
                down = (target-st['cur'])%st['count']
                up = (st['cur']-target)%st['count']
                key('RIGHT' if down<=up else 'UP')
            else: raise RuntimeError('navigation target not reached')
            st = state()
            expected = C.D.expand_effect(raw, look['index'])
            assert c.read(at('g.live'),552)==expected, look
            record=c.read(u(0x200c0dac)+0xfd4,40)
            literal=b'GXR2'+bytes((3,64+look['index'],unit_index,1))+struct.pack('>10h',*st['levels'])+raw[20:28]
            literal+=__import__('zlib').crc32(literal).to_bytes(4,'big')
            assert record==literal and not st['memory_dirty'] and not st['memory_error']
            assert st['cursor']==st['cached']==st['physical']+1
            sample = dict(look, full_40_equal=True, ordinal=ordinal, expected_code=0x40+look['index'], complete_552_equal=True, state=st)
            sample['unit_readback']=unit_readback(expected)
            result['samples'].append(sample)
            (out/(f'look-{ordinal}-S.bin')).write_bytes(c.read(u(0x200c0dac),4096))
            print(json.dumps(dict(label=a.label, name=look['name'], dirty=st['memory_dirty'], stored_code=st['record'][10:12], text=st['text'])),flush=True)
            save()
        if not a.only:
            math_ref=C.load(C.HERE/'math_reference.py','g158_menu_math');reference=math_ref.Reference()
            result['user_samples']=[]
            for user in range(3):
                slot,levels=math_ref.user_record(raw,user);select_flat(8+len(looks)+user)
                expected=reference.compute(raw,unit_index,C.D.expand(raw,unit_index,slot),levels)
                assert state()['levels']==levels and c.read(at('g.live'),552)==expected;assert_record(128+user)
                result['user_samples'].append(dict(user=user+1,slot=slot,full_40_equal=True,state=state(),unit_readback=unit_readback(expected)))
                save()
        result['before_DISP']=state()
        close_record=c.read(u(0x200c0dac)+0xfd4,40)
        key('DISP');assert state()['state']==56 and state()['screen']==1
        result['DISP_card']=state()
        key('UP');assert state()['screen']==1 and state()['cur']==0
        result['DISP_title']=state()
        key('DISP');assert state()['state']==56 and state()['screen']==0
        result['DISP_back']=state()
        # Exercise real confirmation and reopening of the last selected Look.
        key('OK')
        result['after_OK']=state()
        if state()['state']==56: key('OK')
        result['after_close']=state()
        assert state()['state']==5
        key('ADJ');assert state()['state']==56 and state()['rows']==8
        result['reopened']=state()
        assert state()['cursor']==state()['cached']==state()['physical']+1
        key('ADJ');assert state()['state']==5
        result['ADJ_closed']=state()
        assert c.read(u(0x200c0dac)+0xfd4,40)==close_record
        result['close_record_equal']=True
        save()
        (out/'final-S.bin').write_bytes(c.read(u(0x200c0dac),4096))
        result['status']='OBSERVED'
    else:
        result['status']='OBSERVED'
    if a.expect_final:
        expected=a.expect_final.read_bytes();assert len(expected)==552
        assert c.read(at('g.live'),552)==expected
        result['explicit_expected_552_equal']=True
        result['explicit_unit_readback']=unit_readback(expected)
    export=N.export_state(m)
    _flow=export.get('flow',{});result['flow']=dict(counts=_flow.get('counts'),BOOT=[r for r in _flow.get('rows',[]) if 'BOOT' in r.get('kind','')])
    result['io_counts']={str(k):v for k,v in c.io_counts.items()}
    nand=m.devices['nand']
    result['NAND_model']={name:getattr(nand,name) for name in ('writes','erases','program_count','erase_count') if hasattr(nand,name)}
    result['NAND_model']['commands']=list(nand.commands)
    result['NAND_model_boundary']='A zero write count does not establish power-off persistence; explicit exported S replay is reported separately.'
    rpc = [dict(r) for r in m.devices['startup'].rpc_state.get('log',[])]
    C.save(out/'rpc.json',rpc)
    result['unit_W']=sum(r['cmd']==22 for r in rpc)
    (out/'menu-S.bin').write_bytes(c.read(u(0x200c0dac),4096))
    if base: (out/'live-552.bin').write_bytes(c.read(at('g.live'),552))
except BaseException as exc:
    try:
        if m is not None and 'state' in globals():result['failure_state']=state()
    except BaseException:
        pass
    result.update(status='ERROR',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    raise
finally:
    if m is not None:
        result.update(steps=m.cpu.steps,actual_backend=m.cpu.backend_kind,library_sha256=C.sha(m.cpu.library_path.read_bytes()))
        m.close()
    result['seconds']=time.monotonic()-start
    save()
    print(json.dumps(dict(label=a.label,status=result['status'],seconds=result['seconds'])),flush=True)

# Finish the separate downgrade instruction probes in this queue slot, after
# the cold machine is closed. The first failed probe receipts stay intact.
if a.fault=='alloc-main':
    C.run(['/usr/bin/python3','-I','-B',C.LOCAL/'memory_audit.py'],'memory-audit')
    for proof_backend in ('c','python'):
        C.run(['/usr/bin/python3','-I','-B',C.LOCAL/'downgrade_probe.py','--backend',proof_backend],
              'downgrade-'+proof_backend+'-r2')
