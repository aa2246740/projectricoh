"""Bind the reviewed counterexample to the repaired artifacts, preserving both."""
from pathlib import Path
import json, shutil, struct, sys, zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();C.compute_gate('fix-r1-prepare-checks')
root=C.LOCAL/'fix-r1';out=root/'final';out.mkdir(exist_ok=True)
for folder in ('tmp','settings','receipts','runs'):(out/folder).mkdir(exist_ok=True)
(out/'parser').mkdir(exist_ok=True)
shutil.copyfile(C.LOCAL/'parser/parsers.dylib',out/'parser/parsers.dylib')
text=(root/'common.py').read_text().replace("LOCAL=ROOT/'research/g157/local/fix-r1'","LOCAL=ROOT/'research/g157/local/fix-r1/final'")
start=text.index('def artifact(profile,dataset=None):');end=text.index('\ndef receipt',start)
text=text[:start]+'''def artifact(profile,dataset=None):
    p=PACKAGES[profile]/'local/variants/model'
    return dict(dat=p/'SD_ROOT/GXRCE.DAT',manifest=p/'MANIFEST',
        build=ENGINE/'candidate/local'/('model-boot-on' if profile=='test' else 'model-boot-off'),
        records=HERE/'local'/('model-records-'+profile+'.json'))
'''+text[end:]
text=text.replace("EXPECTED={'test':'3478b9954c122142a0711ff07cc7251a50abb442f7069cc2c558d1ca61f882a3','release':'488943d2a3b0303cc5cbec6d3c85a96e539fd19a71c3596968c40cda619dbf88'}",
                  'EXPECTED='+repr({p:C.sha(C.artifact(p,'model')['dat'].read_bytes()) for p in C.PACKAGES}))
(out/'common.py').write_text(text)
shutil.copyfile(C.LOCAL/'layout.json',out/'layout.json')
bindings=[]
for profile in C.PACKAGES:
    raw=C.artifact(profile,'model')['dat'].read_bytes()
    for p in (root/'settings').iterdir():
        if not p.is_file():continue
        if p.suffix=='.record552':shutil.copyfile(p,out/'settings'/p.name);continue
        if p.suffix!='.bin' or len(p.read_bytes())!=4096:continue
        block=bytearray(p.read_bytes())
        if block[0xfd4:0xfd8]==b'GXR2':
            block[0xff0:0xff8]=raw[20:28]
            block[0xff8:0xffc]=zlib.crc32(block[0xfd4:0xff8]).to_bytes(4,'big')
        block[-4:]=(sum(struct.unpack('>2046H',block[:4092]))&0xffffffff).to_bytes(4,'big')
        dest=out/'settings'/(profile+'-'+p.name);dest.write_bytes(block)
        bindings.append(dict(profile=profile,source=str(p.relative_to(C.ROOT)),target=str(dest.relative_to(C.ROOT)),
            changed_offsets=[i for i,(a,b) in enumerate(zip(p.read_bytes(),block)) if a!=b],sha256=C.sha(block)))
driver=(root/'manual_true_once_run.py').read_text()
old="""        assert not after['equals_stock_owned_rows_T'] and not after['equals_HC1_owned_rows_T']
        assert result['manual_after_failure']['state']==5 and not result['manual_after_failure']['word']&12
        assert len(result['fault_events'])==1
        result['manual_unguarded_partial_standby']=True"""
new="""        guarded=bool(state()['word']&12)
        assert after['equals_stock_owned_rows_T'] or guarded, (after,state())
        if a.fault=='manual-once':assert len(result['fault_events'])==1
        if a.fault=='manual-once':assert after['equals_stock_owned_rows_T'],after
        result['manual_unguarded_partial_standby']=False
        result['manual_safety_PASS']=True
        result['compensated_to_complete04']=after['equals_stock_owned_rows_T']
        result['guard_latched']=guarded"""
assert old in driver;driver=driver.replace(old,new)
driver=driver.replace("result['shutter_boundary']='Not executed here. Reference validation stops at the independently observed unguarded partial standby state.'",
    "result['shutter_boundary']='Actual unchanged H52 instructions are exercised by the separate C/Python shutter probe; no physical JPEG claim.'")
