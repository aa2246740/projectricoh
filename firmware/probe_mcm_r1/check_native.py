"""Behavior checks through actual H01/H07/H08 and the final DAT instructions."""
from pathlib import Path
import hashlib
import json
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n

REPORT=n.c.RESEARCH/'evidence/native-functional.json'
report={'status':'RUNNING','checks':[],'dat_sha256':n.c.sha(n.DAT),'scope':'native instructions; device tick/link/font/file-read models'}


def check(name,**values):
    report['checks'].append(dict(name=name,**values))
    n.c.save(REPORT,report)
    print('PASS',name,flush=True)


def unit_digest(p):
    return hashlib.sha256(b''.join(base.to_bytes(4,'big')+bytes(data) for base,data,_ in p.rpc.backend.regions)).hexdigest()


def press(h,key=0x23):
    return n.require(n.fr.press(h,key))


def go_main(h,p):
    for _ in range(4):
        if p.state()['page']==0:
            return
        press(h)
        n.reopen(h,p)
    raise AssertionError(('main',p.state(),p.rows()))


def select(h,p,row):
    go_main(h,p)
    n.move(h,row)
    press(h)


def reference(h,p,delta=30000,start=None):
    select(h,p,2)
    assert p.state()['phase']==1,p.state()
    if start is not None:p.ticks=start
    n.reopen(h,p)
    state=p.state()
    assert state['phase']==2,state
    assert p.rows()[3]=='START saved in REF HISTORY',p.rows()
    p.ticks=(state['ref_start']+delta)&0xffffffff
    press(h)
    state=p.state()
    n.reopen(h,p)
    return state


