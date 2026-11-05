"""Adapt the prior cold-MAIN driver, preserving its native input and model contract."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup()
s=(C.ROOT/'research/g156_field_issues_r1/local/run.py').read_text()
prefix='''
C.FAST=C.ROOT/'tools/gxr_emulator_fast/strict_r4'
C.DATASET=sys.argv[sys.argv.index('--dataset')+1] if '--dataset' in sys.argv else 'control'
_field=C.load(C.ROOT/'research/g156_field_issues_r1/local/common.py','g157_medium_helper')
C.medium_bytes=_field.medium_bytes
_load=lambda name,path:C.load(path,name)
C.VERSIONS={}
for _profile,_package in C.PACKAGES.items():
    _variant=C.artifact(_profile);_folder=_variant['build']
    C.VERSIONS[_profile]=dict(dat=str(_variant['dat'].relative_to(C.ROOT)),
        sha=__import__('json').loads(_variant['manifest'].read_text())['dat_sha256'],
        elf=str((_folder/'engine.elf').relative_to(C.ROOT)),engine=str(C.ENGINE.relative_to(C.ROOT)),
        body='firmware/image_v310/local/ilaunch3',resident=C.BODY)
'''
s=s.replace('import common as C\n','import common as C\n'+prefix)
s=s.replace("p = argparse.ArgumentParser()", "p = argparse.ArgumentParser()\np.add_argument('--dataset',choices=('control','model'),default='control')")
s=s.replace("p.add_argument('--expected',", "p.add_argument('--require-vivid',action='store_true',help='require a persistent declared Vivid S input and no DAT active marker')\np.add_argument('--expected',")
s=s.replace("p.add_argument('--expected',", "p.add_argument('--expect-final',type=Path,help='complete record after explicit session apply')\np.add_argument('--expected',")
s=s.replace("cold_start=True, snapshots=False,", "cold_start=True, snapshots=False, dataset=C.DATASET,")
s=s.replace("default='g156-test'","default='test'").replace('C.setup()\nsignal.alarm',"C.setup();C.compute_gate('cold-'+a.label)\nsignal.alarm")
s=s.replace("C.load('g156_field_elf',", "_load('g157_field_elf',").replace("C.load('g156_absent_fat',","_load('g157_absent_fat',")
s=s.replace("offsets = json.loads((C.ROOT/'research/field_gate_r1/local/layouts'/(Path(v['engine']).name+'.json')).read_text())", "offsets = json.loads((C.LOCAL/'layout.json').read_text())['offsets']")
s=s.replace("C.HERE/'runs'","C.LOCAL/'runs'")
s=s.replace("    def at(name): return base+syms[name.split('.')[0]]+offsets[name]", '''    def at(name):
        if name.startswith('g.'):return u(base+syms['g'])+offsets[name]
        return base+syms[name.split('.')[0]]+offsets[name]''')
s=s.replace("choices=('none','boot-activity6','boot-raw255','boot-mode4','list6','absent')", "choices=('none','boot-activity6','boot-raw255','boot-mode4','boot-both','boot-vivid','boot-wb','no-dispatch','list6','absent')")
s=s.replace("('boot-activity6','boot-raw255','boot-mode4')", "('boot-activity6','boot-raw255','boot-mode4','boot-both','boot-vivid','boot-wb','no-dispatch')")
s=s.replace("challenge_at=resident['rv_hook_51']", "challenge_at=resident['rv_hook_51'] if a.challenge=='no-dispatch' else resident['rv_engine']")
s=s.replace("    if challenge_at is not None:N.stop_at(c,challenge_at,task=6)", "    challenge_previous=c.breakpoints.get(challenge_at) if challenge_at is not None else None\n    if challenge_at is not None:N.stop_at(c,challenge_at,task=6)")
s=s.replace("                elif a.challenge=='list6':", '''                elif a.challenge=='boot-both':
                    c.write(0x205d9bf8,(6).to_bytes(4,'big'));c.write(0x205d9a7f,b'\\x04')
                elif a.challenge=='boot-vivid':c.write(u(0x200c0dac)+0x36e,b'\\x02')
                elif a.challenge=='boot-wb':c.write(u(0x200c0dac)+0x6dd,b'\\x0a')
                elif a.challenge=='no-dispatch':c.write(0x200547ec,(2).to_bytes(4,'big'))
                elif a.challenge=='list6':''')
s=s.replace("                before=state()\n", """                before=state()
                premature=(a.challenge=='no-dispatch' and not (before['word']==1 and before['state']==5 and before['root_state']!=255))
                if challenge_at==resident['rv_engine'] and u(c.get_reg('r2')+40)!=0x101:premature=True
                if premature:
                    c.breakpoints.pop(challenge_at)
                    if challenge_previous is not None:c.breakpoints[challenge_at]=challenge_previous
                    assert c.run(1).reason=='max_steps'
                    N.stop_at(c,challenge_at,task=6)
                    continue
