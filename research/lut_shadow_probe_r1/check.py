"""Run final DAT instructions in both host backends; keep every partial receipt."""
from pathlib import Path
import argparse
import json
import struct
import sys
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
import vectors as V
from session import Session

def admitted(label):
    waiting=False
    while True:
        try:
            C.gate(label)
            if waiting: C.save(C.LOCAL/'workload-wait.json',dict(waiting=False,label=label))
            return
        except RuntimeError as error:
            if not str(error).startswith('LOAD_DEFERRED'): raise
            waiting=True
            C.save(C.LOCAL/'workload-wait.json',dict(waiting=True,label=label))
            time.sleep(20)

def expected_checksum(raw,seed=0x4c503136):
    for word, in struct.iter_unpack('>I',raw):
        seed=(((seed<<5)|(seed>>27))^((word+0x9e3779b9)&0xffffffff))&0xffffffff
    return seed

def kernel(backend):
    h=Session(backend); rows=[]; words=V.words(); data=b''.join(struct.pack('>I',w) for w in words)
    coord=V.coordinates(); base=h.cfg['vector_base']; table_at=base
    coord_at=base+32768; input_at=base+36864; output_at=base+65536
    h.cpu.map(coord_at,struct.pack('>256I',*coord),False)
    h.cpu.map(input_at,data,False); h.cpu.map(output_at,bytes(len(data)+8),True)
    for kind in ('identity','mixed','extreme'):
        admitted('kernel-'+backend+'-'+kind)
        nodes=V.table(kind); table=V.packed(nodes); h.cpu.map(table_at,table,False)
        expected=b''.join(V.transform(w,nodes,coord) for w in words)
        before=h.cpu.total_steps
        h.invoke('lp_kernel',[input_at,output_at,len(words),table_at],budget=3000000,extra=[coord_at])
        actual=h.cpu.read(output_at,len(data)); assert actual==expected,(kind,'oracle mismatch')
        assert h.cpu.read(input_at,len(data))==data
        assert h.cpu.read(table_at,len(table))==table
        rows.append(dict(table=kind,pairs=len(words),oracle_equal=True,source_unchanged=True,table_unchanged=True,
            output_sha256=C.sha(actual),instructions=h.cpu.total_steps-before))
    # MMIO read counting uses a short independent call. No host shortcut is installed.
    table=V.packed(V.table('mixed')); read_counts={'nodes':0,'coordinates':0,'input':0}
    def read_region(raw,start,key):
        def read(at,size):
            read_counts[key]+=1
            assert size==(2 if key=='nodes' else 4),(key,size)
            return raw[at-start:at-start+size]
        return read
    h.cpu.add_mmio(table_at,table_at+len(table),read_region(table,table_at,'nodes'),None)
    coord_raw=struct.pack('>256I',*coord)
    h.cpu.add_mmio(coord_at,coord_at+1024,read_region(coord_raw,coord_at,'coordinates'),None)
    h.cpu.add_mmio(input_at,input_at+len(data),read_region(data,input_at,'input'),None)
    count=13
    h.invoke('lp_kernel',[input_at,output_at,count,table_at],budget=200000,extra=[coord_at])
    assert read_counts==dict(nodes=24*count,coordinates=4*count,input=count),read_counts
    return dict(rows=rows,read_counts=read_counts,counted_pairs=count,
        native_stats=getattr(h.cpu,'native_stats',None),tick_callee_clobbers_preserved=True)

def fresh(backend):
    h=Session(backend); h.calibrate(); h.tick_period=100; return h

