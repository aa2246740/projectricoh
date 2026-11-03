"""Device-edge failures, denied services and timer cancellation on final code."""
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import native_probe as n
import check_native as flow

OUT=n.c.RESEARCH/'evidence/native-faults.json'
report=dict(status='RUNNING',dat_sha256=n.c.sha(n.DAT),checks=[])


def done(name,**facts):
    report['checks'].append(dict(name=name,**facts));n.c.save(OUT,report);print('PASS',name,flush=True)


def four(h):return [h.u(a,size) for a,size in ((0x2022f5a8,4),(0x2022f5ac,1),(0x2022f725,1),(0x2022f726,1))]


def timer_ready(h,p):
    flow.reference(h,p);flow.reference(h,p);flow.select(h,p,3);n.reopen(h,p)
    assert p.state()['phase']==4 and p.state()['ref_count']>=2,p.state()


def main():
    h,p,w=n.boot();n.open_menu(h,p)
    unit=flow.unit_digest(p);forced={};returns=[]
    def force_api(b):
        spec=forced.get('spec')
        if not spec:return False
        service,op=b.get_reg('r0'),b.get_reg('r1')
        if spec['on']=='text' and (service,op)!=(11,2):return False
        if spec['on']=='read' and (service,op)!=(4,2):return False
        if spec['on']=='X' and (service,op)!=(4,4):return False
        forced['spec']=None;ret=b.get_reg('r14');q=b.get_reg('r2');row=dict(spec)
        if 'value' in spec:h.put(q+40,spec['value'])
        b.set_reg('r0',spec['id']);b.set_reg('r1',spec['op']);row['pending']=True
        def back(b):
            if row['pending']:
                row['status']=n.pe.signed(b.get_reg('r0'));row['pending']=False;returns.append(row)
            return False
        h.b.add_breakpoint(ret,back)
        return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['rv_call'],force_api)
    n.require(n.fr.press(h,0x29))
    for op in list(range(10))+[255]:
        forced['spec']=dict(on='text',id=1,op=op)
        h.parent();n.require(n.fr.open_settings(h))
        assert returns[-1]['status']==-12,returns[-1]
        assert h.u(n.pe.ROOT_ADDR+156)==0
    for service in (3,5,6):
        forced['spec']=dict(on='text',id=service,op=1)
        h.parent();n.require(n.fr.open_settings(h));assert returns[-1]['status']==-12,returns[-1]
    done('storage-all-ops-preview-settings-cache-denied',returns=returns[:])
    h.parent();n.open_menu(h,p)
    forced['spec']=dict(on='read',id=4,op=3,value=0x1234)
    flow.select(h,p,1);assert returns[-1]['status']==-12,returns[-1]
    n.reopen(h,p)
    forced['spec']=dict(on='X',id=4,op=4,value=0x12c0)
    flow.select(h,p,1);assert returns[-1]['status']==-10,returns[-1]
    n.reopen(h,p)
    assert not any(x['cmd']==22 or x['cmd']==23 and x['value']==0x12c0 for x in p.rpc.log)
    assert flow.unit_digest(p)==unit
    done('valid-RPC-token-W-and-T-page-rejected',returns=returns[-2:],unit_unchanged=True)
    flow.select(h,p,2);n.reopen(h,p)
    n.require(n.fr.open_settings(h))
    assert p.state()['error']==3 and p.state()['ref_count']==0,p.state()
    done('H01-reentry-invalidates-reference',state=p.state())
    flow.go_main(h,p);flow.select(h,p,2);n.reopen(h,p)
    n.require(n.fr.native(h,0x202be220))
    assert p.state()['error']==3 and p.state()['ref_count']==0 and h.u(0x2022f5ac,1)==7,p.state()
    n.reopen(h,p)
    done('H06-invalidates-and-withdraws',state=p.state())
    for delta in (0,0x80000000,0xffffffff):
        state=flow.reference(h,p,delta)
        assert state['error']==5 and state['ref_count']==0,state
    done('zero-half-wrap-backwards-reference-rejected')
    timer_ready(h,p)
    p.tick_step=51
    n.require(n.fr.move_key(h,0x20))
    assert p.state()['error']==8 and p.state()['admit_l']==0,p.state()
    before=h.b.visits[p.image_base+p.elf.symbols['p0_kernel']]
    for _ in range(8):n.require(n.fr.move_key(h,0x20))
    assert h.b.visits[p.image_base+p.elf.symbols['p0_kernel']]==before
    p.tick_step=1
    done('budget-51-over-50-stops-further-work',state=p.state())
    timer_ready(h,p)
    p.tick_step=50;n.require(n.fr.move_key(h,0x20));p.tick_step=1
    assert p.state()['admit_l']==1 and p.state()['admit_l_done']==1 and not p.state()['error'],p.state()
    done('budget-equal-allowed-no-next-L-expansion',state=p.state())
    timer_ready(h,p)
    p.tick_step=0x80000000;n.require(n.fr.move_key(h,0x20));p.tick_step=1
    assert p.state()['error']==5,p.state()
    done('half-wrap-sample-rejected',state=p.state())
    timer_ready(h,p)
    fault=[False];tick_count=[0]
    def corrupt_guard(b):
        if fault[0]:
            tick_count[0]+=1
            if tick_count[0]==2:
                h.put(p.state()['work_base'],0);fault[0]=False
        return False
    h.b.breakpoints[0x2005f164].insert(0,corrupt_guard)
    fault[0]=True;n.require(n.fr.move_key(h,0x20))
    assert p.state()['error']==6 and p.state()['admit_l']==0,p.state()
    done('private-guard-fault-not-valid-sample',state=p.state())
    timer_ready(h,p)
    irq_fault=[True];irq_ticks=[0]
    def clear_irq(b):
        if irq_fault[0]:
            irq_ticks[0]+=1
            if irq_ticks[0]==2:b.set_reg('psw',b.get_reg('psw')&~0x40);irq_fault[0]=False
        return False
    h.b.breakpoints[0x2005f164].insert(0,clear_irq)
    n.require(n.fr.move_key(h,0x20))
    assert p.state()['error']==4 and p.state()['used']==0,p.state()
    h.b.set_reg('psw',0x41);h.parent();n.open_menu(h,p)
    done('IRQ-off-at-end-rejects-sample',state=p.state())
    flow.go_main(h,p);flow.select(h,p,2);n.reopen(h,p)
    mode=n.pe.ROOT_ADDR+8+4*8;h.put(mode,h.u(mode)+1)
    n.require(n.fr.move_key(h,0x20))
    assert p.state()['error']==3 and p.state()['ref_count']==0,p.state()
    done('mode-epoch-invalidates-reference',state=p.state())
    n.require(n.fr.press(h,0x29));h.parent();n.open_menu(h,p)
    # Interrupt publication after its first native cursor store. The old
    # request is stale, but the local owned abort must restore exact raw bytes.
    n.require(n.fr.press(h,0x29));h.parent()
    partial=dict(armed=True,aborts=[])
    def partial_write(event):
        if partial['armed'] and event.pc is not None and event.address==0x2022f725:
            if p.image_base+256<=event.pc<p.image_base+256+int.from_bytes(p.dat[136:140],'big'):
                partial['armed']=False;at=n.pe.ROOT_ADDR+8+4*6;h.put(at,h.u(at)+1)
    h.b.add_write_trace(0,2**32,partial_write)
    def abort(b):
        v=n.pe.ROOT_ADDR+156;want=[h.u(v),h.u(v+4),h.u(v+40),h.u(v+44)];ret=b.get_reg('r14')
        row=dict(want=want,pending=True)
        def back(b):
            if row['pending']:row['after']=four(h);row['pending']=False;partial['aborts'].append(row)
            return False
        h.b.add_breakpoint(ret,back);return False
    h.b.add_breakpoint(p.image_base+p.elf.symbols['es_ui_abort'],abort)
    n.require(n.fr.open_settings(h))
    assert partial['aborts'] and all(x['want']==x['after'] for x in partial['aborts']),partial
    assert h.u(n.pe.ROOT_ADDR+156)==0
    done('partial-publication-epoch-change-exact-withdrawal',aborts=partial['aborts'])
    # Fail glyph conversion by returning a nonterminated private glyph buffer.
    h.parent();n.open_menu(h,p);flow.select(h,p,2)
    glyph=[True]
    def bad_glyph(b):
        if glyph[0]:
            glyph[0]=False;b.write(b.get_reg('r6'),b'A'*84);b.set_reg('r0',0xffffffff);b.set_reg('pc',b.get_reg('r14'))
        return False
    h.b.add_breakpoint(0x201d73e0,bad_glyph)
    h.parent();n.require(n.fr.open_settings(h))
    assert p.state()['error']==1 and h.u(n.pe.ROOT_ADDR+156)==0,p.state()
    done('glyph-nontermination-before-capture',state=p.state())
    language=[True];raw_language=h.u(0x2023eab8,1)
    def changed_language(b):
        if language[0]:language[0]=False;h.put(0x2023eab8,(raw_language+1)%10,1)
        return False
    h.b.add_breakpoint(0x201d73e0,changed_language)
    h.parent();n.require(n.fr.open_settings(h))
    assert p.state()['error']==1 and h.u(n.pe.ROOT_ADDR+156)==0,p.state()
    h.put(0x2023eab8,raw_language,1)
    done('language-changes-during-glyph-before-capture',state=p.state())
    h.parent();n.open_menu(h,p)
    restore=n.pe.ROOT_ADDR+156;want=[h.u(restore),h.u(restore+4),h.u(restore+40),h.u(restore+44)]
    snap=h.u(n.pe.ROOT_ADDR+136);h.put(snap+1960,h.u(snap+1960)^1)
    n.require(n.fr.move_key(h,0x20))
    assert h.u(n.pe.ROOT_ADDR+5,1)==6 and four(h)==want,(four(h),want,n.fr.root_fields(h))
    done('resident-retire-restores-exact-native-fields',expected=want,actual=four(h))
    assert flow.unit_digest(p)==unit and not p.rpc.overlay
    # Allocation failure on the very first UI publish, after genuine loader IO.
    h2,p2,w2=n.boot();alloc=[0]
    def no_ui_alloc(b):
        if b.get_reg('r4')==1968:
            alloc[0]+=1;b.set_reg('r0',0);b.set_reg('pc',b.get_reg('r14'))
        return False
    h2.b.add_breakpoint(0x2005bf5c,no_ui_alloc)
    n.require(n.fr.open_settings(h2))
    assert alloc[0]==1 and p2.state()['error']==1 and h2.u(n.pe.ROOT_ADDR+156)==0,p2.state()
    done('first-publish-allocation-failure-zero-capture',state=p2.state(),allocation_failures=alloc[0])
    for unit_name in ('28mm','mount'):
        hh,pp,ww=n.boot(unit_name);before=flow.unit_digest(pp);n.open_menu(hh,pp)
        assert pp.rows()==['50MM ONLY']*8 and pp.state()['is50']==0
        for row in range(1,9):
            n.move(hh,row);n.require(n.fr.press(hh,0x23));n.reopen(hh,pp)
        assert not pp.rpc.log and not pp.tick_log and flow.unit_digest(pp)==before
        done('non-50mm-'+unit_name+'-zero-RPC-and-zero-bench',rows=pp.rows(),unit_sha256=before,files=pp.native_log)
    report.update(status='PASS',unit_before=unit,unit_after=flow.unit_digest(p),rpc_W=0,file_mutations=0)
    n.c.save(OUT,report);print('PASS native fault suite',flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        report['status']='FAIL';report['error']=traceback.format_exc();n.c.save(OUT,report)
        n.c.save(n.c.RESEARCH/('evidence/failures/faults-'+report['dat_sha256'][:12]+'.json'),report)
        raise
