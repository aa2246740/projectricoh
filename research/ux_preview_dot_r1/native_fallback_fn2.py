"""A pure-04 compensation must not reapply a previous RAM tweak on ADJ."""
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import native_ux as ux

def main():
    dat,elf=ux.configure(False,'50mm-fallback-fn2')
    r=dict(unit='50mm',dat_sha256=ux.m.sha(dat.read_bytes()),engine_elf_sha256=ux.m.sha(elf.read_bytes()))
    try:
        m,fr=ux.m,ux.fr
        h,p,w=m.boot('50mm');ins=ux.instrument(h,p)
        m.published(h,p,w);ux.arm_entries(h,p,ins)
        ux.need(fr.native(h,0x202be220));ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b))
        r['modified04']=ux.matches(h,p,4,contrast=1)
        m.reopen(h,p,w);ux.need(fr.move_key(h,0x20));ux.need(fr.press(h,0x2b));m.reopen(h,p,w)
        ux.matches(h,p,5)
        fail,original=ux.injected_rpc(p,16,after_write=True,extra_failures=(22,))
        r['failure']=ux.measure_move(h,p,0x20,ins);p.rpc.call=original
        assert len(fail['events'])==2 and r['failure']['after']['cursor']==4
        r['restored']=ux.matches(h,p,4)
        before=len(p.rpc.log);refresh=h.stub_hits.get('preview',0)
        ux.need(fr.press(h,0x2b))
        r['confirmation']=dict(extra_rpc=len(p.rpc.log)-before,
            extra_refresh=h.stub_hits.get('preview',0)-refresh,state=ux.snap(h,p),actual=ux.matches(h,p,4))
        assert r['confirmation']['extra_rpc']==0 and r['confirmation']['extra_refresh']==0
        m.reopen(h,p,w);r['reopened']=ux.snap(h,p)
        assert r['reopened']['cursor']==4
        ux.matches(h,p,4)
        r['file_mutations']=m.no_writes(p);r['status']='PASS'
        print('PASS pure 04 fallback accepted without restoring older Fn2 tweak',flush=True)
    except Exception:
        r['status']='FAIL';r['error']=traceback.format_exc();ux.save('fallback-fn2-50mm.json',r);raise
    ux.save('fallback-fn2-50mm.json',r)

if __name__=='__main__':main()