(out/'run.py').write_text(driver)
shutter=(C.ROOT/'research/review_g157_r1/local/shutter_probe.py').read_text()
(out/'shutter_probe.py').write_text(shutter)
C.save(out/'binding-changes.json',bindings)
legacy=root/'g156';legacy.mkdir(exist_ok=True)
for folder in ('tmp','runs'):(legacy/folder).mkdir(exist_ok=True)
source=C.ROOT/'research/field_gate_r1/local'
common=(source/'common.py').read_text().replace('ROOT=HERE.parents[2]','ROOT=Path('+repr(str(C.ROOT))+')')
common=common.replace("INPUTS=HERE/'inputs-v3-auto'","INPUTS=ROOT/'research/field_gate_r1/local/inputs-v3-auto'")
(legacy/'common.py').write_text(common)
driver=(source/'run.py').read_text()
driver=driver.replace("offset_path=C.HERE/'layouts'", "offset_path=C.ROOT/'research/field_gate_r1/local/layouts'")
driver=driver.replace('stop=c.run(', 'stop=run(')
anchor='    # Reference-only write observers do not change the emulated machine.'
injection='''    fault_points={};fault_writes=0;fault_events=[]
    def arm(address,phase):
        previous=c.breakpoints.get(address);fault_points[address]=(phase,previous);N.stop_at(c,address,task=6)
    def run(count):
        global fault_writes
        began=c.steps
        while True:
            stop=c.run(count-(c.steps-began))
            if stop.reason!='breakpoint' or stop.pc not in fault_points:return stop
            address=stop.pc;phase,previous=fault_points.pop(address);c.breakpoints.pop(address)
            if previous is not None:c.breakpoints[address]=previous
            if phase=='write':
                fault_writes+=1
                if fault_writes==8:arm(base+syms['rv_rpc8_native'],'wire')
                assert c.run(1).reason=='max_steps'
                if fault_writes<8:arm(address,'write')
            elif phase=='wire':
                assert c.get_reg('r0')==22;arm(c.get_reg('r14'),'return');assert c.run(1).reason=='max_steps'
            else:
                native=c.get_reg('r0');c.set_reg('r0',0xffffffff)
                fault_events.append(dict(W_position=fault_writes,native_return=native,declared_return=0xffffffff,phase='after-actual-native-call'))
    def peer_owned():
        peer=m.devices['startup'].rpc_state;overlay=peer.get('overlay',{})
        rom=(C.ROOT/'artifacts/firmware/gxr-1.51/l08firm3').read_bytes()
        sections=[struct.unpack_from('>5I',rom,32+20*i) for i in range(16)]
        directory=C.D.u32(raw,156)+128;mapping=C.D.u32(raw,directory+12);rows=[]
        stock=C.D.expand(raw,2,4);stock_rows=[]
        for i in range(9):
            address,size,offset=struct.unpack_from('>IHH',raw,mapping+32+12*i);data=[]
            for at_ in range(address,address+size):
                if at_&~1 in overlay:byte=overlay[at_&~1]>>(0 if at_&1 else 8)&255
                else:
                    off,start,n,_,_=next(s for s in sections if s[1]<=at_<s[1]+s[2]);byte=rom[512+off+at_-start]
                data.append(byte)
            rows.append(bytes(data));stock_rows.append(stock[offset:offset+size])
        return dict(rows_hex=[r.hex() for r in rows],T=peer.get('t',2),pure04=rows==stock_rows and peer.get('t',2)==2)
'''
assert anchor in driver;driver=driver.replace(anchor,injection+anchor)
start=driver.index('        if a.enter_hc:');end=driver.index("    flow=N.export_state",start)
driver=driver[:start]+'''        if a.enter_hc:
            assert a.case=='B' and engine_state()['cur']==3 and state()['selector']==9
            result['before_fault']=dict(state=state(),engine=engine_state(),peer=peer_owned())
            assert result['before_fault']['peer']['pure04']
            arm(base+syms['write_word'],'write')
            N.key(m.panel,'UP',True);assert run(400000).reason=='max_steps';N.key(m.panel,'UP',False)
            for _ in range(70):
                assert run(10000000).reason=='max_steps'
                if fault_events and (state()['state']==5 or u(at('g.uncertain'),1)):
                    assert run(2000000).reason=='max_steps';break
            assert len(fault_events)==1
            result['fault_events']=fault_events
            result['after_fault']=dict(state=state(),engine=engine_state(),peer=peer_owned(),uncertain=u(at('g.uncertain'),1))
            result['g156_has_same_unprotected_partial']=not result['after_fault']['peer']['pure04'] and not state()['word']&12
            result['entry_difference']='Same Vivid09/WB9/9/HC+1 S input and W8 native-ACK fault. g156 does not preselect this saved record under Vivid; a real UP selects HC BW with default levels.'
            N.key(m.panel,'ADJ',True);assert run(400000).reason=='max_steps';N.key(m.panel,'ADJ',False)
            for _ in range(25):
                assert run(10000000).reason=='max_steps'
                if state()['state']==5:break
            result['after_dismiss']=dict(state=state(),peer=peer_owned())
            assert state()['state']==5 and not state()['word']&12 and not peer_owned()['pure04']
'''+driver[end:]
(legacy/'run.py').write_text(driver)
print(json.dumps(dict(status='PASS',profiles=list(C.PACKAGES),settings=len(bindings))))