def state(backend):
    rows=[]
    def record(case,h,**extra):
        rows.append(dict(case=case,status=h.s('status'),locked=h.s('locked'),stage=h.s('stage'),
            used=h.s('used'),text=h.text(),**extra))
    h=Session(backend)
    assert not h.arm(1) and not h.arm(2) and not h.arm(3)
    result,text=h.menu(); assert result==1 and len(text)==8
    h.request({8:10,9:35}); assert h.invoke('ig_panel_event',[0,1,h.q,h.reply])==0 and h.u(h.reply+28)==0
    published=h.u(h.cfg['names_word']); glyphs=[]
    for i,row in enumerate(text):
        pointer=h.u(h.u(published+4*i)); raw=h.cpu.read(pointer,84).split(b'\0')[0]
        assert raw==b''.join(bytes((1,c)) for c in row.encode())
        glyphs.append(raw.hex())
    h.move(0); h.ok(); result,text=h.menu(); assert result==1 and h.s('ref_running')==1
    h.ticks+=30000; h.ok(); result,text=h.menu(); assert result==1 and h.s('ref_count')==1
    h.ok(); h.menu(); h.move(0); h.ok(); h.menu(); h.ticks+=30000; h.ok(); h.menu()
    assert h.s('stage')==1 and h.s('ref_count')==2
    record('UI-two-references',h,glyphs= glyphs,references=h.references())
    assert not h.arm(3)
    h.ok(); h.menu(); h.move(1); h.ok(); assert h.s('armed')==1
    h.request({8:10,9:35}); assert h.invoke('ig_panel_event',[0,1,h.q,h.reply])==0
    sample=h.capture_bridge(); assert sample['valid'] and not sample['on'] and sample['pairs']==0
    assert h.s('stage')==2
    record('L1-no-LUT',h,sample=sample,whole_frame_sha256=h.frame_hash)
    assert h.arm(2)==1
    sample=h.capture_bridge(); assert sample['valid'] and sample['pairs']==2144 and h.s('level')==1
    assert sample['checksum']==expected_checksum(h.frame_bytes[:8576])
    record('L2-one-row',h,sample=sample,whole_frame_sha256=h.frame_hash)
    assert h.arm(2)==1; h.invoke('lp_cancel'); assert h.s('armed')==0 and h.s('locked')==0
    record('cancel-single-use',h)
    # Each fault starts a new session. First failures remain latched.
    for case in ('expired','epoch','geometry','slot','encoder-word','encoder-word-max','encoder-word-range','missing-h41','soft-budget','soft-mid-batch','IRQ','tick-wrap','ref-timeout','ref-cancel'):
        admitted('state-'+backend+'-'+case)
        h=Session(backend) if case.startswith('ref-') else fresh(backend)
        if case=='ref-timeout':
            h.invoke('lp_reference_start'); h.ticks+=45001; h.invoke('lp_reconcile')
            assert h.s('locked')==1 and h.s('status')==16
        elif case=='ref-cancel':
            h.menu(); h.move(0); h.ok(); h.menu(); assert h.s('ref_running')==1
            h.request({8:7,9:0,13:34}); h.invoke('ig_event',[0,1,h.q,h.reply]); h.menu()
            assert h.s('ref_running')==0 and h.s('ref_count')==0
        else:
            assert h.arm(1)==1
            if case=='expired': h.ticks+=60001
            elif case=='epoch': h.put(h.root+h.off['root.epoch']+8,99)
            elif case=='IRQ': h.cpu.set_reg('psw',0)
            geometry=[(h.cfg['k']+342,4272,2)] if case=='geometry' else None
            if case=='tick-wrap': h.ticks=0xfffffff0; h.set_s('arm_tick',0xfffffff0)
            if case=='slot':
                h.cfg['k']+=4
                sample=h.capture_bridge()
                assert sample['status']==5 and sample['slot']==0xffffffff
            else: sample=h.capture(encoder={'encoder-word':1,'encoder-word-max':65535,'encoder-word-range':65536}.get(case,4),h41=case!='missing-h41',geometry=geometry)
            if case in ('soft-budget','soft-mid-batch'):
                assert h.s('stage')==2 and h.arm(2)==1
                h.tick_period=1; h.tick_step=300 if case=='soft-budget' else 40
                sample=h.capture()
                assert sample['pairs']==(0 if case=='soft-budget' else 128) and sample['status']==4
                assert sample['checksum']==expected_checksum(h.frame_bytes[:sample['pairs']*4])
                if case=='soft-mid-batch':
                    index=h.s('used')-1
                    address=h.state+h.off['state.samples']+index*h.off['sample.size']
                    h.put(address+h.off['sample.h41_seen'],0); h.set_s('pending',index)
                    h.invoke('lp_reconcile'); sample=h.sample(index)
                    assert sample['status']==4 and h.s('status')==4, 'missing H41 masked the first budget failure'
            if case in ('tick-wrap','encoder-word','encoder-word-max'):
                assert sample['valid'] and sample['status']==3 and h.s('locked')==0
                if case.startswith('encoder-word'): assert sample['encoder']==(1 if case=='encoder-word' else 65535)
            else:
                assert h.s('locked')==1 and h.s('armed')==0,(case,sample)
                assert not h.arm(1) and not h.arm(2) and not h.arm(3)
        record(case,h,sample=sample if not case.startswith('ref-') else None)
    return dict(rows=rows,cases=len(rows),scope='Actual DAT entry/core instructions; native tick/font/task/allocator modeled. No physical capture or LCD pixels.')

