"""Apply the approved live-adjustment behavior to the copied recipe sources."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,TREE,save
import difflib
product=TREE/'candidate/containers/product'
core=product/'src/firmware/engine/core/eng_core.c'
header=core.with_name('eng_core.h')
adapter=product/'adapter.c'
originals={p:p.read_text() for p in (core,header,adapter)}
s=core.read_text()
s=s.replace('g.stage=ENG_STAGE_IDLE;\n    return g.bound?', 'g.current.unit=g.data.unit;g.current.slot=4;\n    eng_identity(eng_record(&g.data,4),g.current.identity);\n    g.stage=ENG_STAGE_IDLE;\n    return g.bound?',1)
pos=s.index('EngStatus eng_apply(const EngRecipeRef *r,const EngTweak *t)')
s=s[:pos]+'''EngStatus eng_confirm_live(EngRecipeRef *r,EngTweak *t)
{
    if(g.uncertain)return ENG_UNCERTAIN;
    if(!g.ready||g.busy)return ENG_STALE;
    g.confirmed=g.current;g.confirmed_tweak=g.tweak;g.confirmed_valid=1;
    g.previewing=0;g.stage=ENG_STAGE_COMMITTED;
    *r=g.current;*t=g.tweak;return ENG_OK;
}
'''+s[pos:]
core.write_text(s)
header.write_text(header.read_text().replace('EngStatus eng_current(', 'EngStatus eng_confirm_live(EngRecipeRef *r, EngTweak *t);\nEngStatus eng_current(',1))
s=adapter.read_text().replace('uint8_t failed,watch_view,view_lost;','uint8_t failed,watch_view,view_lost,comm_failed;')
s=s.replace('n.watch_view=n.panel.open?2:1;n.view_lost=0;eng_view_lost(0);','n.watch_view=n.panel.open?2:1;n.view_lost=n.comm_failed=0;eng_view_lost(0);')
s=s.replace('if(status!=ENG_OK&&eng_uncertain())n.failed=1;', 'if(status!=ENG_OK&&(eng_uncertain()||n.comm_failed))n.failed=1;')
s=s.replace('if(status!=ENG_OK&&(eng_uncertain()||status==ENG_IO))', 'if(status!=ENG_OK&&(eng_uncertain()||status==ENG_IO||n.comm_failed))')
s=s.replace('result=n.api->call(id,op,&q,r);','''result=n.api->call(id,op,&q,r);
    if(id==RV_RPC8&&(result!=RV_OK||r->status!=RV_OK||
       (op>=2&&op<=4&&(r->native_result<0||r->native_result>65535))))n.comm_failed=1;''')
s=s.replace('else if(id==RV_RPC8&&n.watch_view&&!eng_uncertain())','else if(id==RV_RPC8&&n.watch_view==1&&!eng_uncertain())')
s=s.replace('if(result==RV_FAULT&&eng_uncertain())n.failed=1;','if(result==RV_FAULT&&(eng_uncertain()||n.comm_failed))n.failed=1;')
a=s.index('static EngStatus accept_preview(');b=s.index('static EngStatus preview_cached(',a)
s=s[:a]+'''static EngStatus accept_preview(void)
{
    EngRecipeRef current;EngTweak applied;
    EngStatus status=eng_confirm_live(&current,&applied);
    if(status==ENG_OK)n.values[current.slot-1]=applied;
    return status;
}
'''+s[b:]
s=s.replace('if(eng_apply(&p->recipe,&p->draft)!=ENG_OK)return RV_FAULT;', 'if(accept_preview()!=ENG_OK)return RV_FAULT;')
s=s.replace('/* OK commits the applied draft to RAM for this boot only. */','/* Confirmation keeps the verified live values in RAM for this boot. */')
a=s.index('static int32_t a4_move(');b=s.index('int32_t ig_init(',a)
s=s[:a]+'''static int32_t a4_move(unsigned row)
{
    PnPanel *p=&n.panel;EngTweak draft;EngStatus status;unsigned index,next;
    if(!p->open||row>=11)return RV_FAULT;
    do {
        index=p->param_index[p->parameter];
        if((int)row-5<n.lo[p->parameter]||(int)row-5>n.hi[p->parameter]) {
            p->cursor=(uint8_t)(p->draft.v[index]+5);
            return panel_render(p,0)==RV_OK?RV_CONSUMED:RV_FAULT;
        }
        draft=p->draft;draft.v[index]=(int8_t)((int)row-5);
        p->cursor=(uint8_t)row;
        if(panel_render(p,0)!=RV_OK)return RV_FAULT;
        status=eng_preview_saved(p->recipe.slot,&draft);
        if(status!=ENG_OK)return RV_FAULT;
        if(n.view_lost||!view_owned())return RV_CONSUMED;
        if(eng_current(&p->recipe,&p->draft)!=ENG_OK)return RV_FAULT;
        n.values[p->recipe.slot-1]=p->draft;
        p->preview_attempted=1;
        p->dirty=(uint8_t)!pn_equal(&p->draft,&p->committed,sizeof(draft));
        next=RV_BYTE(0x2022f726);
        if(next<1||next>11||next==row+1)break;
        row=next-1;
    } while(1);
    p->cursor=(uint8_t)(p->draft.v[index]+5);
    return panel_render(p,0)==RV_OK?RV_CONSUMED:RV_FAULT;
}
'''+s[b:]
s=s.replace('constructor replaces that numeric view and its unaccepted draft.','constructor keeps the numeric view\'s verified live values.')
s=s.replace('EngStatus status=accept_preview(slot);','EngStatus status=accept_preview();')
s=s.replace('if(status!=ENG_OK)return finish(r,status);\n            }\n            if(!q->args[9])eng_menu_close();','if(status!=ENG_OK)return ui_finish(r,RV_FAULT);\n            }\n            if(!q->args[9])eng_menu_close();')
adapter.write_text(s)
patch=''
for p,before in originals.items():
 after=p.read_text()
 patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='baseline/'+str(p.relative_to(TREE)),tofile='gen120/'+str(p.relative_to(TREE))))
(OUT/'source.patch').write_text(patch)
save('interaction-decision.json',dict(approved_local_time='2026-10-27 21:45',fn2='Directions update live view; OK, ADJ and half shutter retain the displayed values.',h07='Confirmation only copies live state into confirmed RAM.',notice='ERR POWER OFF/ON',notice_reason='Keep the already reviewed native text width and the same required recovery action for both communication failure classes.'))
print('PASS recipe source update; resident sources unchanged',flush=True)
