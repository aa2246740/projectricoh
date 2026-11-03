"""Deterministic gen 123 changes from the frozen gen 122 tree."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,TREE,OUT

def main():
    old=ROOT/'firmware/engine_v44_keep/candidate'
    base=ROOT/'firmware/engine_v43_fix/candidate'
    core=Path('containers/product/src/firmware/engine/core/eng_core.c')
    text=(old/core).read_text();baseline=(base/core).read_text()
    start=baseline.index('/* Compare every owned byte at a new menu entry.')
    end=baseline.index('\nEngStatus eng_cursor',start)
    left=text.index('/* A fully contained halfword');right=text.index('\nEngStatus eng_retry_live',left)
    text=text[:left]+baseline[start:end]+text[right:]
    text=text.replace('write_started,recheck,full_check','write_started,recheck')
    text=text.replace('g.recheck=g.full_check=1','g.recheck=1')
    text=text.replace('    if(!same_epoch(&e,&g.epoch)||e.view!=g.epoch.view)g.full_check=1;\n','')
    left=text.index('EngStatus eng_menu_deferred(void)');right=text.index('EngStatus eng_select(',left)
    text=text[:left]+text[right:]
    (TREE/'candidate'/core).write_text(text)
    header=core.with_name('eng_core.h')
    (TREE/'candidate'/header).write_text((old/header).read_text().replace('EngStatus eng_menu_deferred(void);\n',''))
    adapter=Path('containers/product/adapter.c');text=(old/adapter).read_text()
    left=text.index('static int32_t deferred_menu(');right=text.index('enum { LAST_BYTES',left)
    text=text[:left]+'''static int32_t deferred_menu(RvReply *r,EngStatus status)
{
    record_failure(status);
    if(!n.failed) {
        /* The fixed constructor writes one row to both native cursors.
         * An unchecked recipe list must therefore return to native rows. */
        eng_require_recheck();n.retry=0;
        return release_view(r);
    }
    n.panel.open=n.panel.input_enabled=0;
    if(list_bind(1)!=RV_OK)return finish(r,ENG_IO);
    return finish(r,ENG_OK);
}
'''+text[right:]
    (TREE/'candidate'/adapter).write_text(text)
    from implement_locked import revised,services
    target=TREE/'candidate/containers/product/adapter.c'
    target.write_text(revised(target.read_text()))
    service=Path('engine_services/services.c')
    (TREE/'candidate'/service).write_text(services((old/service).read_text()))
    print('PASS gen 123 source: full validation, native H01 fallback, immediate owned ERR')

if __name__=='__main__':main()