def full(backend,reference_one=False):
    h=fresh(backend); h.tick_period=100
    receipt=dict(status='RUNNING',backend=backend,dat_sha256=h.layout['dat_sha256'],samples=[],
        scope='Final-DAT instructions with declared K/frame/native-encoder input; main photo includes alignment tail. No ISP/DMA/card completion model.')
    path=C.LOCAL/('full-'+backend+'.json')
    C.save(path,receipt)
    sequence=[1]+[2]*6+[3]*6
    if reference_one:
        # A declared function input, not a CPU checkpoint or a gate-coverage claim.
        h.set_s('stage',3); h.set_s('level',6); h.set_s('l3_count',0)
        sequence=[3,3]; receipt['declared_admission_input']=True
    h.frame()
    try:
        for index,stage in enumerate(sequence):
            admitted('full-'+backend+'-'+str(index)); assert h.arm(stage)==1
            start=time.monotonic(); sample=h.capture_bridge(budget=4000000000)
            assert sample['valid'] and sample['status']==3,sample
            if sample['on']:
                count=sample['pairs']*4
                assert sample['checksum']==expected_checksum(h.frame_bytes[:count]),sample
                assert sample['pairs']==sample['expected_pairs']
            if stage==3 and sample['on']: assert sample['full'] and sample['pairs']==6106112
            row=dict(sample=sample,frame_sha256=h.frame_hash,full_frame_bytes=len(h.frame_bytes),
                source_unchanged=True,K_unchanged=True,write_whitelist_enforced=True,
                bridge=h.last_bridge,
                text=h.text(),host_seconds=time.monotonic()-start,
                instructions=h.calls[-3:])
            receipt['samples'].append(row); C.save(path,receipt)
            print(json.dumps(dict(backend=backend,index=index,stage=stage,on=sample['on'],pairs=sample['pairs'],status='PASS')),flush=True)
        if not reference_one:
            assert h.s('stage')==4 and h.s('l3_count')==6
            result,summary=h.menu()
            assert result==1 and summary[0]==f'LP{C.GENERATION} L3 N6/6 OK'
            assert summary[6].endswith(' P6106112x3')
            assert summary[7]=='S0004/0004 0004/0004 0004/0004'
            published=h.u(h.cfg['names_word'])
            for i,row in enumerate(summary):
                pointer=h.u(h.u(published+4*i))
                assert h.cpu.read(pointer,84).split(b'\0')[0]==b''.join(bytes((1,c)) for c in row.encode())
            receipt['published_summary']=summary
        receipt.update(status='PASS',native_stats=getattr(h.cpu,'native_stats',None),final_stage=h.s('stage'),
            frame_sha256=h.frame_hash,table_sha256=h.layout['table_sha256'],references=h.references())
        C.save(path,receipt)
    except BaseException:
        receipt.update(status='INCOMPLETE',first_failure=traceback.format_exc()); C.save(path,receipt); raise
    return dict(path=str(path.relative_to(C.ROOT)),samples=len(receipt['samples']))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--backend',choices=('c','python','reference'),required=True)
    p.add_argument('--check',choices=('smoke','kernel','state','full','reference-one'),required=True); a=p.parse_args()
    C.setup(); C.gate(a.check+'-'+a.backend)
    out=C.LOCAL/(a.check+'-'+('summary-' if a.check=='full' else '')+a.backend+'.json')
    try:
        if a.check=='smoke':
            h=Session(a.backend); result=dict(status='PASS',text=h.text(),state_bytes=h.off['state.size'],dat_sha256=h.layout['dat_sha256'])
        elif a.check=='kernel': result=kernel(a.backend)
        elif a.check=='state': result=state(a.backend)
        else: result=full(a.backend,a.check=='reference-one')
        result.update(status='PASS',backend=a.backend,check=a.check,
            dat_sha256=json.loads((C.ENGINE/'local/build/layout.json').read_text())['dat_sha256'])
        C.save(out,result); print(json.dumps(dict(status='PASS',backend=a.backend,check=a.check)))
    except BaseException:
        failure=dict(status='FAIL',backend=a.backend,check=a.check,error=traceback.format_exc())
        path=C.LOCAL/('first-failure-'+a.check+'-'+a.backend+'.json')
        if not path.exists(): C.save(path,failure)
        raise

if __name__=='__main__': main()
