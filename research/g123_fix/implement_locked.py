"""Owned ERR re-publication through existing UI_LIST update and redraw."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,TREE,OUT

def revised(text):
    marker='status=list_bind(2);'
    if marker in text:
        assert 'n.panel.open=n.panel.input_enabled=0;n.watch_view=1;' in text
        return text
    needle='    if(!n.failed) {\n        eng_require_recheck();eng_restore_cursor();n.retry=1;'
    extra='''    if(n.failed) {
        status=list_bind(2);
        if(status==RV_OK) {
            n.panel.open=n.panel.input_enabled=0;n.watch_view=1;
            status=list_bind(3);
        }
    }
'''
    assert needle in text;return text.replace(needle,extra+needle,1)

def services(text):
    old='''    if(op!=1&&(u->view_token!=r->epoch[RV_VIEW_E]||s->view_source!=u->state_address))return RV_STALE;'''
    new='''    if(op!=1&&(u->view_token!=r->epoch[RV_VIEW_E]||
       (op!=2&&s->view_source!=u->state_address)))return RV_STALE;'''
    assert old in text;text=text.replace(old,new,1)
    old='''    if(op==3&&!rv_view_owned(r,u,0)){rv_irq_restore(irq);return RV_STALE;}'''
    new='''    if(op==2) {
        /* Update may replace rows/source in the same lease. Validate the
         * previous live owner under IRQ before publishing the new shape. */
        RvUiList previous;
        memcpy(&previous,u,sizeof(previous));
        previous.state_address=s->view_source;previous.rows=s->rows;
        if(!rv_view_owned(r,&previous,0)){rv_irq_restore(irq);return RV_STALE;}
    }
'''+old
    assert old in text;text=text.replace(old,new,1)
    definition='static int32_t ui_list(RvRoot *r,uint32_t op,RvUiList *u)\n'
    declaration='static int32_t ui_list(RvRoot *,uint32_t,RvUiList *) __attribute__((noinline));\n'
    assert definition in text;text=text.replace(definition,declaration+definition,1)
    return text

def main():
    phase=OUT/'local/p1-verified/source/candidate'
    adapter=TREE/'candidate/containers/product/adapter.c'
    service=TREE/'candidate/engine_services/services.c'
    adapter.write_text(revised((phase/'containers/product/adapter.c').read_text()))
    service.write_text(services((phase/'engine_services/services.c').read_text()))
    print('Applied owned ERR via existing op 2 and op 3; ownership gate inside existing UI IRQ boundary')
if __name__=='__main__':main()
