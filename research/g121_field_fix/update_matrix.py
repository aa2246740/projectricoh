"""Keep the previous case domains while applying the new recovery contract."""
from pathlib import Path

OUT = Path(__file__).resolve().parent

def replace(text, old, new):
    assert old in text, old[:80]
    return text.replace(old,new,1)

def main():
    p=OUT/'native_ux.py';text=p.read_text()
    text=replace(text, "    assert len(fail['events'])==2 and step['after']['cursor']==4,(fail,step)",
        "    assert len(fail['events'])==2 and step['after']['cursor']==3,(fail,step)")
    text=replace(text, "    report['fallback04']['actual']=matches(h,p,4)",
        "    report['fallback04']['actual']=matches(h,p,3)")
    text=replace(text, "    assert h.u(0x2022f5ac,1)==1", "    assert h.u(0x2022f5ac,1)==8")
    text=text.replace('failed_compensation_fallback04_notice','bounded_compensation_retry')
    p.write_text(text)
    p=OUT/'native_cases.py';text=p.read_text()
    text=replace(text, "    assert h.u(0x2022f5ac,1)==1 and texts and all(t=='ERR POWER OFF/ON' for t in texts)",
        "    assert h.u(0x2022f5ac,1)==8 and texts and all(t.startswith('ERR ') and len(t)<=14 for t in texts)\n    assert ux.snap(h,p)['native_snapshot_rows']==[1,1]")
    text=text.replace("'locked_before_W'", "'busy_before_W'")
    text=replace(text, "        if state.startswith('locked_'):\n            persistent(h,p,1 if state=='busy_before_W' else 16)\n            shown=notice(h,p,w)\n            assert shown['state']['root']['state']==3",
        "        if state in ('busy_before_W','locked_after_W'):\n            persistent(h,p,1 if state=='busy_before_W' else 16)\n            if state=='locked_after_W':\n                shown=notice(h,p,w)\n                assert shown['state']['root']['state']==3\n            else:\n                m.reopen(h,p,w)\n                assert h.u(p.symbol_pc('n')+3712,1)==0 and h.u(0x2022f5ac,1)==8")
    p.write_text(text)
    p=OUT/'fn2_quality.py';text=p.read_text()
    start=text.index('            if persistent or extra:')
    end=text.index('            r.update(unit=unit,label=label',start)
    text=text[:start]+'''            if persistent and at>1:
                assert locked and after['list']['uncertain']==1
                saved_rpc=len(p.rpc.log);saved_preview=h.stub_hits.get('preview',0)
                shown=nc.notice(h,p,w)
                assert len(p.rpc.log)==saved_rpc and h.stub_hits.get('preview',0)==saved_preview
            else:
                assert not locked and len(complete)==1
                expected=5 if at==1 else 3
                assert complete[0]['slot']==expected
                assert complete[0]['contrast']==(0 if at==1 else 1)
                live_rows(h,p)
                m.reopen(h,p,w)
                assert h.u(0x2022f5ac,1)==8
''' + text[end:]
    p.write_text(text)
    p=OUT/'concurrent_menu.py';text=p.read_text()
    start=text.index('def fallback(unit,r):')
    end=text.index('\ndef main():',start)
    text=text[:start]+'''def fallback(unit,r):
    h,p,w,ins=start(unit)
    ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b))
    r['modified04']=ux.matches(h,p,4,contrast=1)
    m.reopen(h,p,w);ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b));m.reopen(h,p,w);ux.matches(h,p,5)
    fail,original=ux.simulated_rpc(p,16,after_write=True,extra_failures=(22,))
    ux.need(fr.move_key(h,0x20));p.rpc.call=original
    assert len(fail['events'])==2
    r['restored']=ux.matches(h,p,5)
    assert h.u(p.symbol_pc('n')+3712,1)==0
    ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
    r['reopened']=ux.snap(h,p)
    assert r['reopened']['rows']==8 and r['reopened']['cursor']==5
    ux.matches(h,p,5);r.update(status='PASS',file_mutations=m.no_writes(p))
    print('PASS bounded retry restores confirmed recipe 05 without an error notice',flush=True)
''' + text[end:]
    p.write_text(text)
    p=OUT/'coalescing.py';text=p.read_text().replace('choices=(119,120)','choices=(119,120,121)').replace('if gen==120 and at==1:', 'if gen>=120 and at==1:');p.write_text(text)
    p=OUT/'run_queue.py'
    source=(OUT.parent/'review_g120b/run_queue.py').read_text().replace("for unit in ('28mm', 'mount'):","for unit in units:").replace("'120', unit", "'121', unit")
    p.write_text(source)
    print('PASS case contract updates',flush=True)

if __name__=='__main__':main()
