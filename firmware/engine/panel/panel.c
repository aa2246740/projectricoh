#include "panel.h"

static int same_recipe(const EngRecipeRef *a, const EngRecipeRef *b)
{
    return a->unit==b->unit && a->slot==b->slot &&
           pn_equal(a->identity,b->identity,49);
}
static int tweak_equal(const EngTweak *a, const EngTweak *b)
{ return pn_equal(a->v,b->v,ENG_PARAMS); }
static int metadata_ok(const PnPanel *p, const EngTweak *t)
{
    unsigned i;
    for (i=0;i<ENG_PARAMS;i++)
        if (p->min[i]>p->def[i] || p->def[i]>p->max[i] ||
            t->v[i]<p->min[i] || t->v[i]>p->max[i]) return 0;
    return 1;
}
static int binding_ok(PnPanel *p, const EngTweak *expected)
{
    EngRecipeRef r; EngTweak t;
    return !eng_uncertain() && eng_current(&r,&t)==ENG_OK &&
        same_recipe(&r,&p->recipe) && (!expected || tweak_equal(&t,expected));
}
void pn_panel_init(PnPanel *p, PnPort *port, const PnPanelOps *ops)
{
    unsigned i;
    pn_zero(p,sizeof(*p)); p->port=port;
    if (ops) p->ops=*ops;
    for (i=0;i<6;i++) p->param_index[i]=ops && ops->param_index ? ops->param_index[i] : (uint8_t)i;
}
static int32_t close_panel(PnPanel *p)
{
    int32_t v;
    p->input_enabled=0;
    v=pn_ui_detach(p); p->last_io=v; p->open=0;
    return v==RV_OK ? RV_CONSUMED : RV_FAULT;
}
static int32_t cancel(PnPanel *p, int after_invalid)
{
    int32_t v;
    if (p->preview_attempted || p->dirty) {
        after_invalid=after_invalid || p->stop_after_invalid;
        if (after_invalid || p->unknown || !binding_ok(p,&p->draft)) p->unknown=1;
        else {
            p->last_engine=eng_apply(&p->recipe,&p->committed);
            if (p->last_engine!=ENG_OK || !binding_ok(p,&p->committed)) p->unknown=1;
            else { p->draft=p->committed; p->dirty=0; p->preview_attempted=0; }
        }
    }
    v=close_panel(p); p->stop_requested=0;
    return p->unknown || v==RV_FAULT ? RV_FAULT : RV_CONSUMED;
}
int32_t pn_panel_cancel(PnPanel *p)
{
    int32_t v;
    if (!p || p->busy) return RV_FAULT;
    if (!p->open) return RV_PASS;
    p->busy=1; v=cancel(p,0); p->busy=0;
    return v;
}
int32_t pn_panel_open(PnPanel *p, const PnOpenView *v)
{
    EngRecipeRef r; EngTweak t;
    int32_t status; unsigned i,mask=0;
    if (!p || !p->port || !v || p->busy || p->open || p->ui_pinned ||
        p->unknown || p->commit_uncertain) return RV_FAULT;
    if (v->native_state!=56 || v->activity!=8 || v->count<1 || v->count>2 ||
        !v->array || v->top_tag!=33 || !v->top_state ||
        (v->opener!=0x25 && v->opener!=0x22)) return RV_PASS;
    if (eng_uncertain() || eng_current(&r,&t)!=ENG_OK || r.unit>2 ||
        r.slot<1 || r.slot>16) return RV_FAULT;
    for (i=0;i<6;i++) {
        unsigned index=p->param_index[i];
        if (index>=ENG_PARAMS || (mask&(1u<<index))) return RV_FAULT;
        mask|=1u<<index;
    }
    p->last_engine=eng_metadata(r.slot,p->min,p->max,p->def);
    if (p->last_engine!=ENG_OK || !metadata_ok(p,&t)) return RV_FAULT;
    p->recipe=r; p->committed=t; p->draft=t;
    p->cursor=1; p->dirty=0; p->preview_attempted=0; p->armed=0;
    p->opener=v->opener; p->last_store=RV_OK;
    p->stop_requested=0; p->stop_after_invalid=0;
    p->view.expected_array=v->array; p->view.expected_count=v->count;
    p->view.expected_top_tag=v->top_tag; p->view.expected_top_state=v->top_state;
    p->busy=1;
    status=pn_ui_render(p,1); p->last_io=status;
    if (status!=RV_OK || p->stop_requested || !binding_ok(p,&p->committed)) {
        (void)pn_ui_detach(p); p->busy=0; return RV_FAULT;
    }
    p->open=1; p->input_enabled=1; p->busy=0;
    return RV_CONSUMED;
}
static int32_t preview(PnPanel *p, const EngTweak *candidate)
{
    if (tweak_equal(&p->draft,candidate)) return RV_CONSUMED;
    if (p->stop_requested || !binding_ok(p,&p->draft)) {
        p->unknown=1; return RV_FAULT;
    }
    p->preview_attempted=1;
    p->last_engine=eng_apply(&p->recipe,candidate);
    if (p->last_engine==ENG_OK && binding_ok(p,candidate)) {
        p->draft=*candidate; p->dirty=(uint8_t)!tweak_equal(&p->draft,&p->committed);
    } else if (p->last_engine!=ENG_REJECTED || !binding_ok(p,&p->draft)) {
        p->unknown=1;
    }
    return p->unknown ? RV_FAULT : RV_CONSUMED;
}
static int32_t confirm(PnPanel *p)
{
    int32_t v;
    if (p->stop_requested || !binding_ok(p,&p->draft)) {
        p->unknown=1; return RV_FAULT;
    }
    if (p->dirty) {
        p->last_store=p->ops.save ? p->ops.save(p->ops.save_context,&p->recipe,&p->draft)
                                    : RV_UNSUPPORTED;
        if (p->last_store!=RV_OK) {
            if (p->last_store==RV_UNCERTAIN) p->commit_uncertain=1;
            return RV_CONSUMED;
        }
        /* A lifecycle pre-notice is serialized ahead of a blocking save. */
        if (p->stop_requested || !binding_ok(p,&p->draft)) {
            p->unknown=1; return RV_FAULT;
        }
        p->committed=p->draft; p->dirty=0; p->preview_attempted=0;
    }
    v=close_panel(p);
    return v;
}
static int notice_event(uint32_t e)
{ return e==0x29 || e==0x63 || e==0x2a || e==0x2b || e==0x33; }
static int32_t event(PnPanel *p, uint32_t e, PnKeyPhase phase)
{
    EngTweak t; int32_t v=RV_CONSUMED;
    if (phase==PN_RELEASE) { if (e==p->opener) p->armed=1; return RV_CONSUMED; }
    if (phase!=PN_PRESS) return RV_CONSUMED;
    if (notice_event(e)) {
        v=cancel(p,0); return v==RV_FAULT ? RV_FAULT : RV_CLOSE_AND_PASS;
    }
    if (!p->armed) {
        if (e==p->opener) return RV_CONSUMED;
        p->armed=1;
    }
    if (p->unknown || p->commit_uncertain) {
        if (e==0x23) return cancel(p,0);
        return RV_CONSUMED;
    }
    if (e==0x1f || e==0x59 || e==0x2d) p->cursor=p->cursor==1 ? 8 : p->cursor-1;
    else if (e==0x20 || e==0x5a || e==0x2c) p->cursor=p->cursor==8 ? 1 : p->cursor+1;
    else if (e==0x23) {
        if (p->cursor==8) return cancel(p,0);
        if (p->cursor==7) {
            pn_copy(t.v,p->def,ENG_PARAMS); v=preview(p,&t);
        } else return confirm(p);
    } else if (p->cursor>=1 && p->cursor<=6 &&
               (e==0x21 || e==0x30 || e==0x22 || e==0x2f || e==0x25)) {
        unsigned i=p->param_index[p->cursor-1];
        int x=p->draft.v[i];
        if (e==0x21 || e==0x30) { if (x>p->min[i]) x--; }
        else if (x<p->max[i]) x++;
        t=p->draft; t.v[i]=(int8_t)x; v=preview(p,&t);
    }
    if (v==RV_FAULT) { (void)pn_ui_render(p,0); return RV_FAULT; }
    return RV_CONSUMED;
}
int32_t pn_panel_event(PnPanel *p, uint32_t e, PnKeyPhase phase)
{
    int32_t v; int redraw_failed=0;
    if (!p || p->busy) return RV_FAULT;
    if (!p->open) return RV_PASS;
    if (!p->input_enabled) return RV_FAULT;
    p->busy=1; v=event(p,e,phase);
    if (p->open && v!=RV_FAULT && !p->stop_requested) {
        p->last_io=pn_ui_render(p,0);
        redraw_failed=p->last_io!=RV_OK;
    }
    if (p->stop_requested || redraw_failed) {
        int stopped=p->stop_requested;int32_t io=p->last_io;
        int32_t closed=cancel(p,p->stop_after_invalid);
        if(redraw_failed)p->last_io=io;
        v=stopped && closed!=RV_FAULT ? RV_CLOSE_AND_PASS : RV_FAULT;
    }
    p->busy=0; return v;
}
int32_t pn_panel_notify(PnPanel *p, PnNotice reason, int after_invalid)
{
    int32_t v;
    if (!p || reason>PN_STORAGE_INVALIDATED) return RV_FAULT;
    if (p->busy) {
        p->input_enabled=0; p->stop_requested=1;
        p->stop_after_invalid=(uint8_t)(p->stop_after_invalid || after_invalid);
        return RV_FAULT; /* Owner must drain the in-flight menu call. */
    }
    if (!p->open) return RV_PASS;
    p->busy=1; p->input_enabled=0;
    v=cancel(p,after_invalid); p->busy=0;
    return v==RV_FAULT ? RV_FAULT : RV_CLOSE_AND_PASS;
}
int pn_panel_native_result(int32_t result)
{
    /* Only CONSUMED has a direct Fn2 epilogue result. Other values require the
     * resident hook's replay/close/fault path; -1 means no native result. */
    return result==RV_CONSUMED ? 0 : -1;
}