""")
s=s.replace("                c.breakpoints.pop(challenge_at)\n                continue", "                c.breakpoints.pop(challenge_at)\n                if challenge_previous is not None:c.breakpoints[challenge_at]=challenge_previous\n                continue")
s=s.replace("restore_done=u(at('g.memory_dirty')-3,1),baseline=u(at('g.memory_dirty')-2,1),", "restore_done=u(at('g.restore_done'),1),baseline=u(at('g.baseline'),1),")
s=s.replace("(a.challenge=='absent' and state()['state']==5 and state()['root_state']==6)", "(a.challenge=='absent' and state()['state']==5 and state()['root_state']==6) or (a.challenge=='no-dispatch' and state()['state']==5 and c.steps>=50000000)")
s=s.replace("boot_committed=u(at('g.s_unwritten')+4,1),", "boot_committed=u(at('g.boot_committed'),1),\n                memory_result=u(at('g.memory_result'),1),memory_error=u(at('g.memory_error'),1),")
s=s.replace("        return d\n    def unit_readback", '''            if 'd' in syms:
                diagnostic=u(base+syms['d'])
                if diagnostic:d['diagnostic']={k:u(diagnostic+offsets['diag.'+k],1 if k in ('mode','submode','my','pending','seen','entry','reason','stage','shown','record') else 4) for k in ('failed','activity','state','selection','settings','length','mode','submode','my','pending','seen','entry','reason','stage','shown','record')}
        return d
    def unit_readback''')
# Capture a narrow, declared service-call fixture. It is never loaded into a Machine.
needle="    result['first_menu'] = state()\n"
s=s.replace(needle,needle+'''    if base and state()['rows']==8:
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
''')
# First ADJ must visibly publish the diagnostic before ordinary recipe interaction.
s=s.replace("    if state()['rows'] != 8:\n", '''    if state()['rows']==8 and state()['screen']==5:
        result['diagnostic_page']=state()
        assert len(state()['text'])==8 and state()['text'][0].startswith('G157B')
        key('OK');assert state()['screen']==0 and state()['state']==56
        result['list_after_diagnostic']=state()
    if state()['rows'] != 8:
''')
s=s.replace("    for _ in range(60):\n        if state()['root_state'] not in (1,2): break\n        assert run(10000000).reason=='max_steps'", """    result['publication_wait']=[]
    for _ in range(60):
        current=state()
        result['publication_wait'].append({k:current[k] for k in ('steps','root_state','inflight','rows')})
        if current['root_state'] in (5,6) or (current['root_state'] not in (1,2) and not current['inflight']):break
        assert run(10000000).reason=='max_steps'
    else:raise RuntimeError('first ADJ publication did not finish')""")
# Every Look must have stored its exact full record, including expanded global index.
s=s.replace("        for ordinal in order:\n", """        def select_flat(target):
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
""")
s=s.replace("        # Exercise real confirmation and reopening of the last selected Look.", """        if not a.only:
            math_ref=C.load(C.HERE/'math_reference.py','g157_menu_math');reference=math_ref.Reference()
            result['user_samples']=[]
            for user in range(3):
                slot,levels=math_ref.user_record(raw,user);select_flat(8+len(looks)+user)
                expected=reference.compute(raw,unit_index,C.D.expand(raw,unit_index,slot),levels)
                assert state()['levels']==levels and c.read(at('g.live'),552)==expected;assert_record(128+user)
                result['user_samples'].append(dict(user=user+1,slot=slot,full_40_equal=True,state=state(),unit_readback=unit_readback(expected)))
                save()
        # Exercise real confirmation and reopening of the last selected Look.""")