def main():
    h,p,w=n.boot()
    unit_before=unit_digest(p)
    before=h.state()
    print('Native cold H01 starting',flush=True)
    n.open_menu(h,p)
    assert p.state()['is50']==1 and p.state()['baseline_valid']==1 and p.state()['error']==0,p.state()
    assert p.h.u(p.h.u(n.pe.ROOT_ADDR+56)+328)==3
    assert all(not x.get('path','').startswith('/IROM/') for x in p.native_log)
    assert 0x20271fec not in h.b.breakpoints
    getter=n.fr.native(h,0x20271fec)
    n.require(getter)
    check('cold-H01-no-UI-preseed',before=before,after=h.state(),rows=p.rows(),source=3,
          getter_result=getter,getter_visits=h.b.visits[0x20271fec],getter_stub=h.stub_hits.get('image_mode_getter',0),
          actual_gen117_IROM_slots_present=True,product_sha256=hashlib.sha256(p.files.paths['/IROM/GXRCE0.DAT']).hexdigest())
    apply_inputs=[]
    def on_apply(b):
        q=b.get_reg('r2')
        apply_inputs.append([h.u(q+8+4*i) for i in (8,9,12,13)])
        return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['p0_apply'],on_apply)
    raw_restore=[h.u(n.pe.ROOT_ADDR+156+4*i) for i in range(14)]
    select(h,p,1)
    assert h.u(0x2022f5a8)==raw_restore[0] and h.u(0x2022f5ac,1)==raw_restore[1]
    assert h.u(0x2022f725,1)==raw_restore[10] and h.u(0x2022f726,1)==raw_restore[11]
    assert p.state()['baseline_status']==1 and unit_digest(p)==unit_before
    check('BASE-exact-read-only',bytes=260,unit_sha256=unit_before,restore=raw_restore)
    n.reopen(h,p)
    for row in (4,5,6,7,8):
        select(h,p,row)
        n.reopen(h,p)
        go_main(h,p)
        assert unit_digest(p)==unit_before
    check('all-passive-main-rows-unit-unchanged')
    a=reference(h,p,30000)
    b=reference(h,p,30000,start=0xfffff000)
    assert a['ref_count']==1 and b['ref_count']==2 and not b['error'],(a,b)
    assert all(x['valid']==1 and x['delta']==30000 for x in p.raw_refs()),p.raw_refs()
    check('two-references-and-u32-wrap',references=p.raw_refs(),rows=p.rows())
    select(h,p,3)
    n.reopen(h,p)
    assert p.state()['phase']==4,p.state()
    for i in range(8):
        n.require(n.fr.move_key(h,0x20))
        state=p.state()
        assert not state['error'],(i,state,p.rows(),apply_inputs[-3:])
        assert state['admit_l']+state['admit_d']==i+1,(state,apply_inputs[-3:])
        print('Admission',i+1,state['admit_l'],state['admit_d'],flush=True)
    assert p.state()['phase']==5
    check('one-admission-per-native-DOWN',apply_inputs=apply_inputs[-8:])
    before_used=p.state()['used']
    n.require(n.fr.move_key(h,0x1f))
    assert p.state()['used']==before_used
    check('UP-does-not-run-kernel')
    for i in range(48):
        n.require(n.fr.move_key(h,0x20))
        state=p.state()
        assert not state['error'] and state['used']==i+1,(i,state,p.rows())
        if i%8==7:print('Samples',i+1,flush=True)
    assert p.state()['phase']==6 and p.state()['low_res']==1,p.state()
    samples=p.raw_samples()
    for kind,target in ((0,1),(0,2),(1,1),(2,2)):
        selected=[x for x in samples if x['kind']==kind and x['target']==target]
        counts=sorted(set(x['count'] for x in selected))
        assert len(counts)>=2 and all(sum(x['count']==value for x in selected)>=3 for value in counts)
    assert all(x['valid'] and (x['end']-x['start'])&0xffffffff==1 for x in samples)
    assert h.b.visits[p.image_base+p.elf.symbols['p0_kernel']]>0
    assert h.b.visits[p.image_base+p.elf.symbols['p0_decrement']]>0
    check('48-real-instruction-samples-and-LOW-RES',samples=samples,references=p.raw_refs(),state=p.state(),
          kernel_visits=h.b.visits[p.image_base+p.elf.symbols['p0_kernel']],
          decrement_visits=h.b.visits[p.image_base+p.elf.symbols['p0_decrement']])
    used=p.state()['used'];kernel=h.b.visits[p.image_base+p.elf.symbols['p0_kernel']]
    for _ in range(3):n.require(n.fr.move_key(h,0x20))
    assert p.state()['used']==used and h.b.visits[p.image_base+p.elf.symbols['p0_kernel']]==kernel
    press(h);n.reopen(h,p)
    page1=p.rows();n.require(n.fr.move_key(h,0x20));page2=p.rows()
    assert page1!=page2,(page1,page2)
    assert page1[0].endswith('RUN 2') and page2[0].endswith('RUN 2'),(page1,page2)
    assert p.state()['used']==used
    check('result-pages-and-DONE-do-not-rerun',page1=page1,page2=page2)
    go_main(h,p)
    select(h,p,1);n.reopen(h,p)
    assert p.state()['baseline_status']==1 and unit_digest(p)==unit_before
    p.rpc.fail_read=True
    select(h,p,1);n.reopen(h,p)
    assert p.state()['error']==9 and p.state()['baseline_status']==3,p.state()
    assert unit_digest(p)==unit_before
    check('baseline-read-failure-zero-W',state=p.state(),rows=p.rows())
    # The returned halfword is corrupted only at the read boundary, never in unit RAM.
    original_half=p.rpc.half
    first=[True]
    def mismatch(address):
        word=original_half(address)
        if first[0]:first[0]=False;return word^1
        return word
    p.rpc.half=mismatch
    select(h,p,1);n.reopen(h,p)
    p.rpc.half=original_half
    assert p.state()['baseline_status']==2 and unit_digest(p)==unit_before,p.state()
    check('baseline-readback-mismatch-zero-W',state=p.state(),rows=p.rows())
    select(h,p,2);n.reopen(h,p)
    assert p.state()['phase']==2
    press(h,0x29);n.reopen(h,p)
    assert p.state()['phase']==7 and p.state()['error']==3 and p.state()['ref_count']==0,p.state()
    check('MENU-invalidates-reference',state=p.state())
    assert not p.rpc.overlay and not any(x['cmd']==22 for x in p.rpc.log)
    assert unit_digest(p)==unit_before
    assert all(x['psw']&0x40 and x['sp']%4==0 for x in p.tick_log)
    report.update(status='PASS',final_rows=p.rows(),final_state=p.state(),native_calls=h.calls,
                  unit_before=unit_before,unit_after=unit_digest(p),rpc_commands=sorted(set(x['cmd'] for x in p.rpc.log)),
                  file_calls=p.native_log,ticks=p.tick_log,apply_inputs=apply_inputs)
    n.c.save(REPORT,report)
    print('PASS native functional',flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        report['status']='FAIL';report['error']=traceback.format_exc();n.c.save(REPORT,report)
        n.c.save(n.c.RESEARCH/('evidence/failures/native-functional-'+report['dat_sha256'][:12]+'.json'),report)
        raise
