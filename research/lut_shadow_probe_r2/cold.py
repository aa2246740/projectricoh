"""Fresh MAIN and GPIO menu input in strict_r4; independent reference is separate."""
from pathlib import Path
import argparse
import json
import os
import struct
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def main():
    p=argparse.ArgumentParser(); p.add_argument('--backend',choices=('native','reference'),required=True); a=p.parse_args()
    C.setup(); C.gate('cold-start-'+a.backend)
    os.environ.update(GXR_FAST_BACKEND=a.backend,GXR_FAST_POLICY='strict',GXR_EMULATOR_BATCH='1',
        GXR_FAST_MODEL_FIXES='nand-word,preview-link,sd-long-response,nand-read-tail')
    fast=C.ROOT/'tools/gxr_emulator_fast/strict_r4'; sys.path.insert(0,str(fast))
    import storage_run,outputs,native_controls as N
    helper=C.load(C.ROOT/'research/g156_field_issues_r1/local/common.py','lp_virtual_medium')
    cfg=json.loads((C.LOCAL/'harness.json').read_text())
    offsets=json.loads((C.ENGINE/'local/build/offsets.json').read_text())
    layout=json.loads((C.ENGINE/'local/build/layout.json').read_text())
    Elf=C.load(C.ROOT/'firmware/stage2l_switch/tools/build.py','lp_cold_elf').Elf
    symbols=Elf(C.ENGINE/'local/build/engine.elf').symbols
    dat=(C.PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()
    assert C.sha(dat)==layout['dat_sha256']
    out=C.LOCAL/('cold-'+a.backend+'-'+time.strftime('%H%M%S',time.gmtime()))
    out.mkdir(); outputs.declare_media(out); storage_run.OUT=out
    medium=out/'medium.img'; medium.write_bytes(helper.medium_bytes(dat))
    settings=bytearray((C.ROOT/'research/field_gate_r1/local/inputs-v3-auto/g156-test-A.bin').read_bytes())
    settings[0xfd4:0xffc]=bytes(40)
    settings[-4:]=(sum(struct.unpack('>2046H',settings[:4092]))&0xffffffff).to_bytes(4,'big')
    settings_file=out/'input-S.bin'; settings_file.write_bytes(settings)
    result=dict(status='RUNNING',backend=a.backend,dat_sha256=C.sha(dat),body_sha256=C.sha(C.BODY.read_bytes()),
        cold_start=True,snapshots=False,keys=[],boundary='Fresh MAIN plus GPIO ADJ; no sensor/JPEG-DMA model. H40/H41 exercised separately through actual resident trampoline.')
    C.save(out/'result.json',result)
    machine=None
    def save(): C.save(out/'result.json',result)
    def admitted(label):
        while True:
            try: C.gate(label); return
            except RuntimeError as error:
                if not str(error).startswith('LOAD_DEFERRED'): raise
                result['load_wait']=dict(label=label,load1=os.getloadavg()[0]); save(); time.sleep(20)
    try:
        machine=storage_run.Machine(str(medium)); cpu=machine.cpu
        cpu.set_mode('fast'); cpu.set_batch(True)
        N.prepare(machine,body=C.BODY,unit='mount',settings=settings_file,late_ready=True); N.extend_keys(machine)
        def u(at,size=4): return int.from_bytes(cpu.read(at,size),'big')
        root=offsets['root.address']
        def state():
            block=u(root+offsets['root.block']); base=u(root+offsets['root.code_address'])-256
            row=dict(steps=cpu.steps,view=u(cfg['view']),activity=u(cfg['activity']),rows=u(cfg['names_count'],1),
                root_state=u(root+offsets['root.state'],1),inflight=u(root+offsets['root.inflight'],1),
                word=u(root+offsets['root.reserved_lane']),block=block,base=base,
                cursor1=u(cfg['cursor1'],1),cursor2=u(cfg['cursor2'],1),names=u(cfg['names_word']))
            if row['root_state']==3 and block and base:
                address=base+symbols['lp']['value']
                row.update(generation=u(block+offsets['session.generation']),selected_source=u(block+offsets['session.selected_source']),
                    selftest=u(address+offsets['state.selftest']),table_ok=u(address+offsets['state.table_ok']),
                    stage=u(address+offsets['state.stage']),status=u(address+offsets['state.status']),
                    init_ticks=u(address+offsets['state.init_ticks']),locked=u(address+offsets['state.locked']),
                    page=u(address+offsets['state.page']),ref_running=u(address+offsets['state.ref_running']),
                    ref_count=u(address+offsets['state.ref_count']),armed=u(address+offsets['state.armed']))
                for name in ('init_phase','init_offset','init_slices','init_last','init_max','init_aborts'):
                    row[name]=u(address+offsets['state.'+name])
            return row
        def run(count,label):
            admitted(label); observed=cpu.run(count)
            assert observed.reason=='max_steps',(label,observed)
            return observed
        for index in range(13):
            run(50000000,'cold-main-'+a.backend+'-'+str(index)); result['progress']=state(); save()
            if result['progress']['view']==5 and result['progress']['activity']==0 and result['progress']['word']==2 and not result['progress']['inflight'] and result['progress']['root_state']==3: break
        else: raise RuntimeError('MAIN did not reach settled standby within 650M instructions')
        result['cold']=state()
        initial=result['cold']; initial_address=initial['base']+symbols['lp']['value']
        assert initial['init_phase']==0 and initial['init_offset']==0 and initial['init_slices']==0
        for name,count in (('row',8576),('samples',16*offsets['sample.size']),('refs',2*offsets['reference.size']),('text',320)):
            assert cpu.read(initial_address+offsets['state.'+name],count)==bytes(count),name
        result['loader_zeroed_private_buffers']=True
        # LOADING=1 and VALIDATED=2 are not settled standby. Do not enqueue
        # GPIO input while H51 is still loading the card's DAT.
        assert result['cold']['root_state']==3,result['cold']
        for key in ('ADJ',*(['ADJ_RIGHT']*6)):
            old=state()
            N.key(machine.panel,key,True); run(400000,'key-down-'+key)
            N.key(machine.panel,key,False)
            for _ in range(90):
                run(10000000,'key-settle-'+key); current=state()
                changed=any(current.get(k)!=old.get(k) for k in ('view','activity','cursor1','cursor2','page'))
                if changed and not current['inflight'] and ((current['view']==5 and current['activity']==0) or (current['view']==56 and current['activity']!=0)):
                    run(2000000,'key-confirm-'+key); break
            else: raise RuntimeError('GPIO key did not settle '+key)
            result['keys'].append(dict(key=key,state=state())); save()
            if state()['view']==56 and state()['activity']==8 and state()['rows']==8: break
        for _ in range(60):
            current=state()
            if current['root_state']==3 and current['rows']==8 and not current['inflight']: break
            run(10000000,'publication-wait')
        else: raise RuntimeError('eight-row publication did not finish')
        current=state()
        assert current['generation']==C.GENERATION and current['selected_source']==3,current
        result['loaded']=current
        base=current['base']; address=base+symbols['lp']['value']
        N.watch_point(machine,base+layout['entries']['ig_event'],'probe-H07')
        N.watch_point(machine,base+layout['entries']['ig_panel_open'],'probe-H06')
        image=bytearray(cpu.read(base,len(dat)))
        for patch,target in layout['relocations']:
            assert struct.unpack_from('>I',image,patch)[0]==base+target
            struct.pack_into('>I',image,patch,target)
        assert bytes(image)==dat
        texts=cpu.read(address+offsets['state.text'],320)
        names=u(cfg['names_word']); published=[]
        for row in range(8):
            text=texts[40*row:40*(row+1)].split(b'\0')[0].decode('ascii')
            descriptor=u(names+4*row); pointer=u(descriptor)
            glyph=cpu.read(pointer,84).split(b'\0')[0]
            assert glyph and len(glyph)==2*len(text),(row,text,glyph)
            published.append(dict(row=row,text=text,glyphs_hex=glyph.hex()))
        assert published[0]['text']==f'LP{C.GENERATION} INIT SLICES'
        assert current['selftest']==0 and current['table_ok']==0 and current['stage']==0
        assert current['init_offset']==2048 and current['init_slices']==1 and current['init_max']<=250
        assert current['init_ticks']<=250 and not current['locked']
        result['initial_progress']=current
        def key_once(key):
            old=state(); begin=cpu.steps
            N.key(machine.panel,key,True); run(400000,'GPIO-down-'+key)
            N.key(machine.panel,key,False)
            for _ in range(90):
                run(10000000,'GPIO-settle-'+key); st=state()
                changed=any(st.get(k)!=old.get(k) for k in ('view','activity','cursor1','cursor2','page','ref_running','ref_count','armed','init_offset','init_phase'))
                if changed and not st['inflight'] and ((st['view']==5 and st['activity']==0) or (st['view']==56 and st['activity']!=0)):
                    if cpu.steps-begin+2000000>902400000: raise RuntimeError('GPIO instruction budget '+key)
                    run(2000000,'GPIO-confirm-'+key); confirmed=state()
                    if confirmed['view']==st['view'] and confirmed['activity']==st['activity'] and not confirmed['inflight']: break
                result['settling']=dict(key=key,state=state()); save()
                if cpu.steps-begin+10000000>902400000: raise RuntimeError('GPIO instruction budget '+key)
            else: raise RuntimeError('GPIO action did not settle '+key)
            result['keys'].append(dict(key=key,state=state())); save()
            return state()
        def reopen():
            st=key_once('ADJ')
            for _ in range(6):
                if st['view']==56 and st['activity']==8 and st['rows']==8:break
                st=key_once('ADJ_RIGHT')
            assert st['view']==56 and st['activity']==8 and st['rows']==8,st
            return st
        # MENU is the physical MENU/OK alias, raw 24. It confirms native H07;
        # it must preserve init progress, never masquerade as a cancel key.
        st=key_once('MENU'); assert st['view']==5 and st['root_state']==3,st
        assert st['init_offset']==2048 and st['init_slices']==1 and not st['ref_running'],st
        result['GPIO_MENU_exit_preserves_progress']=st
        st=reopen(); assert st['init_offset']==4096 and st['init_slices']==2,st
        st=key_once('ADJ'); assert st['init_phase']==4 and st['init_offset']==0 and not st['locked'],st
        result['GPIO_init_abort']=st
        st=reopen(); assert st['init_phase']==4 and st['init_offset']==0,st
        st=key_once('MENU'); assert st['view']==5 and st['init_phase']==0,st
        st=reopen(); assert st['init_offset']==2048 and st['init_slices']==1,st
        result['GPIO_init_explicit_restart']=st
        result['init_slices']=[st]
        for _ in range(16):
            if st['init_phase']==3:break
            before=st['init_slices']; offset=st['init_offset']
            st=key_once('MENU')
            assert st['view']==5 and st['init_slices']==before and st['init_offset']==offset,st
            st=reopen()
            assert st['init_slices']==before+1 and st['init_last']<=250 and not st['locked'],st
            result['init_slices'].append(st); save()
        assert st['init_phase']==3 and st['init_slices']==17 and st['init_offset']==29478,st
        assert st['selftest']==1 and st['table_ok']==1 and st['init_max']<=250 and not st['locked'],st
        result['GPIO_initialization_ready']=st
        current=state()
        texts=cpu.read(address+offsets['state.text'],320)
        ready_text=[texts[i*40:(i+1)*40].split(b'\0')[0].decode('ascii') for i in range(8)]
        assert ready_text[0]=='L0 START TIME REF',ready_text
        result['ready_text']=ready_text
        st=key_once('UP'); assert st['cursor2']==8,st
        st=key_once('MENU'); assert st['view']==5,st
        st=reopen(); assert st['page']==4 and not st['ref_running'] and not st['armed'],st
        result['GPIO_native_cursor_selects_diagnostic']=st
        st=key_once('MENU'); assert st['view']==5,st
        st=reopen(); assert st['page']==0 and not st['ref_running'],st
        for _ in range(7):
            if st['cursor2']==1:break
            st=key_once('UP')
        assert st['cursor2']==1,st
        st=key_once('MENU'); assert st['view']==5,st
        st=reopen(); assert st['ref_running']==1 and st['page']==2,st
        result['GPIO_reference_started']=st
        # ADJ is a non-confirm exit. Never use MENU/OK as a second cancel key.
        st=key_once('ADJ'); assert st['ref_running']==0 and st['ref_count']==0,st
        result['GPIO_reference_cancelled']=st
        st=reopen(); assert st['ref_running']==0 and st['ref_count']==0,st
        result['GPIO_cancel_does_not_restart']=True
        st=key_once('ADJ'); assert st['view']==5 and st['activity']==0 and not st['armed'],st
        result['GPIO_final_safe_standby']=st
        current=state()
        rpc=machine.devices['startup'].rpc_state.get('log',[])
        result.update(status='PASS',final=current,published=published,actual_backend=cpu.backend_kind,
            loaded_DAT_normalized_equal=True,unit_W=sum(row.get('cmd')==22 for row in rpc))
        assert result['unit_W']==0
        save(); C.save(C.LOCAL/('cold-'+a.backend+'-latest.json'),result)
        print(json.dumps(dict(status='PASS',backend=a.backend,path=str((out/'result.json').relative_to(C.ROOT)),steps=cpu.steps)),flush=True)
    except BaseException:
        result.update(status='INCOMPLETE',first_failure=traceback.format_exc())
        if machine is not None:
            try:
                result['fault_state']=state()
                result['fault_registers']={name:cpu.get_reg(name) for name in ('pc','lr','psw',*('r'+str(i) for i in range(16)))}
                result['fault_root_hex']=cpu.read(root,offsets['root.size']).hex()
                flow=getattr(cpu,'_flow_owner',None)
                if flow is not None:
                    result['entry_observations']=[dict(row) for row in flow.rows if row.get('kind','').startswith('probe-')]
            except Exception as error: result['diagnostic_error']=str(error)
        save()
        C.save(C.LOCAL/('cold-'+a.backend+'-latest.json'),result)
        first=C.LOCAL/('first-failure-cold-'+a.backend+'-g'+str(C.GENERATION)+'.json')
        if not first.exists(): C.save(first,result)
        raise
    finally:
        if machine is not None: machine.close()

if __name__=='__main__': main()
