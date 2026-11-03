#!/usr/bin/python3
"""Observe settings ownership, preview timing and deferred work on final code."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/review_g127'
SOURCE = ROOT / 'firmware/engine_v48_own'
DAT = ROOT / 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT'
PIN = '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6'
PENDING = 2540

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def setup(unit, name, crc):
    assert __debug__ and not sys.flags.optimize
    assert hashlib.sha256(DAT.read_bytes()).hexdigest() == PIN
    sys.path.insert(0, str(SOURCE))
    m = load(SOURCE/'integration_native.py', 'review127_integration')
    v, fr, pe = m.v, m.fr, m.pe
    m.DAT = pe.STAGED = DAT
    pe.STAGED_SHA = PIN
    pe.ENGINE_ELF = SOURCE/'candidate/local/full-r13/engine.elf'
    mount=ROOT/'firmware/package_v36_g117/SD_ROOT/l08firm3'
    pe.UNITS['mount']=(mount,hashlib.sha256(mount.read_bytes()).hexdigest(),2)
    pe.FileEdge, fr.Product = m.Files, m.Product
    v.harness_mod.Harness = v.V35Harness
    v.python_backend.CACHE = OUT/'local/decode'/name/unit
    syms = v.Elf(v.RESIDENT_ELF).symbols
    fr.OBSERVE = syms['rv_hook_observe']
    fr.LAND = {syms['rv_skip_06']:'h06_skip', syms['rv_close_07']:'h07_close',
               syms['rv_skip_08']:'h08_skip', 0x202871dc:'native_setter',
               0x202bb96c:'native_h08', 0x20268768:'native_setter_store'}
    h, p, w = m.boot(unit)
    original_symbol = p.symbol_pc
    def symbol(name):
        actual = next((x for x in (name, name+'.constprop.0', name+'.lto_priv.0')
                       if x in p.elf.symbols), name)
        return original_symbol(actual)
    p.symbol_pc = symbol
    if crc == 'flag':
        p.crc_fast = True
    elif crc == 'native':
        p.accelerate_crc = lambda image: None
    return m, v, fr, pe, h, p, w

def other_context(h, v):
    h.b.map(0x206a0000, bytes(0x10000))
    backend = v.PythonBackend()
    backend.regions, backend.mmio, backend.traces = h.b.regions, h.b.mmio, h.b.traces
    backend.breakpoints = {k:list(rows) for k, rows in h.b.breakpoints.items()}
    backend.core.r, backend.core.psw = list(h.b.core.r), h.b.core.psw
    backend.core.cr = dict(h.b.core.cr)
    backend.core.bpsw, backend.core.bbpsw, backend.core.acc = h.b.core.bpsw, h.b.core.bbpsw, h.b.core.acc
    backend.set_reg('r15', 0x206afff0)
    other = copy.copy(h)
    other.b = backend
    return other

def state(h, p, pe):
    g = p.symbol_pc('g')
    return dict(mode=h.u(h.settings+0x36e,1), wb=[h.u(h.settings+x,1) for x in (0x6dd,0x6de)],
        rows=h.u(0x2022f5ac,1), activity=h.u(0x205d9bf8), native_state=h.u(0x205d9c00),
        overlay=h.u(0x2037f3bc), view_count=h.u(0x205a27d4,1),
        busy=h.u(g+2525,1), uncertain=h.u(g+2527,1), pending=h.u(g+PENDING,1),
        failed=h.u(p.symbol_pc('n')+3712,1),
        previews=h.stub_hits.get('preview',0), grain=h.u(pe.ROOT_ADDR+216))

def changed_mode(h):
    h.phase = 'model:settings_input'
    h.put(h.settings+0x36e,5,1)
    h.phase = 'cpu'

def checkpoint(record, label):
    folder=OUT/'evidence'
    folder.mkdir(parents=True,exist_ok=True)
    name=record['case']+'-'+record['crc_mode']+'-'+record['unit']+'-'+label+'.json'
    (folder/name).write_text(json.dumps(record,indent=2)+'\n')

def run(unit, case, crc, fixture=None):
    if fixture is None:
        m,v,fr,pe,h,p,w = setup(unit, case+'-'+crc, crc)
        m.published(h,p,w)
    else:
        m,v,fr,pe,h,p,w=fixture
    if case=='h07-parent':
        pid=os.fork()
        if pid==0:
            try:
                run(unit,'h07-parent-preview',crc,(m,v,fr,pe,h,p,w))
                os._exit(0)
            except BaseException as error:
                folder=OUT/'evidence'
                folder.mkdir(parents=True,exist_ok=True)
                (folder/('h07-parent-preview-'+crc+'-'+unit+'-error.json')).write_text(json.dumps(
                    dict(status='FAIL',unit=unit,error_type=type(error).__name__),indent=2)+'\n')
                os._exit(1)
        _,status=os.waitpid(pid,0)
        assert status==0
    record = dict(case=case, unit=unit, crc_mode=crc, dat_sha256=PIN,
                  image_base=hex(p.image_base),
                  generation=int.from_bytes(p.dat[28:32],'big'),
                  elf_sha256=hashlib.sha256(p.elf.raw).hexdigest(),
                  body_sha256=h.image.sha256, assertions_enabled=__debug__,
                  scope='M32R host model; graphics and device leaves remain models')
    before = state(h,p,pe)
    rows=[]
    if case == 'crc-settings':
        changed_mode(h)
        m.reopen(h,p,w)
        after = state(h,p,pe)
        assert after['mode']==1 and after['rows']==8 and not after['busy'] and not after['uncertain']
        assert after['previews'] > before['previews']
        record['status']='PASS'
    elif case in ('preview-window', 'preview-deferred', 'pending-read', 'settings-check', 'h07-parent','h07-parent-preview'):
        changed_mode(h)
        switched=[False]
        writes=[]
        observed=[]
        def switch():
            if switched[0]:
                return
            assert h.b.core.psw & 0x40
            other=other_context(h,v)
            if case in ('h07-parent','h07-parent-preview'):
                m.need(fr.native(other,0x201c092c,(2,1,0)))
                ui=p.symbol_pc('n')+3648
                strict=other.invoke(p.symbol_pc('rv_view_owned'),(pe.ROOT_ADDR,ui,0),native=False)
                loose=other.invoke(p.symbol_pc('rv_view_owned'),(pe.ROOT_ADDR,ui,1),native=False)
                rows.append(dict(phase='hidden',strict_owned=strict,constructing_owned=loose))
                other.invoke(0x202856d0)
                strict=other.invoke(p.symbol_pc('rv_view_owned'),(pe.ROOT_ADDR,ui,0),native=False)
                loose=other.invoke(p.symbol_pc('rv_view_owned'),(pe.ROOT_ADDR,ui,1),native=False)
                rows.append(dict(phase='parent_rebuilt',strict_owned=strict,constructing_owned=loose))
            else:
                other.run_slice(0x202ba380,0x202ba3c8)
                other.leave_other_list()
            switched[0]=True
            rows.append(dict(after_switch=state(h,p,pe),irq_enabled=bool(h.b.core.psw&0x40)))
        def service(backend):
            if case in ('settings-check','h07-parent') and backend.core.r[0:2]==[6,2]:
                switch()
            if case=='h07-parent-preview' and backend.core.r[0:2]==[5,1]:
                switch()
            return False
        def preview_cut(backend):
            if case in ('preview-window','preview-deferred','pending-read'):
                switch()
            return False
        def store(event):
            if switched[0] and event.origin=='cpu':
                writes.append(dict(pc=hex(event.pc),pc_offset=hex(event.pc-p.image_base),
                    offset=hex(event.address-h.settings),value=event.value,
                    irq_enabled=bool(h.b.core.psw&0x40),entry_kind=h.u(p.symbol_pc('n')+3716,1)))
        h.b.add_write_trace(h.settings,h.settings+0xc9e,store)
        h.b.add_breakpoint(p.symbol_pc('rv_call'),service)
        h.b.add_breakpoint(p.image_base+(0xa354 if case in ('preview-deferred','pending-read') else 0xa35c),preview_cut)
        h.b.add_breakpoint(0x202d6f38,lambda b: observed.append(state(h,p,pe)) or False)
        h.b.core.psw |= 0x40
        if case in ('h07-parent','h07-parent-preview'):
            m.need(fr.press(h,0x23,steps=30000000))
        else:
            m.need(fr.native(h,0x202be220,steps=30000000))
        after=state(h,p,pe)
        record.update(switched=switched[0],events=rows,settings_stores_after_switch=list(writes),
                      preview_entries=list(observed),before=before,after=after)
        checkpoint(record,'returned')
        assert switched[0]
        if case in ('settings-check','preview-deferred','pending-read'):
            assert not writes and not observed and after['pending']==1
            if case in ('preview-deferred','pending-read'):
                assert after['mode']==1
            if case=='pending-read':
                failures=[]
                def read_error(backend):
                    if not failures and backend.core.r[0:2]==[6,1]:
                        reply=backend.core.r[3]
                        metadata=0x200c0dac
                        saved=backend.read(metadata,4)
                        return_pc=backend.core.r[14]
                        row=dict(query=1,metadata_address=hex(metadata),restored=False)
                        failures.append(row)
                        backend.write(metadata,bytes(4))
                        def restore_metadata(current):
                            if not row['restored']:
                                row['service_status']=struct.unpack('>i',current.read(reply+4,4))[0]
                                current.write(metadata,saved)
                                row['restored']=True
                            return False
                        backend.add_breakpoint(return_pc,restore_metadata)
                    return False
                h.b.add_breakpoint(p.symbol_pc('rv_call'),read_error)
                h.parent()
                opened,_,error=fr.publish(h,p,w)
                m.need(opened)
                assert error is None and len(failures)==1
                first=state(h,p,pe)
                record['one_read_error_return']=first
                record['settings_query_error']=failures
                checkpoint(record,'read-error-returned')
                assert failures[0]['restored'] and failures[0]['service_status']<0
                assert not first['busy'] and not first['uncertain']
            m.reopen(h,p,w)
            restored=state(h,p,pe)
            record['reopened']=restored
            checkpoint(record,'reopened')
            assert restored['mode']==1 and restored['pending']==0 and restored['rows']==8 and not restored['failed']
            assert restored['previews']>after['previews']
            record.update(status='PASS',reopened=restored)
        else:
            record['status']='OBSERVED'
    else:
        raise ValueError(case)
    record.update(before=before,after=after,file_mutations=m.no_writes(p))
    crc_address=p.symbol_pc('gxr2_crc_add')
    record['crc_observation']=dict(flag=p.crc_fast,
        callbacks=len(h.b.breakpoints.get(crc_address,[])),
        host_calls=h.stub_hits.get('gxr2_crc_add',0),
        entry_visits=h.b.visits[crc_address],loop_visits=h.b.visits[crc_address+4])
    folder=OUT/'evidence'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(case+'-'+crc+'-'+unit+'.json')
    path.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(name=path.stem,returncode=0,PASS=int(record['status']=='PASS'),
                         FAIL=0,OBSERVED=int(record['status']=='OBSERVED'))),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--case',choices=('crc-settings','preview-window','preview-deferred','pending-read','settings-check','h07-parent','h07-parent-preview'),required=True)
    parser.add_argument('--crc-mode',choices=('default','flag','native'),default='native')
    args=parser.parse_args()
    try:
        run(args.unit,args.case,args.crc_mode)
    except BaseException as error:
        frame=error.__traceback__
        while frame.tb_next:
            frame=frame.tb_next
        folder=OUT/'evidence'
        folder.mkdir(parents=True,exist_ok=True)
        name=args.case+'-'+args.crc_mode+'-'+args.unit
        value=dict(case=args.case,unit=args.unit,status='FAIL',error_type=type(error).__name__,
                   file=Path(frame.tb_frame.f_code.co_filename).name,line=frame.tb_lineno,
                   function=frame.tb_frame.f_code.co_name)
        (folder/(name+'-error.json')).write_text(json.dumps(value,indent=2)+'\n')
        print(json.dumps(dict(name=name,returncode=1,PASS=0,FAIL=1,OBSERVED=0)),flush=True)
        raise SystemExit(1)

if __name__=='__main__':
    main()