s=s.replace("        # Exercise real confirmation and reopening of the last selected Look.", """        result['before_DISP']=state()
        close_record=c.read(u(0x200c0dac)+0xfd4,40)
        key('DISP');assert state()['state']==56 and state()['screen']==1
        result['DISP_card']=state()
        key('UP');assert state()['screen']==1 and state()['cur']==0
        result['DISP_title']=state()
        key('DISP');assert state()['state']==56 and state()['screen']==0
        result['DISP_back']=state()
        # Exercise real confirmation and reopening of the last selected Look.""")
s=s.replace("        result['after_close']=state()\n        save()", """        result['after_close']=state()
        assert state()['state']==5
        key('ADJ');assert state()['state']==56 and state()['rows']==8
        result['reopened']=state()
        assert state()['cursor']==state()['cached']==state()['physical']+1
        key('ADJ');assert state()['state']==5
        result['ADJ_closed']=state()
        assert c.read(u(0x200c0dac)+0xfd4,40)==close_record
        result['close_record_equal']=True
        save()""")
s=s.replace("            sample = dict(look, ordinal=ordinal,", '''            record=c.read(u(0x200c0dac)+0xfd4,40)
            literal=b'GXR2'+bytes((3,64+look['index'],unit_index,1))+struct.pack('>10h',*st['levels'])+raw[20:28]
            literal+=__import__('zlib').crc32(literal).to_bytes(4,'big')
            assert record==literal and not st['memory_dirty'] and not st['memory_error']
            assert st['cursor']==st['cached']==st['physical']+1
            sample = dict(look, full_40_equal=True, ordinal=ordinal,''')
s=s.replace("    result['flow']=export.get('flow',{})", "    _flow=export.get('flow',{});result['flow']=dict(counts=_flow.get('counts'),BOOT=[r for r in _flow.get('rows',[]) if 'BOOT' in r.get('kind','')])")
s=s.replace("    export=N.export_state(m)", """    if a.expect_final:
        expected=a.expect_final.read_bytes();assert len(expected)==552
        assert c.read(at('g.live'),552)==expected
        result['explicit_expected_552_equal']=True
        result['explicit_unit_readback']=unit_readback(expected)
    export=N.export_state(m)""")
s=s.replace("    result['after_boot'] = state()", """    result['after_boot'] = state()
    if a.challenge in ('boot-vivid','boot-wb'):
        after=state();snapshot=after['diagnostic']
        result['BOOT_W']=sum(r['cmd']==22 for r in m.devices['startup'].rpc_state.get('log',[]))
        assert snapshot['reason']==20 and snapshot['failed']&128 and after['memory_result']==1 and not after['boot_committed'] and result['BOOT_W']==0
        assert after['selector']==2 if a.challenge=='boot-vivid' else after['wb'][0]==10
    if a.require_vivid:
        after=state();snapshot=after['diagnostic']
        assert after['selector']==2 and after['memory_result']==1 and not after['boot_committed']
        assert snapshot['failed']&128 and not snapshot['seen']&8
        result['persistent_vivid_BOOT_skip']=True
""")
s=s.replace("    if state()['rows'] != 8:\n", """    if a.require_vivid:
        assert state()['selector']==2 and not state()['baseline'] and not state()['boot_committed']
        result['persistent_vivid_menu_not_04']=True
    if state()['rows'] != 8:
""")
s=s.replace("                windows.append(2000000)\n                break", """                windows.append(2000000)
                final=state()
                if final['state'] not in (5,56) or final['word'] not in (2,6,14) or final['inflight']:continue
                if final['state']==56 and final['rows']==8 and base:
                    if not (final['cursor']==final['cached']==final['physical']+1 and final['cur']==final['top']+final['physical']):continue
                break""")
s=s.replace("stable = st['state'] in (5,56) and", "stable = ((st['state']==5 and st['activity']==0) or (st['state']==56 and st['activity']!=0)) and")
s=s.replace("if final['state'] not in (5,56) or final['word'] not in (2,6,14) or final['inflight']:continue", "if not ((final['state']==5 and final['activity']==0) or (final['state']==56 and final['activity']!=0)) or final['word'] not in (2,6,14) or final['inflight']:continue")
s=s.replace("except BaseException as exc:\n", """except BaseException as exc:
    try:
        if m is not None and 'state' in globals():result['failure_state']=state()
    except BaseException:
        pass
""")
(C.HERE/'run.py').write_text(s)
print('cold-MAIN runner generated with pointer-aware layout and full-record assertions')
